# =============================================================================
# Descarga de datos OSM y DEM SRTM — Celdas 5 y 6 del notebook
# GIS Dev Academy — CartografIA API
# =============================================================================

import os
import math
import logging
import warnings

import numpy as np
import requests
import geopandas as gpd

from pyproj import CRS
from scipy.ndimage import gaussian_filter

try:
    import osmnx as ox
    ox.settings.log_console = False
    ox.settings.use_cache   = True
    OSMNX_OK = True
except ImportError:
    OSMNX_OK = False

try:
    import rasterio
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    RASTERIO_OK = True
except ImportError:
    RASTERIO_OK = False

from .geo_utils import geom_tipo

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Descarga OSM
# ---------------------------------------------------------------------------

def descargar_osm(polygon_gdf: gpd.GeoDataFrame, capas: dict) -> dict:
    if not OSMNX_OK:
        logger.warning("osmnx no disponible — omitiendo datos OSM")
        return {}

    datos: dict = {}
    geom = (
        polygon_gdf.geometry.iloc[0]
        if isinstance(polygon_gdf, gpd.GeoDataFrame)
        else polygon_gdf
    )

    def _query(tags: dict, nombre: str):
        try:
            logger.info(f"  OSM ← {nombre}...")
            gdf = ox.features_from_polygon(geom, tags=tags)
            if not gdf.empty:
                datos[nombre] = gdf
                logger.info(f"     OK {len(gdf)} elementos")
        except Exception as e:
            logger.warning(f"  OSM omitida {nombre}: {str(e)[:80]}")

    # Red vial (grafo completo)
    if capas.get("red_vial"):
        try:
            logger.info("  OSM ← Red vial (grafo)...")
            G = ox.graph_from_polygon(geom, network_type="all", retain_all=True)
            _, edges = ox.graph_to_gdfs(G)
            datos["red_vial"] = edges
            logger.info(f"     OK {len(edges)} segmentos")
        except Exception as e:
            logger.warning(f"  OSM omitida red vial: {e}")

    # Hidrografía
    if capas.get("hidrografia"):
        _query(
            {"waterway": True, "water": True, "natural": ["water", "wetland"]},
            "hidrografia",
        )

    # Planimetría urbana
    if capas.get("planimetria"):
        _query({"building": True}, "edificios")
        _query(
            {"landuse": ["residential", "commercial", "industrial", "retail", "construction"]},
            "areas_urbanas",
        )

    # Vegetación y usos del suelo
    if capas.get("vegetacion"):
        _query(
            {
                "natural": ["wood", "scrub", "heath", "bare_rock", "scree", "grassland", "wetland"],
                "landuse": ["forest", "farmland", "meadow", "orchard", "vineyard", "cemetery"],
                "leisure": ["park", "garden", "nature_reserve"],
            },
            "vegetacion",
        )

    # Red ferroviaria
    if capas.get("ferroviario"):
        _query(
            {"railway": ["rail", "disused", "abandoned", "light_rail", "subway", "tram"]},
            "ferroviario",
        )

    # Puntos geográficos y localidades
    if capas.get("puntos_geograficos"):
        _query(
            {"natural": ["peak", "volcano", "cliff", "spring"]},
            "puntos_geo",
        )
        _query(
            {"place": ["city", "town", "suburb", "village", "hamlet", "neighbourhood", "borough"]},
            "localidades",
        )

    logger.info(f"  Capas OSM descargadas: {list(datos.keys())}")
    return datos


# ---------------------------------------------------------------------------
# Descarga DEM SRTM
# ---------------------------------------------------------------------------

def descargar_dem(bounds_wgs84: tuple, cache_dir: str = "/tmp/dem_cache") -> str | None:
    xmin, ymin, xmax, ymax = bounds_wgs84
    os.makedirs(cache_dir, exist_ok=True)

    # Clave de cache por bbox redondeada a 0.1°
    bbox_key = f"{xmin:.1f}_{ymin:.1f}_{xmax:.1f}_{ymax:.1f}".replace("-", "n")
    cached = os.path.join(cache_dir, f"dem_{bbox_key}.tif")
    if os.path.exists(cached) and os.path.getsize(cached) > 1000:
        logger.info(f"  DEM desde cache → {cached}")
        return cached

    out = cached

    # Intento 1: biblioteca elevation (SRTM 30m)
    try:
        import elevation
        logger.info("  Descargando DEM SRTM 30m (elevation)...")
        elevation.clip(
            bounds=(xmin, ymin, xmax, ymax),
            output=out,
            product="SRTM3",
        )
        elevation.clean()
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            logger.info(f"  ✓ DEM descargado → {out}")
            return out
    except Exception as e:
        logger.warning(f"  elevation fallido: {e}")

    # Intento 2: OpenTopography API (SRTM GL3 90m, sin clave)
    try:
        logger.info("  Descargando DEM vía OpenTopography (90m)...")
        url = (
            f"https://portal.opentopography.org/API/globaldem?"
            f"demtype=SRTMGL3&south={ymin}&north={ymax}&"
            f"west={xmin}&east={xmax}&outputFormat=GTiff"
        )
        resp = requests.get(url, timeout=180)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(out, "wb") as f:
                f.write(resp.content)
            logger.info(f"  ✓ DEM OpenTopography → {out}")
            return out
    except Exception as e:
        logger.warning(f"  OpenTopography fallido: {e}")

    logger.warning("  Sin DEM disponible — se omitirán curvas de nivel")
    return None


# ---------------------------------------------------------------------------
# Procesamiento DEM → curvas de nivel
# ---------------------------------------------------------------------------

def procesar_dem(
    dem_path: str,
    eq_ppal: float,
    eq_sec: float,
    epsg_dest: int,
) -> dict:
    if not RASTERIO_OK:
        logger.warning("rasterio no disponible — omitiendo DEM")
        return {}
    if not dem_path or not os.path.exists(dem_path):
        logger.warning("DEM no disponible — omitiendo curvas de nivel")
        return {}

    logger.info("  Reprojectando DEM y calculando curvas de nivel...")
    try:
        with rasterio.open(dem_path) as src:
            src_epsg = src.crs.to_epsg() if src.crs else 4326
            if src_epsg != epsg_dest:
                tf, w, h = calculate_default_transform(
                    src.crs,
                    CRS.from_epsg(epsg_dest),
                    src.width,
                    src.height,
                    *src.bounds,
                )
                dem_data = np.empty((h, w), dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=dem_data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=tf,
                    dst_crs=CRS.from_epsg(epsg_dest),
                    resampling=Resampling.bilinear,
                )
            else:
                dem_data = src.read(1).astype(np.float32)
                tf = src.transform
                w, h = src.width, src.height

        dem_data[(dem_data < -1000) | (dem_data > 9000)] = np.nan
        dem_s = gaussian_filter(
            np.where(np.isnan(dem_data), 0, dem_data),
            sigma=1.2,
        )
        dem_s = np.where(np.isnan(dem_data), np.nan, dem_s)

        rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        X = tf.c + cols * tf.a
        Y = tf.f + rows * tf.e

        z_min = float(np.nanmin(dem_s))
        z_max = float(np.nanmax(dem_s))
        levels_sec  = np.arange(
            math.ceil(z_min / eq_sec) * eq_sec,
            math.floor(z_max / eq_sec) * eq_sec + 1,
            eq_sec,
        )
        levels_ppal = np.arange(
            math.ceil(z_min / eq_ppal) * eq_ppal,
            math.floor(z_max / eq_ppal) * eq_ppal + 1,
            eq_ppal,
        )
        logger.info(f"    Rango de elevación: {z_min:.0f}–{z_max:.0f} m")
        logger.info(f"    Curvas directrices ({int(eq_ppal)}m): {len(levels_ppal)} niveles")
        logger.info(f"    Curvas intermedias ({int(eq_sec)}m): {len(levels_sec)} niveles")

        return {
            "X": X, "Y": Y, "Z": dem_s,
            "levels_sec": levels_sec,
            "levels_ppal": levels_ppal,
            "z_min": z_min,
            "z_max": z_max,
        }
    except Exception as e:
        logger.error(f"  Error procesando DEM: {e}")
        return {}


# ---------------------------------------------------------------------------
# Extracción de localidades para leyenda
# ---------------------------------------------------------------------------

def extraer_localidades(osm_gk: dict) -> list[tuple[int, str]]:
    localidades: list = []
    if "localidades" not in osm_gk:
        return localidades
    locs = osm_gk["localidades"]
    if "name" not in locs.columns:
        return localidades
    pts = geom_tipo(locs, ["Point"])
    if pts.empty:
        return localidades
    important = ["city", "town", "suburb", "village", "neighbourhood", "hamlet", "borough"]
    if "place" in pts.columns:
        pts = pts[pts["place"].isin(important)].copy()
        place_rank = {p: i for i, p in enumerate(important)}
        pts["_rank"] = pts["place"].map(place_rank).fillna(99)
        pts = pts.sort_values("_rank")
    pts = pts.drop_duplicates(subset=["name"]) if "name" in pts.columns else pts
    for i, (_, row) in enumerate(pts.iterrows(), 1):
        if i > 12:
            break
        name = str(row.get("name", "")).strip()
        if name:
            localidades.append((i, name))
    return localidades

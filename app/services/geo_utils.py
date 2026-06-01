# =============================================================================
# Utilidades geográficas — Celdas 4 y 7 del notebook
# GIS Dev Academy — CartografIA API
# =============================================================================

import math
import zipfile
import tempfile
import logging
from pathlib import Path
from datetime import date

import numpy as np
import geopandas as gpd
from shapely.geometry import box
from pyproj import Transformer, CRS

from .constants import FAJAS_GK

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detección de faja y proyección
# ---------------------------------------------------------------------------

def detectar_faja(lon_centro: float) -> dict:
    """Retorna el dict de la faja GK correspondiente a la longitud central."""
    for num, f in FAJAS_GK.items():
        if f["lon_min"] <= lon_centro < f["lon_max"]:
            return {"numero": num, **f}
    # Fuera de rango — asignar la más cercana
    dists = {n: abs(lon_centro - f["meridiano"]) for n, f in FAJAS_GK.items()}
    num = min(dists, key=dists.get)
    return {"numero": num, **FAJAS_GK[num]}


# ---------------------------------------------------------------------------
# Construcción del AOI
# ---------------------------------------------------------------------------

def aoi_desde_coordenadas(
    lon_min: float, lat_min: float,
    lon_max: float, lat_max: float
) -> gpd.GeoDataFrame:
    geom = box(lon_min, lat_min, lon_max, lat_max)
    return gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")


def aoi_desde_archivo(ruta: str) -> gpd.GeoDataFrame:
    """Lee SHP, GeoJSON o ZIP+SHP y retorna GeoDataFrame en WGS84."""
    ruta = str(ruta)
    if ruta.endswith(".zip"):
        tmpdir = tempfile.mkdtemp()
        with zipfile.ZipFile(ruta, "r") as z:
            z.extractall(tmpdir)
        shps = list(Path(tmpdir).rglob("*.shp"))
        if not shps:
            raise FileNotFoundError("No se encontró ningún .shp dentro del ZIP")
        ruta = str(shps[0])

    for enc in ("utf-8", "latin-1", "iso-8859-1", "cp1252"):
        try:
            gdf = gpd.read_file(ruta, encoding=enc)
            break
        except (UnicodeDecodeError, Exception) as e:
            if enc == "cp1252":
                raise e
            continue

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf[["geometry"]].dissolve().reset_index(drop=True)


def centroide_wgs84(aoi_gdf: gpd.GeoDataFrame) -> tuple[float, float]:
    gdf = aoi_gdf.to_crs("EPSG:4326") if aoi_gdf.crs.to_epsg() != 4326 else aoi_gdf
    c = gdf.geometry.centroid.iloc[0]
    return c.x, c.y


def declinacion_magnetica(lon: float, lat: float) -> float:
    decl = -3.0 + (lon + 60) * 0.12 + (lat + 35) * (-0.08)
    return round(decl, 2)


def geom_tipo(gdf: gpd.GeoDataFrame, tipos: list) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(
            geometry=[],
            crs=gdf.crs if (gdf is not None and gdf.crs) else "EPSG:4326"
        )
    mask = gdf.geometry.geom_type.isin(tipos)
    return gdf[mask].copy()


def generar_codigo_hoja(lon_c: float, lat_c: float, escala_val: int) -> tuple[str, str]:
    col_idx    = max(0, int((lon_c + 75) / 1.5)) % 26
    row_idx    = max(1, int((-lat_c) / 1.0) + 1)
    col_letter = chr(ord('A') + col_idx)
    hoja_idx   = f"{row_idx:02d}{col_letter}"
    year       = date.today().year
    return hoja_idx, f"LM-{hoja_idx}-{year}"


# ---------------------------------------------------------------------------
# Utilidades de grilla y etiquetas
# ---------------------------------------------------------------------------

def calcular_grilla(bounds_gk: tuple, intervalo_m: int) -> dict:
    xmin, ymin, xmax, ymax = bounds_gk
    xs = [
        x for x in range(
            math.ceil(xmin / intervalo_m) * intervalo_m,
            math.ceil(xmax / intervalo_m) * intervalo_m + 1,
            intervalo_m,
        )
        if xmin <= x <= xmax
    ]
    ys = [
        y for y in range(
            math.ceil(ymin / intervalo_m) * intervalo_m,
            math.ceil(ymax / intervalo_m) * intervalo_m + 1,
            intervalo_m,
        )
        if ymin <= y <= ymax
    ]
    return {"x": xs, "y": ys}


def etiqueta_gk(coord_m: float, prev_coord_m=None) -> str:
    km   = int(round(coord_m / 1000))
    ult2 = km % 100
    pref = km // 100
    lbl  = f"{ult2:02d}"
    if prev_coord_m is not None:
        km_prev  = int(round(prev_coord_m / 1000))
        pref_prev = km_prev // 100
        if pref != pref_prev:
            SUP = str.maketrans(
                "0123456789",
                "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079",
            )
            lbl = str(pref).translate(SUP) + lbl
    return lbl


def dms_str(decimal: float, tipo: str = "lon") -> str:
    d_abs = abs(decimal)
    deg   = int(d_abs)
    min_  = int((d_abs - deg) * 60)
    suf   = ("O" if decimal < 0 else "E") if tipo == "lon" else ("S" if decimal < 0 else "N")
    return f"{deg}\u00b0{min_:02d}'{suf}"


def clasificar_vias(gdf: gpd.GeoDataFrame) -> dict:
    if gdf is None or gdf.empty or "highway" not in gdf.columns:
        return {"otras": gdf} if (gdf is not None and not gdf.empty) else {}
    catmap = {
        "rutas_ppal": ["motorway", "trunk", "primary"],
        "rutas_sec":  ["secondary", "tertiary"],
        "calles":     ["residential", "living_street", "unclassified", "service"],
        "caminos":    ["track", "road"],
        "senderos":   ["footway", "path", "steps", "cycleway", "pedestrian"],
    }
    result  = {}
    covered = []
    for cat, tipos in catmap.items():
        sub = gdf[gdf["highway"].isin(tipos)]
        if not sub.empty:
            result[cat] = sub.copy()
            covered.extend(tipos)
    otras = gdf[~gdf["highway"].isin(covered)]
    if not otras.empty:
        result.setdefault("calles", otras)
    return result


# ---------------------------------------------------------------------------
# Conversión de bounds entre sistemas
# ---------------------------------------------------------------------------

def bounds_gk_to_wgs(bounds_gk: tuple, epsg_gk: int) -> tuple:
    tr = Transformer.from_crs(epsg_gk, 4326, always_xy=True)
    xmin, ymin, xmax, ymax = bounds_gk
    corners = [
        tr.transform(xmin, ymin),
        tr.transform(xmax, ymin),
        tr.transform(xmax, ymax),
        tr.transform(xmin, ymax),
    ]
    lons = [c[0] for c in corners]
    lats = [c[1] for c in corners]
    return min(lons), min(lats), max(lons), max(lats)


def bounds_para_escala(
    bounds: tuple,
    escala_val: int,
    map_w_cm: float,
    map_h_cm: float,
) -> tuple[tuple, bool]:
    """
    Centra el AOI y calcula el encuadre exacto según escala y tamaño del mapa.
    Retorna (bounds_ajustados, escala_exacta_posible).
    """
    xmin, ymin, xmax, ymax = bounds
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2

    # Tamaño real en metros que ocupa el mapa impreso
    real_w = (map_w_cm / 100) * escala_val
    real_h = (map_h_cm / 100) * escala_val

    aoi_w = xmax - xmin
    aoi_h = ymax - ymin

    if aoi_w <= real_w and aoi_h <= real_h:
        # El AOI cabe: centrar y usar encuadre exacto
        new_xmin = cx - real_w / 2
        new_xmax = cx + real_w / 2
        new_ymin = cy - real_h / 2
        new_ymax = cy + real_h / 2
        return (new_xmin, new_ymin, new_xmax, new_ymax), True
    else:
        # El AOI no cabe: escalar para que entre
        scale_factor = max(aoi_w / real_w, aoi_h / real_h) * 1.05
        adjusted_w = real_w * scale_factor
        adjusted_h = real_h * scale_factor
        new_xmin = cx - adjusted_w / 2
        new_xmax = cx + adjusted_w / 2
        new_ymin = cy - adjusted_h / 2
        new_ymax = cy + adjusted_h / 2
        return (new_xmin, new_ymin, new_xmax, new_ymax), False

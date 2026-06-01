# =============================================================================
# Compositor cartográfico principal — Celdas 10 y 11 del notebook
# GIS Dev Academy — CartografIA API
# =============================================================================

import os
import math
import logging
import warnings
from datetime import date, datetime
from typing import Callable

import numpy as np
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch
from pyproj import Transformer
from shapely.geometry import box

matplotlib.rcParams["pdf.fonttype"]       = 42
matplotlib.rcParams["ps.fonttype"]        = 42
matplotlib.rcParams["font.family"]        = "DejaVu Sans"
matplotlib.rcParams["axes.unicode_minus"] = False
warnings.filterwarnings("ignore")

from .constants import C, ESCALAS, FORMATOS, MARGEN_CM, PANEL_IZQ_CM, PANEL_DER_CM
from .geo_utils  import (
    detectar_faja, aoi_desde_coordenadas, centroide_wgs84,
    calcular_grilla, etiqueta_gk, dms_str, clasificar_vias,
    geom_tipo, bounds_gk_to_wgs, bounds_para_escala,
)
from .data_download import descargar_osm, descargar_dem, procesar_dem, extraer_localidades
from .panel_izq import dibujar_panel_izq
from .panel_der import dibujar_panel_der

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layout de figura
# ---------------------------------------------------------------------------

def _layout_figura(formato: str) -> dict:
    fw_cm, fh_cm = FORMATOS[formato]

    izq_w = PANEL_IZQ_CM / fw_cm
    der_w = PANEL_DER_CM / fw_cm
    mar   = MARGEN_CM / fw_cm
    mar_v = MARGEN_CM / fh_cm
    sep   = 0.002

    map_x = mar + izq_w + sep
    map_w = 1 - mar - izq_w - sep - der_w - sep - mar
    map_y = mar_v
    map_h = 1 - 2 * mar_v

    map_w_cm = map_w * fw_cm
    map_h_cm = map_h * fh_cm

    return {
        "fw_cm": fw_cm,
        "fh_cm": fh_cm,
        "map_w_cm": map_w_cm,
        "map_h_cm": map_h_cm,
        "ax_izq": [mar, mar_v, izq_w, 1 - 2 * mar_v],
        "ax_map": [map_x, map_y, map_w, map_h],
        "ax_pan": [map_x + map_w + sep, mar_v, der_w, 1 - 2 * mar_v],
    }


# ---------------------------------------------------------------------------
# Helpers de renderizado
# ---------------------------------------------------------------------------

def _best_line(geom):
    from shapely.geometry import LineString, MultiLineString
    if geom is None:
        return None
    if geom.geom_type == "LineString":
        return geom
    if geom.geom_type == "MultiLineString":
        lines = list(geom.geoms)
        return max(lines, key=lambda l: l.length) if lines else None
    return None


def _line_angle(line, frac: float = 0.5) -> float:
    try:
        p1 = line.interpolate(frac - 0.05, normalized=True)
        p2 = line.interpolate(frac + 0.05, normalized=True)
        angle = math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))
        if angle < -90:
            angle += 180
        if angle > 90:
            angle -= 180
        return angle
    except Exception:
        return 0.0


def _too_close(x, y, placed: list, minx: float, miny: float) -> bool:
    for px, py, mx, my in placed:
        if abs(x - px) < mx and abs(y - py) < my:
            return True
    return False


def _label_halo(width: float = 1.0):
    return [pe.withStroke(linewidth=width * 2.5, foreground="white")]


def _fmt_route_ref(row, fallback: str = "") -> str:
    for col in ("ref", "name"):
        if col in row.index and isinstance(row[col], str) and row[col].strip():
            val = row[col].strip()
            # Extraer número de la ref (ej: "RN 9" → "9")
            parts = val.replace("-", " ").split()
            for p in parts:
                if p.isdigit():
                    return p
            return val[:5]
    return fallback


def _draw_route_shields(ax, gdf, prefix: str, bounds: tuple, placed: list):
    xm0, ym0, xm1, ym1 = bounds
    dx, dy = xm1 - xm0, ym1 - ym0
    if gdf is None or gdf.empty:
        return
    seen_refs: set = set()
    for _, row in gdf.iterrows():
        line = _best_line(row.geometry)
        if line is None or line.length < min(dx, dy) * 0.08:
            continue
        ref = _fmt_route_ref(row)
        if not ref or ref in seen_refs:
            continue
        pt = line.interpolate(0.50, normalized=True)
        if not (xm0 < pt.x < xm1 and ym0 < pt.y < ym1):
            continue
        if _too_close(pt.x, pt.y, placed, dx * 0.06, dy * 0.04):
            continue
        fc = C["ruta_ppal"] if prefix == "RN" else C["ruta_sec"]
        ax.annotate(
            f"{prefix}\n{ref}",
            xy=(pt.x, pt.y),
            ha="center", va="center", fontsize=2.8,
            fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.15", facecolor=fc,
                      edgecolor="white", linewidth=0.4),
            zorder=35, clip_on=True,
        )
        placed.append((pt.x, pt.y, dx * 0.06, dy * 0.04))
        seen_refs.add(ref)


def _draw_rail(ax, rail: gpd.GeoDataFrame, color: str, zorder: int = 12):
    from shapely.geometry import LineString, MultiLineString
    for _, row in rail.iterrows():
        geom = row.geometry
        lines = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for line in lines:
            coords = list(line.coords)
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            ax.plot(xs, ys, color=color, lw=0.85, zorder=zorder, solid_capstyle="round")
            # Traviesas
            total_len = line.length
            n_ties = max(3, int(total_len / (total_len * 0.08 + 1)))
            for frac in np.linspace(0.1, 0.9, min(n_ties, 12)):
                pt   = line.interpolate(frac, normalized=True)
                ang  = _line_angle(line, frac)
                perp = math.radians(ang + 90)
                half = total_len * 0.012
                x0 = pt.x - half * math.cos(perp)
                y0 = pt.y - half * math.sin(perp)
                x1 = pt.x + half * math.cos(perp)
                y1 = pt.y + half * math.sin(perp)
                ax.plot([x0, x1], [y0, y1], color=color, lw=0.35,
                        zorder=zorder - 1, solid_capstyle="butt")


# ---------------------------------------------------------------------------
# Generador principal
# ---------------------------------------------------------------------------

def generar_carta(
    config: dict,
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict:
    """
    Genera la carta topográfica completa.

    config keys requeridos:
      titulo, subtitulo, escala, formato, aoi_gdf,
      eq_ppal, eq_sec, capas, output_dir,
      archivo_dem (opcional), logo_path (opcional),
      dpi_pdf, dpi_png, export_pdf, export_png

    Retorna dict con paths de los archivos generados.
    """

    def _progress(step: int, msg: str):
        logger.info(f"[{step}/5] {msg}")
        if progress_callback:
            progress_callback(step, msg)

    # ── 1. Parámetros base ─────────────────────────────────────────────────
    _progress(1, "Calculando encuadre y proyección...")

    titulo    = config.get("titulo", "SIN TITULO").upper()
    subtitulo = config.get("subtitulo", "")
    escala_s  = config.get("escala", "1:50.000")
    formato   = config.get("formato", "A3")
    ep        = ESCALAS[escala_s]
    escala_v  = ep["valor"]
    eq_ppal   = config.get("eq_ppal") or ep["eq_ppal"]
    eq_sec    = config.get("eq_sec")  or ep["eq_sec"]
    capas     = config.get("capas", {})

    aoi_gdf   = config.get("aoi_gdf")
    if aoi_gdf is None:
        raise ValueError("Se requiere aoi_gdf en config")

    aoi_wgs   = aoi_gdf.to_crs("EPSG:4326") if aoi_gdf.crs.to_epsg() != 4326 else aoi_gdf.copy()
    lon_c, lat_c = centroide_wgs84(aoi_wgs)
    faja_info = detectar_faja(lon_c)
    epsg_gk   = faja_info["epsg"]

    logger.info(f"  Faja GK {faja_info['numero']} | EPSG:{epsg_gk} | MC {faja_info['meridiano']}°")

    aoi_gk   = aoi_wgs.to_crs(epsg=epsg_gk)
    b_wgs    = tuple(aoi_wgs.total_bounds)
    b_gk     = tuple(aoi_gk.total_bounds)

    ly = _layout_figura(formato)
    b_plot, escala_exacta = bounds_para_escala(
        b_gk, escala_v, ly["map_w_cm"], ly["map_h_cm"]
    )
    b_plot_wgs = bounds_gk_to_wgs(b_plot, epsg_gk)
    if not escala_exacta:
        logger.warning("  El AOI excede el formato para la escala exacta — encuadre ajustado")

    # ── 2. Descarga OSM ────────────────────────────────────────────────────
    _progress(2, "Descargando datos OSM...")

    buf = 0.010
    aoi_buf = gpd.GeoDataFrame(
        geometry=[box(
            b_plot_wgs[0] - buf, b_plot_wgs[1] - buf,
            b_plot_wgs[2] + buf, b_plot_wgs[3] + buf,
        )],
        crs=4326,
    )
    osm_raw = descargar_osm(aoi_buf, capas)
    osm_gk: dict = {}
    for nombre, gdf in osm_raw.items():
        try:
            osm_gk[nombre] = gdf.set_crs(4326, allow_override=True).to_crs(epsg=epsg_gk)
        except Exception as e:
            logger.warning(f"  Repr. {nombre}: {e}")

    # ── 3. Procesamiento DEM ───────────────────────────────────────────────
    _progress(3, "Procesando DEM y curvas de nivel...")

    curvas: dict = {}
    if capas.get("altimetria") or capas.get("curvas_nivel"):
        dem_cache = config.get("dem_cache_dir", "/tmp/dem_cache")
        dem_path  = config.get("archivo_dem") or descargar_dem(tuple(b_plot_wgs), dem_cache)
        if dem_path:
            curvas = procesar_dem(dem_path, eq_ppal, eq_sec, epsg_gk)

    localidades = extraer_localidades(osm_gk)

    # ── 4. Composición de la carta ─────────────────────────────────────────
    _progress(4, "Componiendo carta...")

    fig    = plt.figure(
        figsize=(ly["fw_cm"] / 2.54, ly["fh_cm"] / 2.54),
        facecolor="white",
    )
    ax_izq = fig.add_axes(ly["ax_izq"])
    ax_map = fig.add_axes(ly["ax_map"])
    ax_pan = fig.add_axes(ly["ax_pan"])

    for ax_ in (ax_izq, ax_pan):
        ax_.set_axis_off()
        ax_.set_facecolor("#FFFFFF")

    xm0, ym0, xm1, ym1 = b_plot
    dx, dy = xm1 - xm0, ym1 - ym0

    ax_map.set_xlim(xm0, xm1)
    ax_map.set_ylim(ym0, ym1)
    ax_map.set_facecolor(C["fondo"])
    ax_map.set_aspect("equal", adjustable="box")
    for sp in ax_map.spines.values():
        sp.set_linewidth(0.85)
        sp.set_color(C["borde"])
    ax_map.set_xticks([])
    ax_map.set_yticks([])

    # Vegetación
    if "vegetacion" in osm_gk:
        veg_p = geom_tipo(osm_gk["vegetacion"], ["Polygon", "MultiPolygon"])
        if not veg_p.empty:
            for col, tipos, color in [
                ("natural",  ["wood", "forest"],                          C["veg_alta"]),
                ("natural",  ["scrub", "heath", "grassland"],             C["veg_baja"]),
                ("natural",  ["bare_rock", "scree"],                      C["afloramiento"]),
                ("landuse",  ["farmland", "meadow", "orchard", "vineyard"], C["cultivo"]),
                ("landuse",  ["forest", "wood"],                          C["veg_alta"]),
                ("leisure",  ["park", "garden", "nature_reserve"],        C["veg_baja"]),
            ]:
                if col in veg_p.columns:
                    sub = veg_p[veg_p[col].isin(tipos)]
                    if not sub.empty:
                        sub.plot(ax=ax_map, color=color, edgecolor="none", alpha=0.52, zorder=1)

    # Áreas urbanas
    if "areas_urbanas" in osm_gk:
        urb = geom_tipo(osm_gk["areas_urbanas"], ["Polygon", "MultiPolygon"])
        if not urb.empty:
            if "landuse" in urb.columns:
                res = urb[urb["landuse"].isin(["residential", "commercial", "retail"])]
                ind = urb[urb["landuse"] == "industrial"]
                if not res.empty:
                    res.plot(ax=ax_map, color=C["ejido"], edgecolor="#CC6688",
                             linewidth=0.18, alpha=0.70, zorder=2)
                if not ind.empty:
                    ind.plot(ax=ax_map, color=C["industrial"], edgecolor="#9A80B8",
                             linewidth=0.25, alpha=0.55, zorder=2)
            else:
                urb.plot(ax=ax_map, color=C["ejido"], edgecolor="#CC6688",
                         linewidth=0.18, alpha=0.70, zorder=2)

    # Curvas de nivel
    if curvas and "Z" in curvas:
        try:
            X, Y, Z = curvas["X"], curvas["Y"], curvas["Z"]
            if "levels_sec" in curvas and len(curvas["levels_sec"]) > 1:
                ax_map.contour(X, Y, Z, levels=curvas["levels_sec"],
                               colors=[C["curvas_sec"]], linewidths=0.20, alpha=0.55, zorder=3)
            if "levels_ppal" in curvas and len(curvas["levels_ppal"]) > 1:
                cs = ax_map.contour(X, Y, Z, levels=curvas["levels_ppal"],
                                    colors=[C["curvas_ppal"]], linewidths=0.58, alpha=0.75, zorder=3)
                ax_map.clabel(cs, inline=True, fontsize=3.1, fmt="%d", colors=C["curvas_ppal"])
        except Exception as e:
            logger.warning(f"  Curvas de nivel: {e}")

    # Hidrografía
    if "hidrografia" in osm_gk:
        try:
            agua   = osm_gk["hidrografia"]
            agua_p = geom_tipo(agua, ["Polygon", "MultiPolygon"])
            if not agua_p.empty:
                agua_p.plot(ax=ax_map, color=C["agua_fill"], edgecolor=C["agua_line"],
                            linewidth=0.35, alpha=0.90, zorder=4)
            agua_l = geom_tipo(agua, ["LineString", "MultiLineString"])
            if not agua_l.empty:
                rios = arroyos = gpd.GeoDataFrame(geometry=[], crs=agua_l.crs)
                if "waterway" in agua_l.columns:
                    rios    = agua_l[agua_l["waterway"].isin(["river", "canal"])]
                    arroyos = agua_l[agua_l["waterway"].isin(["stream", "drain", "ditch"])]
                    if not rios.empty:
                        rios.plot(ax=ax_map, color=C["agua_line"], lw=1.0, zorder=14)
                    if not arroyos.empty:
                        arroyos.plot(ax=ax_map, color=C["arroyo"], lw=0.50, alpha=0.85, zorder=14)
                else:
                    agua_l.plot(ax=ax_map, color=C["agua_line"], lw=0.75, zorder=14)

                # Etiquetas de ríos
                placed_r: list = []
                for gdf_w, fs_w, col_w in [
                    (rios,    3.1, C["agua_line"]),
                    (arroyos, 2.7, C["arroyo"]),
                ]:
                    if gdf_w.empty or "name" not in gdf_w.columns:
                        continue
                    for _, rw in gdf_w[gdf_w["name"].notna()].iterrows():
                        line = _best_line(rw.geometry)
                        if line is None or line.length < min(dx, dy) * 0.05:
                            continue
                        pt = line.interpolate(0.52, normalized=True)
                        if _too_close(pt.x, pt.y, placed_r, dx * 0.10, dy * 0.045):
                            continue
                        name = str(rw["name"]).strip()
                        if not name:
                            continue
                        ax_map.text(
                            pt.x, pt.y, name, ha="center", va="center",
                            fontsize=fs_w, fontstyle="italic", color=col_w,
                            rotation=_line_angle(line), rotation_mode="anchor",
                            path_effects=_label_halo(1.0), zorder=32, clip_on=True,
                        )
                        placed_r.append((pt.x, pt.y, dx * 0.10, dy * 0.045))
        except Exception as e:
            logger.warning(f"  Hidrografía: {e}")

    # Edificios
    if "edificios" in osm_gk:
        edif = geom_tipo(osm_gk["edificios"], ["Polygon", "MultiPolygon"])
        if not edif.empty:
            edif.plot(ax=ax_map, color=C["edificio"], edgecolor="#886666",
                      linewidth=0.10, alpha=0.75, zorder=5)

    # Ferroviario
    if "ferroviario" in osm_gk:
        try:
            rail = geom_tipo(osm_gk["ferroviario"], ["LineString", "MultiLineString"])
            if not rail.empty:
                _draw_rail(ax_map, rail, C["ferroviario"], zorder=13)
        except Exception as e:
            logger.warning(f"  Ferroviario: {e}")

    # Red vial
    route_shield_places: list = []
    if "red_vial" in osm_gk:
        try:
            clas = clasificar_vias(osm_gk["red_vial"])
            for cat, color, lw, zo, ls in [
                ("senderos",   C["sendero"],   0.28, 7,  (0, (1, 2))),
                ("caminos",    C["camino"],    0.55, 8,  (0, (5, 2))),
                ("calles",     C["calle"],     0.48, 9,  "solid"),
                ("rutas_sec",  C["ruta_sec"],  1.05, 10, "solid"),
                ("rutas_ppal", C["ruta_ppal"], 1.65, 11, "solid"),
            ]:
                if cat not in clas:
                    continue
                sub = geom_tipo(clas[cat], ["LineString", "MultiLineString"])
                if sub.empty:
                    continue
                sub.plot(ax=ax_map, color="#FFFFFF", lw=lw * 2.2,
                         zorder=zo - 1, alpha=0.86)
                sub.plot(ax=ax_map, color=color, lw=lw, zorder=zo,
                         linestyle=ls, alpha=0.98)

            if "rutas_ppal" in clas:
                _draw_route_shields(
                    ax_map,
                    geom_tipo(clas["rutas_ppal"], ["LineString", "MultiLineString"]),
                    "RN", (xm0, ym0, xm1, ym1), route_shield_places,
                )
            if "rutas_sec" in clas:
                _draw_route_shields(
                    ax_map,
                    geom_tipo(clas["rutas_sec"], ["LineString", "MultiLineString"]),
                    "RP", (xm0, ym0, xm1, ym1), route_shield_places,
                )
        except Exception as e:
            logger.warning(f"  Red vial: {e}")

    # Puntos geográficos
    if "puntos_geo" in osm_gk:
        try:
            pts    = geom_tipo(osm_gk["puntos_geo"], ["Point"])
            pts_in = pts.cx[xm0:xm1, ym0:ym1]
            if not pts_in.empty:
                pts_in.plot(ax=ax_map, color=C["acento"], marker="^",
                            markersize=3.2, edgecolors="white",
                            linewidths=0.25, zorder=30)
                if "name" in pts_in.columns:
                    placed_p: list = []
                    for _, row in pts_in.iterrows():
                        if not row.geometry or not row.get("name"):
                            continue
                        px, py = row.geometry.x, row.geometry.y
                        if _too_close(px, py, placed_p, dx * 0.06, dy * 0.035):
                            continue
                        ax_map.annotate(
                            str(row["name"]), xy=(px, py), xytext=(3, 3),
                            textcoords="offset points", fontsize=3.0,
                            color="#1A1A2E", path_effects=_label_halo(1.0),
                            zorder=33, clip_on=True,
                        )
                        placed_p.append((px, py, dx * 0.06, dy * 0.035))
        except Exception as e:
            logger.warning(f"  Puntos geo: {e}")

    # Localidades
    if "localidades" in osm_gk:
        try:
            places = geom_tipo(osm_gk["localidades"], ["Point"])
            if not places.empty and "name" in places.columns:
                places_in = places.cx[xm0:xm1, ym0:ym1].copy()
                hier = {
                    "city": 0, "town": 1, "suburb": 2,
                    "village": 3, "hamlet": 4, "locality": 5, "neighbourhood": 6,
                }
                if "place" in places_in.columns:
                    places_in["_rank"] = places_in["place"].map(hier).fillna(9)
                else:
                    places_in["_rank"] = 9
                places_in = places_in.sort_values("_rank")
                placed     = list(route_shield_places)
                max_labels = 70 if formato in ["A1", "A2"] else 42
                count      = 0
                for _, row in places_in.iterrows():
                    if count >= max_labels or not row.geometry or not row.get("name"):
                        continue
                    ptype  = row.get("place", "")
                    rank   = int(row.get("_rank", 9))
                    fs_p   = 4.8 if ptype in ["city", "town"] else 3.9 if rank <= 3 else 3.0
                    px, py = row.geometry.x, row.geometry.y
                    label  = str(row["name"]).strip()
                    if not label:
                        continue
                    label = label.upper() if rank <= 3 else label.title()
                    sx = dx * (0.032 + 0.0032 * len(label))
                    sy = dy * (0.030 if rank <= 3 else 0.022)
                    if _too_close(px, py, placed, sx, sy) and rank > 0:
                        continue
                    ax_map.text(
                        px, py, label, ha="center", va="center",
                        fontsize=fs_p,
                        fontweight="semibold" if rank <= 3 else "normal",
                        color="#1D2530", path_effects=_label_halo(1.15),
                        zorder=42, clip_on=True,
                    )
                    placed.append((px, py, sx, sy))
                    count += 1
        except Exception as e:
            logger.warning(f"  Etiquetas localidades: {e}")

    # Grilla y etiquetas
    intervalo_m = ep["grilla_km"] * 1000
    grilla      = calcular_grilla(tuple(b_plot), intervalo_m)
    tr_geo      = Transformer.from_crs(epsg_gk, 4326, always_xy=True)

    xs_prev = None
    for xg in grilla["x"]:
        ax_map.axvline(x=xg, color=C["grilla"], lw=0.34, alpha=0.55, zorder=20)
        lbl = etiqueta_gk(xg, xs_prev)
        for ya, va_ in [(ym1 - dy * 0.006, "top"), (ym0 + dy * 0.006, "bottom")]:
            ax_map.text(
                xg, ya, lbl, ha="center", va=va_, fontsize=4.0,
                color=C["grilla_tick"], zorder=35, fontfamily="monospace",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.25),
                clip_on=True,
            )
        xs_prev = xg

    ys_prev = None
    for yg in grilla["y"]:
        ax_map.axhline(y=yg, color=C["grilla"], lw=0.34, alpha=0.55, zorder=20)
        lbl = etiqueta_gk(yg, ys_prev)
        for xa, ha_ in [(xm0 + dx * 0.006, "left"), (xm1 - dx * 0.006, "right")]:
            ax_map.text(
                xa, yg, lbl, ha=ha_, va="center", fontsize=4.0,
                color=C["grilla_tick"], zorder=35, fontfamily="monospace",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.25),
                clip_on=True,
            )
        ys_prev = yg

    # Coordenadas en esquinas
    for cx_, cy_, ha_, va_ in [
        (xm0 + dx * 0.008, ym1 - dy * 0.012, "left",  "top"),
        (xm1 - dx * 0.008, ym1 - dy * 0.012, "right", "top"),
        (xm0 + dx * 0.008, ym0 + dy * 0.012, "left",  "bottom"),
        (xm1 - dx * 0.008, ym0 + dy * 0.012, "right", "bottom"),
    ]:
        lon_, lat_ = tr_geo.transform(cx_, cy_)
        ax_map.text(
            cx_, cy_, f"{dms_str(lon_, 'lon')} / {dms_str(lat_, 'lat')}",
            ha=ha_, va=va_, fontsize=2.8, style="italic", color="#555555",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.76, pad=0.30),
            zorder=36, clip_on=True,
        )

    # Bordes de paneles
    import matplotlib
    for rect in [ly["ax_izq"], ly["ax_map"], ly["ax_pan"]]:
        x, y0, w, h = rect
        fig.add_artist(matplotlib.patches.Rectangle(
            (x, y0), w, h, transform=fig.transFigure,
            fill=False, edgecolor=C["borde"], linewidth=0.85, zorder=50,
        ))
    fig.add_artist(matplotlib.patches.Rectangle(
        (MARGEN_CM / ly["fw_cm"], MARGEN_CM / ly["fh_cm"]),
        (ly["fw_cm"] - 2 * MARGEN_CM) / ly["fw_cm"],
        (ly["fh_cm"] - 2 * MARGEN_CM) / ly["fh_cm"],
        transform=fig.transFigure,
        fill=False, edgecolor=C["borde"], linewidth=1.4, zorder=60,
    ))

    # Paneles laterales
    dibujar_panel_izq(ax_izq, escala_v, escala_s, eq_ppal, eq_sec, faja_info)
    dibujar_panel_der(
        ax_pan, titulo, subtitulo, escala_s, escala_v,
        faja_info, lon_c, lat_c, eq_ppal, eq_sec,
        aoi_bounds_wgs=tuple(b_wgs),
        localidades=localidades,
        logo_path=config.get("logo_path"),
    )

    # ── 5. Exportación ────────────────────────────────────────────────────
    _progress(5, "Exportando archivos...")

    out_dir = config.get("output_dir", "/tmp/cartografia_outputs")
    os.makedirs(out_dir, exist_ok=True)

    safe = "".join(
        c if c.isalnum() or c in "_-" else "_"
        for c in titulo.lower().replace(" ", "_")
    )[:30]
    fecha     = date.today().strftime("%Y%m%d")
    hora      = datetime.now().strftime("%H%M%S")
    esc_s     = escala_s.replace(":", "").replace(".", "").replace(" ", "")
    base_name = f"M01_carta_{safe}_{esc_s}_{formato}_{fecha}_{hora}"

    result = {"job_id": config.get("job_id"), "faja_info": faja_info}

    dpi_pdf = int(config.get("dpi_pdf", 600))
    dpi_png = int(config.get("dpi_png", 450 if formato in ["A3", "A4"] else 360))

    if config.get("export_pdf", True):
        out_pdf = os.path.join(out_dir, f"{base_name}.pdf")
        fig.savefig(out_pdf, format="pdf", facecolor="white", dpi=dpi_pdf)
        result["pdf_path"] = out_pdf
        result["pdf_size_mb"] = round(os.path.getsize(out_pdf) / 1_048_576, 2)
        logger.info(f"  PDF → {out_pdf} ({result['pdf_size_mb']} MB)")

    if config.get("export_png", True):
        out_png = os.path.join(out_dir, f"{base_name}.png")
        fig.savefig(out_png, format="png", facecolor="white", dpi=dpi_png)
        result["png_path"] = out_png
        result["png_size_mb"] = round(os.path.getsize(out_png) / 1_048_576, 2)
        logger.info(f"  PNG → {out_png} ({result['png_size_mb']} MB)")

    plt.close(fig)
    logger.info("  ✓ Carta generada exitosamente")
    return result

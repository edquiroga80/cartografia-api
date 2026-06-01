# =============================================================================
# Panel derecho: Título e Información — Celda 9 del notebook
# GIS Dev Academy — CartografIA API
# =============================================================================

import os
import logging
from datetime import date

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pyproj import Transformer

from .constants import C
from .geo_utils import generar_codigo_hoja

logger = logging.getLogger(__name__)

try:
    import contextily as cx
    CONTEXTILY_OK = True
except ImportError:
    CONTEXTILY_OK = False


# ---------------------------------------------------------------------------
# Helpers de proyección para insertos de ubicación
# ---------------------------------------------------------------------------

def _pt_3857(lon: float, lat: float) -> tuple:
    tr = Transformer.from_crs(4326, 3857, always_xy=True)
    return tr.transform(lon, lat)


def _bounds_3857_from_wgs(xmin, ymin, xmax, ymax) -> tuple:
    tr = Transformer.from_crs(4326, 3857, always_xy=True)
    x0, y0 = tr.transform(xmin, ymin)
    x1, y1 = tr.transform(xmax, ymax)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _add_basemap_safe(ax, zoom: int, source_name: str = "CartoDB.Positron"):
    if not CONTEXTILY_OK:
        ax.set_facecolor("#E7EEF2")
        return
    try:
        src = getattr(cx.providers.CartoDB, "Positron", None)
        if src:
            cx.add_basemap(
                ax, crs="EPSG:3857", source=src,
                zoom=zoom, attribution=False, reset_extent=False,
            )
    except Exception:
        ax.set_facecolor("#E7EEF2")


def _safe_read_logo(path: str | None):
    try:
        import matplotlib.image as mpimg
        if path and os.path.exists(path):
            return mpimg.imread(path)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Panel derecho principal
# ---------------------------------------------------------------------------

def dibujar_panel_der(
    ax: plt.Axes,
    titulo: str,
    subtitulo: str,
    escala_nombre: str,
    escala_valor: int,
    faja_info: dict,
    lon_c: float,
    lat_c: float,
    eq_ppal: float,
    eq_sec: float,
    aoi_bounds_wgs: tuple | None = None,
    localidades: list | None = None,
    logo_path: str | None = None,
):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")

    ML, MR = 0.045, 0.045
    W = 1 - ML - MR

    def _r(x, yb, w, h, fc="#FFFFFF", ec="#999999", lw=0.35, zo=3):
        ax.add_patch(FancyBboxPatch(
            (x, yb), w, h, boxstyle="square,pad=0",
            linewidth=lw, edgecolor=ec, facecolor=fc,
            transform=ax.transAxes, zorder=zo,
        ))

    def _t(x, y, s, fs=4.0, bold=False, color="#222222",
           ha="left", va="top", italic=False, zo=4):
        ax.text(
            x, y, str(s), ha=ha, va=va, fontsize=fs,
            fontweight="bold" if bold else "normal",
            fontstyle="italic" if italic else "normal",
            color=color, transform=ax.transAxes, zorder=zo,
        )

    def _sec_hdr(y, label, h=0.020):
        _r(ML, y - h, W, h, fc=C["panel_sec"], ec="none", lw=0)
        _t(0.5, y - h / 2, label.upper(), fs=4.2, bold=True,
           color="#FFFFFF", ha="center", va="center")
        return y - h - 0.006

    # ── Bloque de título ────────────────────────────────────────────────────
    title_h = 0.135
    _r(0, 1 - title_h, 1, title_h, fc=C["panel_titulo"], ec="none", lw=0)
    _t(0.5, 0.992, "MAPA TOPOGRAFICO", fs=5.2, bold=True,
       color="#FFFFFF", ha="center", va="top")
    _t(0.5, 0.967, titulo[:42], fs=7.0, bold=True,
       color=C["acento"], ha="center", va="top")
    _t(0.5, 0.928, subtitulo[:58], fs=3.4, color="#DADADA",
       ha="center", va="top")

    logo_img = _safe_read_logo(logo_path)
    if logo_img is not None:
        iax = ax.inset_axes([0.800, 0.888, 0.125, 0.085], transform=ax.transAxes)
        iax.imshow(logo_img, aspect="equal")
        iax.set_axis_off()
        iax.set_anchor("C")
    else:
        _t(0.86, 0.928, "GIS DEV\nACADEMY", fs=3.2, bold=True,
           color="#FFFFFF", ha="center", va="center")

    hoja_codigo, hoja_id = generar_codigo_hoja(lon_c, lat_c, escala_valor)
    _t(0.5, 0.885, f"HOJA  {hoja_codigo}", fs=3.7, bold=True,
       color="#DADADA", ha="center")
    _t(0.5, 0.867, f"EDICION  {date.today().year}", fs=3.4,
       color="#DADADA", ha="center")

    y = 1 - title_h - 0.008

    # ── Ubicación ────────────────────────────────────────────────────────────
    ubi_h   = 0.150
    y       = _sec_hdr(y, "Ubicacion")
    y_ubi_bot = y - ubi_h
    _r(ML, y_ubi_bot, W, ubi_h, fc="#F8FAFB", ec="#B8C0C8", lw=0.35)
    try:
        if aoi_bounds_wgs:
            xmin, ymin, xmax, ymax = aoi_bounds_wgs
        else:
            xmin, ymin, xmax, ymax = lon_c - 1, lat_c - 1, lon_c + 1, lat_c + 1

        ax_arg = ax.inset_axes(
            [ML + 0.02, y_ubi_bot + 0.018, W * 0.34, ubi_h - 0.036],
            transform=ax.transAxes,
        )
        ax_reg = ax.inset_axes(
            [ML + W * 0.46, y_ubi_bot + 0.018, W * 0.50, ubi_h - 0.036],
            transform=ax.transAxes,
        )
        for ia in (ax_arg, ax_reg):
            ia.set_xticks([])
            ia.set_yticks([])
            for sp in ia.spines.values():
                sp.set_visible(False)

        bx0, by0 = _pt_3857(-73, -56)
        bx1, by1 = _pt_3857(-52, -21)
        ax_arg.set_xlim(bx0, bx1)
        ax_arg.set_ylim(by0, by1)
        _add_basemap_safe(ax_arg, 3)
        px, py = _pt_3857(lon_c, lat_c)
        ax_arg.plot(px, py, "o", color=C["acento"], markersize=3.5, zorder=5)

        pad = 2.5
        rx0, ry0, rx1, ry1 = _bounds_3857_from_wgs(
            xmin - pad, ymin - pad, xmax + pad, ymax + pad
        )
        ax_reg.set_xlim(rx0, rx1)
        ax_reg.set_ylim(ry0, ry1)
        _add_basemap_safe(ax_reg, 7)
        ax_reg.plot(px, py, "s", color=C["acento"], markersize=3.2, zorder=5)
    except Exception as e:
        logger.warning(f"  Insertos de ubicación fallidos: {e}")
        _t(0.5, y_ubi_bot + ubi_h / 2, "Ubicacion no disponible",
           fs=4.0, color="#777777", ha="center", va="center")
    y = y_ubi_bot - 0.010

    # ── Leyenda de localidades ───────────────────────────────────────────────
    ley_h     = 0.120
    y         = _sec_hdr(y, "Leyenda")
    y_ley_bot = y - ley_h
    _r(ML, y_ley_bot, W, ley_h, fc="#FAFAFA", ec="#B8B8B8", lw=0.35)
    if localidades:
        max_locs = min(len(localidades), 8)
        spc = (ley_h - 0.018) / max_locs
        for i, (num, nombre) in enumerate(localidades[:max_locs]):
            yy = y - 0.010 - i * spc
            _r(ML + 0.018, yy - 0.012, 0.028, 0.017, fc=C["acento"], ec="none", lw=0)
            _t(ML + 0.032, yy - 0.003, f"{num:02d}", fs=3.2, bold=True,
               color="#FFFFFF", ha="center", va="center")
            _t(ML + 0.058, yy + 0.003, nombre[:34], fs=3.4, color="#222222")
    else:
        _t(0.5, y_ley_bot + ley_h / 2, "Sin localidades en el AOI",
           fs=3.8, color="#777777", ha="center", va="center")
    y = y_ley_bot - 0.010

    # ── Información general ──────────────────────────────────────────────────
    info_h     = 0.112
    y          = _sec_hdr(y, "Informacion general")
    y_info_bot = y - info_h
    _r(ML, y_info_bot, W, info_h, fc="#FAFAFA", ec="#B8B8B8", lw=0.35)
    info_items = [
        ("Elaboracion:", "GIS Dev Academy  |  gisdev.ar"),
        ("Fuente:",      "OpenStreetMap / SRTM / IGN"),
        ("Edicion:",     date.today().strftime("%m/%Y")),
        ("Revision:",    "01"),
        ("Codigo:",      hoja_codigo),
        ("Escala:",      escala_nombre),
        ("Formato:",     "Digital"),
        ("Impresion:",   "Local"),
    ]
    yy = y - 0.010
    for k, v in info_items:
        _t(ML + 0.025, yy, k, fs=3.1, bold=True, color="#333333")
        _t(ML + 0.260, yy, v, fs=3.1, color="#333333")
        yy -= 0.011
    y = y_info_bot - 0.010

    # ── Diagrama de compilación ──────────────────────────────────────────────
    diag_h     = 0.095
    y          = _sec_hdr(y, "Diagrama de compilacion")
    y_diag_bot = y - diag_h
    _r(ML, y_diag_bot, W, diag_h, fc="#FAFAFA", ec="#B8B8B8", lw=0.35)
    cw, ch = W / 3, diag_h / 2
    for ri, row_id in enumerate(["18", "19"]):
        for ci, col_id in enumerate(["L", "M", "N"]):
            bx  = ML + ci * cw
            by  = y_diag_bot + (1 - ri) * ch
            cur = (ri == 0 and ci == 1)
            _r(bx, by, cw, ch,
               fc=C["acento"] if cur else "#FFFFFF",
               ec="#999999", lw=0.35)
            _t(bx + cw / 2, by + ch / 2, f"{row_id}{col_id}",
               fs=3.0, bold=cur,
               color="#FFFFFF" if cur else "#777777",
               ha="center", va="center")
    y = y_diag_bot - 0.010

    # ── Notas ────────────────────────────────────────────────────────────────
    y          = _sec_hdr(y, "Notas")
    notes_bot  = 0.015
    _r(ML, notes_bot, W, max(0.035, y - notes_bot), fc="#FAFAFA", ec="#B8B8B8", lw=0.35)
    notas = [
        "- Carta georreferenciada en WGS84 / POSGAR 1994.",
        "- Limites y datos OSM referenciales.",
        f"- Curvas: directriz {int(eq_ppal)} m / intermedia {int(eq_sec)} m.",
        "- Exportacion local automatica: PDF + PNG.",
    ]
    yy = y - 0.010
    for nota in notas:
        _t(ML + 0.020, yy, nota, fs=3.0, italic=True, color="#555555")
        yy -= 0.012

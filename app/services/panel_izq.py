# =============================================================================
# Panel izquierdo: Signos Convencionales — Celda 8 del notebook
# GIS Dev Academy — CartografIA API
# =============================================================================

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from .constants import C


def dibujar_panel_izq(
    ax: plt.Axes,
    escala_val: int,
    escala_nombre: str,
    eq_ppal: float,
    eq_sec: float,
    faja_info: dict,
):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")

    ML, MR = 0.055, 0.035
    W  = 1 - ML - MR
    XS = ML
    SW = 0.18
    XT = ML + SW + 0.06
    FS = 3.75
    DY = 0.0112

    def _r(x, yb, w, h, fc="#FFFFFF", ec="#999999", lw=0.35, zo=3):
        ax.add_patch(FancyBboxPatch(
            (x, yb), w, h, boxstyle="square,pad=0",
            linewidth=lw, edgecolor=ec, facecolor=fc,
            transform=ax.transAxes, zorder=zo,
        ))

    def _t(x, y, s, fs=FS, bold=False, color="#222222",
           ha="left", va="top", italic=False, zo=4):
        ax.text(
            x, y, s, ha=ha, va=va, fontsize=fs,
            fontweight="bold" if bold else "normal",
            fontstyle="italic" if italic else "normal",
            color=color, transform=ax.transAxes, zorder=zo,
        )

    def _l(x0, x1, yc, color="#333333", lw=0.7, ls="solid", alpha=1.0):
        ax.plot(
            [x0, x1], [yc, yc], color=color, lw=lw,
            linestyle=ls, alpha=alpha, transform=ax.transAxes, zorder=5,
        )

    def _hdr(y, label):
        h = 0.017
        _r(ML, y - h, W, h, fc=C["panel_sec"], ec="none", lw=0)
        _t(0.5, y - h / 2, label.upper(), fs=4.4, bold=True,
           color="#FFFFFF", ha="center", va="center")
        return y - h - 0.003

    def _cat(y, label):
        _t(ML, y, label, fs=3.7, bold=True, color="#555555")
        return y - 0.011

    def _row(y, draw_fn, label, dy=DY):
        yc = y - dy * 0.55
        try:
            draw_fn(yc)
        except Exception:
            pass
        _t(XT, y - 0.001, label)
        return y - dy

    # Cabecera
    _r(0, 0.987, 1, 0.013, fc=C["panel_titulo"], ec="none", lw=0)
    _t(0.5, 0.996, "SIGNOS CONVENCIONALES", fs=5.0, bold=True,
       color="#FFFFFF", ha="center")
    y = 0.984

    # Límites
    y = _hdr(y, "Limites")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#111111", 1.0), "Limite departamental")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#111111", 0.8, (0, (6, 2))), "Limite provincial")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#555555", 0.55, (0, (3, 2))), "Limite distrital")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#999999", 0.35), "Limite de manzana")
    y -= 0.003

    # Vías de comunicación
    y = _hdr(y, "Vias de comunicacion")
    y = _cat(y, "Red vial nacional")
    y = _row(y, lambda yc: (
        _l(XS, XS + SW, yc, "#FFF8E8", 5.0),
        _l(XS, XS + SW, yc, C["autopista"], 3.0),
    ), "Autopista")
    y = _row(y, lambda yc: (
        _l(XS, XS + SW, yc, "#FFF8E8", 3.8),
        _l(XS, XS + SW, yc, C["ruta_ppal"], 2.0),
    ), "Carretera asfaltada")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["ruta_sec"], 1.2), "Carretera afirmada")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["camino"], 0.9, (0, (5, 2))), "Carretera sin afirmar")
    y -= 0.002
    y = _cat(y, "Red vial departamental")
    y = _row(y, lambda yc: (
        _l(XS, XS + SW, yc, "#FFF8E8", 3.2),
        _l(XS, XS + SW, yc, C["ruta_sec"], 1.7),
    ), "Carretera asfaltada")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#AA7030", 1.0), "Carretera afirmada")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#886020", 0.75, (0, (4, 2))), "Carretera sin afirmar")
    y -= 0.002
    y = _cat(y, "Red vial vecinal / local")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#888888", 0.85), "Calle asfaltada")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, "#777777", 0.6, (0, (3, 2))), "Camino")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["sendero"], 0.42, (0, (1, 2))), "Sendero / senda")

    def _sym_ferro(yc):
        _l(XS, XS + SW, yc, C["ferroviario"], 0.8)
        for xi in np.linspace(XS + 0.018, XS + SW - 0.018, 5):
            ax.plot([xi, xi], [yc - 0.004, yc + 0.004],
                    color=C["ferroviario"], lw=0.35, transform=ax.transAxes, zorder=6)

    y = _row(y, _sym_ferro, "Via ferrea")
    y = _row(y, lambda yc: ax.plot(
        (XS + XS + SW) / 2, yc, "o", color=C["ferroviario"],
        markersize=3.0, markeredgecolor="#FFFFFF", markeredgewidth=0.45,
        transform=ax.transAxes,
    ), "Estacion ferroviaria")
    y -= 0.003

    # Hidrografía
    y = _hdr(y, "Hidrografia")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["agua_line"], 1.4), "Rio")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["arroyo"], 0.85), "Arroyo")
    y = _row(y, lambda yc: _l(XS, XS + SW, yc, C["desague"], 0.65), "Canal / acequia")
    y = _row(y, lambda yc: _r(XS, yc - 0.004, SW * 0.55, 0.008, C["agua_fill"], C["agua_line"], 0.45), "Lago / laguna")
    y -= 0.003

    # Áreas de uso
    y = _hdr(y, "Areas de uso")
    for label, fc, ec in [
        ("Zona urbana / residencial", C["ejido"], C["acento"]),
        ("Zona industrial", C["industrial"], "#6A4A8A"),
        ("Area verde / parques", C["veg_baja"], "#2E7D32"),
        ("Cementerio", C["cementerio"], "#5D4037"),
        ("Zona arqueologica", C["arqueologico"], "#8B6914"),
    ]:
        y = _row(
            y,
            lambda yc, _fc=fc, _ec=ec: _r(XS, yc - 0.004, SW * 0.52, 0.008, _fc, _ec, 0.45),
            label,
        )
    y -= 0.003

    # Puntos de interés
    y = _hdr(y, "Puntos de interes")
    poi = [
        ("*", "Institucion educativa", "#333333"),
        ("+", "Posta medica", "#CC0000"),
        ("H", "Hospital", "#CC0000"),
        ("o", "Comisaria", "#222299"),
        ("!", "Bomberos", "#CC4400"),
        ("M", "Municipalidad", "#333333"),
        ("+", "Iglesia / capilla", "#445544"),
        ("■", "Edificio publico", "#555555"),
        ("T", "Terminal de omnibus", "#333333"),
        ("Y", "Aeropuerto", "#003366"),
        ("V", "Monumento / patrimonio", "#555544"),
        ("o", "Tanque de agua", "#0066AA"),
    ]
    for sym, label, color in poi:
        ax.text(
            XS + SW * 0.3, y - 0.0056, sym,
            ha="center", va="center", fontsize=5.3, color=color,
            transform=ax.transAxes, zorder=6,
        )
        _t(XT, y - 0.001, label)
        y -= 0.0102
    y -= 0.004

    # Escala gráfica
    _t(ML, y, f"ESCALA   {escala_nombre}", fs=5.2, bold=True)
    y -= 0.016
    if escala_val <= 25000:
        km_total, n_div = 1, 4
    elif escala_val <= 50000:
        km_total, n_div = 2, 4
    elif escala_val <= 100000:
        km_total, n_div = 4, 4
    else:
        km_total, n_div = 10, 5

    bar_w = W * 0.88
    bar_h = 0.012
    dw    = bar_w / n_div
    for i in range(n_div):
        _r(ML + i * dw, y - bar_h, dw, bar_h,
           fc="#111111" if i % 2 == 0 else "#FFFFFF",
           ec="#111111", lw=0.45)
        v = i * km_total / n_div
        _t(ML + i * dw, y - bar_h - 0.003, f"{v:g}", fs=3.1)
    _t(ML + bar_w, y - bar_h - 0.003, f"{km_total:g}", fs=3.1)
    _t(ML + bar_w / 2, y - bar_h - 0.013, "km", fs=3.4, ha="center", color="#444444")
    y -= bar_h + 0.021

    # Equidistancia
    _t(ML, y, f"EQUIDISTANCIA   {int(eq_sec)} m", fs=4.0, color="#333333")
    y -= 0.014

    # Datum horizontal
    datum_h = 0.066
    _r(ML, y - datum_h, W, datum_h, fc="#F7F7F7", ec="#BBBBBB", lw=0.35)
    _t(ML + 0.02, y - 0.004, "DATUM HORIZONTAL", fs=4.0, bold=True)
    yd = y - 0.017
    for k, v in [
        ("Sistema:", "WGS 84 | POSGAR 1994"),
        ("Proyeccion:", "Gauss-Kruger"),
        (f"Faja {faja_info['numero']}:", f"EPSG:{faja_info['epsg']} | MC {faja_info['meridiano']}°"),
        ("Falso Este:", "5.500.000 m"),
        ("Falso Norte:", "0 m"),
    ]:
        _t(ML + 0.02, yd, k, fs=3.1, bold=True)
        _t(ML + 0.24, yd, v, fs=3.1)
        yd -= 0.009
    y -= datum_h + 0.008

    # Índice de hojas
    if y > 0.045:
        _t(ML, y, "INDICE DE HOJAS", fs=4.0, bold=True)
        y -= 0.015
        gw = W / 3
        gh = min(0.028, (y - 0.008) / 2)
        for ri, row_id in enumerate(["18", "19"]):
            for ci, col_id in enumerate(["L", "M", "N"]):
                bx = ML + ci * gw
                by = y - (ri + 1) * gh
                cur = (ri == 0 and ci == 1)
                _r(bx, by, gw, gh,
                   fc=C["acento"] if cur else "#FFFFFF",
                   ec="#999999", lw=0.45)
                _t(bx + gw / 2, by + gh / 2, f"{row_id}{col_id}",
                   fs=3.2, bold=cur,
                   color="#FFFFFF" if cur else "#555555",
                   ha="center", va="center")

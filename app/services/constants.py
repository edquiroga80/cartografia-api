# =============================================================================
# Constantes del sistema cartográfico — extraídas del notebook v6
# GIS Dev Academy — CartografIA API
# =============================================================================

# -- Fajas Gauss-Krüger POSGAR 1994 ------------------------------------------
FAJAS_GK = {
    1: {"epsg": 22181, "meridiano": -72, "lon_min": -73.5, "lon_max": -70.5},
    2: {"epsg": 22182, "meridiano": -69, "lon_min": -70.5, "lon_max": -67.5},
    3: {"epsg": 22183, "meridiano": -66, "lon_min": -67.5, "lon_max": -64.5},
    4: {"epsg": 22184, "meridiano": -63, "lon_min": -64.5, "lon_max": -61.5},
    5: {"epsg": 22185, "meridiano": -60, "lon_min": -61.5, "lon_max": -58.5},
    6: {"epsg": 22186, "meridiano": -57, "lon_min": -58.5, "lon_max": -55.5},
    7: {"epsg": 22187, "meridiano": -54, "lon_min": -55.5, "lon_max": -52.5},
}

# -- Parámetros por escala ----------------------------------------------------
ESCALAS = {
    "1:25.000":  {"valor": 25000,  "eq_ppal": 25,  "eq_sec": 5,   "grilla_km": 1},
    "1:50.000":  {"valor": 50000,  "eq_ppal": 50,  "eq_sec": 10,  "grilla_km": 2},
    "1:100.000": {"valor": 100000, "eq_ppal": 100, "eq_sec": 20,  "grilla_km": 4},
    "1:250.000": {"valor": 250000, "eq_ppal": 250, "eq_sec": 50,  "grilla_km": 10},
}

# -- Formatos de papel (cm, orientación apaisada) ----------------------------
FORMATOS = {
    "A4": (29.7, 21.0),
    "A3": (42.0, 29.7),
    "A2": (59.4, 42.0),
    "A1": (84.1, 59.4),
}

# -- Layout de paneles (cm fijos) --------------------------------------------
PANEL_IZQ_CM  = 7.0
PANEL_DER_CM  = 9.2
MARGEN_CM     = 0.25
SEPARADOR_CM  = 0.06

# -- Paleta de colores IGN Argentina -----------------------------------------
C = {
    "fondo":           "#F5F0E4",
    "curvas_ppal":     "#8B4513",
    "curvas_sec":      "#C48A5A",
    "agua_fill":       "#B8E4F9",
    "agua_line":       "#3AAED8",
    "arroyo":          "#67BDE1",
    "desague":         "#AADCF0",
    "veg_alta":        "#81C784",
    "veg_baja":        "#C8E6C9",
    "cultivo":         "#FFF9C4",
    "afloramiento":    "#C4A882",
    "ejido":           "#F8BBD9",
    "industrial":      "#D4C9E8",
    "cementerio":      "#C8B4A0",
    "arqueologico":    "#FFF3CD",
    "edificio":        "#CCAAAA",
    "autopista":       "#F07A16",
    "ruta_ppal":       "#E87820",
    "ruta_sec":        "#C97931",
    "calle":           "#D8D8D8",
    "camino":          "#9A7A2F",
    "sendero":         "#B49050",
    "ferroviario":     "#343434",
    "grilla":          "#3060A0",
    "grilla_tick":     "#2A4A8A",
    "borde":           "#333333",
    "panel_titulo":    "#1A1A1A",
    "panel_sec":       "#4A4A4A",
    "acento":          "#CC1100",
}

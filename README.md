# CartografIA API

Backend FastAPI para generación automática de cartas topográficas.  
Desarrollado por **GIS Dev Academy** — [gisdev.ar](https://gisdev.ar)

---

## Arquitectura

```
cartografia-api/
├── app/
│   ├── main.py                    ← FastAPI app + CORS + static files
│   ├── core/
│   │   ├── config.py              ← Settings desde .env
│   │   ├── models.py              ← Pydantic models (request/response)
│   │   └── job_store.py           ← Estado de jobs en memoria + sync Supabase
│   ├── routers/
│   │   ├── maps.py                ← Endpoints: /generate-map, /jobs/{id}, etc.
│   │   └── health.py              ← GET /health
│   └── services/
│       ├── constants.py           ← Fajas GK, escalas, colores IGN
│       ├── geo_utils.py           ← AOI, proyección, grilla (Celdas 4+7)
│       ├── data_download.py       ← OSM + DEM SRTM (Celdas 5+6)
│       ├── panel_izq.py           ← Signos convencionales (Celda 8)
│       ├── panel_der.py           ← Título e información (Celda 9)
│       ├── compositor.py          ← Pipeline principal (Celda 10)
│       └── generation_task.py     ← BackgroundTask async
├── run.py
├── requirements.txt
├── Dockerfile
├── railway.toml
└── .env.example
```

---

## Instalación local

```bash
# 1. Clonar y crear entorno
git clone <tu-repo>
cd cartografia-api
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Instalar dependencias del sistema (Ubuntu/Debian)
sudo apt-get install gdal-bin libgdal-dev libproj-dev libgeos-dev

# 3. Instalar dependencias Python
pip install GDAL==$(gdal-config --version)
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# editar .env con tus valores

# 5. Levantar el servidor
python run.py
# → API en http://localhost:8000
# → Docs en http://localhost:8000/docs
```

---

## Endpoints

### `POST /api/generate-map`
Inicia la generación. Retorna `job_id` inmediatamente.

```json
{
  "titulo": "CAMPO DE MAYO",
  "subtitulo": "PROVINCIA DE BUENOS AIRES - ARGENTINA",
  "escala": "1:50.000",
  "formato": "A3",
  "lon_min": -58.75,
  "lon_max": -58.45,
  "lat_min": -34.70,
  "lat_max": -34.45,
  "eq_ppal": 50,
  "eq_sec": 10,
  "dpi_pdf": 600,
  "dpi_png": 450,
  "export_pdf": true,
  "export_png": true,
  "capas": {
    "planimetria": true,
    "altimetria": true,
    "red_vial": true,
    "hidrografia": true,
    "vegetacion": true,
    "ferroviario": true,
    "puntos_geograficos": true
  }
}
```

Respuesta:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job en cola..."
}
```

### `GET /api/jobs/{job_id}`
Polling de estado del job.

```json
{
  "job_id": "550e8400...",
  "status": "processing",  // pending | processing | completed | error
  "progress": { "step": 2, "total": 5, "message": "Descargando datos OSM..." },
  "log": ["[1/5] Calculando encuadre...", "[2/5] Descargando datos OSM..."],
  "pdf_url": "/outputs/M01_carta_campo_de_mayo_150000_A3_20250601_143022.pdf",
  "png_url": "/outputs/M01_carta_campo_de_mayo_150000_A3_20250601_143022.png",
  "pdf_size_mb": 24.3,
  "png_size_mb": 41.7,
  "faja_numero": 5,
  "faja_epsg": 22185,
  "elapsed_sec": 87.4
}
```

### `POST /api/upload-aoi`
Subir archivo SHP/GeoJSON/ZIP para obtener el bbox.

### `GET /api/faja?lon=-58.6&lat=-34.5`
Detectar faja GK para un punto.

### `GET /outputs/{filename}`
Descarga directa de archivos generados (PDF/PNG).

---

## Deploy en Railway

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login y deploy
railway login
railway init
railway up

# 3. Configurar variables de entorno en Railway Dashboard:
#    CORS_ORIGINS, SUPABASE_URL, SUPABASE_SERVICE_KEY, LOGO_PATH
```

## Deploy en Render

1. Crear nuevo **Web Service** en render.com
2. Conectar tu repo GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python run.py`
5. Agregar variables de entorno en el dashboard

---

## Integración con Lovable

En tu app Lovable, el endpoint base es la URL pública del deploy:

```javascript
// En tu componente React
const API_BASE = "https://tu-app.railway.app"

// Iniciar generación
const res = await fetch(`${API_BASE}/api/generate-map`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(config)
})
const { job_id } = await res.json()

// Polling de estado (cada 3 segundos)
const interval = setInterval(async () => {
  const status = await fetch(`${API_BASE}/api/jobs/${job_id}`).then(r => r.json())
  if (status.status === "completed") {
    clearInterval(interval)
    window.open(`${API_BASE}${status.pdf_url}`)
  }
}, 3000)
```

---

## Notas técnicas

- **1 worker**: matplotlib no es thread-safe. Usar `workers=1` en uvicorn.
- **Jobs en memoria**: se pierden al reiniciar el proceso. Para persistencia, conectar Supabase.
- **DEM cache**: los DEMs descargados se cachean en `DEM_CACHE_DIR` por bbox.
- **Timeout**: jobs con más de `JOB_TIMEOUT_SECONDS` se cancelan automáticamente (TODO en v2).
- **Backend Agg**: necesario para matplotlib sin display. Ya configurado en Dockerfile.

---

## Escalas y formatos soportados

| Escala | Eq. directriz | Eq. intermedia | Grilla |
|--------|--------------|----------------|--------|
| 1:25.000 | 25 m | 5 m | 1 km |
| 1:50.000 | 50 m | 10 m | 2 km |
| 1:100.000 | 100 m | 20 m | 4 km |
| 1:250.000 | 250 m | 50 m | 10 km |

| Formato | Dimensiones (apaisado) |
|---------|----------------------|
| A4 | 29.7 × 21.0 cm |
| A3 | 42.0 × 29.7 cm |
| A2 | 59.4 × 42.0 cm |
| A1 | 84.1 × 59.4 cm |

---

*CartografIA API v1.0 — GIS Dev Academy 2025*

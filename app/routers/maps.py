# =============================================================================
# Router de mapas — endpoints principales
# GIS Dev Academy — CartografIA API
# =============================================================================

import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app.core.models    import MapJobRequest, MapJobResponse, MapJobResult, JobStatus
from app.core.job_store import create_job, get_job
from app.core.config    import settings
from app.services.generation_task import run_map_generation

router = APIRouter(tags=["maps"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# POST /api/generate-map — Iniciar generación
# ---------------------------------------------------------------------------

@router.post(
    "/generate-map",
    response_model=MapJobResponse,
    summary="Iniciar generación de carta topográfica",
    description="""
Recibe los parámetros de configuración, crea un job en background y
retorna inmediatamente el `job_id` para hacer polling de estado.
    """,
)
async def generate_map(req: MapJobRequest, background_tasks: BackgroundTasks):
    # Validar área del AOI
    area = (req.lon_max - req.lon_min) * (req.lat_max - req.lat_min)
    if area > settings.MAX_AOI_AREA_DEG2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El área del AOI ({area:.1f}°²) supera el límite de "
                f"{settings.MAX_AOI_AREA_DEG2}°². Reducí la extensión del área."
            ),
        )
    if area < 0.0001:
        raise HTTPException(
            status_code=400,
            detail="El área del AOI es demasiado pequeña. Verificá las coordenadas.",
        )

    job_id = req.job_id or str(uuid.uuid4())
    create_job(job_id)

    logger.info(
        f"Nuevo job {job_id[:8]} — {req.titulo} | {req.escala} | {req.formato} | "
        f"AOI ({req.lon_min:.3f},{req.lat_min:.3f}) → ({req.lon_max:.3f},{req.lat_max:.3f})"
    )

    background_tasks.add_task(run_map_generation, job_id, req)

    return MapJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Job en cola. Usá GET /api/jobs/{job_id} para seguir el progreso.",
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — Consultar estado
# ---------------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}",
    response_model=MapJobResult,
    summary="Consultar estado de un job",
)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    return job


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/download/{file_type} — Descarga directa
# ---------------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}/download/{file_type}",
    summary="Descargar PDF o PNG de una carta generada",
)
async def download_file(job_id: str, file_type: str):
    if file_type not in ("pdf", "png"):
        raise HTTPException(status_code=400, detail="file_type debe ser 'pdf' o 'png'")

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Job no completado (estado: {job.status})")

    url = job.pdf_url if file_type == "pdf" else job.png_url
    if not url:
        raise HTTPException(status_code=404, detail=f"Archivo {file_type} no disponible")

    # url es "/outputs/filename.ext" — construir path real
    filename = url.split("/")[-1]
    filepath = f"{settings.OUTPUT_DIR}/{filename}"

    import os
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    media_type = "application/pdf" if file_type == "pdf" else "image/png"
    return FileResponse(filepath, media_type=media_type, filename=filename)


# ---------------------------------------------------------------------------
# POST /api/upload-aoi — Subir archivo vectorial
# ---------------------------------------------------------------------------

@router.post(
    "/upload-aoi",
    summary="Subir archivo SHP/GeoJSON/ZIP para usar como AOI",
)
async def upload_aoi(file: UploadFile = File(...)):
    """
    Acepta .geojson, .json, .shp, .zip (con shapefile).
    Retorna el bbox en WGS84 que puede usarse en generate-map.
    """
    allowed = (".geojson", ".json", ".shp", ".zip")
    fname   = file.filename or ""
    if not any(fname.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Usar: {', '.join(allowed)}",
        )

    import os
    import tempfile
    tmp_path = os.path.join(settings.UPLOAD_DIR, fname)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        from app.services.geo_utils import aoi_desde_archivo
        gdf   = aoi_desde_archivo(tmp_path)
        bounds = gdf.total_bounds  # [xmin, ymin, xmax, ymax]
        return {
            "message":  "AOI cargado correctamente",
            "filename": fname,
            "bounds": {
                "lon_min": round(float(bounds[0]), 6),
                "lat_min": round(float(bounds[1]), 6),
                "lon_max": round(float(bounds[2]), 6),
                "lat_max": round(float(bounds[3]), 6),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error leyendo el archivo: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# GET /api/faja — Info de faja GK para un punto
# ---------------------------------------------------------------------------

@router.get(
    "/faja",
    summary="Detectar faja Gauss-Krüger para una longitud central",
)
async def get_faja(lon: float, lat: float = -34.0):
    from app.services.geo_utils import detectar_faja
    faja = detectar_faja(lon)
    return {
        "faja_numero": faja["numero"],
        "epsg":        faja["epsg"],
        "meridiano":   faja["meridiano"],
        "rango":       f"{faja['lon_min']}° a {faja['lon_max']}°",
    }

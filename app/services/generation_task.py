# =============================================================================
# Task de generación — ejecutado en background por FastAPI
# GIS Dev Academy — CartografIA API
# =============================================================================

import time
import logging
import traceback
from datetime import datetime

from app.core.models  import MapJobRequest, JobStatus
from app.core.job_store import update_job, set_progress, add_log
from app.core.config  import settings

logger = logging.getLogger(__name__)


async def run_map_generation(job_id: str, req: MapJobRequest):
    """
    Tarea asíncrona que orquesta la generación completa de la carta.
    Se lanza con BackgroundTasks de FastAPI.
    """
    start = time.time()
    update_job(job_id, status=JobStatus.PROCESSING)
    add_log(job_id, f"Inicio del job {job_id[:8]} — {datetime.now().isoformat()}")

    try:
        # Importar aquí para no bloquear el arranque del servidor
        from app.services.compositor  import generar_carta
        from app.services.geo_utils   import aoi_desde_coordenadas
        from app.core.models          import JobStatus

        # Construir AOI
        aoi_gdf = aoi_desde_coordenadas(
            req.lon_min, req.lat_min, req.lon_max, req.lat_max
        )

        def _progress(step: int, msg: str):
            set_progress(job_id, step, msg)

        # Armar config igual al notebook
        config = dict(
            job_id      = job_id,
            titulo      = req.titulo.upper(),
            subtitulo   = req.subtitulo,
            escala      = req.escala,
            formato     = req.formato,
            aoi_gdf     = aoi_gdf,
            eq_ppal     = req.eq_ppal,
            eq_sec      = req.eq_sec,
            capas       = req.capas.model_dump(),
            output_dir  = settings.OUTPUT_DIR,
            dem_cache_dir = settings.DEM_CACHE_DIR,
            logo_path   = settings.LOGO_PATH or None,
            dpi_pdf     = req.dpi_pdf,
            dpi_png     = req.dpi_png,
            export_pdf  = req.export_pdf,
            export_png  = req.export_png,
        )

        result = generar_carta(config, progress_callback=_progress)

        elapsed = round(time.time() - start, 1)

        # Construir URLs públicas
        def _url(path: str | None) -> str | None:
            if not path:
                return None
            filename = path.split("/")[-1]
            return f"/outputs/{filename}"

        update_job(
            job_id,
            status       = JobStatus.COMPLETED,
            pdf_url      = _url(result.get("pdf_path")),
            png_url      = _url(result.get("png_path")),
            pdf_size_mb  = result.get("pdf_size_mb"),
            png_size_mb  = result.get("png_size_mb"),
            faja_numero  = result.get("faja_info", {}).get("numero"),
            faja_epsg    = result.get("faja_info", {}).get("epsg"),
            elapsed_sec  = elapsed,
        )
        add_log(job_id, f"✓ Completado en {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start, 1)
        tb      = traceback.format_exc()
        logger.error(f"[{job_id[:8]}] Error en generación: {e}\n{tb}")
        update_job(
            job_id,
            status      = JobStatus.ERROR,
            error       = str(e),
            elapsed_sec = elapsed,
        )
        add_log(job_id, f"✗ Error: {e}")

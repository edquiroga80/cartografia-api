# =============================================================================
# Store de jobs en memoria + integración opcional con Supabase
# =============================================================================

import time
import logging
from typing import Dict, Optional
from app.core.models import JobStatus, ProgressStep, MapJobResult

logger = logging.getLogger(__name__)

# Store en memoria: { job_id: MapJobResult }
_jobs: Dict[str, MapJobResult] = {}


def create_job(job_id: str) -> MapJobResult:
    job = MapJobResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        progress=ProgressStep(step=0, total=5, message="En cola..."),
        log=[],
    )
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[MapJobResult]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs):
    job = _jobs.get(job_id)
    if job is None:
        return
    for k, v in kwargs.items():
        setattr(job, k, v)
    # Sincronizar con Supabase si está configurado
    _sync_supabase(job_id, job)


def add_log(job_id: str, message: str):
    job = _jobs.get(job_id)
    if job:
        job.log.append(message)
        logger.info(f"[{job_id[:8]}] {message}")


def set_progress(job_id: str, step: int, message: str):
    job = _jobs.get(job_id)
    if job:
        job.progress = ProgressStep(step=step, total=5, message=message)
        add_log(job_id, f"[{step}/5] {message}")


def _sync_supabase(job_id: str, job: MapJobResult):
    """Sincroniza el estado del job con Supabase (no bloqueante)."""
    from app.core.config import settings
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    try:
        import httpx
        payload = {
            "status": job.status,
            "progress_step": job.progress.step,
            "log_messages": job.log[-20:],  # últimos 20 mensajes
            "output_pdf_url": job.pdf_url,
            "output_png_url": job.png_url,
            "error_message": job.error,
        }
        # Fire-and-forget: no esperamos respuesta
        httpx.patch(
            f"{settings.SUPABASE_URL}/rest/v1/map_jobs?id=eq.{job_id}",
            headers={
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=5.0,
        )
    except Exception as e:
        logger.debug(f"Supabase sync error (non-critical): {e}")

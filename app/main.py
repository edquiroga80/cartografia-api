# =============================================================================
# CartografIA API — GIS Dev Academy
# Backend FastAPI para generación automática de cartas topográficas
# =============================================================================

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import maps, health
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cartografia-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.DEM_CACHE_DIR, exist_ok=True)
    logger.info("CartografIA API iniciada ✓")
    yield
    logger.info("CartografIA API detenida")


app = FastAPI(
    title="CartografIA API",
    description="Generador automático de cartografía topográfica — GIS Dev Academy",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(maps.router, prefix="/api")

# Servir archivos generados como archivos estáticos descargables
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")

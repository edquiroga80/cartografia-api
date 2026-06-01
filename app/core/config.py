# =============================================================================
# Configuración central de la aplicación
# =============================================================================

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS — en producción reemplazar con el dominio de Lovable
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.lovable.app",
        "https://*.gisdev.ar",
    ]

    # Directorios de trabajo
    OUTPUT_DIR: str = "/tmp/cartografia_outputs"
    UPLOAD_DIR: str = "/tmp/cartografia_uploads"
    DEM_CACHE_DIR: str = "/tmp/dem_cache"

    # Supabase (opcional — para reportar estado del job)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Logo institucional (ruta local en el servidor)
    LOGO_PATH: str = ""

    # Límites de generación
    MAX_AOI_AREA_DEG2: float = 25.0       # grados cuadrados máximos por AOI
    JOB_TIMEOUT_SECONDS: int = 600        # 10 min por carta
    MAX_CONCURRENT_JOBS: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

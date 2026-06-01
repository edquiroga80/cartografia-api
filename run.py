#!/usr/bin/env python
# =============================================================================
# CartografIA API — Punto de entrada
# Uso: python run.py
#      o:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# =============================================================================

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        workers=1,          # 1 worker recomendado — matplotlib no es thread-safe
        log_level="info",
    )

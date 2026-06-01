from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/", include_in_schema=False)
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "CartografIA API",
        "version": "1.0.0",
        "vendor": "GIS Dev Academy — gisdev.ar",
    }

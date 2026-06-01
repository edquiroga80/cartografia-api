# =============================================================================
# Modelos de datos — CartografIA API
# =============================================================================

from __future__ import annotations
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class EscalaEnum(str, Enum):
    e25k  = "1:25.000"
    e50k  = "1:50.000"
    e100k = "1:100.000"
    e250k = "1:250.000"


class FormatoEnum(str, Enum):
    A4 = "A4"
    A3 = "A3"
    A2 = "A2"
    A1 = "A1"


class CapasConfig(BaseModel):
    planimetria:        bool = True
    altimetria:         bool = True
    red_vial:           bool = True
    hidrografia:        bool = True
    vegetacion:         bool = True
    ferroviario:        bool = True
    puntos_geograficos: bool = True


class MapJobRequest(BaseModel):
    """Cuerpo del POST /api/generate-map"""

    # Identificador de job (generado por el cliente o el servidor)
    job_id: Optional[str] = None

    # Metadatos de la carta
    titulo:    str = Field(..., min_length=1, max_length=60,  description="Nombre principal del área cartografiada")
    subtitulo: str = Field("",  max_length=100, description="Provincia, país, etc.")

    # Escala y formato
    escala:  EscalaEnum  = EscalaEnum.e50k
    formato: FormatoEnum = FormatoEnum.A3

    # Área de interés (WGS84, negativos = S/O)
    lon_min: float = Field(..., ge=-74.0, le=-52.0)
    lon_max: float = Field(..., ge=-74.0, le=-52.0)
    lat_min: float = Field(..., ge=-56.0, le=-20.0)
    lat_max: float = Field(..., ge=-56.0, le=-20.0)

    # Curvas de nivel (None = automático según escala)
    eq_ppal: Optional[float] = Field(None, gt=0, description="Equidistancia directriz en metros")
    eq_sec:  Optional[float] = Field(None, gt=0, description="Equidistancia intermedia en metros")

    # Capas
    capas: CapasConfig = Field(default_factory=CapasConfig)

    # Exportación
    dpi_pdf:     int  = Field(600, ge=150, le=1200)
    dpi_png:     int  = Field(450, ge=150, le=600)
    export_pdf:  bool = True
    export_png:  bool = True

    @field_validator("lon_max")
    @classmethod
    def lon_max_gt_min(cls, v, info):
        if "lon_min" in info.data and v <= info.data["lon_min"]:
            raise ValueError("lon_max debe ser mayor que lon_min")
        return v

    @field_validator("lat_max")
    @classmethod
    def lat_max_gt_min(cls, v, info):
        if "lat_min" in info.data and v <= info.data["lat_min"]:
            raise ValueError("lat_max debe ser mayor que lat_min")
        return v


class JobStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    ERROR      = "error"


class ProgressStep(BaseModel):
    step:    int
    total:   int
    message: str


class MapJobResponse(BaseModel):
    """Respuesta del POST /api/generate-map (inicio de job)"""
    job_id:  str
    status:  JobStatus
    message: str


class MapJobResult(BaseModel):
    """Respuesta del GET /api/jobs/{job_id}"""
    job_id:      str
    status:      JobStatus
    progress:    ProgressStep
    log:         List[str] = []
    pdf_url:     Optional[str] = None
    png_url:     Optional[str] = None
    pdf_size_mb: Optional[float] = None
    png_size_mb: Optional[float] = None
    error:       Optional[str] = None
    faja_numero: Optional[int] = None
    faja_epsg:   Optional[int] = None
    elapsed_sec: Optional[float] = None

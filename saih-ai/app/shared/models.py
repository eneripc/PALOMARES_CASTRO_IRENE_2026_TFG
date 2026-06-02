# app/models.py
# Modelos de request/response de la API FBL1N


from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# =========================
# REQUEST MODELS
# =========================

class Outputs(BaseModel):
    """Flags de salida del pipeline"""
    excel: bool = True


class Analitica(BaseModel):
    """Flags de analítica a aplicar"""
    casuistica: bool = True
    anticipos: bool = True
    generar_solicitudes: bool = True


class Fbl1nRequest(BaseModel):
    """Request principal para iniciar el job FBL1N"""

    fecha_low: str = Field(..., description="Fecha inicial del análisis (YYYY-MM-DD)")
    fecha_high: str = Field(..., description="Fecha final del análisis (YYYY-MM-DD)")

    sociedades: Optional[List[str]] = None
    hotel: Optional[str] = None

    variante: str = "PAG_MASTER"
    clase: str = "K"
    status: str = "ABIERTO"

    outputs: Outputs = Field(default_factory=Outputs)
    analitica: Analitica = Field(default_factory=Analitica)


# =========================
# JOB RESPONSES
# =========================

class StartJobResponse(BaseModel):
    jobId: str
    statusUrl: str


class JobStatusResponse(BaseModel):
    jobId: str
    state: Literal["queued", "running", "succeeded", "failed"]
    progress: int = 0
    step: Optional[str] = None
    error: Optional[str] = None


# =========================
# RESULT MODELS
# =========================

class ResultSummary(BaseModel):
    proveedores_con_solicitud: int = 0
    proveedores_cxp: int = 0
    proveedores_anticipos: int = 0
    partidas_con_incidencia: int = 0
    anticipos_rows: int = 0


class SupplierRequestItem(BaseModel):
    fecha_clave: Optional[str] = None
    sociedad: Optional[str] = None
    cuenta: Optional[str] = None
    nombre1: Optional[str] = None

    tipo_origen: List[str] = Field(default_factory=list)
    saldo_total: Optional[float] = None
    moneda: Optional[str] = None

    solicitud: Optional[str] = None
    incidencias_detectadas: List[str] = Field(default_factory=list)
    conceptos_relacionados: List[str] = Field(default_factory=list)
    n_partidas_relacionadas: int = 0


class LineItemResult(BaseModel):
    fecha_clave: Optional[str] = None
    sociedad: Optional[str] = None
    cuenta: Optional[str] = None
    nombre1: Optional[str] = None

    n_doc: Optional[str] = None
    clase: Optional[str] = None
    texto: Optional[str] = None

    importe_ml: Optional[float] = None
    ml: Optional[str] = None
    antiguedad: Optional[float] = None
    demora: Optional[float] = None

    categoria: Optional[str] = None  # "cxp" o "anticipos"
    casuistica: Optional[str] = None
    etiqueta: Optional[str] = None
    analisis: Optional[str] = None
    solicitud: Optional[str] = None


class ReportFile(BaseModel):
    type: str
    name: str
    url: str


class JobResultResponse(BaseModel):
    jobId: str
    state: Literal["succeeded"]
    summary: ResultSummary
    supplier_requests: List[SupplierRequestItem] = Field(default_factory=list)
    line_items: List[LineItemResult] = Field(default_factory=list)
    files: List[ReportFile] = Field(default_factory=list)
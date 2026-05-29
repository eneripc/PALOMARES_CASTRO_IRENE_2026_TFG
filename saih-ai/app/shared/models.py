# app/models.py
# Modelos de request/response de la API FBL1N

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Outputs(BaseModel):
    """
    Flags de salida del pipeline.
    """
    csv: bool = True
    excel: bool = True


class Analitica(BaseModel):
    """
    Flags de analítica a aplicar.
    """
    casuistica: bool = True
    anticipos: bool = True
    generar_solicitudes: bool = True


class Delivery(BaseModel):
    """
    Parámetros de entrega de artefactos.
    En la arquitectura actual, el backend por defecto es Azure Blob Storage.
    """
    store: Literal["blob", "sharepoint"] = "blob"

    # SharePoint
    siteUrl: Optional[str] = None
    library: Optional[str] = None
    folder: Optional[str] = None

    # Blob
    container: Optional[str] = None
    prefix: Optional[str] = None


class Fbl1nRequest(BaseModel):
    """
    Request principal para iniciar el job.
    """
    fecha_low: str = Field(..., description="YYYY-MM-DD")
    fecha_high: str = Field(..., description="YYYY-MM-DD")

    sociedades: Optional[List[str]] = None
    hotel: Optional[str] = Field(
        default=None,
        description="Nombre hotel/UE, p.ej. 'Maya'",
    )

    variante: str = "PAG_MASTER"
    clase: str = "K"
    status: str = "ABIERTO"

    outputs: Outputs = Field(default_factory=Outputs)
    analitica: Analitica = Field(default_factory=Analitica)
    delivery: Delivery = Field(default_factory=Delivery)


class StartJobResponse(BaseModel):
    """
    Respuesta del endpoint que inicia el job.
    """
    jobId: str
    statusUrl: str
    message: str = "Job started"


class JobStatusResponse(BaseModel):
    """
    Respuesta del endpoint de estado del job.
    """
    jobId: str
    state: Literal["queued", "running", "succeeded", "failed"]
    progress: int = 0
    step: Optional[str] = None
    error: Optional[str] = None


class JobResultFile(BaseModel):
    """
    Metadatos de un archivo generado.
    """
    type: Literal["excel", "csv", "zip"]
    name: str
    url: str


class JobResultResponse(BaseModel):
    """
    Respuesta del endpoint de resultado final.
    """
    jobId: str
    state: Literal["succeeded"]
    summary: Dict[str, Any]
    files: List[JobResultFile]
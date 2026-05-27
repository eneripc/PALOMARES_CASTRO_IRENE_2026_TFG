from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class Outputs(BaseModel):
    csv: bool = True
    excel: bool = True

class Analitica(BaseModel):
    casuistica: bool = True
    anticipos: bool = True
    generar_solicitudes: bool = True

class Delivery(BaseModel):
    store: Literal["local", "blob", "sharepoint"] = "local"
    # sharepoint
    siteUrl: Optional[str] = None
    library: Optional[str] = None
    folder: Optional[str] = None
    # blob
    container: Optional[str] = None
    prefix: Optional[str] = None

class Fbl1nRequest(BaseModel):
    fecha_low: str = Field(..., description="YYYY-MM-DD")
    fecha_high: str = Field(..., description="YYYY-MM-DD")
    sociedades: Optional[List[str]] = None
    hotel: Optional[str] = Field(None, description="Nombre hotel/UE, p.ej. 'Maya'")
    variante: str = "PAG_MASTER"
    clase: str = "K"
    status: str = "ABIERTO"

    outputs: Outputs = Outputs()
    analitica: Analitica = Analitica()
    delivery: Delivery = Delivery()

class StartJobResponse(BaseModel):
    jobId: str
    statusUrl: str
    message: str = "Job started"

class JobStatusResponse(BaseModel):
    jobId: str
    state: Literal["queued", "running", "succeeded", "failed"]
    progress: int = 0
    step: Optional[str] = None
    error: Optional[str] = None

class JobResultFile(BaseModel):
    type: Literal["excel", "csv", "zip"]
    name: str
    url: str

class JobResultResponse(BaseModel):
    jobId: str
    state: Literal["succeeded"]
    summary: Dict[str, Any]
    files: List[JobResultFile]

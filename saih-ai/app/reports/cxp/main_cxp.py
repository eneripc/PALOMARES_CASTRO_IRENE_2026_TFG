# app/reports/main_cxp.py
# API principal para lanzar y consultar análisis FBL1N

import json
import os
import tempfile
import uuid
import pandas as pd

from fastapi import BackgroundTasks, HTTPException, APIRouter
#from fastapi.security.api_key import APIKeyHeader

from app.core.auth import require_api_key

from app.shared.jobs import create_job, fail_job, get_job, update_job
from app.shared.models import (
    Fbl1nRequest,
    JobResultResponse,
    JobStatusResponse,
    StartJobResponse,
)
from .pipeline_cxp import build_fbl1n_fact, generate_excel, run_analitica, build_supplier_requests, build_line_items
from app.infraestructure.storage import generate_blob_sas_url, upload_file_to_blob


router = APIRouter(prefix="/v1/reports/cxp", tags=["CXP"])

#api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def _summarize(
    supplier_requests: list[dict] | None,
    line_items: list[dict] | None,
    df_ant: pd.DataFrame | None = None,
) -> dict:
    supplier_requests = supplier_requests or []
    line_items = line_items or []

    proveedores_con_solicitud = len({
        (r.get("fecha_clave"), r.get("sociedad"), r.get("cuenta"))
        for r in supplier_requests
    })

    proveedores_cxp = len({
        (r.get("fecha_clave"), r.get("sociedad"), r.get("cuenta"))
        for r in supplier_requests
        if "cxp" in (r.get("tipo_origen") or [])
    })

    proveedores_anticipos = len({
        (r.get("fecha_clave"), r.get("sociedad"), r.get("cuenta"))
        for r in supplier_requests
        if "anticipos" in (r.get("tipo_origen") or [])
    })

    summary = {
        "proveedores_con_solicitud": proveedores_con_solicitud,
        "proveedores_cxp": proveedores_cxp,
        "proveedores_anticipos": proveedores_anticipos,
        "partidas_con_incidencia": len(line_items),
        "anticipos_rows": int(len(df_ant)) if df_ant is not None else 0,
    }

    return summary


def run_job(job_id: str, req: Fbl1nRequest) -> None:
    """
    Ejecuta el pipeline completo en segundo plano:
    - extracción SAP
    - analítica
    - generación opcional de Excel
    - subida del fichero a Azure Blob Storage
    - persistencia del resultado final en Azure SQL
    """
    try:
        update_job(
            job_id,
            state="running",
            progress=5,
            step="Llamando SAP / construyendo DataFrame",
        )

        df_fact = build_fbl1n_fact(req)

        update_job(
            job_id,
            progress=55,
            step="Aplicando analítica (casuística/anticipos)",
        )

        df_proc, df_cas, df_ant = run_analitica(df_fact, req)

        files = []

        if req.outputs.excel:
            update_job(job_id, progress=80, step="Generando Excel")

            temp_dir = tempfile.gettempdir()
            xlsx_path = generate_excel(df_fact, req, temp_dir)

            blob_name = f"reports/{job_id}/{os.path.basename(xlsx_path)}"
            upload_file_to_blob(xlsx_path, blob_name)

            file_url = generate_blob_sas_url(blob_name, expiry_minutes=60)

            files.append(
                {
                    "type": "excel",
                    "name": os.path.basename(xlsx_path),
                    "url": file_url,
                }
            )

            try:
                os.remove(xlsx_path)
            except OSError:
                pass

        line_items = build_line_items(df_cas, df_ant)
        supplier_requests = build_supplier_requests(df_cas, df_ant)

        result_payload = {
            "jobId": job_id,
            "state": "succeeded",
            "summary": _summarize(
                supplier_requests=supplier_requests,
                line_items=line_items,
                df_ant=df_ant,
            ),
            "supplier_requests": supplier_requests,
            "line_items": line_items,
            "files": files,
        }

        update_job(
            job_id,
            state="succeeded",
            progress=100,
            step="Finalizado",
            result_json=json.dumps(
                result_payload,
                ensure_ascii=False,
                default=str
            ),
        )

    except Exception as e:
        fail_job(job_id, e)

@router.post(
    "/fbl1n",
    response_model=StartJobResponse,
    status_code=202,
    summary="Inicia análisis FBL1N y generación de informe de auditoría",
    description=(
        "Inicia un proceso asíncrono que ejecuta un análisis completo de datos SAP FBL1N "
        "(cuentas a pagar - proveedores).\n\n"
        "Este endpoint debe utilizarse cuando el usuario solicita:\n"
        "- Analizar extractos FBL1N\n"
        "- Revisar saldos de proveedores\n"
        "- Identificar incidencias en cuentas a pagar\n"
        "- Generar informes de auditoría financiera\n\n"
        "El proceso incluye:\n"
        "1. Extracción de datos desde SAP (servicio SOAP FBL1N)\n"
        "2. Normalización y estandarización de columnas\n"
        "3. Aplicación de analítica:\n"
        "   - Casuística de saldos (deudor, acreedor, antiguo)\n"
        "   - Detección de incidencias (Z6, compensaciones, partidas antiguas)\n"
        "   - Análisis de anticipos y retenciones\n"
        "   - Generación de solicitudes de auditoría por proveedor\n"
        "4. Generación opcional de archivo Excel\n\n"
        "IMPORTANTE:\n"
        "- Este endpoint NO devuelve el resultado final directamente.\n"
        "- Devuelve un jobId que debe usarse para consultar el progreso.\n"
        "- A continuación se debe llamar al endpoint de estado (status).\n\n"
        "Sinónimos: FBL1N, análisis de proveedores, cuentas a pagar, AP, auditoría, reporte financiero."
    ),
    #dependencies=[Depends(require_api_key)]

)
def start_fbl1n(req: Fbl1nRequest, bg: BackgroundTasks):
    """
    Inicia el job asíncrono y devuelve el jobId.
    """
    job_id = str(uuid.uuid4())
    create_job(job_id, req.model_dump())
    bg.add_task(run_job, job_id, req)

    return StartJobResponse(
        jobId=job_id,
        statusUrl=f"/v1/reports/jobs/{job_id}",
    )

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Consultar estado de un análisis FBL1N",
    description=(
        "Devuelve el estado actual de un proceso de análisis FBL1N iniciado previamente.\n\n"
        "Este endpoint debe utilizarse después de iniciar un job para:\n"
        "- Consultar progreso del análisis\n"
        "- Verificar si el procesamiento ha finalizado\n"
        "- Detectar errores en la ejecución\n\n"
        "Estados posibles:\n"
        "- queued: en cola\n"
        "- running: en ejecución\n"
        "- succeeded: completado correctamente\n"
        "- failed: error en el procesamiento\n\n"
        "Flujo recomendado:\n"
        "1. Llamar a POST /v1/reports/fbl1n\n"
        "2. Consultar este endpoint periódicamente\n"
        "3. Cuando state = 'succeeded', llamar al endpoint de resultado\n\n"
        "Este endpoint no devuelve resultados finales ni archivos."
    ),
    #dependencies=[Depends(require_api_key)]
)

def status(job_id: str):
    """
    Devuelve el estado actual del job.
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        jobId=job["jobId"],
        state=job["state"],
        progress=job["progress"] or 0,
        step=job["step"],
        error=job["error"],
    )

@router.get(
    "/jobs/{job_id}/result",
    response_model=JobResultResponse,
    summary="Obtener resultado final del análisis FBL1N",
    description=(
        "Devuelve el resultado final de un análisis FBL1N previamente ejecutado.\n\n"
        "Este endpoint debe utilizarse SOLO cuando el estado del job sea 'succeeded'.\n\n"
        "Incluye:\n"
        "- Resumen de resultados:\n"
        "  - Número de proveedores con solicitud de auditoría\n"
        "  - Número de registros de anticipos\n"
        "- Archivos generados:\n"
        "  - Excel con análisis completo\n"
        "  - Otros formatos si están habilitados\n\n"
        "Cada archivo incluye una URL de descarga.\n\n"
        "Errores comunes:\n"
        "- Si el job no ha finalizado → devolverá error 409\n"
        "- Si el job no existe → devolverá error 404\n\n"
        "Flujo correcto:\n"
        "1. Iniciar análisis (POST)\n"
        "2. Esperar a estado 'succeeded' (GET status)\n"
        "3. Obtener resultado (este endpoint)\n\n"
        "Sinónimos: resultado análisis, informe final, reporte FBL1N, output auditoría."
    ),
    #dependencies=[Depends(require_api_key)]
)
def result(job_id: str):
    """
    Devuelve el resultado final del job si ya ha finalizado correctamente.
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["state"] != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed: {job['state']}",
        )

    return job["result"]
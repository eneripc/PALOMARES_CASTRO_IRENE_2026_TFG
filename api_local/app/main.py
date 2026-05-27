import uuid
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models import Fbl1nRequest, StartJobResponse, JobStatusResponse, JobResultResponse
from .jobs import init_db, create_job, update_job, get_job, fail_job
from .pipeline import build_fbl1n_fact, run_analitica, generate_excel
from .storage import ensure_dir, local_file_url

app = FastAPI(title="FBL1N Reporting API", version="1.0.0")

@app.on_event("startup")
def _startup():
    init_db()
    ensure_dir(settings.OUT_DIR)

# Servir ficheros locales (MVP)
app.mount("/files", StaticFiles(directory=settings.OUT_DIR), name="files")

def _summarize(df_cas, df_ant):
    summary = {}
    if df_cas is not None and "Solicitud" in df_cas.columns:
        summary["proveedores_con_solicitud"] = int(df_cas["Solicitud"].notna().sum())
    if df_ant is not None:
        summary["anticipos_rows"] = int(len(df_ant))
    return summary

def run_job(job_id: str, req: Fbl1nRequest, request_base: str):
    try:
        update_job(job_id, state="running", progress=5, step="Llamando SAP / construyendo DataFrame")

        df_fact = build_fbl1n_fact(req)
        update_job(job_id, progress=55, step="Aplicando analítica (casuística/anticipos)")

        df_proc, df_cas, df_ant = run_analitica(df_fact, req)

        files = []
        if req.outputs.excel:
            update_job(job_id, progress=80, step="Generando Excel")
            xlsx_path = generate_excel(df_fact, req, settings.OUT_DIR)

            # construir URL pública (MVP local)
            # request_base es base_url del request original
            rel = os.path.relpath(xlsx_path, settings.OUT_DIR).replace("\\", "/")
            url = request_base.rstrip("/") + f"/files/{rel}"
            files.append({"type": "excel", "name": os.path.basename(xlsx_path), "url": url})

        update_job(
            job_id,
            state="succeeded",
            progress=100,
            step="Finalizado",
            result_json=__import__("json").dumps({
                "jobId": job_id,
                "state": "succeeded",
                "summary": _summarize(df_cas, df_ant),
                "files": files
            }, ensure_ascii=False)
        )
    except Exception as e:
        fail_job(job_id, e)

@app.post("/v1/reports/fbl1n", response_model=StartJobResponse, status_code=202)
def start_fbl1n(req: Fbl1nRequest, bg: BackgroundTasks, request: Request):
    job_id = str(uuid.uuid4())
    create_job(job_id, req.model_dump())

    # Pasamos base_url para crear URLs de descarga
    base = str(request.base_url)

    bg.add_task(run_job, job_id, req, base)

    return StartJobResponse(jobId=job_id, statusUrl=f"/v1/reports/jobs/{job_id}")

@app.get("/v1/reports/jobs/{job_id}", response_model=JobStatusResponse)
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(
        jobId=job["jobId"],
        state=job["state"],
        progress=job["progress"] or 0,
        step=job["step"],
        error=job["error"]
    )

@app.get("/v1/reports/jobs/{job_id}/result", response_model=JobResultResponse)
def result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["state"] != "succeeded":
        raise HTTPException(409, f"Job not completed: {job['state']}")
    return job["result"]

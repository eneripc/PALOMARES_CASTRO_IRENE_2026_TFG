# app/main.py
from fastapi import FastAPI
import pandas as pd

from app.shared.jobs import init_db
from app.infraestructure.storage import ensure_container_exists

from app.reports.cxp.main_cxp import router as cxp_router

app = FastAPI(
    title="AI Audit API",
    version="1.0.0"
)

# Startup global
@app.on_event("startup")
def startup():
    init_db()
    ensure_container_exists()

# Registrar routers
app.include_router(cxp_router)
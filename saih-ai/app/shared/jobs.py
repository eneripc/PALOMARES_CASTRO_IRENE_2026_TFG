
# app/jobs.py
# Persistencia de jobs asíncronos en Azure SQL Database

import json
import traceback
from typing import Any, Dict, Optional

import pyodbc

from app.core.config import settings


def _connection_string() -> str:
    """
    Construye la cadena de conexión para Azure SQL Database.
    Requiere tener instalado el driver ODBC correspondiente en el entorno.
    """
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={settings.AZURE_SQL_SERVER};"
        f"DATABASE={settings.AZURE_SQL_DATABASE};"
        f"UID={settings.AZURE_SQL_USERNAME};"
        f"PWD={settings.AZURE_SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def _conn() -> pyodbc.Connection:
    """
    Abre una conexión nueva a Azure SQL Database.
    """
    return pyodbc.connect(_connection_string())


def init_db() -> None:
    """
    Inicializa la tabla de jobs si no existe.
    """
    sql = """
    IF NOT EXISTS (
        SELECT 1
        FROM sys.tables
        WHERE name = 'jobs'
    )
    BEGIN
        CREATE TABLE jobs (
            job_id NVARCHAR(100) PRIMARY KEY,
            state NVARCHAR(30) NOT NULL,
            progress INT NOT NULL DEFAULT 0,
            step NVARCHAR(255) NULL,
            error NVARCHAR(MAX) NULL,
            result_json NVARCHAR(MAX) NULL,
            req_json NVARCHAR(MAX) NULL,
            created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
            updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
        );
    END
    """
    with _conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()


def create_job(job_id: str, req: Dict[str, Any]) -> None:
    """
    Inserta un job nuevo con estado inicial 'queued'.
    """
    sql = """
    INSERT INTO jobs (
        job_id,
        state,
        progress,
        step,
        error,
        result_json,
        req_json,
        created_at,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME())
    """
    with _conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            sql,
            (
                job_id,
                "queued",
                0,
                None,
                None,
                None,
                json.dumps(req, ensure_ascii=False),
            ),
        )
        conn.commit()


def update_job(job_id: str, **fields: Any) -> None:
    """
    Actualiza uno o varios campos del job.
    """
    if not fields:
        return

    assignments = []
    values = []

    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        values.append(value)

    assignments.append("updated_at = SYSUTCDATETIME()")
    values.append(job_id)

    sql = f"""
    UPDATE jobs
    SET {", ".join(assignments)}
    WHERE job_id = ?
    """

    with _conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Recupera un job y lo devuelve como diccionario estructurado.
    """
    sql = """
    SELECT
        job_id,
        state,
        progress,
        step,
        error,
        result_json,
        req_json
    FROM jobs
    WHERE job_id = ?
    """

    with _conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (job_id,))
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "jobId": row[0],
        "state": row[1],
        "progress": int(row[2]) if row[2] is not None else 0,
        "step": row[3],
        "error": row[4],
        "result": json.loads(row[5]) if row[5] else None,
        "req": json.loads(row[6]) if row[6] else None,
    }


def fail_job(job_id: str, e: Exception) -> None:
    """
    Marca el job como fallido y guarda el detalle del error + traceback.
    """
    update_job(
        job_id,
        state="failed",
        step="Error",
        error=f"{str(e)}\n{traceback.format_exc()}",
    )
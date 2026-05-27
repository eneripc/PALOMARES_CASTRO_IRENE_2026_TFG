import sqlite3
import json
import traceback
from typing import Any, Dict, Optional
from .config import settings

def _conn():
    return sqlite3.connect(settings.JOB_DB, check_same_thread=False)

def init_db():
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            state TEXT,
            progress INTEGER,
            step TEXT,
            error TEXT,
            result_json TEXT,
            req_json TEXT
        )
        """)
        c.commit()

def create_job(job_id: str, req: Dict[str, Any]):
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs(job_id,state,progress,step,error,result_json,req_json) VALUES(?,?,?,?,?,?,?)",
            (job_id, "queued", 0, None, None, None, json.dumps(req, ensure_ascii=False))
        )
        c.commit()

def update_job(job_id: str, **fields):
    keys = []
    vals = []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(job_id)
    sql = f"UPDATE jobs SET {', '.join(keys)} WHERE job_id=?"
    with _conn() as c:
        c.execute(sql, vals)
        c.commit()

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        cur = c.execute("SELECT job_id,state,progress,step,error,result_json,req_json FROM jobs WHERE job_id=?", (job_id,))
        row = cur.fetchone()
    if not row:
        return None
    return {
        "jobId": row[0],
        "state": row[1],
        "progress": row[2],
        "step": row[3],
        "error": row[4],
        "result": json.loads(row[5]) if row[5] else None,
        "req": json.loads(row[6]) if row[6] else None
    }

def fail_job(job_id: str, e: Exception):
    update_job(job_id, state="failed", error=f"{e}\n{traceback.format_exc()}", step="Error")

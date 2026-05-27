import os
from fastapi import Request

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def local_file_url(request: Request, file_path: str, base_dir: str) -> str:
    # file_path debe estar dentro de base_dir
    rel = os.path.relpath(file_path, base_dir).replace("\\", "/")
    return str(request.base_url).rstrip("/") + f"/files/{rel}"

# app/auth.py
# Módulo de autenticación/autorización simple por API Key

from fastapi import Header, HTTPException, status, Request
from .config import settings

def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
):
    """  expected_api_key = settings.API_KEY

    
    if expected_api_key and x_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )"""
    pass
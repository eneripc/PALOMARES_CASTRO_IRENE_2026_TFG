# app/storage.py
# Utilidades de almacenamiento en Azure Blob Storage

import mimetypes
import os
from datetime import datetime, timedelta, timezone

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from app.core.config import settings


def _get_blob_service_client() -> BlobServiceClient:
    """
    Devuelve un cliente de Azure Blob Storage.
    Usa AZURE_STORAGE_CONNECTION_STRING si está configurado.
    """
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise ValueError(
            "AZURE_STORAGE_CONNECTION_STRING no está configurado. "
            "Configúrala en .env o implementa autenticación con Managed Identity."
        )

    return BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    )


def ensure_container_exists() -> None:
    """
    Crea el contenedor si no existe.
    """
    service_client = _get_blob_service_client()
    container_client = service_client.get_container_client(settings.AZURE_BLOB_CONTAINER)

    try:
        container_client.create_container()
    except Exception:
        # Si ya existe, no pasa nada.
        pass


def upload_file_to_blob(local_path: str, blob_name: str) -> str:
    """
    Sube un archivo local a Azure Blob Storage y devuelve su URL base.
    """
    service_client = _get_blob_service_client()
    blob_client = service_client.get_blob_client(
        container=settings.AZURE_BLOB_CONTAINER,
        blob=blob_name,
    )

    content_type, _ = mimetypes.guess_type(local_path)
    if content_type is None:
        content_type = "application/octet-stream"

    with open(local_path, "rb") as data:
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    return blob_client.url


def get_blob_url(blob_name: str) -> str:
    """
    Devuelve la URL base del blob (sin SAS).
    """
    account = settings.AZURE_STORAGE_ACCOUNT
    container = settings.AZURE_BLOB_CONTAINER
    return f"https://{account}.blob.core.windows.net/{container}/{blob_name}"


def generate_blob_sas_url(blob_name: str, expiry_minutes: int = 60) -> str:
    """
    Genera una URL SAS temporal de solo lectura para un blob.
    """
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise ValueError(
            "AZURE_STORAGE_CONNECTION_STRING no está configurado. "
            "No se puede generar SAS sin credenciales de cuenta."
        )

    service_client = _get_blob_service_client()
    credential = service_client.credential

    if not hasattr(credential, "account_key") or not credential.account_key:
        raise ValueError(
            "No se ha podido obtener account_key desde la connection string. "
            "Para generar SAS necesitas una clave de cuenta válida."
        )

    sas_token = generate_blob_sas(
        account_name=settings.AZURE_STORAGE_ACCOUNT,
        container_name=settings.AZURE_BLOB_CONTAINER,
        blob_name=blob_name,
        account_key=credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
    )

    return f"{get_blob_url(blob_name)}?{sas_token}"
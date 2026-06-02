# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SAP SOAP
    SAP_URL: str
    SAP_USER: str
    SAP_PASSWORD: str
    SAP_VERIFY_SSL: bool = False

    # Azure SQL Database
    AZURE_SQL_SERVER: str
    AZURE_SQL_DATABASE: str
    AZURE_SQL_USERNAME: str
    AZURE_SQL_PASSWORD: str

    # Azure Blob Storage
    AZURE_STORAGE_ACCOUNT: str
    AZURE_BLOB_CONTAINER: str
    AZURE_STORAGE_CONNECTION_STRING: str | None = None

    # Seguridad simple temporal
    API_KEY: str | None = None


settings = Settings()
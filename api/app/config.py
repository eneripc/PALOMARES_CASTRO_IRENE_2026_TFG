from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SAP SOAP
    SAP_URL: str
    SAP_USER: str
    SAP_PASSWORD: str
    SAP_VERIFY_SSL: bool = False

    # Local storage
    OUT_DIR: str = "./out"

    # Job DB
    JOB_DB: str = "./jobs.sqlite"

settings = Settings()

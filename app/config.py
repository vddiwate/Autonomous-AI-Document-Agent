import os
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Application settings loaded directly from .env.
    No model names or API settings are hardcoded.
    """
    # Server Settings
    APP_NAME: str = Field(default="Fluid AI - Autonomous Document Agent")
    APP_VERSION: str = Field(default="1.0.0")
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # LLM Settings (loaded strictly from .env)
    GROQ_API_KEY: str = Field(...)
    MODEL_NAME: str = Field(...)
    FALLBACK_MODEL_NAME: str = Field(...)
    LLM_TEMPERATURE: float = Field(default=0.0)
    LLM_MAX_TOKENS: int = Field(default=800)
    LLM_REQUEST_TIMEOUT: float = Field(default=60.0)
    LLM_MAX_RETRIES: int = Field(default=3)

    # Storage Settings
    DOCS_STORAGE_DIR: str = Field(default="storage/generated_docs")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GROQ_API_KEY is required in .env")
        return v.strip()

    @property
    def absolute_storage_dir(self) -> Path:
        path = Path(self.DOCS_STORAGE_DIR)
        return path if path.is_absolute() else (BASE_DIR / path)

# Safe settings initialization with try-except
try:
    settings = Settings()
    os.makedirs(settings.absolute_storage_dir, exist_ok=True)
except Exception as e:
    raise RuntimeError(f"Config Error: Unable to load settings from .env -> {e}")

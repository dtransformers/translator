from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    HOST: str
    PORT: int
    
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    DUCKLING_URL: str 

    # LLM Settings
    LLM_PROVIDER: str 
    GEMINI_API_KEY: str 
    OLLAMA_BASE_URL: str 
    LLM_MODEL_NAME: str 

    # Authentication
    API_USERNAME: str
    API_PASSWORD: str 

    COMPLEXITY_THRESHOLD: int = 50

    # S3 / MinIO
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION_NAME: str | None = None
    S3_ENDPOINT_URL: str | None = None

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

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
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL_NAME: str 

    # Authentication
    API_USERNAME: str
    API_PASSWORD: str 

    # Calibrated on the rebuilt score: simple UI/marketing copy lands at 9-25, dense legal/jargon at 29-45
    COMPLEXITY_THRESHOLD: int = 28
    # Scores within this distance of the threshold are averaged with an LLM complexity rating
    COMPLEXITY_LLM_WINDOW: int = 8
    TRUST_SCORE_THRESHOLD: float = 0.85
    SEMANTIC_CACHE_MAX_DISTANCE: float = 0.02

    # Readiness monitor
    READINESS_CHECK_INTERVAL: int = 20
    READINESS_CHECK_TIMEOUT: float = 5.0

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

from pydantic_settings import BaseSettings
from pydantic_settings.main import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # Encryption (for API keys stored in DB)
    fernet_key: str

    # FBS Fubon Neo
    fbs_account: str = ""
    fbs_password: str = ""
    fbs_cert_path: str = ""

    # AI
    gemini_api_key: str = ""
    gemini_embedding_model: str = "models/text-embedding-004"
    gemini_chat_model: str = "gemini-2.0-flash"
    ai_max_debate_rounds: int = 1          # Bull/Bear exchange rounds (1 = Bull→Bear→done)
    store_similarity_threshold: float = 0.75
    store_max_results: int = 10
    store_max_per_symbol: int = 100
    checkpoint_ttl_days: int = 7

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

settings: Settings = get_settings()

from pydantic_settings.main import SettingsConfigDict


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
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

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aichat:aichat@localhost:5433/aichat"
    jwt_secret: str = "dev-secret-change-me-please-32-bytes!!"
    session_ttl_hours: int = 12
    admin_username: str = "admin"
    admin_password: str = "admin123"
    cors_origins: list[str] = ["http://localhost:3002"]
    upload_dir: str = "uploads"
    max_message_length: int = 5000
    max_avatar_bytes: int = 2 * 1024 * 1024


settings = Settings()

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
    # Attachments: 0 = no size limit. Files go to Cloudflare R2 when all four R2 settings are set,
    # otherwise to <upload_dir>/attachments on disk.
    max_attachment_mb: int = 0
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    @property
    def r2_enabled(self) -> bool:
        return all((self.r2_account_id, self.r2_access_key_id, self.r2_secret_access_key, self.r2_bucket))
    # MCP endpoint (/mcp) protection against DNS rebinding: Host / Origin values allowed to call it.
    # Add your server's hostname (e.g. "myserver:8002") to accept remote AIs, or ["*"] to allow any.
    mcp_allowed_hosts: list[str] = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    mcp_allowed_origins: list[str] = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


settings = Settings()

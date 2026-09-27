from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_drive_credentials_file: str = "credentials/credentials.json"
    google_drive_token_file: str = "token.json"
    google_drive_parent_folder_id: str

    frontend_origin: str = "http://localhost:3000"

    max_file_size_mb: int = 500
    max_files_per_request: int = 50
    max_total_upload_mb: int = 2048
    max_name_length: int = 120
    max_filename_length: int = 180

    # Lightweight single-process abuse protection. For multi-instance production,
    # move this limiter to Redis or another shared store.
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 3600
    rate_limit_files: int = 120
    rate_limit_file_window_seconds: int = 3600
    max_concurrent_uploads: int = 3

    app_env: str = "development"
    enable_docs: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

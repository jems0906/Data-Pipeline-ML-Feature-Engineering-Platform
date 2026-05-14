from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Data Pipeline & ML Feature Engineering Platform"
    environment: str = "dev"
    api_prefix: str = "/api/v1"

    postgres_url: str = "postgresql+psycopg://platform:platform@localhost:5432/feature_platform"
    redis_url: str = "redis://localhost:6379/0"
    bigquery_project: str | None = None
    bigquery_credentials_path: str | None = None
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None
    snowflake_role: str | None = None

    data_dir: str = "../data"
    raw_dir: str = "../data/raw"
    processed_dir: str = "../data/processed"
    exports_dir: str = "../data/exports"
    metadata_dir: str = "../data/metadata"

    default_train_ratio: float = 0.8
    outlier_zscore_threshold: float = 3.0
    missing_rate_alert_threshold: float = 0.2
    outlier_rate_alert_threshold: float = 0.1
    default_freshness_lag_seconds: int = 3600
    alert_channels_csv: str = "slack://data-platform-alerts,email://ml-ops@company.com"
    slack_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_sender: str | None = None
    alert_dispatch_timeout_seconds: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def sqlalchemy_postgres_url(self) -> str:
        """Normalize Postgres URLs so SQLAlchemy uses psycopg3 in all environments."""
        if self.postgres_url.startswith("postgresql+psycopg://"):
            return self.postgres_url
        if self.postgres_url.startswith("postgresql://"):
            return self.postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.postgres_url


settings = Settings()

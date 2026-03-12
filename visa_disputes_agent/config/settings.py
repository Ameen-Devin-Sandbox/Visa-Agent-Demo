"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Visa Disputes Processing Brain"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Queue settings
    queue_max_size: int = 10000
    queue_poll_interval_seconds: float = 1.0
    queue_max_retries: int = 3
    queue_dead_letter_enabled: bool = True

    # Processing settings
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    human_review_threshold: float = 0.7
    auto_approve_threshold: float = 0.95

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["*"]

    # Feature flags
    enable_human_in_loop: bool = True
    enable_auto_escalation: bool = True
    enable_compelling_evidence_check: bool = True
    enable_time_limit_enforcement: bool = True

    model_config = {"env_prefix": "VISA_AGENT_"}


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()

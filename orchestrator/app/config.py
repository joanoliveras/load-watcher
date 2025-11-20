from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    load_watcher_url: str = Field(
        default="http://load-watcher:2020/watcher",
        description="Endpoint used to fetch observed metrics snapshots.",
    )
    ml_agent_url: str = Field(
        default="http://ml-agent:8080/predict",
        description="Endpoint used to request predictions for a snapshot.",
    )
    poll_interval_seconds: PositiveInt = Field(
        default=60,
        description="How often (in seconds) to run the orchestrator pipeline.",
    )
    request_timeout_seconds: PositiveInt = Field(
        default=15, description="HTTP timeout for both fetch and predict requests."
    )
    metrics_port: PositiveInt = Field(
        default=9105,
        description="Port exposed by the Prometheus exporter server.",
    )
    metrics_bind_address: str = Field(
        default="0.0.0.0",
        description="Bind address for the Prometheus exporter server.",
    )
    log_level: str = Field(
        default="INFO", description="Python logging level (DEBUG, INFO, ...)."
    )

    model_config = SettingsConfigDict(env_prefix="ORCH_", case_sensitive=False)

    @field_validator("load_watcher_url", "ml_agent_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            msg = f"URL must include scheme and host, got '{value}'."
            raise ValueError(msg)
        return value


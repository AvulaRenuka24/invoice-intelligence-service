"""
config.py — Centralised application settings (Week 4 Renuka Task 5).

Every configurable knob lives here.  Read from environment variables and an
optional ``.env`` file.  Import the ``settings`` singleton — never use
hardcoded constants anywhere else in the project.

Usage::

    from config import settings
    print(settings.llm_provider)   # "local" | "stub" | "tinyllama"
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration, driven by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # LLM Provider selection
    # ------------------------------------------------------------------
    llm_provider: str = Field(
        default="local",
        description="Which provider to activate: 'local', 'stub', or 'tinyllama'.",
    )

    model_name: str = Field(
        default="Qwen/Qwen2.5-0.5B-Instruct",
        description="Hugging Face model ID used by LocalQwenProvider.",
    )

    tinyllama_model_name: str = Field(
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        description="Hugging Face model ID used by TinyLlamaProvider.",
    )

    # ------------------------------------------------------------------
    # Resilience — timeout, retry, circuit breaker
    # ------------------------------------------------------------------
    request_timeout_s: float = Field(
        default=30.0,
        description="Seconds before a provider call is aborted (TimeoutError).",
    )

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts on transient errors (does not retry bad input).",
    )

    breaker_threshold: int = Field(
        default=5,
        description="Consecutive failures before the circuit breaker opens.",
    )

    breaker_cool_off_s: float = Field(
        default=30.0,
        description="Seconds the breaker stays OPEN before a probe is allowed.",
    )

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    cache_max_size: int = Field(
        default=256,
        description="Maximum number of LLM responses to keep in the LRU cache.",
    )

    # ------------------------------------------------------------------
    # Quality gates
    # ------------------------------------------------------------------
    confidence_threshold: float = Field(
        default=0.6,
        description="Confidence below this value marks an extraction as needs_review=True.",
    )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    db_path: str = Field(
        default="jobs.db",
        description="Path to the SQLite database (review queue + import jobs).",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(
        default="INFO",
        description="Python logging level: DEBUG, INFO, WARNING, or ERROR.",
    )


#: Application-wide singleton — import and use this everywhere.
settings = Settings()

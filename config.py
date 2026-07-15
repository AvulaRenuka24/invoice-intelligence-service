"""
config.py — One place for every knob (Renuka Task 5).

All settings are read from environment variables, with an optional
.env file. Import `settings` everywhere; no hardcoded constants
anywhere else in the service.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Renuka Task 2 — provider selection
    llm_provider: str = "local"          # "local" | "stub" | "tinyllama"
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    tinyllama_model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    # Renuka Task 3 — resilience
    request_timeout_s: float = 10.0
    max_retries: int = 2                 # retries AFTER the first attempt
    breaker_threshold: int = 5           # consecutive failures before OPEN
    breaker_cool_off_s: float = 30.0     # OPEN -> HALF_OPEN after this long

    # Renuka Task 4 — cache
    cache_max_size: int = 256            # max entries kept in memory

    # Rohit Task 1 — confidence / review threshold (shared setting)
    confidence_threshold: float = 0.6

    # Rohit Tasks 2-4 — storage
    db_path: str = "data/extracted_invoices.csv"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
"""Runtime settings. An analysis still runs when no AI key is configured."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a whole number.") from exc
    if value < low or value > high:
        raise RuntimeError(f"{name} must be between {low} and {high}.")
    return value


def _float(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number.") from exc
    if value < low or value > high:
        raise RuntimeError(f"{name} must be between {low} and {high}.")
    return value


@dataclass(frozen=True)
class Settings:
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_timeout_seconds: float
    admin_token: str
    cors_origins: tuple[str, ...]
    rate_limit_per_minute: int
    log_level: str

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key)


def load_settings() -> Settings:
    key = os.getenv("COSMIX_AI_API_KEY", "").strip()
    base = os.getenv("COSMIX_AI_BASE_URL", "").strip().rstrip("/")
    if key and not base:
        base = "https://api.openai.com/v1"
    origins = tuple(item.strip() for item in os.getenv("COSMIX_CORS_ORIGINS", "").split(",") if item.strip())
    return Settings(
        ai_api_key=key,
        ai_base_url=base,
        ai_model=os.getenv("COSMIX_AI_MODEL", "").strip() or "gpt-4o-mini",
        ai_timeout_seconds=_float("COSMIX_AI_TIMEOUT_SECONDS", 25.0, 1.0, 120.0),
        admin_token=os.getenv("COSMIX_ADMIN_TOKEN", "").strip(),
        cors_origins=origins,
        rate_limit_per_minute=_int("COSMIX_RATE_LIMIT_PER_MINUTE", 60, 1, 600),
        log_level=os.getenv("COSMIX_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )

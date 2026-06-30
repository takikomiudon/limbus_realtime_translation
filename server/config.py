"""server.config

Centralized server runtime settings loaded from environment variables.
This keeps API, rate-limit, CORS, and Firestore defaults out of route code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ServerSettings:
    """Runtime settings used by the FastAPI server."""

    api_key: str
    firestore_database: str
    google_cloud_project: str | None
    cors_origins: list[str]
    max_requests_per_second: int
    rate_limit_window_seconds: int
    retry_multiplier: float
    initial_retry_delay: float
    max_retry_delay: float
    max_retry_attempts: int
    firestore_emulator_host: str | None
    google_application_credentials: str | None


def _split_csv(value: str) -> list[str]:
    """Parse comma-separated environment values while dropping empty entries."""
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings() -> ServerSettings:
    """Load settings from .env and process environment variables."""
    load_dotenv()
    return ServerSettings(
        api_key=os.environ.get("API_KEY", ""),
        firestore_database=os.environ.get(
            "FIRESTORE_DATABASE",
            "limbus-realtime-translator",
        ),
        google_cloud_project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        cors_origins=_split_csv(os.environ.get("CORS_ORIGINS", "*")),
        max_requests_per_second=int(os.environ.get("MAX_REQUESTS_PER_SECOND", "2")),
        rate_limit_window_seconds=int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "1")),
        retry_multiplier=float(os.environ.get("RETRY_MULTIPLIER", "1.5")),
        initial_retry_delay=float(os.environ.get("INITIAL_RETRY_DELAY", "1.0")),
        max_retry_delay=float(os.environ.get("MAX_RETRY_DELAY", "30.0")),
        max_retry_attempts=int(os.environ.get("MAX_RETRY_ATTEMPTS", "3")),
        firestore_emulator_host=os.environ.get("FIRESTORE_EMULATOR_HOST"),
        google_application_credentials=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    )

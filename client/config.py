"""client.config

Runtime settings for microphone capture, translation, and API publishing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

STREAMING_LIMIT = 240000
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE / 10)


@dataclass(frozen=True)
class ClientSettings:
    """Client-side environment settings."""

    google_api_key: str
    api_base_url: str | None
    api_key: str | None


def load_client_settings() -> ClientSettings:
    """Load local client settings from .env and process environment variables."""
    load_dotenv()
    return ClientSettings(
        google_api_key=os.environ["GOOGLE_API_KEY"],
        api_base_url=os.environ.get("API_BASE_URL"),
        api_key=os.environ.get("API_KEY"),
    )

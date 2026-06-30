"""tests.test_firestore_emulator

Optional Firestore emulator integration test.
It runs only when FIRESTORE_EMULATOR_HOST is set by docker compose or CI.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator is not configured",
)


def test_post_then_get_translation_with_firestore_emulator() -> None:
    """Verify that the real Firestore repository works against the emulator."""
    app = create_app()
    timestamp = int(time.time() * 1000)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/translations",
            headers={"X-API-Key": os.environ["API_KEY"]},
            json={
                "timestamp": timestamp,
                "translation": "エミュレータ翻訳",
                "korean_text": "에뮬레이터",
            },
        )
        get_response = client.get("/api/translations?order=desc&limit=10")

    assert create_response.status_code == 200
    assert get_response.status_code == 200
    translations = get_response.json()["translations"]
    assert any(item["timestamp"] == timestamp for item in translations)

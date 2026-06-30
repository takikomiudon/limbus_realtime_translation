"""tests.test_server

API tests for the translation server using an in-memory repository.
These tests avoid Firestore so local development remains fast and offline.
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server
from server.server import app, get_translation_repository, rate_limit_store

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeTranslationRepository:
    """Small in-memory repository matching the production repository contract."""

    def __init__(self) -> None:
        self.records = [
            {
                "timestamp": 1000,
                "translation": "こんにちは",
                "korean_text": "안녕하세요",
            }
        ]

    async def create_translation(
        self, timestamp: int, translation: str, korean_text: str
    ) -> None:
        self.records.append(
            {
                "timestamp": timestamp,
                "translation": translation,
                "korean_text": korean_text,
            }
        )

    async def get_translations(
        self, limit: int, page: int, order: str
    ) -> dict[str, object]:
        records = sorted(
            self.records,
            key=lambda record: record["timestamp"],
            reverse=order != "asc",
        )
        start = (page - 1) * limit
        end = start + limit
        return {
            "translations": records[start:end],
            "pagination": {
                "current_page": page,
                "total_pages": math.ceil(len(records) / limit) if records else 0,
                "total_items": len(records),
                "items_per_page": limit,
            },
        }


@pytest.fixture(autouse=True)
def reset_app_state():
    """Clear mutable FastAPI test state between cases."""
    rate_limit_store.clear()
    app.dependency_overrides = {}
    yield
    rate_limit_store.clear()
    app.dependency_overrides = {}


def build_client(repository: FakeTranslationRepository) -> TestClient:
    """Create a TestClient with Firestore replaced by the fake repository."""
    app.dependency_overrides[get_translation_repository] = lambda: repository
    return TestClient(app)


def test_get_html_returns_page() -> None:
    repository = FakeTranslationRepository()
    with build_client(repository) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Limbus" in response.text


def test_package_exports_cloud_run_entrypoint() -> None:
    """Keep uvicorn server:app working for Cloud Build Trigger deploys."""
    assert server.app is app


def test_buildpack_runtime_and_entrypoint_are_pinned() -> None:
    """Keep Cloud Run source deploys aligned with the tested server runtime."""
    config = tomllib.loads((PROJECT_ROOT / "project.toml").read_text())
    build_env = {
        item["name"]: item["value"]
        for item in config["build"]["env"]
    }

    assert build_env["GOOGLE_RUNTIME_VERSION"] == "3.12"
    assert build_env["GOOGLE_ENTRYPOINT"] == (
        "uvicorn server:app --host 0.0.0.0 --port $PORT"
    )


def test_get_translations_returns_fake_data_and_pagination() -> None:
    repository = FakeTranslationRepository()
    with build_client(repository) as client:
        response = client.get("/api/translations")

    assert response.status_code == 200
    body = response.json()
    assert body["translations"] == repository.records
    assert body["pagination"] == {
        "current_page": 1,
        "total_pages": 1,
        "total_items": 1,
        "items_per_page": 100,
    }


def test_post_translation_with_valid_api_key_saves_record() -> None:
    repository = FakeTranslationRepository()
    with build_client(repository) as client:
        response = client.post(
            "/api/translations",
            headers={"X-API-Key": "test-key"},
            json={
                "timestamp": 2000,
                "translation": "翻訳",
                "korean_text": "번역",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert repository.records[-1] == {
        "timestamp": 2000,
        "translation": "翻訳",
        "korean_text": "번역",
    }


def test_post_translation_with_invalid_api_key_returns_403() -> None:
    repository = FakeTranslationRepository()
    with build_client(repository) as client:
        response = client.post(
            "/api/translations",
            headers={"X-API-Key": "wrong-key"},
            json={
                "timestamp": 2000,
                "translation": "翻訳",
                "korean_text": "번역",
            },
        )

    assert response.status_code == 403
    assert len(repository.records) == 1


def test_get_translations_caps_limit_at_1000() -> None:
    repository = FakeTranslationRepository()
    with build_client(repository) as client:
        response = client.get("/api/translations?limit=2000")

    assert response.status_code == 200
    assert response.json()["pagination"]["items_per_page"] == 1000

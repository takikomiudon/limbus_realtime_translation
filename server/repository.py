"""server.repository

Firestore-backed translation storage and a small repository interface.
Keeping Firestore client creation here avoids network/database work at import time.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Protocol

from google.cloud import firestore


class TranslationRepository(Protocol):
    """Storage contract used by FastAPI endpoints and tests."""

    async def create_translation(
        self, timestamp: int, translation: str, korean_text: str
    ) -> None:
        """Persist a completed translation."""

    async def get_translations(
        self, limit: int, page: int, order: str
    ) -> dict[str, object]:
        """Return translations and pagination metadata."""


class FirestoreTranslationRepository:
    """Firestore implementation of the translation repository contract."""

    def __init__(self, database: str, project: str | None = None) -> None:
        """Create the Firestore client lazily from the FastAPI dependency."""
        self._db = firestore.Client(project=project, database=database)

    async def create_translation(
        self, timestamp: int, translation: str, korean_text: str
    ) -> None:
        """Store a translation document with the same fields used historically."""
        doc_ref = self._db.collection("translations").document()
        doc_ref.set(
            {
                "timestamp": timestamp,
                "translation": translation,
                "korean_text": korean_text,
                "created_at": datetime.now(),
            }
        )

    async def get_translations(
        self, limit: int, page: int, order: str
    ) -> dict[str, object]:
        """Fetch paginated translation records from Firestore."""
        translations_ref = self._db.collection("translations")
        total_docs = len(list(translations_ref.stream()))
        total_pages = math.ceil(total_docs / limit) if total_docs else 0
        direction = (
            firestore.Query.ASCENDING
            if order == "asc"
            else firestore.Query.DESCENDING
        )

        docs = (
            translations_ref.order_by("timestamp", direction=direction)
            .offset((page - 1) * limit)
            .limit(limit)
            .stream()
        )

        translations = []
        for doc in docs:
            data = doc.to_dict()
            translations.append(
                {
                    "timestamp": data["timestamp"],
                    "translation": data["translation"],
                    "korean_text": data.get("korean_text", ""),
                }
            )

        return {
            "translations": translations,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total_docs,
                "items_per_page": limit,
            },
        }

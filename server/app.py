"""server.app

FastAPI application factory, dependencies, middleware, and HTTP routes.
The app can use real Firestore or test-provided repository overrides.
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from server.config import ServerSettings, load_settings
from server.models import Translation
from server.repository import FirestoreTranslationRepository, TranslationRepository

logging.basicConfig(level=logging.INFO)

rate_limit_store: dict[str, list[float]] = {}
api_key_header = APIKeyHeader(name="X-API-Key")
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


def with_firestore_retry(func):
    """Retry route work that depends on Firestore availability."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        settings = (
            request.app.state.settings
            if isinstance(request, Request)
            else load_settings()
        )
        retry_delay = settings.initial_retry_delay
        attempts = 0

        while attempts < settings.max_retry_attempts:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as exc:
                attempts += 1
                if attempts == settings.max_retry_attempts:
                    logging.error(f"Failed after {attempts} attempts: {exc}")
                    raise HTTPException(
                        status_code=503,
                        detail="Database service temporarily unavailable",
                    ) from exc

                logging.warning(f"Attempt {attempts} failed: {exc}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(
                    retry_delay * settings.retry_multiplier,
                    settings.max_retry_delay,
                )

        return None

    return wrapper


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small in-memory rate limiter for public GET requests."""

    async def dispatch(self, request: Request, call_next):
        try:
            settings: ServerSettings = request.app.state.settings

            # POST requests still require API-key auth, so rate limiting them here
            # would mostly interfere with the local realtime client.
            if request.method == "POST":
                return await call_next(request)

            api_key = request.headers.get("X-API-Key")
            if api_key and api_key == settings.api_key:
                return await call_next(request)

            client_ip = request.client.host if request.client else "unknown"
            current_time = time.time()

            if client_ip not in rate_limit_store:
                rate_limit_store[client_ip] = []

            rate_limit_store[client_ip] = [
                item
                for item in rate_limit_store[client_ip]
                if current_time - item < settings.rate_limit_window_seconds
            ]
            rate_limit_store[client_ip].append(current_time)

            if len(rate_limit_store[client_ip]) > settings.max_requests_per_second:
                logging.warning(f"Rate limit exceeded for IP: {client_ip}")
                return Response(
                    status_code=429,
                    content="Rate limit exceeded",
                    media_type="text/plain",
                )

            return await call_next(request)
        except Exception as exc:
            logging.error(f"Error in rate limit middleware: {exc}")
            return Response(
                status_code=500,
                content="Internal server error",
                media_type="text/plain",
            )


async def get_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
) -> str:
    """Validate the shared API key configured for write requests."""
    settings: ServerSettings = request.app.state.settings

    if not settings.api_key:
        raise HTTPException(status_code=500, detail="API key is not configured")

    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


def get_translation_repository(request: Request) -> TranslationRepository:
    """Create the production repository only when a request needs it."""
    settings: ServerSettings = request.app.state.settings
    return FirestoreTranslationRepository(
        database=settings.firestore_database,
        project=settings.google_cloud_project,
    )


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    """Build the FastAPI app with explicit settings for tests and runtime."""
    app_settings = settings or load_settings()
    app = FastAPI(title="Limbus Translation API")
    app.state.settings = app_settings

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key"],
    )

    @app.post("/api/translations")
    @with_firestore_retry
    async def create_translation(
        request: Request,
        translation: Translation,
        api_key: str = Depends(get_api_key),
        repository: TranslationRepository = Depends(get_translation_repository),
    ):
        """Store a completed translation."""
        del request, api_key
        await repository.create_translation(
            timestamp=translation.timestamp,
            translation=translation.translation,
            korean_text=translation.korean_text,
        )
        return {"status": "success"}

    @app.get("/api/translations")
    @with_firestore_retry
    async def get_translations(
        request: Request,
        limit: int = 100,
        page: int = 1,
        order: str = "asc",
        repository: TranslationRepository = Depends(get_translation_repository),
    ):
        """Return saved translations with pagination."""
        del request
        if limit > 1000:
            limit = 1000

        if page < 1:
            page = 1

        return await repository.get_translations(limit=limit, page=page, order=order)

    @app.get("/")
    async def get_html():
        """Return the static translation history page."""
        return HTMLResponse(content=TEMPLATE_PATH.read_text(encoding="utf-8"))

    return app

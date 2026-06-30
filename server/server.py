"""server.server

Backward-compatible ASGI entrypoint for the translation API server.
Runtime implementation lives in server.app so it can be configured and tested.
"""

from server.app import create_app, get_translation_repository, rate_limit_store

__all__ = ["app", "get_translation_repository", "rate_limit_store"]

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

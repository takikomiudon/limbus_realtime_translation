"""server.server

Backward-compatible ASGI entrypoint for package and Cloud Build source deploys.
The import fallback supports Cloud Build Triggers that use server/ as root.
"""

try:
    from server.app import create_app, get_translation_repository, rate_limit_store
except ModuleNotFoundError:
    from app import create_app, get_translation_repository, rate_limit_store

__all__ = ["app", "get_translation_repository", "rate_limit_store"]

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

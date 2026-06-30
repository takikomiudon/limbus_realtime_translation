"""server package

FastAPI server modules for storing and displaying translation history.
This also exposes the ASGI app for legacy Cloud Run entrypoints.
"""

from server.server import app

__all__ = ["app"]

"""server.models

Pydantic request models shared by server routes and tests.
"""

from pydantic import BaseModel


class Translation(BaseModel):
    """Translation payload accepted by POST /api/translations."""

    timestamp: int
    translation: str
    korean_text: str

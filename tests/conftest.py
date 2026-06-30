"""tests.conftest

Shared pytest setup for server tests.
Environment defaults must be set before importing the FastAPI app module.
"""

import os

os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("FIRESTORE_DATABASE", "test-database")

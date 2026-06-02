"""Compatibility entrypoint for Uvicorn.

The actual FastAPI application lives in app.py. This file lets commands like
`python -m uvicorn main:app` work as expected.
"""

from app import app


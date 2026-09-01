# Entry point for local development and for platforms like Render that
# run `uvicorn main:app`. All actual logic lives in app_core.py so that
# both this file and api/index.py (used by Vercel) share the same code.
from app_core import app  # noqa: F401

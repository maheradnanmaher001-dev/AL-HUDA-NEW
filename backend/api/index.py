# Entry point for Vercel's Python serverless runtime. Vercel looks for a
# file under /api that exposes an ASGI/WSGI "app" object — this just
# re-exports the real FastAPI app defined in app_core.py so the logic
# only has to be written once.
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app_core import app  # noqa: F401,E402

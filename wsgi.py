"""Entry point for the production server:  gunicorn wsgi:app

Locally you keep using `python app.py`. This file only adds production safety checks.
"""
import os

PRODUCTION = os.environ.get("APP_ENV") == "production"

# Fail fast, before anything else loads, if the secret is missing
if PRODUCTION and not os.environ.get("SECRET_KEY"):
    raise RuntimeError("Set the SECRET_KEY environment variable before running in production.")

from app import create_app  # noqa: E402

app = create_app()

if PRODUCTION:
    # Only send the session cookie over HTTPS
    app.config["SESSION_COOKIE_SECURE"] = True
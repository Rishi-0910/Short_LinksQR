"""
Central configuration, loaded from environment variables (.env).
Keeping every tunable in one place makes the security posture auditable at a glance.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Pair-token auth (spec: 15m access / 7d refresh, httpOnly cookie) ---
    JWT_ACCESS_SECRET = os.environ.get("JWT_ACCESS_SECRET", "dev-access-secret")
    JWT_REFRESH_SECRET = os.environ.get("JWT_REFRESH_SECRET", "dev-refresh-secret")
    ACCESS_TOKEN_TTL = timedelta(minutes=15)
    REFRESH_TOKEN_TTL = timedelta(days=7)
    REFRESH_COOKIE_NAME = "refresh_token"

    # A reset/verification token is short-lived on purpose: it only needs to
    # survive the time it takes someone to open their inbox.
    EMAIL_VERIFICATION_TTL = timedelta(hours=24)
    PASSWORD_RESET_TTL = timedelta(minutes=30)

    # --- Short link engine ---
    SHORT_CODE_LENGTH = 6
    SHORT_CODE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    SHORT_CODE_MAX_ATTEMPTS = 8  # collision retries before giving up

    # --- Frontend / cookie behaviour ---
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")
    COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

    # --- Email simulation ---
    # No real SMTP server is wired up for this evaluation build. Instead,
    # "sent" emails are written to backend/outbox.log and also returned in
    # dev-only API responses so the flow can be exercised end-to-end.
    EMAIL_SIMULATION = True

    # --- Rate limiting (express-rate-limit equivalent via Flask-Limiter) ---
    RATELIMIT_STORAGE_URI = "memory://"
    RATE_LIMIT_AUTH = "10 per minute"
    RATE_LIMIT_LINK_CREATE = "30 per minute"
    RATE_LIMIT_REDIRECT = "120 per minute"

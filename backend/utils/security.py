"""
Everything touching secrets, tokens, and hashing lives here so the auth
routes stay readable and the crypto choices are auditable in one place.
"""
import hashlib
import secrets
from datetime import datetime, timezone
import jwt
from flask import current_app


# ---------------------------------------------------------------------------
# Access / Refresh JWT pair
# ---------------------------------------------------------------------------
def issue_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + current_app.config["ACCESS_TOKEN_TTL"],
    }
    return jwt.encode(payload, current_app.config["JWT_ACCESS_SECRET"], algorithm="HS256")


def issue_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (token, jti). jti lets us support rotation/blacklisting later
    without needing to inspect the token body server-side."""
    now = datetime.now(timezone.utc)
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + current_app.config["REFRESH_TOKEN_TTL"],
    }
    token = jwt.encode(payload, current_app.config["JWT_REFRESH_SECRET"], algorithm="HS256")
    return token, jti


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, current_app.config["JWT_ACCESS_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def decode_refresh_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, current_app.config["JWT_REFRESH_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# One-time tokens (email verification / password reset)
# We only ever store a hash of these, mirroring how we treat passwords --
# a leaked database should never hand out usable tokens.
# ---------------------------------------------------------------------------
def generate_one_time_token() -> tuple[str, str]:
    """Returns (raw_token_to_email, sha256_hash_to_store)."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


def hash_one_time_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def hash_refresh_jti(jti: str) -> str:
    """Hash refresh-token IDs before storage so database leaks cannot identify live JWTs."""
    salt = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{salt}:{jti}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# IP hashing for click telemetry -- never store raw IPs (spec: "IP hash")
# ---------------------------------------------------------------------------
def hash_ip(ip_address: str) -> str:
    salt = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{salt}:{ip_address}".encode()).hexdigest()

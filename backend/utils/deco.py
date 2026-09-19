"""
@require_auth reads the short-lived access token from the Authorization
header (Bearer <token>) -- the access token is never stored in a cookie,
only the long-lived refresh token is, so it can't be silently replayed by
a CSRF request the way a cookie-based access token could.
"""
from functools import wraps
from flask import request, jsonify, g
from utils.security import decode_access_token
from models import User


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(error="missing_token", message="Authentication required."), 401

        token = auth_header.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if not payload or payload.get("type") != "access":
            return jsonify(error="invalid_token", message="Session expired or invalid. Please log in again."), 401

        user = User.query.get(payload["sub"])
        if not user:
            return jsonify(error="user_not_found", message="Account no longer exists."), 401

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper

"""
Auth routes implementing the brief's "Universal Security & Architecture
Requirements":
  - Pair token auth: 15m access JWT (returned in body) + 7d refresh JWT
    (httpOnly cookie), rotated on every /refresh call.
  - Signup with simulated email verification.
  - Forgot / reset password via a one-time, hashed token.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app, g
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import User, BioProfile, RefreshToken
from utils.validators import is_valid_email, is_valid_username, password_strength_errors
from utils.security import (
    issue_access_token,
    issue_refresh_token,
    decode_refresh_token,
    generate_one_time_token,
    hash_one_time_token,
    hash_refresh_jti,
)
from utils.deco import require_auth
from utils.mailer import send_simulated_email

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _set_refresh_cookie(response, token):
    response.set_cookie(
        current_app.config["REFRESH_COOKIE_NAME"],
        token,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite="Lax",
        max_age=int(current_app.config["REFRESH_TOKEN_TTL"].total_seconds()),
        path="/api/auth",  # scope the cookie to auth endpoints only
    )


def _store_refresh_token(user_id, jti):
    db.session.add(
        RefreshToken(
            user_id=user_id,
            jti_hash=hash_refresh_jti(jti),
            expires_at=datetime.utcnow() + current_app.config["REFRESH_TOKEN_TTL"],
        )
    )


def _clear_refresh_cookie(response):
    response.set_cookie(
        current_app.config["REFRESH_COOKIE_NAME"],
        "",
        expires=0,
        max_age=0,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite="Lax",
        path="/api/auth",
    )


@auth_bp.post("/signup")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("displayName") or username).strip()[:120]

    field_errors = {}
    if not is_valid_email(email):
        field_errors["email"] = "Enter a valid email address."
    elif User.query.filter_by(email=email).first():
        field_errors["email"] = "An account with this email already exists."

    if not is_valid_username(username):
        field_errors["username"] = "Username must be 3-30 characters: letters, numbers, underscore."
    elif User.query.filter_by(username=username).first():
        field_errors["username"] = "That username is taken."

    pw_errors = password_strength_errors(password)
    if pw_errors:
        field_errors["password"] = " ".join(pw_errors)

    if field_errors:
        return jsonify(error="validation_error", fields=field_errors), 422

    user = User(email=email, username=username, display_name=display_name)
    user.set_password(password)

    raw_token, token_hash = generate_one_time_token()
    user.verification_token_hash = token_hash
    user.verification_expires_at = datetime.now(timezone.utc) + current_app.config["EMAIL_VERIFICATION_TTL"]

    try:
        db.session.add(user)
        db.session.flush()  # get user.id before creating the dependent profile
        db.session.add(BioProfile(user_id=user.id, display_name=display_name))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            error="validation_error",
            fields={
                "email": "This email or username is already registered.",
                "username": "This email or username is already registered.",
            },
        ), 409

    verify_url = f"{current_app.config['FRONTEND_URL']}/verify-email.html?token={raw_token}"
    send_simulated_email(
        to=email,
        subject="Verify your email",
        body=f"Welcome! Confirm your address to activate your account: {verify_url}",
    )

    return jsonify(
        message="Account created. Check your email to verify your address.",
        user=user.to_public_dict(),
        # Included ONLY because there's no real mail server in this evaluation
        # build -- lets the frontend demo the verify flow without an inbox.
        devVerificationToken=raw_token if current_app.config["EMAIL_SIMULATION"] else None,
    ), 201


@auth_bp.post("/verify-email")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def verify_email():
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token") or ""
    if not raw_token:
        return jsonify(error="missing_token", message="Verification token is required."), 400

    token_hash = hash_one_time_token(raw_token)
    user = User.query.filter_by(verification_token_hash=token_hash).first()

    if not user or not user.verification_expires_at:
        return jsonify(error="invalid_token", message="This verification link is invalid."), 400

    if datetime.now(timezone.utc) > user.verification_expires_at.replace(tzinfo=timezone.utc):
        return jsonify(error="expired_token", message="This verification link has expired. Request a new one."), 400

    user.is_verified = True
    user.verification_token_hash = None
    user.verification_expires_at = None
    db.session.commit()

    return jsonify(message="Email verified. You can now log in."), 200


@auth_bp.post("/login")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    # Same generic message whether the email or password was wrong -- avoids
    # leaking which accounts exist.
    if not user or not user.check_password(password):
        return jsonify(error="invalid_credentials", message="Incorrect email or password."), 401

    if not user.is_verified:
        return jsonify(error="email_not_verified", message="Please verify your email before logging in."), 403

    access_token = issue_access_token(user.id)
    refresh_token, jti = issue_refresh_token(user.id)

    resp = jsonify(message="Logged in.", accessToken=access_token, user=user.to_public_dict())
    try:
        _store_refresh_token(user.id, jti)
        db.session.commit()
        _set_refresh_cookie(resp, refresh_token)
        return resp, 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to create refresh session")
        return jsonify(error="server_error", message="Unable to create a session. Please retry."), 500


@auth_bp.post("/refresh")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def refresh():
    """Rotation: every refresh call invalidates the old refresh token by
    issuing (and cookie-setting) a brand new one, and hands back a new
    15-minute access token. If a stale/replayed refresh token is used, the
    signature/expiry check below simply rejects it."""
    token = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    if not token:
        return jsonify(error="missing_refresh_token", message="Session expired. Please log in again."), 401

    payload = decode_refresh_token(token)
    if not payload or payload.get("type") != "refresh":
        return jsonify(error="invalid_refresh_token", message="Session expired. Please log in again."), 401

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        return jsonify(error="invalid_refresh_token", message="Session expired. Please log in again."), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify(error="user_not_found", message="Account no longer exists."), 401

    stored_token = RefreshToken.query.filter_by(jti_hash=hash_refresh_jti(jti), user_id=user.id).first()
    if not stored_token or not stored_token.is_active:
        return jsonify(error="invalid_refresh_token", message="Session expired. Please log in again."), 401

    new_access_token = issue_access_token(user.id)
    new_refresh_token, new_jti = issue_refresh_token(user.id)

    resp = jsonify(accessToken=new_access_token)
    try:
        stored_token.revoked_at = datetime.utcnow()
        _store_refresh_token(user.id, new_jti)
        db.session.commit()
        _set_refresh_cookie(resp, new_refresh_token)
        return resp, 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to rotate refresh token")
        return jsonify(error="server_error", message="Unable to refresh the session. Please retry."), 500


@auth_bp.post("/logout")
def logout():
    resp = jsonify(message="Logged out.")
    token = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    if token:
        payload = decode_refresh_token(token)
        jti = payload.get("jti") if payload else None
        user_id = payload.get("sub") if payload else None
        if jti and user_id:
            stored_token = RefreshToken.query.filter_by(jti_hash=hash_refresh_jti(jti), user_id=user_id).first()
            if stored_token and stored_token.revoked_at is None:
                try:
                    stored_token.revoked_at = datetime.utcnow()
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Failed to revoke refresh token during logout")
    _clear_refresh_cookie(resp)
    return resp, 200


@auth_bp.post("/forgot-password")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()

    # Always return 200 with the same message -- never confirm/deny whether
    # an email is registered.
    generic_response = jsonify(message="If that email is registered, a reset link has been sent.")

    if not user:
        return generic_response, 200

    raw_token, token_hash = generate_one_time_token()
    user.reset_token_hash = token_hash
    user.reset_expires_at = datetime.now(timezone.utc) + current_app.config["PASSWORD_RESET_TTL"]
    db.session.commit()

    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password.html?token={raw_token}"
    send_simulated_email(
        to=email,
        subject="Reset your password",
        body=f"Reset your password (valid 30 minutes): {reset_url}",
    )

    return generic_response, 200


@auth_bp.post("/reset-password")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_AUTH"])
def reset_password():
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token") or ""
    new_password = data.get("password") or ""

    pw_errors = password_strength_errors(new_password)
    if pw_errors:
        return jsonify(error="weak_password", message=" ".join(pw_errors)), 422

    token_hash = hash_one_time_token(raw_token)
    user = User.query.filter_by(reset_token_hash=token_hash).first()

    if not user or not user.reset_expires_at:
        return jsonify(error="invalid_token", message="This reset link is invalid."), 400

    if datetime.now(timezone.utc) > user.reset_expires_at.replace(tzinfo=timezone.utc):
        return jsonify(error="expired_token", message="This reset link has expired. Request a new one."), 400

    user.set_password(new_password)
    user.reset_token_hash = None
    user.reset_expires_at = None
    db.session.commit()

    return jsonify(message="Password updated. You can now log in."), 200


@auth_bp.get("/me")
@require_auth
def me():
    return jsonify(user=g.current_user.to_public_dict()), 200

"""
CRUD surface for the "Link Library Studio" (spec section 2C) plus the
create-time logic for the redirection engine (spec section 2A):
  - auto 6-char short codes OR custom vanity slugs
  - duplicate alias collision detection
  - valid URL format enforcement
"""
from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models import Link
from utils.deco import require_auth
from utils.validators import is_valid_url
from utils.shortcode import generate_unique_short_code, is_valid_vanity_slug, slug_is_available

links_bp = Blueprint("links", __name__, url_prefix="/api/links")


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


@links_bp.post("")
@require_auth
@limiter.limit(lambda: current_app.config["RATE_LIMIT_LINK_CREATE"])
def create_link():
    data = request.get_json(silent=True) or {}
    original_url = (data.get("originalUrl") or "").strip()
    custom_alias = (data.get("customAlias") or "").strip()
    title = ((data.get("title") or "").strip()[:200]) or None

    if not is_valid_url(original_url):
        return jsonify(
            error="validation_error",
            fields={"originalUrl": "Enter a full URL starting with http:// or https://."},
        ), 422

    if custom_alias:
        if not is_valid_vanity_slug(custom_alias):
            return jsonify(
                error="validation_error",
                fields={"customAlias": "Use 3-32 characters: letters, numbers, - or _."},
            ), 422
        if not slug_is_available(custom_alias):
            return jsonify(
                error="alias_taken",
                fields={"customAlias": "That custom alias is already in use."},
            ), 409
        short_code = custom_alias
        is_custom = True
    else:
        try:
            short_code = generate_unique_short_code()
        except RuntimeError:
            current_app.logger.exception("Failed to generate a unique short code")
            return jsonify(error="short_code_unavailable", message="Could not create a unique short link. Try again."), 503
        is_custom = False

    link = Link(
        user_id=g.current_user.id,
        original_url=original_url,
        short_code=short_code,
        is_custom_alias=is_custom,
        title=title,
    )
    try:
        db.session.add(link)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if not is_custom:
            return jsonify(error="short_code_unavailable", message="Short-code collision. Please retry."), 503
        return jsonify(
            error="alias_taken",
            fields={"customAlias": "That custom alias is already in use."},
        ), 409

    return jsonify(link=link.to_dict(request.host_url)), 201


@links_bp.get("")
@require_auth
def list_links():
    """Search + pagination across the caller's own link library."""
    search = (request.args.get("search") or "").strip()
    page = _bounded_int(request.args.get("page"), 1, 1, 10_000)
    page_size = _bounded_int(request.args.get("pageSize"), 10, 1, 100)

    query = g.current_user.links
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Link.original_url.ilike(like), Link.short_code.ilike(like), Link.title.ilike(like)))

    query = query.order_by(Link.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return jsonify(
        links=[l.to_dict(request.host_url) for l in items],
        pagination={"page": page, "pageSize": page_size, "total": total, "totalPages": max(1, -(-total // page_size))},
    ), 200


@links_bp.get("/<link_id>")
@require_auth
def get_link(link_id):
    link = Link.query.filter_by(id=link_id, user_id=g.current_user.id).first()
    if not link:
        return jsonify(error="not_found", message="Link not found."), 404
    return jsonify(link=link.to_dict(request.host_url)), 200


@links_bp.delete("/<link_id>")
@require_auth
def delete_link(link_id):
    link = Link.query.filter_by(id=link_id, user_id=g.current_user.id).first()
    if not link:
        return jsonify(error="not_found", message="Link not found."), 404
    try:
        db.session.delete(link)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete link")
        return jsonify(error="server_error", message="Could not delete the link. Please retry."), 500
    return jsonify(message="Link deleted."), 200

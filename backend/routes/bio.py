"""
Spec 2D: "Link-in-Bio" hub.
  - /api/bio/*        -- authenticated editor (avatar, displayName, bio, theme, social links)
  - /bio/<username>   -- public, mobile-responsive, server-rendered profile page
"""
from flask import Blueprint, request, jsonify, g, render_template, abort, current_app

from extensions import db
from models import User, BioProfile, SocialLink
from utils.deco import require_auth
from utils.validators import is_valid_url

bio_bp = Blueprint("bio", __name__)

VALID_THEMES = {"minimal_light", "dark_slate", "gradient"}
VALID_ICONS = {"link", "instagram", "youtube", "github", "x", "linkedin", "facebook", "website"}


@bio_bp.get("/api/bio")
@require_auth
def get_my_bio():
    profile = g.current_user.bio_profile
    return jsonify(bio=profile.to_dict(), username=g.current_user.username), 200


@bio_bp.put("/api/bio")
@require_auth
def update_my_bio():
    data = request.get_json(silent=True) or {}
    profile = g.current_user.bio_profile

    if "displayName" in data:
        profile.display_name = (data["displayName"] or "").strip()[:120]
    if "bio" in data:
        profile.bio = (data["bio"] or "").strip()[:280]
    if "avatarUrl" in data:
        avatar = (data["avatarUrl"] or "").strip()
        if avatar and not is_valid_url(avatar):
            return jsonify(error="validation_error", fields={"avatarUrl": "Enter a valid image URL."}), 422
        profile.avatar_url = avatar or None
    if "theme" in data:
        theme = data["theme"]
        if theme not in VALID_THEMES:
            return jsonify(error="validation_error", fields={"theme": f"Theme must be one of {sorted(VALID_THEMES)}."}), 422
        profile.theme = theme

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update bio profile")
        return jsonify(error="server_error", message="Could not save the profile. Please retry."), 500
    return jsonify(bio=profile.to_dict(), message="Profile updated."), 200


@bio_bp.post("/api/bio/social-links")
@require_auth
def add_social_link():
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()[:80]
    url = (data.get("url") or "").strip()
    icon = (data.get("icon") or "link").strip().lower()

    field_errors = {}
    if not label:
        field_errors["label"] = "Label is required."
    if not is_valid_url(url):
        field_errors["url"] = "Enter a valid URL starting with http:// or https://."
    if icon not in VALID_ICONS:
        field_errors["icon"] = "Choose a supported icon."
    if field_errors:
        return jsonify(error="validation_error", fields=field_errors), 422

    profile = g.current_user.bio_profile
    next_position = len(profile.social_links)
    link = SocialLink(bio_profile_id=profile.id, label=label, url=url, icon=icon, position=next_position)
    try:
        db.session.add(link)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to add social link")
        return jsonify(error="server_error", message="Could not add the social link. Please retry."), 500

    return jsonify(bio=profile.to_dict(), message="Social link added."), 201


@bio_bp.delete("/api/bio/social-links/<link_id>")
@require_auth
def delete_social_link(link_id):
    profile = g.current_user.bio_profile
    link = SocialLink.query.filter_by(id=link_id, bio_profile_id=profile.id).first()
    if not link:
        return jsonify(error="not_found", message="Social link not found."), 404
    try:
        db.session.delete(link)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete social link")
        return jsonify(error="server_error", message="Could not remove the social link. Please retry."), 500
    return jsonify(bio=profile.to_dict(), message="Social link removed."), 200


@bio_bp.put("/api/bio/social-links/reorder")
@require_auth
def reorder_social_links():
    """Body: {"orderedIds": ["id1", "id2", ...]}"""
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("orderedIds") or []
    if not isinstance(ordered_ids, list) or not all(isinstance(item, str) for item in ordered_ids):
        return jsonify(error="validation_error", message="orderedIds must be a list of link IDs."), 422
    profile = g.current_user.bio_profile
    id_to_link = {l.id: l for l in profile.social_links}

    if set(ordered_ids) != set(id_to_link.keys()):
        return jsonify(error="validation_error", message="orderedIds must match the profile's existing links."), 422

    for index, link_id in enumerate(ordered_ids):
        id_to_link[link_id].position = index
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to reorder social links")
        return jsonify(error="server_error", message="Could not reorder links. Please retry."), 500

    return jsonify(bio=profile.to_dict()), 200


@bio_bp.get("/bio/<username>")
def public_bio_page(username):
    """Public, mobile-responsive route rendering the configured profile page."""
    user = User.query.filter_by(username=username.lower()).first()
    if not user or not user.bio_profile:
        abort(404, description="This profile doesn't exist.")

    profile = user.bio_profile
    return render_template(
        "public_bio.html",
        display_name=profile.display_name or user.display_name or user.username,
        bio=profile.bio or "",
        avatar_url=profile.avatar_url,
        theme=profile.theme,
        social_links=sorted(profile.social_links, key=lambda s: s.position),
        username=user.username,
    )

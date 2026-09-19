"""
Data model.

User            -- account + auth state (email verification, reset token)
RefreshToken    -- server-side refresh-token rotation / replay protection
Link            -- one shortened URL owned by a user
ClickEvent      -- one recorded hit on a Link (telemetry row for analytics)
BioProfile      -- the "Link-in-Bio" hub configuration, one per user
SocialLink      -- an ordered button on a BioProfile's public page
"""
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


def _uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token_hash = db.Column(db.String(255), nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)

    reset_token_hash = db.Column(db.String(255), nullable=True)
    reset_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    links = db.relationship("Link", backref="owner", cascade="all, delete-orphan", lazy="dynamic")
    refresh_tokens = db.relationship(
        "RefreshToken", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    bio_profile = db.relationship(
        "BioProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "displayName": self.display_name,
            "isVerified": self.is_verified,
            "createdAt": self.created_at.isoformat() + "Z",
        }


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    jti_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.utcnow()


class Link(db.Model):
    __tablename__ = "links"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    original_url = db.Column(db.Text, nullable=False)
    short_code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    is_custom_alias = db.Column(db.Boolean, default=False)
    title = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    click_events = db.relationship(
        "ClickEvent", backref="link", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, request_root: str) -> dict:
        return {
            "id": self.id,
            "originalUrl": self.original_url,
            "shortCode": self.short_code,
            "shortUrl": f"{request_root.rstrip('/')}/r/{self.short_code}",
            "isCustomAlias": self.is_custom_alias,
            "title": self.title,
            "createdAt": self.created_at.isoformat() + "Z",
            "totalClicks": self.click_events.count(),
        }


class ClickEvent(db.Model):
    __tablename__ = "click_events"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    link_id = db.Column(db.String(36), db.ForeignKey("links.id"), nullable=False, index=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    referrer = db.Column(db.String(500), nullable=True, default="Direct")
    device_type = db.Column(db.String(20), nullable=False, default="Desktop")  # Mobile/Desktop/Tablet
    ip_hash = db.Column(db.String(64), nullable=False)


class BioProfile(db.Model):
    __tablename__ = "bio_profiles"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False)

    avatar_url = db.Column(db.Text, nullable=True)
    display_name = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.String(280), nullable=True, default="")
    theme = db.Column(db.String(30), nullable=False, default="minimal_light")  # minimal_light|dark_slate|gradient

    social_links = db.relationship(
        "SocialLink",
        backref="profile",
        cascade="all, delete-orphan",
        order_by="SocialLink.position",
        lazy="joined",
    )

    def to_dict(self) -> dict:
        return {
            "avatarUrl": self.avatar_url,
            "displayName": self.display_name,
            "bio": self.bio,
            "theme": self.theme,
            "socialLinks": [s.to_dict() for s in self.social_links],
        }


class SocialLink(db.Model):
    __tablename__ = "social_links"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    bio_profile_id = db.Column(db.String(36), db.ForeignKey("bio_profiles.id"), nullable=False)

    label = db.Column(db.String(80), nullable=False)
    url = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(40), nullable=True, default="link")
    position = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "url": self.url, "icon": self.icon, "position": self.position}

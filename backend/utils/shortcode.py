"""
Generates unique 6-character short codes and validates custom vanity slugs.
"""
import re
import secrets
from flask import current_app
from models import Link

_VANITY_PATTERN = re.compile(r"^[a-zA-Z0-9-_]{3,32}$")


def generate_unique_short_code() -> str:
    """Random base62-ish code, retried on the rare collision.

    Raises RuntimeError if the keyspace is saturated after max attempts --
    at 6 chars over 62 symbols that's ~5.6e10 codes, so this is a safety
    valve rather than an expected path.
    """
    length = current_app.config["SHORT_CODE_LENGTH"]
    alphabet = current_app.config["SHORT_CODE_ALPHABET"]
    max_attempts = current_app.config["SHORT_CODE_MAX_ATTEMPTS"]

    for _ in range(max_attempts):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not Link.query.filter_by(short_code=candidate).first():
            return candidate
    raise RuntimeError("Could not generate a unique short code, please retry.")


def is_valid_vanity_slug(slug: str) -> bool:
    """3-32 chars, alphanumeric plus hyphen/underscore -- keeps slugs URL-safe
    and avoids collisions with reserved routes like /r/ itself."""
    return bool(_VANITY_PATTERN.match(slug))


def slug_is_available(slug: str) -> bool:
    return Link.query.filter_by(short_code=slug).first() is None

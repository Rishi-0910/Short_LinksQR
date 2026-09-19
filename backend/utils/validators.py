"""
Small, dependency-light validators. Kept as pure functions so they're easy
to unit test and reuse from both the API layer and (if ever needed) scripts.
"""
import re
from urllib.parse import urlsplit

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def is_valid_url(url: str) -> bool:
    if not url or _CONTROL_CHARS.search(url):
        return False
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            return False
    except ValueError:
        return False
    return True


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_PATTERN.match(email.strip()))


def is_valid_username(username: str) -> bool:
    return bool(username) and bool(_USERNAME_PATTERN.match(username.strip()))


def password_strength_errors(password: str) -> list[str]:
    """Returns a list of human-readable problems; empty list == acceptable."""
    errors = []
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("Password must include an uppercase letter.")
    if not re.search(r"[0-9]", password or ""):
        errors.append("Password must include a number.")
    return errors


def detect_device_type(user_agent: str) -> str:
    """Very small heuristic classifier -- good enough for dashboard buckets
    without pulling in a full user-agent-parsing dependency."""
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "Tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "Mobile"
    return "Desktop"

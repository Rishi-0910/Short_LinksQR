"""
Spec 2A: "Redirection endpoint (GET /r/:shortCode): Returns 302 Found and
logs click events asynchronously."

The redirect is issued immediately; the click write happens in a background
thread so telemetry logging never adds latency to the user-facing hop. For
a production deployment this thread hand-off would become a queue/task
worker (e.g. Celery/RQ) -- the interface (`_log_click_async`) is written so
that swap only touches this one file.
"""
import threading
from flask import Blueprint, redirect, abort, request, current_app

from extensions import db, limiter
from models import Link, ClickEvent
from utils.security import hash_ip
from utils.validators import detect_device_type

redirect_bp = Blueprint("redirect", __name__)


def _log_click_async(app, link_id, referrer, device_type, ip_hash):
    def _write():
        # Needs its own app context since it runs outside the request cycle.
        with app.app_context():
            try:
                db.session.add(
                    ClickEvent(link_id=link_id, referrer=referrer or "Direct", device_type=device_type, ip_hash=ip_hash)
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Failed to record click event")
            finally:
                db.session.remove()

    threading.Thread(target=_write, daemon=True).start()


@redirect_bp.get("/r/<short_code>")
@limiter.limit(lambda: current_app.config["RATE_LIMIT_REDIRECT"])
def redirect_short_link(short_code):
    link = Link.query.filter_by(short_code=short_code).first()
    if not link:
        abort(404, description="This short link doesn't exist or has been removed.")

    # Capture everything we need from `request` BEFORE handing off to the
    # background thread -- the request context won't be alive there.
    referrer = request.referrer or "Direct"
    device_type = detect_device_type(request.headers.get("User-Agent", ""))
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    ip_hash = hash_ip(forwarded_for or request.remote_addr or "unknown")

    _log_click_async(current_app._get_current_object(), link.id, referrer, device_type, ip_hash)

    return redirect(link.original_url, code=302)

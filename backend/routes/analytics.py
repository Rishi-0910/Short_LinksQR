"""
Spec 2B: dashboard charts for total clicks over time, top referrers, and
device distribution -- aggregated either across all of a user's links or
scoped to one link via ?linkId=.
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from extensions import db
from models import Link, ClickEvent
from utils.deco import require_auth

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _owned_link_ids(link_id_filter=None):
    query = g.current_user.links.with_entities(Link.id)
    if link_id_filter:
        query = query.filter(Link.id == link_id_filter)
    return [row[0] for row in query.all()]


@analytics_bp.get("/overview")
@require_auth
def overview():
    link_id = request.args.get("linkId")
    days = _bounded_int(request.args.get("days"), 30, 1, 365)

    link_ids = _owned_link_ids(link_id)
    if link_id and not link_ids:
        return jsonify(error="not_found", message="Link not found."), 404
    if not link_ids:
        return jsonify(
            totalClicks=0,
            clicksOverTime=[],
            topReferrers=[],
            deviceDistribution={d: 0 for d in ("Mobile", "Desktop", "Tablet")},
            rangeDays=days,
        ), 200

    since = datetime.utcnow() - timedelta(days=days)
    base = ClickEvent.query.filter(ClickEvent.link_id.in_(link_ids), ClickEvent.timestamp >= since)

    # --- Total clicks over time (daily buckets) ---
    daily_rows = (
        base.with_entities(func.date(ClickEvent.timestamp).label("day"), func.count().label("count"))
        .group_by("day")
        .order_by("day")
        .all()
    )
    clicks_over_time = [{"date": str(r.day), "clicks": r.count} for r in daily_rows]

    # --- Top referrers ---
    referrer_rows = (
        base.with_entities(ClickEvent.referrer, func.count().label("count"))
        .group_by(ClickEvent.referrer)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    top_referrers = [{"referrer": r[0] or "Direct", "clicks": r[1]} for r in referrer_rows]

    # --- Device distribution ---
    device_rows = (
        base.with_entities(ClickEvent.device_type, func.count().label("count")).group_by(ClickEvent.device_type).all()
    )
    device_distribution = {d: 0 for d in ("Mobile", "Desktop", "Tablet")}
    for device, count in device_rows:
        device_distribution[device] = count

    return jsonify(
        totalClicks=base.count(),
        clicksOverTime=clicks_over_time,
        topReferrers=top_referrers,
        deviceDistribution=device_distribution,
        rangeDays=days,
    ), 200

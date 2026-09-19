from datetime import date
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from extensions import db
from models import Application, UsageRecord, Settings
from utils import fmt_minutes

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


def _get_settings():
    settings = Settings.query.get(1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


@alerts_bp.route("", methods=["GET"])
def get_alerts():
    settings = _get_settings()
    today = date.today()

    total_today = (
        db.session.query(func.sum(UsageRecord.minutes))
        .filter(UsageRecord.date == today)
        .scalar()
        or 0
    )
    limit = settings.global_daily_limit_minutes or 1
    pct_used = round(min(total_today / limit, 1.5) * 100)

    per_app_limits = []
    for app in Application.query.filter(Application.daily_limit_minutes.isnot(None)):
        used = (
            db.session.query(func.sum(UsageRecord.minutes))
            .filter(UsageRecord.application_id == app.id, UsageRecord.date == today)
            .scalar()
            or 0
        )
        ratio = used / app.daily_limit_minutes if app.daily_limit_minutes else 0
        status = "Exceeded" if ratio >= 1 else "At risk" if ratio >= 0.8 else "On track"
        per_app_limits.append(
            {
                "application_id": app.id,
                "name": app.name,
                "color": app.color,
                "limit_minutes": app.daily_limit_minutes,
                "limit_display": fmt_minutes(app.daily_limit_minutes),
                "used_minutes": round(used, 1),
                "used_display": fmt_minutes(used),
                "status": status,
            }
        )

    return jsonify(
        {
            "global_limit_minutes": settings.global_daily_limit_minutes,
            "global_limit_display": fmt_minutes(settings.global_daily_limit_minutes),
            "used_today_minutes": round(total_today, 1),
            "used_today_display": fmt_minutes(total_today),
            "pct_used": pct_used,
            "notifications": {
                "popup": settings.notif_popup,
                "system": settings.notif_system,
                "sound": settings.notif_sound,
            },
            "per_app_limits": per_app_limits,
        }
    )


@alerts_bp.route("/global", methods=["PATCH"])
def update_global_limit():
    settings = _get_settings()
    payload = request.get_json(force=True)
    settings.global_daily_limit_minutes = int(payload["minutes"])
    db.session.commit()
    return jsonify({"global_limit_minutes": settings.global_daily_limit_minutes})


@alerts_bp.route("/notifications", methods=["PATCH"])
def update_notifications():
    settings = _get_settings()
    payload = request.get_json(force=True)
    for field in ("notif_popup", "notif_system", "notif_sound"):
        if field in payload:
            setattr(settings, field, bool(payload[field]))
    db.session.commit()
    return jsonify(
        {
            "popup": settings.notif_popup,
            "system": settings.notif_system,
            "sound": settings.notif_sound,
        }
    )


@alerts_bp.route("/app-limit/<int:app_id>", methods=["PATCH"])
def update_app_limit(app_id):
    app_row = Application.query.get_or_404(app_id)
    payload = request.get_json(force=True)
    app_row.daily_limit_minutes = payload.get("minutes")  # None clears the limit
    db.session.commit()
    return jsonify(app_row.to_dict())

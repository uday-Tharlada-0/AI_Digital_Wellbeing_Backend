from datetime import date
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from extensions import db
from models import Application, UsageRecord
from utils import fmt_minutes, date_range

applications_bp = Blueprint("applications", __name__, url_prefix="/api/applications")


def _serialize(app: Application):
    today = date.today()
    week_start = date_range(7)[0]

    today_minutes = (
        db.session.query(func.sum(UsageRecord.minutes))
        .filter(UsageRecord.application_id == app.id, UsageRecord.date == today)
        .scalar()
        or 0
    )
    week_minutes = (
        db.session.query(func.sum(UsageRecord.minutes))
        .filter(
            UsageRecord.application_id == app.id, UsageRecord.date >= week_start
        )
        .scalar()
        or 0
    )
    weekly_avg = week_minutes / 7

    data = app.to_dict()
    data.update(
        {
            "today_minutes": round(today_minutes, 1),
            "today_display": fmt_minutes(today_minutes),
            "weekly_avg_minutes": round(weekly_avg, 1),
            "weekly_avg_display": fmt_minutes(weekly_avg),
            "limit_display": fmt_minutes(app.daily_limit_minutes)
            if app.daily_limit_minutes
            else "No limit",
        }
    )
    return data


@applications_bp.route("", methods=["GET"])
def list_applications():
    category = request.args.get("category")
    status = request.args.get("status")  # productive | leisure | hidden
    search = request.args.get("q", "").strip().lower()

    query = Application.query
    if category and category != "All Categories":
        query = query.filter(Application.category == category)
    if status == "productive":
        query = query.filter(Application.is_productive.is_(True))
    elif status == "leisure":
        query = query.filter(Application.is_productive.is_(False))
    elif status == "hidden":
        query = query.filter(Application.is_visible.is_(False))
    if search:
        query = query.filter(Application.name.ilike(f"%{search}%"))

    apps = query.order_by(Application.name).all()
    return jsonify([_serialize(a) for a in apps])


@applications_bp.route("", methods=["POST"])
def create_application():
    payload = request.get_json(force=True)
    if not payload.get("name"):
        return jsonify({"error": "name is required"}), 400
    if Application.query.filter_by(name=payload["name"]).first():
        return jsonify({"error": "application already exists"}), 409

    app_row = Application(
        name=payload["name"],
        category=payload.get("category", "Uncategorized"),
        color=payload.get("color", "#4a6cf7"),
        is_productive=bool(payload.get("is_productive", False)),
        is_visible=bool(payload.get("is_visible", True)),
        daily_limit_minutes=payload.get("daily_limit_minutes"),
    )
    db.session.add(app_row)
    db.session.commit()
    return jsonify(_serialize(app_row)), 201


@applications_bp.route("/<int:app_id>", methods=["PATCH"])
def update_application(app_id):
    app_row = Application.query.get_or_404(app_id)
    payload = request.get_json(force=True)

    for field in (
        "category",
        "color",
        "is_productive",
        "is_visible",
        "daily_limit_minutes",
    ):
        if field in payload:
            setattr(app_row, field, payload[field])

    db.session.commit()
    return jsonify(_serialize(app_row))


@applications_bp.route("/<int:app_id>", methods=["DELETE"])
def delete_application(app_id):
    app_row = Application.query.get_or_404(app_id)
    db.session.delete(app_row)
    db.session.commit()
    return jsonify({"deleted": app_id})


@applications_bp.route("/<int:app_id>/log-usage", methods=["POST"])
def log_usage(app_id):
    """Increment today's usage for an app by N minutes.
    In a real desktop deployment this is called by the native tracking
    process (foreground-window watcher) every polling interval."""
    Application.query.get_or_404(app_id)
    minutes = float(request.get_json(force=True).get("minutes", 0))
    today = date.today()

    record = UsageRecord.query.filter_by(application_id=app_id, date=today).first()
    if record:
        record.minutes += minutes
    else:
        record = UsageRecord(application_id=app_id, date=today, minutes=minutes)
        db.session.add(record)
    db.session.commit()
    return jsonify({"application_id": app_id, "date": today.isoformat(), "minutes": record.minutes})

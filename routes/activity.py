from datetime import date
from flask import Blueprint, jsonify, request, session
from sqlalchemy import or_
from urllib.error import HTTPError, URLError

from activitywatch_service import aggregate_events, ingest_events, sync_activitywatch
from extensions import db
from models import ActivityEvent, Application, HourlyActivity, UsageRecord


activity_bp = Blueprint("activity", __name__, url_prefix="/api/activity")
REVIEW_APPS = {"ChatGPT", "Google Chrome", "Microsoft Edge", "Spotify", "YouTube", "Slack", "Discord"}
ALLOWED_CATEGORIES = {"Development", "Study", "Work", "Communication", "Entertainment", "Design", "Browsing", "Personal", "Background", "System", "Other"}


def _mobile_app_profile(name):
    normalized = name.lower()
    if any(value in normalized for value in ("youtube", "netflix", "spotify", "instagram", "games")):
        return "Entertainment", False
    if any(value in normalized for value in ("chrome", "browser", "edge", "firefox")):
        return "Browsing", False
    if any(value in normalized for value in ("code", "androidstudio", "github", "docs")):
        return "Development", True
    return "Other", False


@activity_bp.post("/sync")
def sync():
    payload = request.get_json(silent=True) or {}
    try:
        result = sync_activitywatch(session["user_id"], payload.get("base_url", "http://localhost:5600"))
        return jsonify(result)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return jsonify({"error": f"Could not connect to ActivityWatch: {exc}"}), 502


@activity_bp.post("/ingest")
def ingest():
    payload = request.get_json(force=True)
    return jsonify(ingest_events(session["user_id"], payload)), 201


@activity_bp.post("/mobile-sync")
def mobile_sync():
    """Store the Android UsageStats snapshot in the shared analytics tables."""
    payload = request.get_json(force=True) or {}
    apps = payload.get("apps", [])
    if not isinstance(apps, list):
        return jsonify({"error": "apps must be a list."}), 400

    tracked_date = date.today()
    user_id = session["user_id"]
    # A real mobile account must never inherit the seeded demo timeline.
    had_demo = UsageRecord.query.filter(UsageRecord.user_id.is_(None)).first() is not None
    UsageRecord.query.filter(UsageRecord.user_id.is_(None)).delete(synchronize_session=False)
    if had_demo:
        HourlyActivity.query.delete(synchronize_session=False)
    UsageRecord.query.filter_by(user_id=user_id, date=tracked_date, source="mobile").delete(
        synchronize_session=False
    )
    synced = []
    for item in apps:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("package_name") or "").strip()[:120]
        minutes = float(item.get("minutes", 0) or 0)
        if not name or minutes < 0 or minutes > 1440:
            return jsonify({"error": "Each app needs a valid name and minutes value."}), 400

        application = Application.query.filter_by(name=name).first()
        if not application:
            category, productive = _mobile_app_profile(name)
            application = Application(
                name=name,
                category=category,
                is_productive=productive,
                color="#4a6cf7",
            )
            db.session.add(application)
            db.session.flush()
        elif application.category in {"Uncategorized", "Other"}:
            category, productive = _mobile_app_profile(name)
            application.category = category
            application.is_productive = productive

        record = UsageRecord.query.filter_by(
            application_id=application.id,
            date=tracked_date,
            user_id=user_id,
            source="mobile",
        ).first()
        if record:
            record.minutes = minutes
        else:
            db.session.add(UsageRecord(
                application_id=application.id,
                user_id=user_id,
                date=tracked_date,
                minutes=minutes,
                source="mobile",
            ))
        synced.append({"name": name, "minutes": round(minutes, 1)})

    db.session.commit()
    return jsonify({"date": tracked_date.isoformat(), "synced": synced})


@activity_bp.get("/mobile-apps")
def mobile_apps():
    rows = (
        db.session.query(Application)
        .join(UsageRecord, UsageRecord.application_id == Application.id)
        .filter(UsageRecord.user_id == session["user_id"], UsageRecord.source == "mobile")
        .distinct()
        .order_by(Application.name)
        .all()
    )
    return jsonify([app.to_dict() for app in rows])


@activity_bp.patch("/mobile-apps/<int:app_id>")
def classify_mobile_app(app_id):
    app = Application.query.get_or_404(app_id)
    payload = request.get_json(force=True) or {}
    category = str(payload.get("category", app.category)).strip()
    if category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "Invalid category."}), 400
    app.category = category
    app.is_productive = bool(payload.get("is_productive", category in {"Development", "Study", "Work", "Design"}))
    if "daily_limit_minutes" in payload:
        app.daily_limit_minutes = payload["daily_limit_minutes"]
    db.session.commit()
    return jsonify(app.to_dict())


@activity_bp.get("/events")
def events():
    rows = ActivityEvent.query.filter_by(user_id=session["user_id"]).order_by(ActivityEvent.start_time.desc()).limit(200).all()
    return jsonify([
        {
            "application_name": row.application_name,
            "website": row.website,
            "category": row.user_category or row.category,
            "detected_category": row.category,
            "purpose": row.purpose,
            "is_background_audio": row.is_background_audio,
            "classification_source": row.classification_source,
            "start_time": row.start_time.isoformat(),
            "end_time": row.end_time.isoformat(),
            "duration_seconds": row.duration_seconds,
        }
        for row in rows
    ])


@activity_bp.get("/review")
def review_events():
    rows = ActivityEvent.query.filter(
        ActivityEvent.user_id == session["user_id"],
        ActivityEvent.user_category.is_(None),
        or_(ActivityEvent.application_name.in_(REVIEW_APPS), ActivityEvent.category == "Uncategorized"),
    ).order_by(ActivityEvent.start_time.desc()).all()
    grouped = {}
    for row in rows:
        key = (row.application_name, row.website or "", row.category)
        group = grouped.setdefault(
            key,
            {
                "id": row.id,
                "application_name": row.application_name,
                "website": row.website,
                "detected_category": row.category,
                "start_time": row.start_time,
                "duration_minutes": 0,
                "event_count": 0,
                "is_background_audio": row.is_background_audio,
            },
        )
        group["duration_minutes"] += row.duration_seconds / 60
        group["event_count"] += 1
    return jsonify([
        {
            **group,
            "start_time": group["start_time"].isoformat(),
            "duration_minutes": round(group["duration_minutes"], 1),
        }
        for group in list(grouped.values())[:50]
    ])


@activity_bp.patch("/events/<int:event_id>/classify")
def classify_event(event_id):
    row = ActivityEvent.query.filter_by(id=event_id, user_id=session["user_id"]).first_or_404()
    payload = request.get_json(force=True)
    category = str(payload.get("category", "")).strip()
    purpose = str(payload.get("purpose", "")).strip()
    is_background_audio = bool(payload.get("is_background_audio", False))
    if category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "Invalid category."}), 400
    matching_events = ActivityEvent.query.filter_by(
        user_id=session["user_id"],
        application_name=row.application_name,
        website=row.website,
        category=row.category,
        user_category=None,
    ).all()
    affected_dates = {event.start_time.date() for event in matching_events}
    for event in matching_events:
        event.user_category = category
        event.purpose = purpose[:120] or None
        event.is_background_audio = is_background_audio
        event.classification_source = "user"
    application = Application.query.filter_by(name=row.application_name).first()
    if application:
        application.category = category
        application.is_productive = category in {"Development", "Study", "Work", "Communication", "Design"}
    db.session.commit()
    for affected_date in affected_dates:
        if application:
            UsageRecord.query.filter_by(
                date=affected_date,
                application_id=application.id,
                user_id=session["user_id"],
                source="desktop",
            ).delete(synchronize_session=False)
        HourlyActivity.query.filter_by(date=affected_date).delete(synchronize_session=False)
    aggregate_events(session["user_id"])
    db.session.commit()
    return jsonify({"id": row.id, "category": category, "purpose": row.purpose, "is_background_audio": is_background_audio})
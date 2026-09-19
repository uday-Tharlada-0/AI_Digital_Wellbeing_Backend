from datetime import date, datetime, timedelta
from flask import Blueprint, jsonify, request

from extensions import db
from models import FocusSession
from utils import date_range

focus_bp = Blueprint("focus", __name__, url_prefix="/api/focus")

PRESETS = {"Deep Work": 60, "Quick Task": 25, "Reading": 45}


@focus_bp.route("/sessions", methods=["GET"])
def list_sessions():
    day = request.args.get("date")
    the_date = date.fromisoformat(day) if day else date.today()
    sessions = (
        FocusSession.query.filter(FocusSession.date == the_date)
        .order_by(FocusSession.start_time)
        .all()
    )
    return jsonify([s.to_dict() for s in sessions])


@focus_bp.route("/sessions/start", methods=["POST"])
def start_session():
    payload = request.get_json(force=True)
    session_type = payload.get("session_type", "Deep Work")
    planned_minutes = int(payload.get("planned_minutes", PRESETS.get(session_type, 60)))

    session = FocusSession(
        session_type=session_type,
        date=date.today(),
        planned_minutes=planned_minutes,
        start_time=datetime.utcnow(),
        completed=False,
    )
    db.session.add(session)
    db.session.commit()
    return jsonify(session.to_dict()), 201


@focus_bp.route("/sessions/<int:session_id>/complete", methods=["POST"])
def complete_session(session_id):
    session = FocusSession.query.get_or_404(session_id)
    payload = request.get_json(force=True) if request.data else {}
    session.end_time = datetime.utcnow()
    session.actual_minutes = payload.get(
        "actual_minutes", session.planned_minutes
    )
    session.completed = True
    db.session.commit()
    return jsonify(session.to_dict())


@focus_bp.route("/trend", methods=["GET"])
def trend():
    days = int(request.args.get("days", 7))
    out = []
    for d in date_range(days):
        count = FocusSession.query.filter(
            FocusSession.date == d, FocusSession.completed.is_(True)
        ).count()
        out.append({"date": d.isoformat(), "label": d.strftime("%a"), "sessions": count})
    return jsonify(out)

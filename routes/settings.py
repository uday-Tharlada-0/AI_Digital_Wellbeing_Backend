from flask import Blueprint, jsonify, request
from extensions import db
from models import Settings

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _get_settings():
    settings = Settings.query.get(1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


@settings_bp.route("", methods=["GET"])
def get_settings():
    return jsonify(_get_settings().to_dict())


@settings_bp.route("", methods=["PATCH"])
def update_settings():
    settings = _get_settings()
    payload = request.get_json(force=True)
    editable = {
        "theme_mode",
        "accent_color",
        "language",
        "launch_at_startup",
        "launch_minimized",
        "minimize_to_tray",
        "idle_detection",
        "notif_popup",
        "notif_system",
        "notif_sound",
        "global_daily_limit_minutes",
    }
    for field in editable & payload.keys():
        setattr(settings, field, payload[field])
    db.session.commit()
    return jsonify(settings.to_dict())

from datetime import date
from flask import Blueprint, jsonify, request

from extensions import db
from models import Application, UsageRecord
from mobile_auth import verify_mobile_token


mobile_bp = Blueprint("mobile", __name__, url_prefix="/api/mobile")


def get_mobile_user_id():
    """Get the authenticated user ID from the Bearer token."""

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()

    if not token:
        return None

    return verify_mobile_token(token)
@mobile_bp.get("/me")
def get_mobile_user():
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    from models import User

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found."
        }), 404

    return jsonify({
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email
    }), 200


@mobile_bp.post("/usage")
def upload_usage():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    data = request.get_json(silent=True) or {}

    usage_date = data.get("date")
    apps = data.get("apps")

    if not usage_date:
        return jsonify({
            "error": "date is required."
        }), 400

    if not isinstance(apps, list):
        return jsonify({
            "error": "apps must be a list."
        }), 400

    try:
        usage_date = date.fromisoformat(usage_date)
    except ValueError:
        return jsonify({
            "error": "date must use YYYY-MM-DD format."
        }), 400

    saved_apps = []

    for item in apps:

        app_name = str(item.get("app_name", "")).strip()
        package_name = str(item.get("package_name", "")).strip()
        minutes = float(item.get("minutes", 0))

        if not app_name or not package_name:
            continue

        if minutes < 0:
            continue

        application = Application.query.filter_by(
    package_name=package_name
).first()

        if not application:
            application = Application.query.filter(
        db.func.lower(Application.name) == app_name.lower()
    ).first()

        if application:
            if not application.package_name:
                application.package_name = package_name
        else:
            application = Application(
        name=app_name,
        package_name=package_name,
        category="Uncategorized",
        is_productive=False,
        is_visible=True
    )

        db.session.add(application)
        db.session.flush()

        record = UsageRecord.query.filter_by(
            user_id=user_id,
            application_id=application.id,
            date=usage_date,
            source="android"
        ).first()

        if record:
            record.minutes = minutes
        else:
            record = UsageRecord(
                user_id=user_id,
                application_id=application.id,
                date=usage_date,
                minutes=minutes,
                source="android"
            )

            db.session.add(record)

        saved_apps.append({
            "application_id": application.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "minutes": round(minutes, 1)
        })

    db.session.commit()

    return jsonify({
        "message": "Usage uploaded successfully.",
        "user_id": user_id,
        "date": usage_date.isoformat(),
        "apps": saved_apps
    }), 200
@mobile_bp.get("/usage")
def get_mobile_usage():
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    usage_date = request.args.get("date")

    if usage_date:
        try:
            usage_date = date.fromisoformat(usage_date)
        except ValueError:
            return jsonify({
                "error": "date must use YYYY-MM-DD format."
            }), 400
    else:
        usage_date = date.today()

    records = (
        UsageRecord.query
        .filter_by(
            user_id=user_id,
            date=usage_date,
            source="android"
        )
        .all()
    )

    apps = []

    for record in records:

        application = Application.query.get(
            record.application_id
        )

        if not application:
            continue

        apps.append({
            "application_id": application.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "minutes": round(record.minutes, 1)
        })

    total_minutes = sum(
        app["minutes"] for app in apps
    )

    return jsonify({
        "user_id": user_id,
        "date": usage_date.isoformat(),
        "total_minutes": round(total_minutes, 1),
        "apps": apps
    }), 200
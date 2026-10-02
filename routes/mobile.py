from datetime import date,datetime, timezone, timedelta
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
@mobile_bp.get("/apps")
def get_mobile_apps():
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    applications = (
        Application.query
        .order_by(Application.name.asc())
        .all()
    )

    return jsonify({
        "apps": [
            {
                "application_id": app.id,
                "app_name": app.name,
                "package_name": app.package_name,
                "category": app.category,
                "is_productive": bool(app.is_productive)
            }
            for app in applications
        ]
    }), 200


@mobile_bp.patch("/apps/<int:application_id>")
def update_mobile_app_classification(application_id):
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    application = Application.query.get(application_id)

    if not application:
        return jsonify({
            "error": "Application not found."
        }), 404

    data = request.get_json(silent=True) or {}

    category = data.get("category")
    is_productive = data.get("is_productive")

    if category is not None:
        category = str(category).strip()

        if not category:
            return jsonify({
                "error": "category cannot be empty."
            }), 400

        if len(category) > 60:
            return jsonify({
                "error": "category must be 60 characters or less."
            }), 400

        application.category = category

    if is_productive is not None:

        if not isinstance(is_productive, bool):
            return jsonify({
                "error": "is_productive must be true or false."
            }), 400

        application.is_productive = is_productive

    db.session.commit()

    return jsonify({
        "message": "Application classification updated successfully.",
        "app": {
            "application_id": application.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "category": application.category,
            "is_productive": bool(application.is_productive)
        }
    }), 200
@mobile_bp.post("/sessions")
def upload_usage_sessions():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    data = request.get_json(silent=True) or {}

    sessions = data.get("sessions")

    if not isinstance(sessions, list):
        return jsonify({
            "error": "sessions must be a list."
        }), 400

    from models import UsageSession

    saved_sessions = []

    for item in sessions:

        app_name = str(
            item.get("app_name", "")
        ).strip()

        package_name = str(
            item.get("package_name", "")
        ).strip()

        start_time = item.get("start_time")
        end_time = item.get("end_time")

        if not app_name or not package_name:
            continue

        if not start_time or not end_time:
            continue

        try:
            start_time = datetime.fromisoformat(
            str(start_time).replace("Z", "+00:00")
            )

            end_time = datetime.fromisoformat(
            str(end_time).replace("Z", "+00:00")
     )

    # Android sends UTC timestamps.
    # Store them as naive IST timestamps.
            ist = timezone(timedelta(hours=5, minutes=30))

            start_time = start_time.astimezone(ist).replace(tzinfo=None)
            end_time = end_time.astimezone(ist).replace(tzinfo=None)

        except ValueError:
            continue

        if end_time <= start_time:
            continue

        minutes = (
            end_time - start_time
        ).total_seconds() / 60

        if minutes < 1:
            continue

        # Find existing application
        application = Application.query.filter_by(
            package_name=package_name
        ).first()

        if not application:
            application = Application.query.filter(
                db.func.lower(Application.name)
                == app_name.lower()
            ).first()

        # Create application if needed
        if not application:

            application = Application(
                name=app_name,
                package_name=package_name,
                category="Uncategorized",
                is_productive=False,
                is_visible=True
            )

            db.session.add(application)
            db.session.flush()

        elif not application.package_name:

            application.package_name = package_name

        # -------------------------------------------------
        # DUPLICATE SESSION CHECK
        # -------------------------------------------------

        existing_session = UsageSession.query.filter_by(
            user_id=user_id,
            application_id=application.id,
            start_time=start_time,
            end_time=end_time
        ).first()

        if existing_session:
            # Already uploaded.
            # Do NOT create another copy.
            continue

        # -------------------------------------------------
        # CREATE NEW SESSION
        # -------------------------------------------------

        session = UsageSession(
            user_id=user_id,
            application_id=application.id,
            start_time=start_time,
            end_time=end_time,
            minutes=round(minutes, 1),
            category=None,
            is_productive=None,
            classification_status="unclassified"
        )

        db.session.add(session)

        saved_sessions.append({
            "application_id": application.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "minutes": round(minutes, 1),
            "classification_status": "unclassified"
        })

    db.session.commit()

    return jsonify({
        "message": "Usage sessions uploaded successfully.",
        "user_id": user_id,
        "saved_count": len(saved_sessions),
        "sessions": saved_sessions
    }), 200
@mobile_bp.get("/sessions")
def get_usage_sessions():
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    date_string = request.args.get("date")

    if date_string:
        try:
            usage_date = date.fromisoformat(date_string)
        except ValueError:
            return jsonify({
                "error": "Invalid date format. Use YYYY-MM-DD."
            }), 400
    else:
        usage_date = date.today()

    from models import UsageSession, Application

    sessions = (
        db.session.query(UsageSession, Application)
        .join(
            Application,
            UsageSession.application_id == Application.id
        )
        .filter(
            UsageSession.user_id == user_id,
            db.func.date(UsageSession.start_time) == usage_date
        )
        .order_by(UsageSession.start_time.asc())
        .all()
    )

    result = []

    for session, application in sessions:
        result.append({
            "id": session.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat(),
            "minutes": round(session.minutes, 1),
            "category": session.category,
            "is_productive": session.is_productive,
            "classification_status": session.classification_status
        })

    return jsonify({
        "date": usage_date.isoformat(),
        "session_count": len(result),
        "sessions": result
    }), 200
@mobile_bp.patch("/sessions/<int:session_id>")
def classify_usage_session(session_id):
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    from models import UsageSession

    session = UsageSession.query.filter_by(
        id=session_id,
        user_id=user_id
    ).first()

    if not session:
        return jsonify({
            "error": "Usage session not found."
        }), 404

    data = request.get_json(silent=True) or {}

    category = data.get("category")
    is_productive = data.get("is_productive")

    if category is None or is_productive is None:
        return jsonify({
            "error": "category and is_productive are required."
        }), 400

    if not isinstance(category, str) or not category.strip():
        return jsonify({
            "error": "category must be a non-empty string."
        }), 400

    if not isinstance(is_productive, bool):
        return jsonify({
            "error": "is_productive must be true or false."
        }), 400

    session.category = category.strip()
    session.is_productive = is_productive
    session.classification_status = "classified"

    db.session.commit()

    return jsonify({
        "message": "Usage session classified successfully.",
        "session": {
            "id": session.id,
            "category": session.category,
            "is_productive": session.is_productive,
            "classification_status": session.classification_status
        }
    }), 200
@mobile_bp.get("/debug/duplicate-sessions")
def debug_duplicate_sessions():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    from models import UsageSession
    from sqlalchemy import func

    duplicate_groups = (
        db.session.query(
            UsageSession.application_id,
            UsageSession.start_time,
            UsageSession.end_time,
            func.count(UsageSession.id).label("count")
        )
        .filter(
            UsageSession.user_id == user_id
        )
        .group_by(
            UsageSession.application_id,
            UsageSession.start_time,
            UsageSession.end_time
        )
        .having(
            func.count(UsageSession.id) > 1
        )
        .all()
    )

    return jsonify({
        "duplicate_group_count": len(duplicate_groups),
        "groups": [
            {
                "application_id": group.application_id,
                "start_time": group.start_time.isoformat(),
                "end_time": group.end_time.isoformat(),
                "count": group.count
            }
            for group in duplicate_groups
        ]
    }), 200
@mobile_bp.post("/debug/cleanup-duplicate-sessions")
def cleanup_duplicate_sessions():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    from models import UsageSession

    sessions = (
        UsageSession.query
        .filter_by(user_id=user_id)
        .order_by(
            UsageSession.application_id,
            UsageSession.start_time,
            UsageSession.end_time,
            UsageSession.id
        )
        .all()
    )

    groups = {}

    for session in sessions:

        key = (
            session.application_id,
            session.start_time,
            session.end_time
        )

        groups.setdefault(key, []).append(session)

    deleted_ids = []
    kept_ids = []

    for key, group in groups.items():

        if len(group) <= 1:
            continue

        # Prefer a classified session.
        classified = [
            session
            for session in group
            if session.classification_status == "classified"
        ]

        if classified:
            keep = classified[0]
        else:
            keep = group[0]

        kept_ids.append(keep.id)

        for session in group:

            if session.id == keep.id:
                continue

            deleted_ids.append(session.id)
            db.session.delete(session)

    db.session.commit()

    return jsonify({
        "message": "Duplicate session cleanup completed.",
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "kept_ids": kept_ids
    }), 200
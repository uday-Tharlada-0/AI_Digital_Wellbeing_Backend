from datetime import date, timedelta

from flask import Blueprint, jsonify

from extensions import db
from models import Application, UsageRecord,UsageSession
from mobile_auth import verify_mobile_token
from flask import request


mobile_analytics_bp = Blueprint(
    "mobile_analytics",
    __name__,
    url_prefix="/api/mobile/analytics"
)


def get_mobile_user_id():
    """Get the authenticated user ID from the Bearer token."""

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()

    if not token:
        return None

    return verify_mobile_token(token)


def get_usage_for_date(user_id, usage_date):
    records = UsageRecord.query.filter_by(
        user_id=user_id,
        date=usage_date,
        source="android"
    ).all()

    apps = []

    for record in records:
        application = Application.query.get(record.application_id)

        if not application:
            continue

        minutes = round(record.minutes, 1)

        apps.append({
            "application_id": application.id,
            "app_name": application.name,
            "package_name": application.package_name,
            "minutes": minutes,
            "category": application.category,
            "is_productive": bool(application.is_productive)
        })

    apps.sort(
        key=lambda app: app["minutes"],
        reverse=True
    )

    total_minutes = sum(
        app["minutes"] for app in apps
    )

       # -------------------------------------------------
    # Session-level productivity
    # -------------------------------------------------

    sessions = UsageSession.query.filter(
        UsageSession.user_id == user_id,
        db.func.date(UsageSession.start_time) == usage_date
    ).all()

    classified_sessions = [
        session for session in sessions
        if session.is_productive is not None
    ]

    if sessions:
        # When session data exists, use sessions as the
        # source of truth.
        total_minutes = sum(
    record.minutes for record in records
        )

        productive_minutes = sum(
            session.minutes
            for session in classified_sessions
            if session.is_productive is True
        )

        # Build app usage from sessions.
        session_apps = {}

        for session in sessions:
            application = Application.query.get(
                session.application_id
            )

            if not application:
                continue

            if application.id not in session_apps:
                session_apps[application.id] = {
                    "application_id": application.id,
                    "app_name": application.name,
                    "package_name": application.package_name,
                    "minutes": 0.0,
                    "category": session.category,
                    "is_productive": session.is_productive
                }

            session_apps[application.id]["minutes"] += session.minutes

            # Prefer a classified session's information.
            if session.classification_status == "classified":
                session_apps[application.id]["category"] = session.category
                session_apps[application.id]["is_productive"] = session.is_productive

        apps = list(session_apps.values())

        for app in apps:
            app["minutes"] = round(app["minutes"], 1)

        apps.sort(
            key=lambda app: app["minutes"],
            reverse=True
        )

    else:
        # No session data yet: keep the existing
        # daily UsageRecord behaviour.
        productive_minutes = sum(
            record.minutes
            for record in records
            if (
                Application.query.get(record.application_id)
                and Application.query.get(record.application_id).is_productive
            )
        )

    productivity_score = (
        round((productive_minutes / total_minutes) * 100)
        if total_minutes > 0
        else 0
    )

    return (
        total_minutes,
        apps,
        productive_minutes,
        productivity_score
    )


@mobile_analytics_bp.get("")
def get_mobile_analytics():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    today = date.today()

    yesterday = today - timedelta(days=1)

    today_total, today_apps, today_productive, today_score = get_usage_for_date(
    user_id,
    today
)

    yesterday_total, yesterday_apps, yesterday_productive, yesterday_score = get_usage_for_date(
    user_id,
    yesterday
)
    # Calculate change from yesterday.

    if yesterday_total > 0:
        change_percent = round(
            ((today_total - yesterday_total) / yesterday_total) * 100,
            1
        )
    else:
        change_percent = None

    # Create factual insights.

    insights = []

    if today_total > 0:

        hours = int(today_total // 60)
        minutes = int(today_total % 60)

        if hours > 0:
            time_text = f"{hours}h {minutes}m"
        else:
            time_text = f"{minutes}m"

        insights.append(
            f"You have used your phone for {time_text} today."
        )

    if today_apps:

        top_app = today_apps[0]

        insights.append(
            f"{top_app['app_name']} is your most-used app today "
            f"at {round(top_app['minutes'], 1)} minutes."
        )

    if change_percent is not None:

        if change_percent > 0:
            insights.append(
                f"Today's total usage is {abs(change_percent)}% "
                f"higher than yesterday."
            )

        elif change_percent < 0:
            insights.append(
                f"Today's total usage is {abs(change_percent)}% "
                f"lower than yesterday."
            )

        else:
            insights.append(
                "Today's total usage is the same as yesterday."
            )

    if not insights:

        insights.append(
            "Not enough usage data yet."
        )

    return jsonify({
        "date": today.isoformat(),

        "total_minutes": round(today_total, 1),
        "productive_minutes": round(today_productive, 1),

        "productivity_score": today_score,

        "app_count": len(today_apps),

        "top_apps": today_apps[:5],

        "yesterday_minutes": round(
            yesterday_total,
            1
        ),

        "change_percent": change_percent,

        "insights": insights
    }), 200
@mobile_analytics_bp.get("/prediction")
def get_mobile_prediction():
    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({"error": "Invalid or missing authentication token."}), 401

    try:
        from ml import predictor

        result = predictor.forecast(days=1, auto_train=True)

        forecast = result.get("forecast", [])

        if not forecast:
            return jsonify({
                "error": "No prediction available."
            }), 422

        tomorrow = forecast[0]

        return jsonify({
            "today": {
                "total_minutes": result.get("today_total_minutes", 0),
                "productivity_score": result.get("today_productivity_score", 0)
            },
            "tomorrow": {
                "date": tomorrow.get("date"),
                "predicted_productive_minutes": tomorrow.get(
                    "predicted_productive_minutes", 0
                ),
                "predicted_total_minutes": tomorrow.get(
                    "predicted_total_minutes", 0
                ),
                "predicted_productivity_score": tomorrow.get(
                    "predicted_productivity_score", 0
                )
            }
        }), 200

    except predictor.ModelNotTrainedError as e:
        return jsonify({"error": str(e)}), 409

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 422
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from models import UsageRecord, Application
from mobile_auth import verify_mobile_token


mobile_suggestions_bp = Blueprint(
    "mobile_suggestions",
    __name__,
    url_prefix="/api/mobile/suggestions"
)


def get_mobile_user_id():
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

        apps.append({
            "app_name": application.name,
            "package_name": application.package_name,
            "minutes": round(record.minutes, 1)
        })

    apps.sort(key=lambda app: app["minutes"], reverse=True)

    total_minutes = sum(app["minutes"] for app in apps)

    return round(total_minutes, 1), apps


def get_tracked_days(user_id):
    records = (
        UsageRecord.query
        .filter_by(
            user_id=user_id,
            source="android"
        )
        .with_entities(UsageRecord.date)
        .distinct()
        .all()
    )

    return len(records)


@mobile_suggestions_bp.get("")
def get_mobile_suggestions():

    user_id = get_mobile_user_id()

    if not user_id:
        return jsonify({
            "error": "Invalid or missing authentication token."
        }), 401

    today = date.today()

    days_tracked = get_tracked_days(user_id)

    today_total, today_apps = get_usage_for_date(
        user_id,
        today
    )

    suggestions = []

    # Determine personalization level

    if days_tracked <= 1:
        personalization_level = "new_user"

    elif days_tracked < 7:
        personalization_level = "early"

    else:
        personalization_level = "personalized"

    # ---------------------------------------------------------
    # NEW USER / DAY 1
    # ---------------------------------------------------------

    if personalization_level == "new_user":

        suggestions.append({
            "type": "welcome",
            "title": "Welcome to Digital Wellbeing",
            "message": (
                "We're learning your phone usage patterns. "
                "As you use the app over the next few days, "
                "your insights will become more personalized."
            )
        })

        if today_total > 0:

            hours = int(today_total // 60)
            minutes = int(today_total % 60)

            if hours > 0:
                time_text = f"{hours}h {minutes}m"
            else:
                time_text = f"{minutes}m"

            suggestions.append({
                "type": "observation",
                "title": "Today's screen time",
                "message": (
                    f"You have recorded {time_text} of phone usage today."
                )
            })

        if today_apps:

            top_app = today_apps[0]

            suggestions.append({
                "type": "observation",
                "title": "Most-used app",
                "message": (
                    f"{top_app['app_name']} has the highest recorded "
                    f"usage today at {top_app['minutes']} minutes."
                )
            })

            suggestions.append({
                "type": "observation",
                "title": "Apps used today",
                "message": (
                    f"You have recorded usage across "
                    f"{len(today_apps)} apps today."
                )
            })

    # ---------------------------------------------------------
    # EARLY USER / 2-6 DAYS
    # ---------------------------------------------------------

    elif personalization_level == "early":

        suggestions.append({
            "type": "progress",
            "title": "Building your usage history",
            "message": (
                f"You have {days_tracked} tracked days. "
                "Keep using Digital Wellbeing so we can identify "
                "more meaningful patterns."
            )
        })

        if today_total > 0:

            hours = int(today_total // 60)
            minutes = int(today_total % 60)

            if hours > 0:
                time_text = f"{hours}h {minutes}m"
            else:
                time_text = f"{minutes}m"

            suggestions.append({
                "type": "observation",
                "title": "Today's screen time",
                "message": (
                    f"You have recorded {time_text} of phone usage today."
                )
            })

        if today_apps:

            top_app = today_apps[0]

            suggestions.append({
                "type": "observation",
                "title": "Most-used app today",
                "message": (
                    f"{top_app['app_name']} currently has the highest "
                    f"recorded usage at {top_app['minutes']} minutes."
                )
            })

    # ---------------------------------------------------------
    # PERSONALIZED USER / 7+ DAYS
    # ---------------------------------------------------------

    else:

        suggestions.append({
            "type": "progress",
            "title": "Your usage history is growing",
            "message": (
                f"You have {days_tracked} tracked days. "
                "We can now start identifying patterns in your usage."
            )
        })

        if today_total > 0:

            hours = int(today_total // 60)
            minutes = int(today_total % 60)

            if hours > 0:
                time_text = f"{hours}h {minutes}m"
            else:
                time_text = f"{minutes}m"

            suggestions.append({
                "type": "observation",
                "title": "Today's screen time",
                "message": (
                    f"You have recorded {time_text} of phone usage today."
                )
            })

        # Get the previous 7 calendar days

        historical_totals = []

        for days_ago in range(1, 8):

            historical_date = today - timedelta(days=days_ago)

            total, _ = get_usage_for_date(
                user_id,
                historical_date
            )

            if total > 0:
                historical_totals.append(total)

        if historical_totals:

            average_usage = round(
                sum(historical_totals) / len(historical_totals),
                1
            )

            if today_total > 0:

                difference = round(
                    today_total - average_usage,
                    1
                )

                if difference > 0:

                    suggestions.append({
                        "type": "comparison",
                        "title": "Compared with your recent usage",
                        "message": (
                            f"Today's recorded usage is {difference} minutes "
                            f"above your recent average of "
                            f"{average_usage} minutes."
                        )
                    })

                elif difference < 0:

                    suggestions.append({
                        "type": "comparison",
                        "title": "Compared with your recent usage",
                        "message": (
                            f"Today's recorded usage is "
                            f"{abs(difference)} minutes below your "
                            f"recent average of {average_usage} minutes."
                        )
                    })

                else:

                    suggestions.append({
                        "type": "comparison",
                        "title": "Compared with your recent usage",
                        "message": (
                            "Today's recorded usage is close to "
                            "your recent average."
                        )
                    })

        if today_apps:

            top_app = today_apps[0]

            suggestions.append({
                "type": "observation",
                "title": "Most-used app today",
                "message": (
                    f"{top_app['app_name']} has the highest recorded "
                    f"usage today at {top_app['minutes']} minutes."
                )
            })

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    return jsonify({
        "date": today.isoformat(),
        "days_tracked": days_tracked,
        "personalization_level": personalization_level,
        "total_minutes": today_total,
        "app_count": len(today_apps),
        "suggestions": suggestions
    }), 200
from datetime import date
from flask import Blueprint, jsonify, session
from sqlalchemy import func

from extensions import db
from models import Application, UsageRecord, FocusSession
from utils import fmt_minutes, productivity_score, date_range

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _day_totals(the_date):
    """Return (total_minutes, productive_minutes) for a given date."""
    rows = (
        db.session.query(UsageRecord.minutes, Application.is_productive)
        .join(Application, Application.id == UsageRecord.application_id)
        .filter(UsageRecord.date == the_date, UsageRecord.user_id == session["user_id"])
        .all()
    )
    total = sum(r[0] for r in rows)
    productive = sum(r[0] for r in rows if r[1])
    return total, productive


@dashboard_bp.route("/today", methods=["GET"])
def today_summary():
    today = date.today()
    yesterday_list = date_range(2)  # [yesterday, today]
    yesterday = yesterday_list[0]

    total_today, productive_today = _day_totals(today)
    total_yday, productive_yday = _day_totals(yesterday)

    score_today = productivity_score(productive_today, total_today)

    pct_change_total = (
        round(((total_today - total_yday) / total_yday) * 100) if total_yday else 0
    )
    pct_change_prod = (
        round(((productive_today - productive_yday) / productive_yday) * 100)
        if productive_yday
        else 0
    )

    # Most used apps today (top 5, visible only)
    top_apps = (
        db.session.query(Application, UsageRecord.minutes)
        .join(UsageRecord, UsageRecord.application_id == Application.id)
        .filter(UsageRecord.date == today, UsageRecord.user_id == session["user_id"], Application.is_visible.is_(True))
        .order_by(UsageRecord.minutes.desc())
        .limit(5)
        .all()
    )
    most_used = [
        {
            "name": app.name,
            "category": app.category,
            "color": app.color,
            "minutes": round(mins, 1),
            "display": fmt_minutes(mins),
        }
        for app, mins in top_apps
    ]

    # Weekly trend (last 7 days, productive vs leisure)
    week_days = date_range(7)
    weekly_trend = []
    for d in week_days:
        t, p = _day_totals(d)
        weekly_trend.append(
            {
                "date": d.isoformat(),
                "label": d.strftime("%a"),
                "productive_hours": round(p / 60, 2),
                "leisure_hours": round((t - p) / 60, 2),
                "total_hours": round(t / 60, 2),
            }
        )

    # Category breakdown (last 7 days)
    cat_rows = (
        db.session.query(Application.category, func.sum(UsageRecord.minutes))
        .join(UsageRecord, UsageRecord.application_id == Application.id)
        .filter(UsageRecord.date >= week_days[0], UsageRecord.user_id == session["user_id"])
        .group_by(Application.category)
        .all()
    )
    category_breakdown = [
        {"category": c, "minutes": round(m, 1)} for c, m in cat_rows if m
    ]

    # App usage bars (today, all visible apps)
    app_bars = (
        db.session.query(Application.name, Application.color, UsageRecord.minutes)
        .join(UsageRecord, UsageRecord.application_id == Application.id)
        .filter(UsageRecord.date == today, UsageRecord.user_id == session["user_id"], Application.is_visible.is_(True))
        .order_by(UsageRecord.minutes.desc())
        .all()
    )
    app_usage_bars = [
        {"name": n, "color": c, "minutes": round(m, 1)} for n, c, m in app_bars
    ]

    # Focus sessions today
    focus_today = FocusSession.query.filter(FocusSession.date == today).all()
    focus_minutes = sum((s.actual_minutes or 0) for s in focus_today)
    focus_count = len(focus_today)

    return jsonify(
        {
            "date": today.isoformat(),
            "total_screen_time": {
                "minutes": round(total_today, 1),
                "display": fmt_minutes(total_today),
                "pct_change_vs_yesterday": pct_change_total,
            },
            "productive_time": {
                "minutes": round(productive_today, 1),
                "display": fmt_minutes(productive_today),
                "pct_change_vs_yesterday": pct_change_prod,
            },
            "productivity_score": score_today,
            "focus_sessions_today": {
                "count": focus_count,
                "minutes": focus_minutes,
                "display": fmt_minutes(focus_minutes),
            },
            "most_used_applications": most_used,
            "weekly_trend": weekly_trend,
            "category_breakdown": category_breakdown,
            "app_usage_bars": app_usage_bars,
        }
    )

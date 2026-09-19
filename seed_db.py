"""
Seeds the database with default tracked applications and simulated
historical usage so the dashboard, analytics, and AI predictions all have
data to work with immediately.

Run once, before starting the server for the first time:
    python seed_db.py

Re-running is safe: it clears and regenerates usage history, but will not
duplicate application rows.
"""
import sys

from app import create_app
from extensions import db
from models import Application, UsageRecord, HourlyActivity, FocusSession, Settings
from app_catalog import DEFAULT_APPS
from ml.data_generator import generate_history

N_DAYS = 180


def seed(n_days=N_DAYS):
    app = create_app()
    with app.app_context():
        db.create_all()

        # --- Applications -------------------------------------------------
        name_to_app = {}
        for spec in DEFAULT_APPS:
            existing = Application.query.filter_by(name=spec["name"]).first()
            if existing:
                name_to_app[spec["name"]] = existing
                continue
            row = Application(
                name=spec["name"],
                category=spec["category"],
                color=spec["color"],
                is_productive=spec["is_productive"],
                is_visible=spec["is_visible"],
                daily_limit_minutes=spec["daily_limit_minutes"],
            )
            db.session.add(row)
            name_to_app[spec["name"]] = row
        db.session.commit()

        # --- Settings singleton --------------------------------------------
        if not Settings.query.get(1):
            db.session.add(Settings(id=1))
            db.session.commit()

        # --- Clear old generated history, then regenerate -------------------
        UsageRecord.query.delete()
        HourlyActivity.query.delete()
        FocusSession.query.delete()
        db.session.commit()

        history = generate_history(n_days=n_days)
        for day in history:
            for app_name, minutes in day["app_minutes"].items():
                db.session.add(
                    UsageRecord(
                        application_id=name_to_app[app_name].id,
                        date=day["date"],
                        minutes=minutes,
                    )
                )
            for hour, minutes in day["hourly_minutes"].items():
                db.session.add(
                    HourlyActivity(date=day["date"], hour=hour, minutes=minutes)
                )
            for session in day["focus_sessions"]:
                db.session.add(
                    FocusSession(
                        session_type=session["session_type"],
                        date=day["date"],
                        planned_minutes=session["planned_minutes"],
                        actual_minutes=session["actual_minutes"],
                        completed=session["completed"],
                    )
                )
        db.session.commit()

        print(f"Seeded {len(DEFAULT_APPS)} applications and {n_days} days of history.")
        print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_DAYS
    seed(n)

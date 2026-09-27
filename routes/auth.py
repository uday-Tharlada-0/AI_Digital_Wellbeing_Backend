import re

from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from extensions import db
from models import (
    Application,
    FocusSession,
    HourlyActivity,
    OnboardingProfile,
    UsageRecord,
    User,
)
from app_catalog import DEFAULT_APPS


auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _mobile_request():
    return request.headers.get("Accept") == "application/json"


def _validate_registration(data):
    name = str(data.get("name", "")).strip()
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not username or not email or not password:
        return "Name, username, email, and password are required."
    if len(username) < 3:
        return "Username must contain at least 3 characters."
    if not EMAIL_PATTERN.match(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if User.query.filter(or_(User.username == username, User.email == email)).first():
        return "That username or email is already registered."
    return None


def _login_user(user):
    session.clear()
    session["user_id"] = user.id
    session["user_name"] = user.name


def _needs_onboarding(user_id):
    return OnboardingProfile.query.filter_by(user_id=user_id).first() is None


def _onboarding_options():
    apps = Application.query.order_by(Application.id).all()
    if not apps:
        return DEFAULT_APPS
    return apps


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(
            or_(User.username == identifier, User.email == identifier)
        ).first()
        if not user or not user.check_password(password):
            error = "Incorrect username/email or password."
        else:
            _login_user(user)
            if _mobile_request():
                return jsonify({"user": user.to_dict()})
            destination = "auth.onboarding" if _needs_onboarding(user.id) else "index"
            return redirect(url_for(destination))

    if error and _mobile_request():
        return jsonify({"error": error}), 401
    return render_template("login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        data = request.form.to_dict()
        error = _validate_registration(data)
        if not error and data.get("password") != data.get("confirm_password"):
            error = "Passwords do not match."
        if error and _mobile_request():
            return jsonify({"error": error}), 400
        if not error:
            user = User(
                name=data["name"].strip(),
                username=data["username"].strip().lower(),
                email=data["email"].strip().lower(),
            )
            user.set_password(data["password"])
            db.session.add(user)
            db.session.commit()
            _login_user(user)
            if _mobile_request():
                return jsonify({"user": user.to_dict()}), 201
            return redirect(url_for("auth.onboarding"))

    return render_template("register.html", error=error)


@auth_bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    existing = OnboardingProfile.query.filter_by(user_id=user_id).first()
    apps = _onboarding_options()
    error = None

    if request.method == "POST":
        try:
            daily_screen_minutes = int(request.form.get("daily_screen_minutes", "0"))
            productive_minutes = int(request.form.get("productive_minutes", "0"))
            focus_minutes = int(request.form.get("focus_minutes", "0"))
            if not 0 <= daily_screen_minutes <= 1440:
                raise ValueError("Daily screen time must be between 0 and 1440 minutes.")
            if not 0 <= productive_minutes <= daily_screen_minutes:
                raise ValueError("Productive time must not exceed total screen time.")
            if not 0 <= focus_minutes <= 1440:
                raise ValueError("Focus time must be between 0 and 1440 minutes.")

            app_usage = {}
            app_limits = {}
            for app in apps:
                app_id = app.id if isinstance(app, Application) else app["name"]
                raw_usage = request.form.get(f"usage_{app_id}", "0")
                raw_limit = request.form.get(f"limit_{app_id}", "")
                usage = float(raw_usage or 0)
                if usage < 0 or usage > 1440:
                    raise ValueError("Application usage must be between 0 and 1440 minutes.")
                app_usage[str(app_id)] = usage
                if raw_limit.strip():
                    limit = int(raw_limit)
                    if limit <= 0 or limit > 1440:
                        raise ValueError("App limits must be between 1 and 1440 minutes.")
                    app_limits[str(app_id)] = limit

            if existing:
                profile = existing
            else:
                profile = OnboardingProfile(user_id=user_id)
                db.session.add(profile)
            profile.daily_screen_minutes = daily_screen_minutes
            profile.productive_minutes = productive_minutes
            profile.focus_minutes = focus_minutes
            profile.active_period = request.form.get("active_period", "afternoon")
            profile.goal = request.form.get("goal", "balance")
            profile.app_usage = app_usage
            profile.app_limits = app_limits

            # Store the questionnaire's baseline in the same tables used by
            # the dashboard and prediction pipeline.
            today = date.today()
            for app in apps:
                app_id = app.id if isinstance(app, Application) else None
                if app_id is None:
                    continue
                usage = app_usage.get(str(app_id), 0)
                if usage <= 0:
                    continue
                    record = UsageRecord.query.filter_by(
                        application_id=app_id, user_id=user_id, date=today, source="web"
                    ).first()
                if record:
                    record.minutes = usage
                else:
                    db.session.add(UsageRecord(
                        application_id=app_id,
                        user_id=user_id,
                        date=today,
                        minutes=usage,
                        source="web",
                    ))
                if str(app_id) in app_limits:
                    app.daily_limit_minutes = app_limits[str(app_id)]

            bucket_hours = {"morning": 9, "afternoon": 14, "evening": 19, "night": 22}
            hour = bucket_hours.get(profile.active_period, 14)
            hourly = HourlyActivity.query.filter_by(date=today, hour=hour).first()
            if hourly:
                hourly.minutes = max(hourly.minutes, float(daily_screen_minutes))
            else:
                db.session.add(HourlyActivity(date=today, hour=hour, minutes=daily_screen_minutes))

            if focus_minutes > 0:
                db.session.add(
                    FocusSession(
                        session_type="Onboarding baseline",
                        date=today,
                        planned_minutes=focus_minutes,
                        actual_minutes=focus_minutes,
                        completed=True,
                    )
                )
            db.session.commit()

            try:
                from ml.train_model import train

                train()
            except Exception:
                pass
            return redirect(url_for("index"))
        except (TypeError, ValueError) as exc:
            db.session.rollback()
            error = str(exc)

    return render_template("onboarding.html", error=error, apps=apps, profile=existing)


@auth_bp.post("/logout")
def logout():
    session.clear()
    if request.is_json:
        return jsonify({"message": "Signed out successfully."})
    return redirect(url_for("auth.login"))


@auth_bp.get("/api/auth/me")
def current_user():
    user = User.query.get(session.get("user_id"))
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": user.to_dict()})
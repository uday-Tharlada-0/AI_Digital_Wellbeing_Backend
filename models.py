from datetime import datetime, date as date_cls
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "email": self.email,
        }


class OnboardingProfile(db.Model):
    __tablename__ = "onboarding_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    daily_screen_minutes = db.Column(db.Integer, nullable=False)
    productive_minutes = db.Column(db.Integer, nullable=False)
    focus_minutes = db.Column(db.Integer, nullable=False)
    active_period = db.Column(db.String(30), nullable=False)
    goal = db.Column(db.String(40), nullable=False)
    app_usage = db.Column(db.JSON, nullable=False, default=dict)
    app_limits = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    category = db.Column(db.String(60), nullable=False, default="Uncategorized")
    color = db.Column(db.String(9), nullable=False, default="#4a6cf7")
    is_productive = db.Column(db.Boolean, nullable=False, default=False)
    is_visible = db.Column(db.Boolean, nullable=False, default=True)
    daily_limit_minutes = db.Column(db.Integer, nullable=True)  # null = no limit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    usage_records = db.relationship(
        "UsageRecord", backref="application", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "color": self.color,
            "is_productive": self.is_productive,
            "is_visible": self.is_visible,
            "daily_limit_minutes": self.daily_limit_minutes,
        }


class UsageRecord(db.Model):
    """One row = total minutes spent in `application` on a given `date`."""

    __tablename__ = "usage_records"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id"), nullable=False
    )
    date = db.Column(db.Date, nullable=False, default=date_cls.today)
    minutes = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint("application_id", "date", name="uq_app_date"),
    )


class HourlyActivity(db.Model):
    """Aggregated minutes-of-activity per hour bucket, across all apps, per day.
    Used for the 'Time of Day' analytics chart."""

    __tablename__ = "hourly_activity"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date_cls.today)
    hour = db.Column(db.Integer, nullable=False)  # 0-23
    minutes = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint("date", "hour", name="uq_date_hour"),
    )


class FocusSession(db.Model):
    __tablename__ = "focus_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_type = db.Column(db.String(40), nullable=False, default="Deep Work")
    date = db.Column(db.Date, nullable=False, default=date_cls.today)
    planned_minutes = db.Column(db.Integer, nullable=False, default=60)
    actual_minutes = db.Column(db.Integer, nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    completed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "session_type": self.session_type,
            "date": self.date.isoformat(),
            "planned_minutes": self.planned_minutes,
            "actual_minutes": self.actual_minutes,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "completed": self.completed,
        }


class Settings(db.Model):
    """Singleton settings row (id is always 1)."""

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    theme_mode = db.Column(db.String(20), default="light")  # light | dark | system
    accent_color = db.Column(db.String(9), default="#4a6cf7")
    language = db.Column(db.String(40), default="English (United States)")

    launch_at_startup = db.Column(db.Boolean, default=True)
    launch_minimized = db.Column(db.Boolean, default=True)
    minimize_to_tray = db.Column(db.Boolean, default=True)
    idle_detection = db.Column(db.Boolean, default=True)

    notif_popup = db.Column(db.Boolean, default=True)
    notif_system = db.Column(db.Boolean, default=True)
    notif_sound = db.Column(db.Boolean, default=False)

    global_daily_limit_minutes = db.Column(db.Integer, default=480)  # 8h default

    def to_dict(self):
        return {
            "theme_mode": self.theme_mode,
            "accent_color": self.accent_color,
            "language": self.language,
            "launch_at_startup": self.launch_at_startup,
            "launch_minimized": self.launch_minimized,
            "minimize_to_tray": self.minimize_to_tray,
            "idle_detection": self.idle_detection,
            "notif_popup": self.notif_popup,
            "notif_system": self.notif_system,
            "notif_sound": self.notif_sound,
            "global_daily_limit_minutes": self.global_daily_limit_minutes,
        }

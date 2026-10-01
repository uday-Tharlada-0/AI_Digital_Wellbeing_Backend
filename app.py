from flask import Flask, render_template, redirect, request, session, url_for
from sqlalchemy import inspect, text
from models import OnboardingProfile
from flask_cors import CORS
from routes.mobile_analytics import mobile_analytics_bp
from config import Config
from extensions import db

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    db.init_app(app)
    CORS(app)  # allow the frontend to be served separately during development

    from routes.dashboard import dashboard_bp
    from routes.applications import applications_bp
    from routes.alerts import alerts_bp
    from routes.analytics import analytics_bp
    from routes.focus import focus_bp
    from routes.settings import settings_bp
    from routes.predictions import predictions_bp
    from routes.auth import auth_bp
    from routes.activity import activity_bp
    from routes.mobile import mobile_bp
    from routes.mobile_suggestions import mobile_suggestions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(mobile_bp)
    app.register_blueprint(mobile_analytics_bp)
    app.register_blueprint(mobile_suggestions_bp)

    for bp in (
        dashboard_bp,
        applications_bp,
        alerts_bp,
        analytics_bp,
        focus_bp,
        settings_bp,
        predictions_bp,
    ):
        app.register_blueprint(bp)

    @app.before_request
    def require_authentication():
        public_paths = {"/login", "/register", "/health","/api/mobile/login"}
        if (
            request.path in public_paths
            or request.path.startswith("/static/")
            or request.path.startswith("/api/auth/")
            or request.path.startswith("/api/mobile/")
        ):
            return None
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return {"error": "Authentication required."}, 401
            return redirect(url_for("auth.login"))
        return None

    @app.route("/")
    def index():
        if not OnboardingProfile.query.filter_by(user_id=session["user_id"]).first():
            return redirect(url_for("auth.onboarding"))
        return render_template("index.html")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        db.create_all()
        application_columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("applications")
}

        if "package_name" not in application_columns:
            db.session.execute(
            text(
            "ALTER TABLE applications "
            "ADD COLUMN package_name VARCHAR(255)"
        )
    )

        db.session.commit()
        activity_columns = {column["name"] for column in inspect(db.engine).get_columns("activity_events")}
        for column_name, column_type in (
            ("user_category", "VARCHAR(60)"),
            ("purpose", "VARCHAR(120)"),
            ("is_background_audio", "BOOLEAN NOT NULL DEFAULT 0"),
            ("classification_source", "VARCHAR(20) NOT NULL DEFAULT 'automatic'"),
        ):
            if column_name not in activity_columns:
                db.session.execute(text(f"ALTER TABLE activity_events ADD COLUMN {column_name} {column_type}"))
        db.session.commit()

        usage_columns = {column["name"] for column in inspect(db.engine).get_columns("usage_records")}
        if "user_id" not in usage_columns:
            db.session.execute(text("ALTER TABLE usage_records ADD COLUMN user_id INTEGER"))
        if "source" not in usage_columns:
            db.session.execute(text("ALTER TABLE usage_records ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'web'"))
                # SQLite-specific legacy migration.
        # PostgreSQL gets its schema from db.create_all() above.
        if db.engine.dialect.name == "sqlite":
            usage_table_sql = db.session.execute(text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='usage_records'"
            )).scalar() or ""

            legacy_usage_constraint = (
                "uq_app_date" in usage_table_sql
                or "UNIQUE (application_id, date)" in usage_table_sql
            )

            if legacy_usage_constraint:
                db.session.execute(text("PRAGMA foreign_keys=OFF"))

                db.session.execute(text("""
                    CREATE TABLE usage_records_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        application_id INTEGER NOT NULL,
                        date DATE NOT NULL,
                        minutes FLOAT NOT NULL DEFAULT 0.0,
                        source VARCHAR(20) NOT NULL DEFAULT 'web'
                    )
                """))

                db.session.execute(text("""
                    INSERT INTO usage_records_new
                    (id, user_id, application_id, date, minutes, source)
                    SELECT id, user_id, application_id, date, minutes,
                           COALESCE(source, 'web')
                    FROM usage_records
                """))

                db.session.execute(text("DROP TABLE usage_records"))

                db.session.execute(text(
                    "ALTER TABLE usage_records_new "
                    "RENAME TO usage_records"
                ))

                db.session.execute(text("PRAGMA foreign_keys=ON"))

            usage_indexes = {
                index["name"]
                for index in inspect(db.engine).get_indexes("usage_records")
            }

            if "uq_app_date" in usage_indexes:
                db.session.execute(
                    text("DROP INDEX uq_app_date")
                )

            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_user_app_date_source "
                "ON usage_records "
                "(user_id, application_id, date, source)"
            ))

            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

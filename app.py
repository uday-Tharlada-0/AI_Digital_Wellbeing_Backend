from flask import Flask, render_template, redirect, request, session, url_for
from flask_cors import CORS

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

    app.register_blueprint(auth_bp)

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
        public_paths = {"/login", "/register", "/health"}
        if (
            request.path in public_paths
            or request.path.startswith("/static/")
            or request.path.startswith("/api/auth/")
        ):
            return None
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return {"error": "Authentication required."}, 401
            return redirect(url_for("auth.login"))
        return None

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

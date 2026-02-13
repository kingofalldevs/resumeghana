"""
ResumeGhana - AI-powered resume builder.
Factory pattern application initialization.
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=None):
    """Create and configure the Flask application."""
    import os as _os
    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if load_dotenv is not None:
        # Load .env for local/dev runs (Render/prod uses real env vars).
        load_dotenv(_os.path.join(_base, ".env"), override=False)
    app = Flask(__name__, template_folder=_os.path.join(_base, "templates"), static_folder=_os.path.join(_base, "static"))

    # Load config (config.py at project root)
    import sys
    if _base not in sys.path:
        sys.path.insert(0, _base)
    from config import Config
    app.config.from_object(Config)

    # Ensure upload folder exists
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.resume import resume_bp
    from app.routes.ai import ai_bp

    from app.routes.landing import landing_bp

    app.register_blueprint(landing_bp)  # Includes "/" index
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(resume_bp)
    app.register_blueprint(ai_bp, url_prefix="/api")
    csrf.exempt(ai_bp)  # API uses JSON, auth via session

    # Local developer safety net: create tables automatically for SQLite.
    # Production should rely on migrations.
    if str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite:///"):
        with app.app_context():
            db.create_all()

    return app

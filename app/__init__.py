import os

from flask import Flask, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_mail import Mail

from app.config import config


# =========================================================
# EXTENSIONS
# =========================================================

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()


# =========================================================
# FLASK-LOGIN USER LOADER
# =========================================================

@login_manager.user_loader
def load_user(user_id):
    """Load logged-in user by ID."""
    from app.models.user import User

    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


# =========================================================
# APPLICATION FACTORY
# =========================================================

def create_app(config_name="default"):
    """Create and configure the SalahMate Flask application."""

    app = Flask(__name__)

    # -----------------------------------------------------
    # Configuration
    # -----------------------------------------------------

    app.config.from_object(config[config_name])

    # -----------------------------------------------------
    # Initialize Flask extensions
    # -----------------------------------------------------

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    mail.init_app(app)

    # -----------------------------------------------------
    # Import models
    #
    # Models are imported so SQLAlchemy knows about them.
    # Database creation is NOT performed on every startup.
    # -----------------------------------------------------

    from app.models import (
        user,
        prayer,
        attendance,
        quran,
        dhikr,
        password_reset,
    )

    # -----------------------------------------------------
    # Flask-Login configuration
    # -----------------------------------------------------

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.unauthorized_handler
    def unauthorized():
        """Redirect unauthenticated users to login."""
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # Register blueprints
    # -----------------------------------------------------

    from app.routes.auth import auth_bp
    from app.routes.attendance import attendance_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.prayer import prayer_bp
    from app.routes.quran import quran_bp
    from app.routes.reports import reports_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(prayer_bp)
    app.register_blueprint(quran_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    # -----------------------------------------------------
    # Android App Links / Digital Asset Links
    # -----------------------------------------------------

    @app.route("/.well-known/assetlinks.json")
    def assetlinks():
        assetlinks_path = os.path.join(
            app.root_path,
            ".well-known",
            "assetlinks.json"
        )

        return send_file(
            assetlinks_path,
            mimetype="application/json"
        )

    return app
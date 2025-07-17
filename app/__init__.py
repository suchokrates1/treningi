from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import logging
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def _resolve_log_level(value):
    """Return an integer log level or ``None`` if invalid."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    str_val = str(value)
    if str_val.isdigit():
        return int(str_val)
    resolved = logging.getLevelName(str_val.upper())
    if isinstance(resolved, int):
        return resolved
    return None


def create_app():
    # Serve static files from the project-level "static" directory so that
    # resources are available when running via ``python run.py`` as well as
    # inside Docker containers.
    app = Flask(__name__, static_folder="../static")
    os.makedirs(app.instance_path, exist_ok=True)
    db_file = os.path.join(app.instance_path, "db.sqlite3")
    db_uri = os.environ.get("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_file}")
    app.config['SECRET_KEY'] = os.environ.get(
        "SECRET_KEY", "default-dev-secret"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ADMIN_PASSWORD'] = os.environ.get("ADMIN_PASSWORD")
    app.config['SMTP_HOST'] = os.environ.get("SMTP_HOST")
    app.config['SMTP_PORT'] = int(os.environ.get("SMTP_PORT", 587))
    app.config['SMTP_USERNAME'] = os.environ.get("SMTP_USERNAME")
    app.config['SMTP_PASSWORD'] = os.environ.get("SMTP_PASSWORD")
    app.config['SMTP_SENDER'] = os.environ.get(
        "SMTP_SENDER",
        "noreply@example.com",
    )
    app.config['SMTP_USE_TLS'] = os.environ.get("SMTP_USE_TLS", "1") == "1"

    log_level = os.environ.get("LOG_LEVEL")
    if log_level:
        level_value = _resolve_log_level(log_level)
        if isinstance(level_value, int):
            app.logger.setLevel(level_value)
            # Ensure the root logger matches the application log level
            logging.getLogger().setLevel(level_value)
            app.logger.info(
                "Logging level set to %s", logging.getLevelName(level_value)
            )
        else:
            app.logger.warning("Invalid LOG_LEVEL value: %s", log_level)
    elif os.environ.get("FLASK_ENV") == "development" or app.debug:
        app.logger.setLevel(logging.INFO)

    db.init_app(app)
    migrate_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "migrations"
    )
    migrate.init_app(app, db, directory=migrate_dir)
    csrf.init_app(app)

    with app.app_context():
        from . import routes, admin_routes
        app.register_blueprint(routes.bp)
        app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')
        # Blueprints are registered after extensions so migrations can run

    return app

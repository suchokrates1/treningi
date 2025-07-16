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
        level_value = getattr(logging, log_level.upper(), None)
        if isinstance(level_value, int):
            app.logger.setLevel(level_value)
        else:
            app.logger.warning("Invalid LOG_LEVEL: %s", log_level)

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

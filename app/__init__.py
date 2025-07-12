from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
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
    app.config['SECRET_KEY'] = os.environ.get(
        "SECRET_KEY", "default-dev-secret"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ADMIN_PASSWORD'] = os.environ.get("ADMIN_PASSWORD")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    with app.app_context():
        from . import routes, admin_routes
        app.register_blueprint(routes.bp)
        app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')
        # Blueprints are registered after extensions so migrations can run

    return app

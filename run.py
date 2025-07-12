from app import create_app, db
from flask_migrate import upgrade, stamp
from sqlalchemy import inspect

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        inspector = inspect(db.engine)
        if "alembic_version" not in inspector.get_table_names():
            stamp()  # mark current state
        upgrade()
    app.run(host="0.0.0.0", port=8000)

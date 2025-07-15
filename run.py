from app import create_app, db
from flask_migrate import upgrade, stamp
from sqlalchemy import inspect, text

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        tmp_tables = [t for t in tables if t.startswith("_alembic_tmp_")]
        if tmp_tables:
            with db.engine.begin() as conn:
                for tbl in tmp_tables:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())

        # For databases created before Alembic was introduced we need to mark
        # the current revision so ``upgrade()`` does not try to recreate
        # existing tables. For a brand new database we simply run the
        # migrations which will create all tables.
        if "alembic_version" not in tables:
            model_tables = {
                "coaches",
                "locations",
                "volunteers",
                "trainings",
                "bookings",
                "email_settings",
            }
            if tables & model_tables:
                stamp()  # mark existing schema as current

        upgrade()

    app.run(host="0.0.0.0", port=8000)

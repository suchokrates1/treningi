from app import create_app
from flask_migrate import upgrade

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        upgrade()
    app.run(host="0.0.0.0", port=8000)

import logging
from app import create_app


def test_default_log_level(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app()
    assert app.logger.level == logging.INFO

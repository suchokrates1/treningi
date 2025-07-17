import logging
from app import create_app


def test_default_log_level(monkeypatch):
    logging.getLogger("app").setLevel(logging.NOTSET)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app()
    assert app.logger.level == logging.INFO


def test_valid_log_level(monkeypatch):
    logging.getLogger("app").setLevel(logging.NOTSET)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app()
    assert app.logger.level == logging.DEBUG


def test_invalid_log_level(monkeypatch, caplog):
    logging.getLogger("app").setLevel(logging.NOTSET)
    monkeypatch.setenv("LOG_LEVEL", "nope")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    with caplog.at_level(logging.WARNING):
        app = create_app()
    assert any("Invalid LOG_LEVEL" in r.getMessage() for r in caplog.records)
    assert app.logger.level == logging.NOTSET

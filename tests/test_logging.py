import logging
import smtplib
import pytest

from app import create_app
from app.email_utils import send_email


@pytest.fixture(autouse=True)
def no_email():
    yield


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


def test_send_email_emits_info(monkeypatch, caplog):
    logging.getLogger("app").setLevel(logging.NOTSET)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app()

    captured = {}

    class DummySMTP:
        def __init__(self, host, port):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, msg):
            captured["message"] = msg

    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)

    with app.app_context(), caplog.at_level(logging.INFO):
        from app import db
        db.create_all()
        send_email(
            "Subject",
            "Body",
            ["to@example.com"],
            host="smtp.example.com",
            port=25,
            sender="Admin",
            attachments=[("info.txt", "text/plain", b"hello")],
        )

    assert any("Email sent successfully" in r.getMessage() for r in caplog.records)
    message = captured.get("message")
    assert message is not None
    attachment = next(message.iter_attachments(), None)
    assert attachment is not None
    assert attachment.get_filename() == "info.txt"

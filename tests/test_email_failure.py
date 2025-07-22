import smtplib
import pytest
from app.email_utils import send_email

# override autouse fixture so send_email is not mocked
@pytest.fixture(autouse=True)
def no_email():
    yield


def test_send_email_failure_returns_false(app_instance, monkeypatch):
    class FailingSMTP:
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
            raise smtplib.SMTPException("boom")

    monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)
    with app_instance.app_context():
        success, error = send_email("Sub", "Body", ["to@example.com"], host="h", port=25)
        assert success is False
        assert error == "boom"


def test_admin_flash_on_email_failure(client, app_instance, monkeypatch):
    # login first
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    class FailingSMTP:
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
            raise smtplib.SMTPException("boom")

    monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)

    form_data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hi",
        "cancellation_template": "Bye",
        "test_recipient": "dest@example.com",
    }

    resp = client.post(
        "/admin/settings/test-email", data=form_data, follow_redirects=True
    )
    assert b"Nie uda\xc5\x82o si\xc4\x99 wys\xc5\x82a\xc4\x87 wiadomo\xc5\x9bci testowej" in resp.data
    assert b"boom" in resp.data


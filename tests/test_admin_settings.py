import pytest
from io import BytesIO
from pathlib import Path
from app import db
from app.models import EmailSettings
import app

# allow send_email to run in this module
@pytest.fixture(autouse=True)
def no_email():
    yield


def test_admin_settings_update(client, app_instance):
    # log in as admin
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    form_data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hello {first_name}",
        "cancellation_template": "Bye {first_name}",
    }

    resp = client.post("/admin/settings", data=form_data, follow_redirects=True)
    assert b"Zapisano ustawienia." in resp.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert settings.server == "smtp.test.com"
        assert settings.port == 2525
        assert settings.login == "user"
        assert settings.password == "pass"
        assert settings.sender == "Admin"
        assert settings.registration_template == "Hello {first_name}"
        assert settings.cancellation_template == "Bye {first_name}"


def test_admin_settings_manage_attachments(client, app_instance):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hello",
        "cancellation_template": "Bye",
    }

    response = client.post(
        "/admin/settings",
        data={
            **data,
            "registration_files_adult": [(BytesIO(b"adult"), "adult.txt")],
            "registration_files_minor": [(BytesIO(b"minor"), "minor.pdf")],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Zapisano ustawienia." in response.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert len(settings.registration_files_adult) == 1
        assert len(settings.registration_files_minor) == 1
        adult_meta = settings.registration_files_adult[0]
        minor_meta = settings.registration_files_minor[0]
        assert adult_meta["original_name"] == "adult.txt"
        assert minor_meta["original_name"] == "minor.pdf"
        attachments_dir = Path(app_instance.instance_path) / "attachments"
        assert (attachments_dir / adult_meta["stored_name"]).read_bytes() == b"adult"
        assert (attachments_dir / minor_meta["stored_name"]).read_bytes() == b"minor"

    remove_response = client.post(
        "/admin/settings",
        data={
            **data,
            "remove_adult_files": [adult_meta["stored_name"]],
            "remove_minor_files": [minor_meta["stored_name"]],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert remove_response.status_code == 200
    assert b"Zapisano ustawienia." in remove_response.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert settings.registration_files_adult == []
        assert settings.registration_files_minor == []
        attachments_dir = Path(app_instance.instance_path) / "attachments"
        assert attachments_dir.exists()
        assert not (attachments_dir / adult_meta["stored_name"]).exists()
        assert not (attachments_dir / minor_meta["stored_name"]).exists()


def test_admin_send_test_email(client, app_instance, monkeypatch):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    form_data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hello",
        "cancellation_template": "Bye",
    }

    client.post("/admin/settings", data=form_data, follow_redirects=True)

    captured = {}

    class DummySMTP:
        def __init__(self, host, port):
            captured['host'] = host
            captured['port'] = port
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass
        def starttls(self):
            captured['tls'] = True
        def login(self, username, password):
            captured['login'] = (username, password)
        def send_message(self, msg):
            captured['message'] = msg

    monkeypatch.setattr(app.email_utils.smtplib, "SMTP", DummySMTP)

    form_data["test_recipient"] = "dest@example.com"

    resp = client.post(
        "/admin/settings/test-email", data=form_data, follow_redirects=True
    )
    assert resp.status_code == 200
    assert captured["message"]["From"] == "Admin <noreply@example.com>"
    assert captured["message"]["To"] == "dest@example.com"
    assert b"Wys\xc5\x82ano wiadomo\xc5\x9b\xc4\x87 testow\xc4\x85." in resp.data


def test_test_email_preserves_form_data(client, monkeypatch):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    form_data = {
        "server": "smtp.example.com",
        "port": "2500",
        "login": "foo",
        "password": "bar",
        "encryption": "tls",
        "sender": "Sender Name",
        "registration_template": "Hi",
        "cancellation_template": "Bye",
        "test_recipient": "dest@example.com",
    }

    monkeypatch.setattr("app.admin_routes.send_email", lambda *a, **k: (True, None))

    resp = client.post("/admin/settings/test-email", data=form_data)
    assert resp.status_code == 200
    assert b"smtp.example.com" in resp.data


def test_settings_validation_passes(client, app_instance, monkeypatch):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    form_data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hello",
        "cancellation_template": "Bye",
    }

    captured = {}
    orig_validate = app.admin_routes.SettingsForm.validate_on_submit

    def capture(self, *a, **kw):
        result = orig_validate(self, *a, **kw)
        if "result" not in captured:
            captured["result"] = result
        return result

    monkeypatch.setattr(app.admin_routes.SettingsForm, "validate_on_submit", capture)

    resp = client.post("/admin/settings", data=form_data, follow_redirects=True)
    assert resp.status_code == 200
    assert captured.get("result") is True
    assert b"Zapisano ustawienia." in resp.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert settings.server == "smtp.test.com"
        assert settings.port == 2525
        assert settings.login == "user"
        assert settings.password == "pass"
        assert settings.sender == "Admin"

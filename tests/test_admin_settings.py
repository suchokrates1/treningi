import pytest
from io import BytesIO
from pathlib import Path
from app import db
from app.models import EmailSettings, StoredFile
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


def test_admin_settings_edit_keeps_existing_files(client, app_instance):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    base_data = {
        "server": "smtp.test.com",
        "port": "2525",
        "login": "user",
        "password": "pass",
        "encryption": "tls",
        "sender": "Admin",
        "registration_template": "Hello",
        "cancellation_template": "Bye",
    }

    create_resp = client.post(
        "/admin/settings",
        data={
            **base_data,
            "registration_files_adult": [(BytesIO(b"adult"), "adult.txt")],
            "registration_files_minor": [(BytesIO(b"minor"), "minor.pdf")],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert create_resp.status_code == 200

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        adult_meta = settings.registration_files_adult[0]
        minor_meta = settings.registration_files_minor[0]

    edit_data = {
        **base_data,
        "server": "smtp.edited.com",
        "port": "2626",
        "sender": "Edited Admin",
    }

    edit_resp = client.post(
        "/admin/settings",
        data=edit_data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert edit_resp.status_code == 200
    assert b"Zapisano ustawienia." in edit_resp.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert settings.server == "smtp.edited.com"
        assert settings.port == 2626
        assert settings.sender == "Edited Admin"
        assert settings.registration_files_adult[0]["stored_name"] == adult_meta["stored_name"]
        assert settings.registration_files_minor[0]["stored_name"] == minor_meta["stored_name"]
        attachments_dir = Path(app_instance.instance_path) / "attachments"
        assert (attachments_dir / adult_meta["stored_name"]).read_bytes() == b"adult"
        assert (attachments_dir / minor_meta["stored_name"]).read_bytes() == b"minor"


def test_admin_settings_migrates_legacy_file_ids(client, app_instance):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert b"Zalogowano" in login.data

    with app_instance.app_context():
        adult_file = StoredFile(
            filename="legacy_adult.pdf",
            content_type="application/pdf",
            data=b"adult",
        )
        minor_file = StoredFile(
            filename="legacy_minor.pdf",
            content_type="application/pdf",
            data=b"minor",
        )
        db.session.add_all([adult_file, minor_file])
        db.session.flush()
        settings = EmailSettings(
            id=1,
            port=587,
            sender="Admin",
            encryption="tls",
            registration_template="Hello",
            registration_files_adult=[adult_file.id],
            registration_files_minor=[minor_file.id],
        )
        db.session.merge(settings)
        db.session.commit()

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

    response = client.post(
        "/admin/settings",
        data=form_data,
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Zapisano ustawienia." in response.data

    with app_instance.app_context():
        settings = db.session.get(EmailSettings, 1)
        assert settings is not None
        assert isinstance(settings.registration_files_adult, list)
        assert isinstance(settings.registration_files_minor, list)
        assert settings.registration_files_adult
        assert settings.registration_files_minor

        adult_meta = settings.registration_files_adult[0]
        minor_meta = settings.registration_files_minor[0]
        assert adult_meta["original_name"] == "legacy_adult.pdf"
        assert minor_meta["original_name"] == "legacy_minor.pdf"
        assert adult_meta["stored_name"].startswith("legacy_")
        assert minor_meta["stored_name"].startswith("legacy_")

        attachments_dir = Path(app_instance.instance_path) / "attachments"
        assert (attachments_dir / adult_meta["stored_name"]).read_bytes() == b"adult"
        assert (attachments_dir / minor_meta["stored_name"]).read_bytes() == b"minor"


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


def test_test_email_requires_recipient(client, monkeypatch):
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
    }

    monkeypatch.setattr(
        "app.admin_routes.send_email",
        lambda *args, **kwargs: pytest.fail("send_email should not be called"),
    )

    resp = client.post(
        "/admin/settings/test-email",
        data=form_data,
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"Podaj adres e-mail odbiorcy wiadomo\xc5\x9bci testowej." in resp.data


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

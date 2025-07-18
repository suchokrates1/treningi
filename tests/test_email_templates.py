import smtplib
import pytest

from app.template_utils import render_template_string
from app.email_utils import send_email
from app.models import EmailSettings
from app import db

# Override the autouse fixture from conftest so we can test send_email
@pytest.fixture(autouse=True)
def no_email():
    yield


def test_render_template_string_substitution():
    template = "Hello {name}!"
    result = render_template_string(template, {"name": "Alice"})
    assert result == "Hello Alice!"


def test_send_email_includes_plain_and_html(app_instance, monkeypatch):
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

    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)

    with app_instance.app_context():
        settings = EmailSettings(id=1, server="smtp.example.com", port=25, sender="Admin")
        db.session.add(settings)
        db.session.commit()
        send_email("Subject", None, ["to@example.com"], html_body="<p>Hello</p>")

    msg = captured['message']
    assert msg.is_multipart()
    assert msg['From'] == 'Admin <noreply@example.com>'
    assert msg.get_body(preferencelist=('plain',)).get_content().strip() == "Hello"
    assert msg.get_body(preferencelist=('html',)).get_content().strip() == "<p>Hello</p>"


def test_preview_endpoint_renders(client, app_instance):
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    with app_instance.app_context():
        settings = EmailSettings(id=1, port=587, sender='Admin', registration_template='Hi {first_name}', cancellation_template='')
        db.session.add(settings)
        db.session.commit()
    resp = client.get('/admin/settings/preview/registration')
    assert resp.status_code == 200
    assert b'Hi Jan' in resp.data


def test_preview_endpoint_allows_posting_html(client, app_instance):
    """Posting custom HTML should be rendered without saving it."""
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    with app_instance.app_context():
        settings = EmailSettings(id=1, port=587, sender='Admin')
        db.session.add(settings)
        db.session.commit()
    html = '<p>Custom Preview</p>'
    resp = client.post('/admin/settings/preview/registration', data={'content': html})
    assert resp.status_code == 200
    assert b'Custom Preview' in resp.data


def test_preview_endpoint_allows_posting_specific_html(client, app_instance):
    """Posting HTML renders that exact HTML snippet."""
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    with app_instance.app_context():
        settings = EmailSettings(id=1, port=587, sender='Admin')
        db.session.add(settings)
        db.session.commit()

    html = '<p>X</p>'
    resp = client.post('/admin/settings/preview/registration', data={'content': html})
    assert resp.status_code == 200
    assert b'<p>X</p>' in resp.data


def test_preview_endpoint_returns_modal_html(client, app_instance):
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    with app_instance.app_context():
        settings = EmailSettings(id=1, port=587, sender='Admin')
        db.session.add(settings)
        db.session.commit()

    html = '<p>Modal Test</p>'
    resp = client.post('/admin/settings/preview/registration', data={'content': html})
    assert resp.status_code == 200
    assert b'<div class="border p-3">' in resp.data
    assert b'Modal Test' in resp.data
    assert b'<html' not in resp.data


def test_preview_without_settings_record(client, app_instance):
    """Preview should work when no EmailSettings exist."""
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    html = '<p>No settings</p>'
    resp = client.post('/admin/settings/preview/registration', data={'content': html})
    assert resp.status_code == 200
    assert b'No settings' in resp.data

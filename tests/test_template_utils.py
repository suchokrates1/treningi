from app.template_utils import render_template_string
from app import db
from app.models import EmailSettings

def test_render_template_string():
    template = "Hello {first_name} {last_name}!"
    result = render_template_string(template, {"first_name": "A", "last_name": "B"})
    assert result == "Hello A B!"


def test_preview_requires_login(client):
    resp = client.get('/admin/settings/preview/registration', follow_redirects=True)
    assert b'Zaloguj' in resp.data


def test_preview_logged_in(client, app_instance):
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    with app_instance.app_context():
        settings = EmailSettings(id=1, port=587, sender='Admin',
                                 registration_template='Hello {first_name} {logo}', cancellation_template='')
        db.session.add(settings)
        db.session.commit()
    resp = client.get('/admin/settings/preview/registration')
    assert b'Hello' in resp.data
    assert b'static/logo.png' in resp.data

import pytest
from app.models import EmailSettings


def test_admin_settings_update(client, app_instance):
    # log in as admin
    login = client.post('/admin/login', data={'password': 'secret'}, follow_redirects=True)
    assert b'Zalogowano' in login.data

    form_data = {
        'server': 'smtp.test.com',
        'port': '2525',
        'login': 'user',
        'password': 'pass',
        'sender': 'admin@example.com',
        'registration_template': 'Hello {first_name}',
        'cancellation_template': 'Bye {first_name}',
    }

    resp = client.post('/admin/settings', data=form_data, follow_redirects=True)
    assert b'Zapisano ustawienia.' in resp.data

    with app_instance.app_context():
        settings = EmailSettings.query.get(1)
        assert settings.server == 'smtp.test.com'
        assert settings.port == 2525
        assert settings.login == 'user'
        assert settings.password == 'pass'
        assert settings.sender == 'admin@example.com'
        assert settings.registration_template == 'Hello {first_name}'
        assert settings.cancellation_template == 'Bye {first_name}'


def test_admin_send_test_email(client, app_instance, monkeypatch):
    login = client.post('/admin/login', data={'password': 'secret'}, follow_redirects=True)
    assert b'Zalogowano' in login.data

    form_data = {
        'server': 'smtp.test.com',
        'port': '2525',
        'login': 'user',
        'password': 'pass',
        'sender': 'admin@example.com',
        'registration_template': 'Hello',
        'cancellation_template': 'Bye',
    }

    client.post('/admin/settings', data=form_data, follow_redirects=True)

    captured = {}

    def fake_send(subject, body, recipients, **kwargs):
        captured['args'] = (subject, body, recipients)

    monkeypatch.setattr('app.admin_routes.send_email', fake_send)

    form_data['test_recipient'] = 'dest@example.com'

    resp = client.post('/admin/settings/test-email', data=form_data, follow_redirects=True)
    assert resp.status_code == 200
    assert captured['args'][2] == ['dest@example.com']
    assert b'Wys\xc5\x82ano wiadomo\xc5\x9b\xc4\x87 testow\xc4\x85.' in resp.data

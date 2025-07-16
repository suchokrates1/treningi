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
    assert b'Zapisano ustawienia' in resp.data

    with app_instance.app_context():
        settings = EmailSettings.query.get(1)
        assert settings.server == 'smtp.test.com'
        assert settings.port == 2525
        assert settings.login == 'user'
        assert settings.password == 'pass'
        assert settings.sender == 'admin@example.com'
        assert settings.registration_template == 'Hello {first_name}'
        assert settings.cancellation_template == 'Bye {first_name}'

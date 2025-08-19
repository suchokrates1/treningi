def test_logout_button_hidden_when_logged_out(client):
    response = client.get('/')
    assert b'Wyloguj' not in response.data


def test_logout_button_visible_when_logged_in(client):
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    response = client.get('/')
    assert b'Wyloguj' in response.data

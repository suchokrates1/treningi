from app.models import Volunteer, Booking


def sign_up(client, training_id, email):
    return client.post(
        '/',
        data={
            'first_name': 'Bob',
            'last_name': 'Tester',
            'email': email,
            'training_id': str(training_id),
        },
        follow_redirects=True,
    )


def test_signup_stores_lowercase(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    mixed_email = 'User@Example.COM'
    sign_up(client, training_id, mixed_email)
    with app_instance.app_context():
        vol = Volunteer.query.filter_by(email=mixed_email.lower()).first()
        assert vol is not None
        assert vol.email == mixed_email.lower()


def test_duplicate_signup_case_insensitive(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    email = 'duplicate@example.com'
    sign_up(client, training_id, email)
    resp = sign_up(client, training_id, email.upper())
    assert b'Jeste' in resp.data
    with app_instance.app_context():
        assert Booking.query.count() == 1
        assert Volunteer.query.filter_by(email=email).count() == 1


def test_cancel_case_insensitive(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    email = 'cancelme@example.com'
    sign_up(client, training_id, email)
    resp = client.post(
        f'/cancel?training_id={training_id}',
        data={'email': email.upper(), 'training_id': training_id},
        follow_redirects=True,
    )
    assert b'Zg' in resp.data
    with app_instance.app_context():
        assert Booking.query.count() == 0

from app.models import Volunteer, Booking


def sign_up(client, training_id, email, is_adult=True):
    return client.post(
        '/',
        data={
            'first_name': 'Bob',
            'last_name': 'Tester',
            'email': email,
            'phone_number': '500600700',
            'training_id': str(training_id),
            'is_adult': 'true' if is_adult else 'false',
            'privacy_consent': 'y',
        },
        follow_redirects=True,
    )


def test_signup_stores_lowercase(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    mixed_email = 'User@Example.COM'
    sign_up(client, training_id, mixed_email, is_adult=True)
    with app_instance.app_context():
        vol = Volunteer.query.filter_by(email=mixed_email.lower()).first()
        assert vol is not None
        assert vol.email == mixed_email.lower()
        assert vol.is_adult is True


def test_duplicate_signup_case_insensitive(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    email = 'duplicate@example.com'
    sign_up(client, training_id, email, is_adult=False)
    resp = sign_up(client, training_id, email.upper(), is_adult=False)
    assert b'Jeste' in resp.data
    with app_instance.app_context():
        assert Booking.query.count() == 1
        assert Volunteer.query.filter_by(email=email).count() == 1
        volunteer = Volunteer.query.filter_by(email=email).first()
        assert volunteer.is_adult is False


def test_cancel_case_insensitive(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    email = 'cancelme@example.com'
    sign_up(client, training_id, email, is_adult=False)
    resp = client.post(
        f'/cancel?training_id={training_id}',
        data={'email': email.upper(), 'training_id': training_id},
        follow_redirects=True,
    )
    assert b'Zg' in resp.data
    with app_instance.app_context():
        assert Booking.query.count() == 0
        volunteer = Volunteer.query.filter_by(email=email.lower()).first()
        assert volunteer is not None
        assert volunteer.is_adult is False

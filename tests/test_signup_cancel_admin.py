from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    Booking,
    Training,
    Volunteer,
    Coach,
    Location,
    EmailSettings,
    StoredFile,
)


def sign_up(client, volunteer_data, training_id):
    return client.post(
        '/',
        data={
            'first_name': volunteer_data['first_name'],
            'last_name': volunteer_data['last_name'],
            'email': volunteer_data['email'],
            'phone_number': volunteer_data.get('phone_number', '500600700'),
            'training_id': str(training_id),
            'is_adult': 'true' if volunteer_data.get('is_adult', True) else 'false',
            'privacy_consent': 'y',
        },
        follow_redirects=True,
    )


def test_volunteer_sign_up(client, app_instance, sample_data):
    training_id, volunteer_id, _, _ = sample_data
    volunteer = {
        'first_name': 'Ann',
        'last_name': 'Smith',
        'email': 'ann@example.com',
        'is_adult': True,
    }
    response = sign_up(client, volunteer, training_id)
    assert b'Zapisano na trening!' in response.data
    with app_instance.app_context():
        booking = Booking.query.filter_by(training_id=training_id, volunteer_id=volunteer_id).first()
        assert booking is not None
        assert booking.volunteer.is_adult is True


def test_cancel_booking(client, app_instance, sample_data):
    training_id, volunteer_id, _, _ = sample_data
    volunteer = {
        'first_name': 'Ann',
        'last_name': 'Smith',
        'email': 'ann@example.com',
        'is_adult': False,
    }
    sign_up(client, volunteer, training_id)
    with app_instance.app_context():
        stored_volunteer = Volunteer.query.filter_by(email=volunteer['email']).first()
        assert stored_volunteer is not None
        assert stored_volunteer.is_adult is False

    response = client.post(
        f'/cancel?training_id={training_id}',
        data={'email': volunteer['email'], 'training_id': training_id},
        follow_redirects=True,
    )
    assert b'Zg\xc5\x82oszenie zosta\xc5\x82o usuni\xc4\x99te.' in response.data
    with app_instance.app_context():
        assert Booking.query.count() == 0


def test_admin_create_training(client, app_instance, sample_data):
    _, _, coach_id, location_id = sample_data
    login = client.post('/admin/login', data={'password': 'secret'}, follow_redirects=True)
    assert b'Zalogowano jako administrator.' in login.data
    new_dt = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).strftime('%Y-%m-%dT%H:%M')
    response = client.post(
        '/admin/trainings',
        data={'date': new_dt, 'location_id': location_id, 'coach_id': coach_id},
        follow_redirects=True,
    )
    assert b'Dodano nowy trening.' in response.data
    with app_instance.app_context():
        assert Training.query.count() == 2


def test_cancel_booking_sends_email(client, app_instance, sample_data, monkeypatch):
    training_id, _, _, _ = sample_data
    volunteer = {
        "first_name": "Ann",
        "last_name": "Smith",
        "email": "ann@example.com",
        "is_adult": True,
    }

    sign_up(client, volunteer, training_id)
    with app_instance.app_context():
        stored_volunteer = Volunteer.query.filter_by(email=volunteer["email"]).first()
        assert stored_volunteer is not None
        assert stored_volunteer.is_adult is True

    called = {}

    def fake_send_email(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        return True, None

    monkeypatch.setattr("app.routes.send_email", fake_send_email)

    client.post(
        f"/cancel?training_id={training_id}",
        data={"email": volunteer["email"], "training_id": training_id},
        follow_redirects=True,
    )

    assert "args" in called
    assert called["kwargs"].get("attachments") in (None, [])


def test_registration_attachments_match_age(
    client, app_instance, sample_data, monkeypatch
):
    training_id, _, _, _ = sample_data

    captured: list[list[tuple[str, str, bytes]] | None] = []

    def fake_send_email(*args, **kwargs):
        captured.append(kwargs.get("attachments"))
        return True, None

    monkeypatch.setattr("app.routes.send_email", fake_send_email)

    with app_instance.app_context():
        adult_file = StoredFile(
            filename="adult.pdf",
            content_type="application/pdf",
            data=b"adult",
        )
        minor_file = StoredFile(
            filename="minor.pdf",
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

    adult_volunteer = {
        "first_name": "Alice",
        "last_name": "Adult",
        "email": "alice.adult@example.com",
        "is_adult": True,
    }
    minor_volunteer = {
        "first_name": "Bobby",
        "last_name": "Minor",
        "email": "bobby.minor@example.com",
        "is_adult": False,
    }

    sign_up(client, adult_volunteer, training_id)
    sign_up(client, minor_volunteer, training_id)

    assert len(captured) == 2
    assert captured[0] and captured[0][0][0] == "adult.pdf"
    assert captured[0][0][1] == "application/pdf"
    assert captured[0][0][2] == b"adult"
    assert captured[1] and captured[1][0][0] == "minor.pdf"
    assert captured[1][0][1] == "application/pdf"
    assert captured[1][0][2] == b"minor"

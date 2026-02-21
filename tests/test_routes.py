import pytest
from datetime import datetime, timezone
from pathlib import Path

from app import db
from app.models import Coach, Location, Training, Volunteer, Booking, EmailSettings


def setup_training(app):
    """Create sample training and volunteer and return their IDs."""
    with app.app_context():
        coach = Coach(first_name='John', last_name='Doe', phone_number='123')
        location = Location(name='Court')
        training = Training(
            date=datetime.now(timezone.utc),
            coach=coach,
            location=location,
        )
        volunteer = Volunteer(
            first_name='Ann',
            last_name='Smith',
            email='ann@example.com',
            is_adult=True,
        )
        db.session.add_all([coach, location, volunteer, training])
        db.session.commit()
        return training.id, volunteer.id


def test_duplicate_booking_flash(client, app_instance):
    training_id, volunteer_id = setup_training(app_instance)

    with app_instance.app_context():
        booking = Booking(training_id=training_id, volunteer_id=volunteer_id)
        db.session.add(booking)
        db.session.commit()

    response = client.post(
        '/',
        data={
            'first_name': 'Ann',
            'last_name': 'Smith',
            'email': 'ann@example.com',
            'phone_number': '500600700',
            'training_id': str(training_id),
            'is_adult': 'true',
            'privacy_consent': 'y',
        },
        follow_redirects=True,
    )

    assert b'Jeste' in response.data
    with app_instance.app_context():
        assert Booking.query.count() == 1
        volunteer = db.session.get(Volunteer, volunteer_id)
        assert volunteer.is_adult is True


def test_deleted_training_shows_in_history(client, app_instance):
    training_id, _ = setup_training(app_instance)

    with app_instance.app_context():
        training = db.session.get(Training, training_id)
        training.is_deleted = True
        db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    response = client.get('/admin/history')

    assert b'Usuni' in response.data


def test_remove_training_deletes_record(client, app_instance):
    training_id, volunteer_id = setup_training(app_instance)

    with app_instance.app_context():
        booking = Booking(training_id=training_id, volunteer_id=volunteer_id)
        db.session.add(booking)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    response = client.post(
        f'/admin/history/{training_id}/remove',
        follow_redirects=True,
    )

    assert b'trwale usuni' in response.data
    with app_instance.app_context():
        assert db.session.get(Training, training_id) is None
        assert Booking.query.count() == 0


def test_signup_handles_attachment_metadata(
    client, app_instance, sample_data, monkeypatch
):
    training_id, _, _, _ = sample_data
    attachments_dir = Path(app_instance.instance_path) / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    stored_name = "test_file.txt"
    (attachments_dir / stored_name).write_text("Important info", encoding="utf-8")

    with app_instance.app_context():
        settings = EmailSettings(
            id=1,
            registration_template="Hello {first_name}",
            registration_files_adult=[
                {
                    "stored_name": stored_name,
                    "original_name": "info.txt",
                    "content_type": "text/plain",
                }
            ],
        )
        db.session.add(settings)
        db.session.commit()

    captured: dict[str, list[tuple[str, str, bytes]] | None] = {"attachments": None}

    def fake_send_email(subject, body, recipients, **kwargs):
        captured["attachments"] = kwargs.get("attachments")
        return True, None

    monkeypatch.setattr("app.email_utils.send_email", fake_send_email)

    response = client.post(
        "/",
        data={
            "first_name": "New",
            "last_name": "Volunteer",
            "email": "new_volunteer@example.com",
            "phone_number": "500600700",
            "training_id": str(training_id),
            "is_adult": "true",
            "privacy_consent": "y",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Zapisano na trening!" in response.data
    attachments = captured["attachments"]
    assert attachments is not None and len(attachments) == 1
    filename, content_type, data = attachments[0]
    assert filename == "info.txt"
    assert content_type == "text/plain"
    assert data == b"Important info"

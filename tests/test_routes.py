import pytest
from datetime import datetime, timezone

from app import db
from app.models import Coach, Location, Training, Volunteer, Booking


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
            'training_id': str(training_id),
            'is_adult': 'true',
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

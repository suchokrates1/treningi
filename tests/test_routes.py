import pytest
from datetime import datetime

from app import db
from app.models import Coach, Location, Training, Volunteer, Booking


def setup_training(app):
    """Create sample training and volunteer and return their IDs."""
    with app.app_context():
        coach = Coach(first_name='John', last_name='Doe', phone_number='123')
        location = Location(name='Court')
        training = Training(date=datetime.utcnow(), coach=coach, location=location)
        volunteer = Volunteer(first_name='Ann', last_name='Smith', email='ann@example.com')
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
        },
        follow_redirects=True,
    )

    assert b'Jeste' in response.data
    with app_instance.app_context():
        assert Booking.query.count() == 1


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

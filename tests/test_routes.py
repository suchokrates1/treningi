import pytest
from datetime import datetime

from app import create_app, db
from app.models import Coach, Location, Training, Volunteer, Booking

@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def setup_training(app):
    with app.app_context():
        coach = Coach(first_name='John', last_name='Doe', phone_number='123')
        location = Location(name='Court')
        training = Training(date=datetime.utcnow(), coach=coach, location=location)
        volunteer = Volunteer(first_name='Ann', last_name='Smith', email='ann@example.com')
        db.session.add_all([coach, location, training, volunteer])
        db.session.commit()
        return training.id, volunteer.id, volunteer


def test_duplicate_booking_flash(client, app_instance):
    training_id, volunteer_id, volunteer = setup_training(app_instance)

    with app_instance.app_context():
        booking = Booking(training_id=training_id, volunteer_id=volunteer_id)
        db.session.add(booking)
        db.session.commit()

    response = client.post(
        '/',
        data={
            'first_name': volunteer.first_name,
            'last_name': volunteer.last_name,
            'email': volunteer.email,
            'training_id': str(training_id),
        },
        follow_redirects=True,
    )

    assert b'Jeste\xc5\x9b ju\xc5\xbc zapisany na ten trening.' in response.data
    with app_instance.app_context():
        assert Booking.query.count() == 1


def test_deleted_training_shows_in_history(client, app_instance):
    training_id, _, _ = setup_training(app_instance)

    with app_instance.app_context():
        training = Training.query.get(training_id)
        training.is_deleted = True
        db.session.commit()

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    response = client.get("/admin/history")

    assert b"Usuni\xc4\x99ty" in response.data




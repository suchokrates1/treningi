from datetime import datetime, timedelta

from app import db
from app.models import Booking, Training, Volunteer, Coach, Location


def sign_up(client, volunteer_data, training_id):
    return client.post(
        '/',
        data={
            'first_name': volunteer_data['first_name'],
            'last_name': volunteer_data['last_name'],
            'email': volunteer_data['email'],
            'training_id': str(training_id),
        },
        follow_redirects=True,
    )


def test_volunteer_sign_up(client, app_instance, sample_data):
    training_id, volunteer_id, _, _ = sample_data
    volunteer = {
        'first_name': 'Ann',
        'last_name': 'Smith',
        'email': 'ann@example.com',
    }
    response = sign_up(client, volunteer, training_id)
    assert b'Zapisano na trening!' in response.data
    with app_instance.app_context():
        booking = Booking.query.filter_by(training_id=training_id, volunteer_id=volunteer_id).first()
        assert booking is not None


def test_cancel_booking(client, app_instance, sample_data):
    training_id, volunteer_id, _, _ = sample_data
    volunteer = {'first_name': 'Ann', 'last_name': 'Smith', 'email': 'ann@example.com'}
    sign_up(client, volunteer, training_id)

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
    new_dt = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    response = client.post(
        '/admin/trainings',
        data={'date': new_dt, 'location_id': location_id, 'coach_id': coach_id},
        follow_redirects=True,
    )
    assert b'Dodano nowy trening.' in response.data
    with app_instance.app_context():
        assert Training.query.count() == 2


def test_cancel_training_email_error(client, app_instance, sample_data, monkeypatch):
    training_id, volunteer_id, _, _ = sample_data

    login = client.post('/admin/login', data={'password': 'secret'}, follow_redirects=True)
    assert b'Zalogowano' in login.data

    with app_instance.app_context():
        db.session.add(Booking(training_id=training_id, volunteer_id=volunteer_id))
        db.session.commit()

    from app.admin_routes import EmailSendError

    def fail_send(*args, **kwargs):
        raise EmailSendError('smtp boom')

    monkeypatch.setattr('app.admin_routes.send_email', fail_send)

    resp = client.post(f'/admin/trainings/{training_id}/cancel', follow_redirects=True)

    assert resp.status_code == 200
    assert b'Trening zosta\xc5\x82 oznaczony jako odwo\xc5\x82any.' in resp.data
    assert b'smtp boom' in resp.data

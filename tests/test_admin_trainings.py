from datetime import datetime

import pytest

from app import db
from app.models import Coach, Location, Training


@pytest.fixture
def coach_and_location(app_instance):
    with app_instance.app_context():
        coach = Coach(first_name="Repeat", last_name="Coach", phone_number="123456")
        location = Location(name="Repeat Hall")
        db.session.add_all([coach, location])
        db.session.commit()
        yield coach.id, location.id


def test_manage_trainings_repeat_controls_render(client, coach_and_location):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.get("/admin/trainings")
    assert response.status_code == 200
    page = response.get_data(as_text=True)

    assert "Powtarzaj" in page
    assert 'id="repeat-toggle"' in page
    assert 'name="repeat_interval"' in page
    assert 'name="repeat_until"' in page
    assert "Łącznie wystąpień" in page


def test_manage_trainings_repeat_creates_series_skipping_conflicts(
    client, app_instance, coach_and_location
):
    coach_id, location_id = coach_and_location
    conflict_date = datetime(2024, 1, 10, 18, 0)
    with app_instance.app_context():
        conflict = Training(
            date=conflict_date,
            coach_id=coach_id,
            location_id=location_id,
            max_volunteers=1,
        )
        db.session.add(conflict)
        db.session.commit()

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.post(
        "/admin/trainings",
        data={
            "date": "2024-01-03T18:00",
            "location_id": str(location_id),
            "coach_id": str(coach_id),
            "max_volunteers": "4",
            "repeat": "y",
            "repeat_interval": "1",
            "repeat_until": "2024-01-17",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Dodano 2 z 3 zaplanowanych treningów." in page
    assert "Pominięto 2024-01-10 18:00" in page

    with app_instance.app_context():
        trainings = (
            Training.query.filter_by(location_id=location_id, is_deleted=False)
            .order_by(Training.date)
            .all()
        )

        assert {t.date.strftime("%Y-%m-%d %H:%M") for t in trainings} == {
            "2024-01-03 18:00",
            "2024-01-10 18:00",
            "2024-01-17 18:00",
        }

        new_trainings = [
            t for t in trainings if t.date.strftime("%Y-%m-%d %H:%M") != "2024-01-10 18:00"
        ]
        assert len(new_trainings) == 2
        for training in new_trainings:
            assert training.max_volunteers == 4
            assert training.coach_id == coach_id
            assert training.location_id == location_id


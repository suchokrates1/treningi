from datetime import datetime, date

import pytest

from app import db
from app.models import Coach, Location, Training, TrainingSeries


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
    assert "Dzień tygodnia" in page
    assert 'id="weekday-label"' in page
    assert 'name="create_schedule"' in page


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
        series_ids = {t.series_id for t in new_trainings}
        assert len(series_ids) == 1
        assert series_ids.pop() is not None
        for training in new_trainings:
            assert training.max_volunteers == 4
            assert training.coach_id == coach_id
            assert training.location_id == location_id


def test_manage_trainings_series_metadata_saved(client, app_instance, coach_and_location):
    coach_id, location_id = coach_and_location

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
            "max_volunteers": "5",
            "repeat": "y",
            "repeat_interval": "2",
            "repeat_until": "2024-01-31",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app_instance.app_context():
        series = TrainingSeries.query.one()
        assert series.start_date == datetime(2024, 1, 3, 18, 0)
        assert series.repeat is True
        assert series.repeat_interval_weeks == 2
        assert series.repeat_until == date(2024, 1, 31)
        assert series.max_volunteers == 5
        assert series.coach_id == coach_id
        assert series.location_id == location_id
        assert series.planned_count == 3
        assert series.created_count == 3
        assert series.skipped_dates == []

        trainings = Training.query.filter(Training.series_id == series.id).all()
        assert len(trainings) == 3


def test_manage_trainings_single_session_has_series(
    client, app_instance, coach_and_location
):
    coach_id, location_id = coach_and_location

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.post(
        "/admin/trainings",
        data={
            "date": "2024-02-05T19:30",
            "location_id": str(location_id),
            "coach_id": str(coach_id),
            "max_volunteers": "6",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app_instance.app_context():
        series = TrainingSeries.query.one()
        assert series.repeat is False
        assert series.repeat_interval_weeks is None
        assert series.repeat_until is None
        assert series.planned_count == 1
        assert series.created_count == 1
        assert series.skipped_dates == []

        trainings = Training.query.all()
        assert len(trainings) == 1
        assert trainings[0].series_id == series.id


def _series_key_for(training: Training) -> str:
    return (
        f"{training.date.weekday()}-"
        f"{training.date.strftime('%H%M')}-"
        f"c{training.coach_id}-"
        f"l{training.location_id}"
    )


def test_edit_series_updates_trainings(client, app_instance, coach_and_location):
    coach_id, location_id = coach_and_location

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.post(
        "/admin/trainings",
        data={
            "date": "2099-01-03T18:00",
            "location_id": str(location_id),
            "coach_id": str(coach_id),
            "max_volunteers": "4",
            "repeat": "y",
            "repeat_interval": "1",
            "repeat_until": "2099-01-17",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app_instance.app_context():
        new_coach = Coach(
            first_name="Updated",
            last_name="Coach",
            phone_number="789",
        )
        new_location = Location(name="Updated Hall")
        db.session.add_all([new_coach, new_location])
        db.session.commit()

        series = TrainingSeries.query.one()
        trainings = sorted(
            [t for t in series.trainings if not t.is_deleted],
            key=lambda t: t.date,
        )
        assert trainings
        series_key = _series_key_for(trainings[0])
        new_coach_id = new_coach.id
        new_location_id = new_location.id

    update = client.post(
        f"/admin/trainings/series/{series_key}/edit",
        data={
            "coach_id": str(new_coach_id),
            "location_id": str(new_location_id),
            "max_volunteers": "7",
        },
        follow_redirects=True,
    )
    assert update.status_code == 200
    page = update.get_data(as_text=True)
    assert "Zaktualizowano serię treningów." in page

    with app_instance.app_context():
        series = TrainingSeries.query.one()
        assert series.coach_id == new_coach_id
        assert series.location_id == new_location_id
        assert series.max_volunteers == 7

        trainings = sorted(
            Training.query.filter_by(series_id=series.id, is_deleted=False),
            key=lambda t: t.date,
        )
        assert trainings
        for training in trainings:
            assert training.coach_id == new_coach_id
            assert training.location_id == new_location_id
            assert training.max_volunteers == 7


def test_delete_series_marks_trainings_deleted(
    client, app_instance, coach_and_location
):
    coach_id, location_id = coach_and_location

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.post(
        "/admin/trainings",
        data={
            "date": "2099-02-05T19:30",
            "location_id": str(location_id),
            "coach_id": str(coach_id),
            "max_volunteers": "5",
            "repeat": "y",
            "repeat_interval": "1",
            "repeat_until": "2099-02-19",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app_instance.app_context():
        series = TrainingSeries.query.one()
        trainings = sorted(
            [t for t in series.trainings if not t.is_deleted],
            key=lambda t: t.date,
        )
        assert trainings
        series_key = _series_key_for(trainings[0])

    delete_resp = client.post(
        f"/admin/trainings/series/{series_key}/delete",
        follow_redirects=True,
    )
    assert delete_resp.status_code == 200
    page = delete_resp.get_data(as_text=True)
    assert "Seria treningów została usunięta." in page

    with app_instance.app_context():
        trainings = Training.query.all()
        assert trainings
        assert all(t.is_deleted for t in trainings)
        series = TrainingSeries.query.one()
        assert series.repeat is False

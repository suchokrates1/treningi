from datetime import date, datetime, timedelta, timezone

import pytest

from app import db
from app.models import Coach, Location, Training, TrainingSeries
from app.admin_routes import _generate_schedule
from app.forms import TrainingForm


@pytest.fixture
def series_setup(app_instance):
    with app_instance.app_context():
        coach_one = Coach(first_name="Adam", last_name="Alpha", phone_number="111")
        coach_two = Coach(first_name="Beata", last_name="Beta", phone_number="222")
        location_one = Location(name="Sala A")
        location_two = Location(name="Sala B")
        db.session.add_all([coach_one, coach_two, location_one, location_two])
        db.session.commit()

        series = TrainingSeries(
            start_date=datetime(2024, 1, 5, 18, 0),
            repeat=True,
            repeat_interval_weeks=1,
            repeat_until=date(2024, 1, 12),
            planned_count=2,
            created_count=2,
            coach_id=coach_one.id,
            location_id=location_one.id,
            max_volunteers=4,
        )
        db.session.add(series)
        db.session.flush()

        first_training = Training(
            date=datetime(2024, 1, 5, 18, 0),
            coach_id=coach_one.id,
            location_id=location_one.id,
            max_volunteers=4,
            series_id=series.id,
        )
        second_training = Training(
            date=datetime(2024, 1, 12, 18, 0),
            coach_id=coach_one.id,
            location_id=location_one.id,
            max_volunteers=4,
            series_id=series.id,
        )
        conflicting_training = Training(
            date=datetime(2024, 1, 12, 19, 30),
            coach_id=coach_two.id,
            location_id=location_two.id,
            max_volunteers=3,
        )
        db.session.add_all([first_training, second_training, conflicting_training])
        db.session.commit()

        yield {
            "series_id": series.id,
            "coach_one": coach_one.id,
            "coach_two": coach_two.id,
            "location_one": location_one.id,
            "location_two": location_two.id,
            "first_training": first_training.id,
            "second_training": second_training.id,
            "conflict_training": conflicting_training.id,
        }


def test_edit_series_updates_trainings_and_reports_conflicts(
    client, app_instance, series_setup
):
    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    series_id = series_setup["series_id"]
    new_data = {
        "time": "19:30",
        "coach_id": str(series_setup["coach_two"]),
        "location_id": str(series_setup["location_two"]),
        "max_volunteers": "6",
    }

    response = client.post(
        f"/admin/schedule/{series_id}/edit",
        data=new_data,
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Zaktualizowano 1 z 2 treningów serii." in page
    assert "Pominięto 2024-01-12 19:30 z powodu kolizji." in page

    with app_instance.app_context():
        updated_first = db.session.get(Training, series_setup["first_training"])
        skipped_second = db.session.get(Training, series_setup["second_training"])
        conflict = db.session.get(Training, series_setup["conflict_training"])
        series = db.session.get(TrainingSeries, series_id)

        assert updated_first.date == datetime(2024, 1, 5, 19, 30)
        assert updated_first.coach_id == series_setup["coach_two"]
        assert updated_first.location_id == series_setup["location_two"]
        assert updated_first.max_volunteers == 6

        assert skipped_second.date == datetime(2024, 1, 12, 18, 0)
        assert skipped_second.coach_id == series_setup["coach_one"]
        assert skipped_second.location_id == series_setup["location_one"]

        assert conflict.date == datetime(2024, 1, 12, 19, 30)
        assert conflict.location_id == series_setup["location_two"]

        assert series.coach_id == series_setup["coach_two"]
        assert series.location_id == series_setup["location_two"]
        assert series.max_volunteers == 6
        assert series.start_date == datetime(2024, 1, 5, 19, 30)


def test_delete_series_marks_trainings_as_deleted(client, app_instance):
    with app_instance.app_context():
        coach = Coach(first_name="Olga", last_name="Omega", phone_number="444")
        location = Location(name="Sala C")
        db.session.add_all([coach, location])
        db.session.commit()

        series = TrainingSeries(
            start_date=datetime(2024, 2, 1, 17, 0),
            repeat=False,
            planned_count=3,
            created_count=3,
            coach_id=coach.id,
            location_id=location.id,
            max_volunteers=2,
        )
        db.session.add(series)
        db.session.flush()

        trainings = [
            Training(
                date=datetime(2024, 2, 1, 17, 0),
                coach_id=coach.id,
                location_id=location.id,
                max_volunteers=2,
                series_id=series.id,
            ),
            Training(
                date=datetime(2024, 2, 8, 17, 0),
                coach_id=coach.id,
                location_id=location.id,
                max_volunteers=2,
                series_id=series.id,
            ),
            Training(
                date=datetime(2024, 2, 15, 17, 0),
                coach_id=coach.id,
                location_id=location.id,
                max_volunteers=2,
                series_id=series.id,
                is_deleted=True,
            ),
        ]
        db.session.add_all(trainings)
        db.session.commit()

        series_id = series.id
        training_ids = [t.id for t in trainings]

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    response = client.post(
        f"/admin/schedule/{series_id}/delete",
        data={"confirm": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Usunięto 2 treningów serii." in page

    with app_instance.app_context():
        trainings = [db.session.get(Training, tid) for tid in training_ids]
        assert all(t.is_deleted for t in trainings)
        series = db.session.get(TrainingSeries, series_id)
        assert series.created_count == 0


def test_generate_schedule_handles_high_occurrence_count():
    start = datetime(2024, 1, 5, 18, 0)
    occurrences = 250
    interval_weeks = 2

    schedule = _generate_schedule(
        start,
        occurrences_limit=occurrences,
        interval_weeks=interval_weeks,
    )

    assert len(schedule) == occurrences


def test_naive_training_conflict_detected_in_schedule_preview(
    client, app_instance, monkeypatch
):
    with app_instance.app_context():
        coach = Coach(first_name="Inga", last_name="Iota", phone_number="555")
        location = Location(name="Sala D")
        db.session.add_all([coach, location])
        db.session.commit()
        coach_id = coach.id
        location_id = location.id

    login = client.post(
        "/admin/login", data={"password": "secret"}, follow_redirects=True
    )
    assert login.status_code == 200

    form_data = {
        "date": "2024-03-01T10:00",
        "location_id": str(location_id),
        "coach_id": str(coach_id),
        "max_volunteers": "4",
        "repeat_interval": "1",
        "repeat_until": "",
    }

    initial_response = client.post(
        "/admin/trainings", data=form_data, follow_redirects=True
    )
    assert initial_response.status_code == 200

    aware_occurrence = datetime(2024, 3, 1, 10, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        TrainingForm,
        "iter_occurrences",
        lambda self: [aware_occurrence],
    )

    collision_response = client.post(
        "/admin/trainings", data=form_data, follow_redirects=True
    )
    assert collision_response.status_code == 200
    page = collision_response.get_data(as_text=True)
    assert "Pominięto 1 terminów z konfliktem." in page
    assert "Pominięto 2024-03-01 10:00" in page

    with app_instance.app_context():
        trainings = Training.query.filter_by(location_id=location_id).all()
        assert len(trainings) == 1
        conflict = (
            Training.query.filter(
                Training.date == aware_occurrence,
                Training.location_id == location_id,
            )
            .order_by(Training.id)
            .first()
        )
        assert conflict is not None

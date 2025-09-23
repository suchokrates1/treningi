from datetime import datetime, timezone

from app import db
from app.models import Coach, Location, Training


def _login(client):
    return client.post("/admin/login", data={"password": "secret"}, follow_redirects=True)


def _prepare_data(app_instance):
    with app_instance.app_context():
        coach = Coach(first_name="Alice", last_name="Trainer", phone_number="123")
        location = Location(name="Main Hall")
        db.session.add_all([coach, location])
        db.session.commit()
        return coach.id, location.id


def test_schedule_page_renders_form(client, app_instance):
    coach_id, location_id = _prepare_data(app_instance)
    _login(client)

    response = client.get("/admin/schedule")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "Harmonogram treningów" in content
    assert "name=\"days\"" in content
    assert str(coach_id) in content
    assert str(location_id) in content


def test_schedule_creates_trainings(client, app_instance):
    coach_id, location_id = _prepare_data(app_instance)
    with app_instance.app_context():
        existing = Training(
            date=datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
            coach_id=coach_id,
            location_id=location_id,
            max_volunteers=5,
        )
        db.session.add(existing)
        db.session.commit()

    _login(client)

    base_data = {
        "days": ["0", "2"],
        "start_date": "2024-01-01",
        "start_time": "10:00",
        "interval_weeks": "1",
        "end_date": "",
        "occurrences": "3",
        "location_id": str(location_id),
        "coach_id": str(coach_id),
        "max_volunteers": "4",
    }

    preview_data = dict(base_data)
    preview_data["preview"] = "Podgląd"
    preview_response = client.post("/admin/schedule", data=preview_data)

    assert preview_response.status_code == 200
    page = preview_response.get_data(as_text=True)
    assert "Podsumowanie zaplanowanych treningów" in page
    assert "2024-01-01 10:00" in page

    save_data = dict(base_data)
    save_data["save"] = "Zapisz harmonogram"
    response = client.post("/admin/schedule", data=save_data)

    assert response.status_code == 302

    with app_instance.app_context():
        trainings = (
            Training.query.filter_by(location_id=location_id, coach_id=coach_id)
            .order_by(Training.date)
            .all()
        )
        created_dates = [t.date for t in trainings]
        assert len(created_dates) == 4
        expected = {
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 8, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 10, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
        }
        normalized = {dt.replace(tzinfo=None) for dt in created_dates}
        expected_normalized = {dt.replace(tzinfo=None) for dt in expected}
        assert normalized == expected_normalized

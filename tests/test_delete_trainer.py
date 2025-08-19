import pytest
from app import db
from app.models import Coach


def test_delete_trainer(client, app_instance):
    with app_instance.app_context():
        coach = Coach(first_name="Temp", last_name="Coach", phone_number="000")
        db.session.add(coach)
        db.session.commit()
        coach_id = coach.id

    login = client.post("/admin/login", data={"password": "secret"}, follow_redirects=True)
    assert login.status_code == 200

    resp = client.post(f"/admin/trainers/{coach_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert "Trener został usunięty." in resp.get_data(as_text=True)

    with app_instance.app_context():
        assert db.session.get(Coach, coach_id) is None

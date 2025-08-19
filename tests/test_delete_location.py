from app import db
from app.models import Location


def test_delete_location_removes_record(client, app_instance):
    with app_instance.app_context():
        location = Location(name="Hall")
        db.session.add(location)
        db.session.commit()
        loc_id = location.id

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    response = client.post(
        f"/admin/locations/{loc_id}/delete",
        follow_redirects=True,
    )

    assert "Miejsce zostało usunięte." in response.get_data(as_text=True)
    with app_instance.app_context():
        assert db.session.get(Location, loc_id) is None

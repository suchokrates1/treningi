import os
from datetime import datetime, timezone

import pytest

from app import create_app, db
from app.models import Coach, Location, Training, Volunteer


@pytest.fixture
def app_instance(monkeypatch):
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    monkeypatch.setattr("app.email_utils.send_email", lambda *a, **k: (True, None))


@pytest.fixture(autouse=True)
def clear_pending_signups():
    """Cancel any pending signup timers and clear the dict between tests."""
    from app.whatsapp_utils import _pending_signups, _pending_lock
    yield
    with _pending_lock:
        for entry in _pending_signups.values():
            if entry.get("timer"):
                entry["timer"].cancel()
        _pending_signups.clear()


@pytest.fixture
def sample_data(app_instance):
    """Create one coach, location, volunteer and training for tests."""
    with app_instance.app_context():
        coach = Coach(first_name="John", last_name="Doe", phone_number="123")
        location = Location(name="Court")
        volunteer = Volunteer(
            first_name="Ann",
            last_name="Smith",
            email="ann@example.com",
            is_adult=True,
        )
        training = Training(
            date=datetime.now(timezone.utc),
            coach=coach,
            location=location,
        )
        db.session.add_all([coach, location, volunteer, training])
        db.session.commit()
        return training.id, volunteer.id, coach.id, location.id

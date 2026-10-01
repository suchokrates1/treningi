import json
from unittest.mock import patch

import pytest

from app.models import Coach, Volunteer


def _webhook_payload(from_field: str, body: str = "cześć") -> dict:
    return {
        "event": "message",
        "payload": {
            "fromMe": False,
            "from": from_field,
            "body": body,
            "id": f"msg-{from_field}-{body}",
        },
    }


@pytest.fixture
def volunteer_with_phone(app_instance):
    with app_instance.app_context():
        volunteer = Volunteer(
            first_name="Anna",
            last_name="Kowalska",
            email="anna@example.com",
            phone_number="607 575 408",
            is_adult=True,
        )
        from app import db
        db.session.add(volunteer)
        db.session.commit()
        return volunteer.id


@pytest.fixture
def coach_with_phone(app_instance):
    with app_instance.app_context():
        coach = Coach(
            first_name="Jan",
            last_name="Nowak",
            phone_number="+48 500 100 200",
        )
        from app import db
        db.session.add(coach)
        db.session.commit()
        return coach.id


def test_unknown_sender_is_ignored(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.webhook_routes.send_whatsapp_message",
        lambda *a, **k: sent.append((a, k)),
    )
    monkeypatch.setattr("app.webhook_routes.ask_gemini", lambda *a, **k: "AI reply")

    resp = client.post(
        "/webhook/whatsapp",
        data=json.dumps(_webhook_payload("491739553455@c.us")),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ignored"
    assert sent == []


def test_volunteer_gets_ai_for_unknown_intent(client, volunteer_with_phone, monkeypatch):
    ai_calls = []
    sent = []
    monkeypatch.setattr(
        "app.webhook_routes.ask_gemini",
        lambda msg, volunteer=None, coach=None: ai_calls.append((msg, volunteer, coach)) or "AI reply",
    )
    monkeypatch.setattr(
        "app.webhook_routes.send_whatsapp_message",
        lambda *a, **k: sent.append((a, k)),
    )

    resp = client.post(
        "/webhook/whatsapp",
        data=json.dumps(_webhook_payload("48607575408@c.us", "kiedy trening?")),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.get_json()["action"] == "unknown"
    assert len(ai_calls) == 1
    assert ai_calls[0][1] is not None
    assert sent


def test_coach_gets_ai_for_unknown_intent(client, coach_with_phone, monkeypatch):
    ai_calls = []
    monkeypatch.setattr(
        "app.webhook_routes.ask_gemini",
        lambda msg, volunteer=None, coach=None: ai_calls.append((msg, volunteer, coach)) or "Coach AI",
    )
    monkeypatch.setattr(
        "app.webhook_routes.send_whatsapp_message",
        lambda *a, **k: None,
    )

    resp = client.post(
        "/webhook/whatsapp",
        data=json.dumps(_webhook_payload("48500100200@c.us", "ile mam wolontariuszy?")),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.get_json()["action"] == "coach_ai"
    assert len(ai_calls) == 1
    assert ai_calls[0][2] is not None
    assert ai_calls[0][1] is None


def test_ask_gemini_rejects_unknown_sender(app_instance):
    with app_instance.app_context():
        from app.ai_assistant import ask_gemini

        assert ask_gemini("hello") is None


def test_ignored_phone_is_not_answered_when_whatsapp_uses_lid(client, app_instance, monkeypatch):
    from app import db
    from app.models import Volunteer

    with app_instance.app_context():
        db.session.add(Volunteer(
            first_name="Dawid",
            last_name="Suchodolski",
            email="dawid@example.com",
            phone_number="",
            is_adult=True,
        ))
        db.session.commit()
    app_instance.config["IGNORED_PHONES"] = "48697495755"
    sent = []
    monkeypatch.setattr(
        "app.webhook_routes.send_whatsapp_message",
        lambda *a, **k: sent.append((a, k)),
    )
    monkeypatch.setattr(
        "app.webhook_routes._extract_phone_from_lid",
        lambda lid: "48697495755",
    )
    payload = _webhook_payload("205866389221398@lid", "Ok")
    payload["payload"]["_data"] = {"notifyName": "Dawid Suchodolski"}

    resp = client.post(
        "/webhook/whatsapp",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.get_json()["reason"] == "ignored phone"
    assert sent == []

"""AI assistant for WhatsApp conversations using Gemini API.

Uses the free tier of Gemini 2.5 Flash to handle conversational messages
that don't match structured commands (POTWIERDZAM / REZYGNUJĘ).
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from flask import current_app

from .models import Volunteer, Booking, Training, db


# System prompt that defines the assistant's personality and knowledge
SYSTEM_PROMPT = """\
Jesteś asystentem Fundacji Widzimy Inaczej, która organizuje treningi blind tenisa \
(tenisa dla osób niewidomych i słabowidzących) z udziałem wolontariuszy.

Odpowiadasz na wiadomości WhatsApp od wolontariuszy. Bądź uprzejmy, zwięzły i pomocny. \
Odpowiadaj po polsku. Używaj emoji oszczędnie.

KONTEKST ORGANIZACJI:
- Fundacja Widzimy Inaczej organizuje regularne treningi blind tenisa
- Wolontariusze pomagają osobom niewidomym podczas treningów
- Wolontariusze zapisują się na treningi przez stronę internetową
- Dzień przed treningiem wysyłamy przypomnienie z prośbą o potwierdzenie
- Wolontariusz może odpowiedzieć POTWIERDZAM lub REZYGNUJĘ

ZASADY:
- Jeśli ktoś pyta o zapisy/rejestrację, kieruj na stronę: treningi.widzimyinaczej.org.pl
- Jeśli ktoś pyta o kontakt z fundacją: biuro@widzimyinaczej.org.pl
- Jeśli ktoś pyta o godziny/lokalizacje treningów, podaj informacje z kontekstu (jeśli dostępne)
- NIE potwierdzaj ani nie odwołuj treningów - to robi system automatycznie na komendę POTWIERDZAM/REZYGNUJĘ
- Jeśli ktoś chce potwierdzić/odwołać ale pisze niestandardowo, podpowiedz żeby napisał POTWIERDZAM lub REZYGNUJĘ
- Odpowiadaj krótko, max 2-3 zdania
- Nie wymyślaj informacji których nie znasz
"""


def _get_volunteer_context(volunteer: Volunteer) -> str:
    """Build context about volunteer's upcoming trainings."""
    now = datetime.now(timezone.utc)
    upcoming = (
        Booking.query.join(Training)
        .filter(
            Booking.volunteer_id == volunteer.id,
            Training.date >= now,
            Training.is_canceled.is_(False),
            Training.is_deleted.is_(False),
        )
        .order_by(Training.date)
        .limit(5)
        .all()
    )

    if not upcoming:
        return f"Wolontariusz: {volunteer.first_name} {volunteer.last_name}. Brak nadchodzących treningów."

    lines = [f"Wolontariusz: {volunteer.first_name} {volunteer.last_name}"]
    lines.append("Nadchodzące treningi:")
    for b in upcoming:
        t = b.training
        status = "potwierdzony" if b.is_confirmed is True else (
            "odwołany" if b.is_confirmed is False else "oczekuje potwierdzenia"
        )
        coach_phone = t.coach.phone_number or "brak"
        lines.append(
            f"- {t.date.strftime('%Y-%m-%d %H:%M')} w {t.location.name}, "
            f"trener: {t.coach.first_name} {t.coach.last_name} (tel: {coach_phone}), "
            f"status: {status}"
        )
    return "\n".join(lines)


def ask_gemini(
    message: str,
    volunteer: Optional[Volunteer] = None,
) -> Optional[str]:
    """Send a message to Gemini and get a response.

    Returns the response text or None if the API call fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        current_app.logger.warning("GEMINI_API_KEY not configured")
        return None

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Build the prompt with volunteer context
    context = ""
    if volunteer:
        try:
            context = _get_volunteer_context(volunteer)
        except Exception:
            context = f"Wolontariusz: {volunteer.first_name} {volunteer.last_name}"

    user_content = message
    if context:
        user_content = f"[Kontekst: {context}]\n\nWiadomość od wolontariusza: {message}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 256,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }

    try:
        current_app.logger.info("Calling Gemini API for message: %s", message[:50])
        resp = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=15,
        )

        if resp.status_code != 200:
            current_app.logger.error("Gemini API error: %s %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            current_app.logger.warning("Gemini returned no candidates")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None

        text = parts[0].get("text", "").strip()
        if not text:
            return None

        current_app.logger.info("Gemini response: %s", text[:100])
        return text

    except requests.RequestException as exc:
        current_app.logger.exception("Gemini API request failed: %s", exc)
        return None
    except (KeyError, IndexError, ValueError) as exc:
        current_app.logger.exception("Failed to parse Gemini response: %s", exc)
        return None

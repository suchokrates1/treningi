"""WhatsApp integration using WAHA (WhatsApp HTTP API) selfhosted solution.

WAHA is a selfhosted WhatsApp API. Documentation: https://waha.devlike.pro/
Docker: devlikeapro/waha

Configuration environment variables:
- WHATSAPP_API_URL: WAHA API base URL (e.g. http://localhost:3000)
- WHATSAPP_SESSION: WAHA session name (default: default)
- WHATSAPP_API_KEY: WAHA API key (optional, if authentication enabled)
"""

import re
import threading
from flask import current_app
import requests
from typing import Optional


# Max length for user-provided text in WhatsApp messages
MAX_NAME_LENGTH = 100
MAX_LOCATION_LENGTH = 200

# Grace period (seconds) before sending signup confirmation to allow consolidation
SIGNUP_GRACE_PERIOD_SECONDS = 90

# Milestone booking counts that trigger celebration messages
MILESTONE_COUNTS = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]

# In-memory pending signups: volunteer_id -> {timer, trainings: [...], app_context_data}
_pending_signups: dict[int, dict] = {}
_pending_lock = threading.Lock()

# ── Message footer ───────────────────────────────────────────────
_FOOTER = "🎾 *Fundacja Widzimy Inaczej*\n_System zapisów Blind Tenis_"


def _get_template_body(key: str, default: str) -> str:
    """Load WhatsApp template body from DB, falling back to *default*."""
    try:
        from .models import WhatsAppTemplate
        tpl = WhatsAppTemplate.query.filter_by(key=key).first()
        if tpl and tpl.body:
            return tpl.body
    except Exception:
        pass
    return default


def sanitize_for_whatsapp(text: str, max_length: int = 200) -> str:
    """Sanitize text for safe inclusion in WhatsApp messages.
    
    Removes control characters and truncates to max length.
    """
    if not text:
        return ""
    # Remove null bytes and control characters
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Truncate
    return text[:max_length].strip()


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to international format for WhatsApp.
    
    Converts Polish phone numbers to +48XXXXXXXXX format.
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', phone)
    
    # If starts with +, keep as is
    if phone.startswith('+'):
        return phone
    
    # If starts with 48 and has 11 digits, add +
    if phone.startswith('48') and len(phone) == 11:
        return f'+{phone}'
    
    # If 9 digits, assume Polish number
    if len(phone) == 9:
        return f'+48{phone}'
    
    # Otherwise return with + prefix
    return f'+{phone}' if not phone.startswith('+') else phone


def format_phone_display(phone: str) -> str:
    """Format phone number for display as 000 000 000."""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Remove country code if present
    if digits.startswith('48') and len(digits) == 11:
        digits = digits[2:]
    
    # Format as 000 000 000
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    
    return phone


def get_waha_config() -> dict:
    """Get WAHA configuration from app config."""
    return {
        'api_url': current_app.config.get('WHATSAPP_API_URL', 'http://waha:3000'),
        'session': current_app.config.get('WHATSAPP_SESSION', 'default'),
        'api_key': current_app.config.get('WHATSAPP_API_KEY'),
    }


def send_whatsapp_message(
    phone: str,
    message: str,
    *,
    chat_id: Optional[str] = None,
    api_url: Optional[str] = None,
    session: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Send a WhatsApp message using WAHA API.
    
    Args:
        phone: Phone number (will be normalized) – ignored when *chat_id* given
        message: Message text to send
        chat_id: Ready-to-use WAHA chatId (e.g. ``12345@lid``)
        api_url: Override WAHA API URL
        session: Override WAHA session name
        api_key: Override WAHA API key
        
    Returns:
        Tuple of (success, error_message)
    """
    config = get_waha_config()
    api_url = api_url or config['api_url']
    session = session or config['session']
    api_key = api_key or config['api_key']
    
    if not api_url:
        current_app.logger.warning("WHATSAPP_API_URL not configured; skipping WhatsApp message")
        return True, None
    
    # Use provided chat_id (e.g. @lid) or build one from phone
    if not chat_id:
        normalized_phone = normalize_phone_number(phone)
        if not normalized_phone:
            return False, "Invalid phone number"
        # WAHA expects phone without + prefix for chatId
        chat_id = normalized_phone.lstrip('+') + '@c.us'
    
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['X-Api-Key'] = api_key
    
    payload = {
        'chatId': chat_id,
        'text': message,
        'session': session,
    }
    
    try:
        current_app.logger.info(
            "Sending WhatsApp message to %s via %s",
            chat_id,
            api_url,
        )
        
        response = requests.post(
            f'{api_url}/api/sendText',
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code in (200, 201):
            current_app.logger.info("WhatsApp message sent successfully")
            return True, None
        else:
            error_msg = f"WAHA API error: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            return False, error_msg
            
    except requests.RequestException as exc:
        error_msg = f"WhatsApp sending failed: {exc}"
        current_app.logger.exception(error_msg)
        return False, error_msg


def _milestone_line(booking_count: int) -> str:
    """Return a celebration line if *booking_count* is a milestone, else ''."""
    if booking_count in MILESTONE_COUNTS:
        return f"\n🏆 To już Twój *{booking_count}. wolontariat* z nami! Dziękujemy! 💛\n"
    return ""


def get_volunteer_booking_count(volunteer_id: int) -> int:
    """Return the total number of (non-canceled) bookings for *volunteer_id*."""
    from .models import Booking, Training
    return (
        Booking.query
        .join(Training)
        .filter(
            Booking.volunteer_id == volunteer_id,
            Training.is_canceled.is_(False),
        )
        .count()
    )


# ═══════════════════════════════════════════════════════════════
#  Coach notifications
# ═══════════════════════════════════════════════════════════════

def notify_coach_new_signup(
    coach_phone: str,
    coach_name: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a coach about a new volunteer signup."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "📋 *Nowy zapis na trening!*\n\n"
        "Cześć {trener}! 👋\n\n"
        "👤 Wolontariusz: *{wolontariusz}*\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        + _FOOTER
    )
    body = _get_template_body("coach_new_signup", default)
    message = (
        body
        .replace("{trener}", coach_name)
        .replace("{wolontariusz}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{miejsce}", training_location)
    )
    return send_whatsapp_message(coach_phone, message)


def notify_coach_volunteer_canceled(
    coach_phone: str,
    coach_name: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a coach that a volunteer has canceled their booking."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "⚠️ *Wypisanie z treningu*\n\n"
        "Cześć {trener}! 👋\n\n"
        "👤 Wolontariusz *{wolontariusz}* wypisał się:\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        + _FOOTER
    )
    body = _get_template_body("coach_volunteer_canceled", default)
    message = (
        body
        .replace("{trener}", coach_name)
        .replace("{wolontariusz}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{miejsce}", training_location)
    )
    return send_whatsapp_message(coach_phone, message)


# ═══════════════════════════════════════════════════════════════
#  Volunteer reminders (day before)
# ═══════════════════════════════════════════════════════════════

def notify_volunteer_reminder(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_time: str,
    training_location: str,
    coach_name: str,
    coach_phone: str,
) -> tuple[bool, Optional[str]]:
    """Send a reminder to a volunteer about their upcoming training (day before)."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)
    coach_name = sanitize_for_whatsapp(coach_name, MAX_NAME_LENGTH)

    formatted_coach_phone = format_phone_display(coach_phone)
    default = (
        "🎾 *Przypomnienie o jutrzejszym wolontariacie!*\n\n"
        "Cześć {imię}! 👋\n\n"
        "Przypominamy, że jutro o *{godzina}* masz wolontariat:\n\n"
        "📍 Miejsce: {miejsce}\n"
        "👨‍🏫 Trener: {trener}\n"
        "📞 Telefon: {telefon}\n\n"
        "📩 *Odpisz:*\n"
        "✅ POTWIERDZAM — będę\n"
        "❌ REZYGNUJĘ — nie mogę\n\n"
        + _FOOTER
    )
    body = _get_template_body("volunteer_reminder", default)
    message = (
        body
        .replace("{imię}", volunteer_name)
        .replace("{godzina}", training_time)
        .replace("{miejsce}", training_location)
        .replace("{trener}", coach_name)
        .replace("{telefon}", formatted_coach_phone)
    )
    return send_whatsapp_message(volunteer_phone, message)


def notify_volunteer_reminder_multi(
    volunteer_phone: str,
    volunteer_name: str,
    trainings_info: list[dict],
) -> tuple[bool, Optional[str]]:
    """Send a combined reminder for multiple trainings on the same day.

    Each entry in *trainings_info* should have keys:
    ``time``, ``location``, ``coach_name``, ``coach_phone``.
    """
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)

    lines = [
        f"🎾 *Przypomnienie o jutrzejszych wolontariatach!*\n",
        f"Cześć {volunteer_name}! 👋\n",
        f"Jutro masz *{len(trainings_info)} wolontariaty*:\n",
    ]
    for i, t in enumerate(trainings_info, 1):
        loc = sanitize_for_whatsapp(t['location'], MAX_LOCATION_LENGTH)
        coach = sanitize_for_whatsapp(t['coach_name'], MAX_NAME_LENGTH)
        phone_fmt = format_phone_display(t['coach_phone'])
        lines.append(
            f"*{i}.* 🕐 {t['time']} — 📍 {loc}\n"
            f"   👨\u200d🏫 {coach}, 📞 {phone_fmt}"
        )

    lines.append("")
    lines.append("📩 *Odpisz:*")
    if len(trainings_info) > 1:
        lines.append("✅ POTWIERDZAM — potwierdź wszystkie")
        lines.append("✅ POTWIERDZAM 1 — potwierdź tylko pierwszy")
        lines.append("❌ REZYGNUJĘ — zrezygnuj ze wszystkich")
    else:
        lines.append("✅ POTWIERDZAM — będę")
        lines.append("❌ REZYGNUJĘ — nie mogę")
    lines.append(f"\n{_FOOTER}")

    return send_whatsapp_message(volunteer_phone, "\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  Volunteer — training canceled / time changed
# ═══════════════════════════════════════════════════════════════

def notify_volunteer_training_canceled(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a volunteer that their training has been canceled."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "⚠️ *Trening został odwołany*\n\n"
        "Cześć {imię}! 👋\n\n"
        "Niestety trening zaplanowany na:\n\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        "został *odwołany*. Przepraszamy za utrudnienia.\n\n"
        + _FOOTER
    )
    body = _get_template_body("training_canceled", default)
    message = (
        body
        .replace("{imię}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{miejsce}", training_location)
    )
    return send_whatsapp_message(volunteer_phone, message)


def notify_volunteer_training_time_changed(
    volunteer_phone: str,
    volunteer_name: str,
    training_old_time: str,
    training_new_time: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a volunteer that their training time has been changed."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "⏰ *Zmiana godziny treningu!*\n\n"
        "Cześć {imię}! 👋\n\n"
        "Godzina Twojego treningu została zmieniona:\n\n"
        "📅 Data: {data}\n"
        "❌ Stara godzina: {stara_godzina}\n"
        "✅ Nowa godzina: *{nowa_godzina}*\n"
        "📍 Miejsce: {miejsce}\n\n"
        "📩 *Odpisz:*\n"
        "✅ POTWIERDZAM — będę o nowej godzinie\n"
        "❌ REZYGNUJĘ — nie mogę\n\n"
        + _FOOTER
    )
    body = _get_template_body("time_changed", default)
    message = (
        body
        .replace("{imię}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{stara_godzina}", training_old_time)
        .replace("{nowa_godzina}", training_new_time)
        .replace("{miejsce}", training_location)
    )
    return send_whatsapp_message(volunteer_phone, message)


# ═══════════════════════════════════════════════════════════════
#  Volunteer signup confirmation (with deferred consolidation)
# ═══════════════════════════════════════════════════════════════

def notify_volunteer_signup_confirmation(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
    booking_count: int = 0,
    *,
    coach_name: str = '',
    coach_phone: str = '',
) -> tuple[bool, Optional[str]]:
    """Send signup confirmation to volunteer (single training)."""
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)
    coach_name = sanitize_for_whatsapp(coach_name, MAX_NAME_LENGTH)
    formatted_coach_phone = format_phone_display(coach_phone) if coach_phone else ''
    milestone = _milestone_line(booking_count)

    returning_line = ""
    if booking_count > 1 and not milestone:
        returning_line = "\n🔄 Miło Cię znów widzieć!\n"

    default = (
        "✅ *Zapisano na wolontariat!*\n\n"
        "Cześć {imię}! 👋\n"
        "{powracajacy}"
        "{kamien_milowy}"
        "\nTwój zapis został przyjęty:\n\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n"
        "👨‍🏫 Trener: {trener}\n"
        "📞 Telefon: {telefon}\n\n"
        "📧 Sprawdź e-mail — wysłaliśmy szczegóły i dokumenty.\n\n"
        "Do zobaczenia! 👋\n\n"
        + _FOOTER
    )
    body = _get_template_body("signup_confirmation", default)
    message = (
        body
        .replace("{imię}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{miejsce}", training_location)
        .replace("{trener}", coach_name)
        .replace("{telefon}", formatted_coach_phone)
        .replace("{powracajacy}", returning_line)
        .replace("{kamien_milowy}", milestone)
    )
    return send_whatsapp_message(volunteer_phone, message)


def notify_volunteer_signup_confirmation_multi(
    volunteer_phone: str,
    volunteer_name: str,
    trainings_info: list[dict],
    booking_count: int = 0,
) -> tuple[bool, Optional[str]]:
    """Send consolidated signup confirmation for multiple trainings.

    Each entry in *trainings_info*: ``date``, ``location``,
    ``coach_name``, ``coach_phone``.

    When all trainings share the same location/coach, the shared info
    is shown once instead of being repeated for every entry.
    """
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    milestone = _milestone_line(booking_count)

    returning_line = ""
    if booking_count > 1 and not milestone:
        returning_line = "\n🔄 Miło Cię znów widzieć!\n"

    lines = [
        "✅ *Zapisano na wolontariat!*\n",
        f"Cześć {volunteer_name}! 👋",
    ]
    if returning_line:
        lines.append(returning_line.strip())
    if milestone:
        lines.append(milestone.strip())

    lines.append(f"\nTwoje zapisy ({len(trainings_info)}) zostały przyjęte:\n")

    # Check if all trainings share the same location + coach
    locations = {t.get('location', '') for t in trainings_info}
    coaches = {t.get('coach_name', '') for t in trainings_info}
    same_venue = len(locations) == 1 and len(coaches) == 1

    if same_venue:
        # Same location + coach → list only dates, show venue once
        for i, t in enumerate(trainings_info, 1):
            lines.append(f"*{i}.* 📅 {t['date']}")
        loc = sanitize_for_whatsapp(trainings_info[0]['location'], MAX_LOCATION_LENGTH)
        coach = sanitize_for_whatsapp(trainings_info[0].get('coach_name', ''), MAX_NAME_LENGTH)
        coach_ph = format_phone_display(trainings_info[0].get('coach_phone', ''))
        lines.append(f"\n📍 Miejsce: {loc}")
        if coach:
            lines.append(f"👨‍🏫 Trener: {coach}")
        if coach_ph:
            lines.append(f"📞 Telefon: {coach_ph}")
    else:
        # Different venues → show all details per training
        for i, t in enumerate(trainings_info, 1):
            loc = sanitize_for_whatsapp(t['location'], MAX_LOCATION_LENGTH)
            coach = sanitize_for_whatsapp(t.get('coach_name', ''), MAX_NAME_LENGTH)
            coach_ph = format_phone_display(t.get('coach_phone', ''))
            line = f"*{i}.* 📅 {t['date']} — 📍 {loc}"
            if coach:
                line += f"\n   👨‍🏫 {coach}"
                if coach_ph:
                    line += f", 📞 {coach_ph}"
            lines.append(line)

    lines.append("\n📧 Sprawdź e-mail — wysłaliśmy szczegóły i dokumenty.")
    lines.append(f"\nDo zobaczenia! 👋\n\n{_FOOTER}")

    return send_whatsapp_message(volunteer_phone, "\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  Deferred signup notification (grace period for consolidation)
# ═══════════════════════════════════════════════════════════════

def schedule_signup_notification(
    volunteer_id: int,
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
    app,
    *,
    coach_name: str = '',
    coach_phone: str = '',
    training_id: int | None = None,
    cancel_link: str = '',
    volunteer_email: str = '',
    volunteer_last_name: str = '',
    is_adult: bool = True,
    logo_url: str = '',
) -> None:
    """Schedule a signup confirmation with a grace period.

    If the same volunteer signs up for another training within
    ``SIGNUP_GRACE_PERIOD_SECONDS``, both WhatsApp and email
    confirmations are consolidated into single messages.
    """
    training_info = {
        "date": training_date,
        "location": training_location,
        "coach_name": coach_name,
        "coach_phone": coach_phone,
        "training_id": training_id,
        "cancel_link": cancel_link,
    }

    with _pending_lock:
        entry = _pending_signups.get(volunteer_id)
        if entry:
            # Cancel existing timer and append training
            entry["timer"].cancel()
            entry["trainings"].append(training_info)
            # Keep latest volunteer data
            if volunteer_email:
                entry["email"] = volunteer_email
            if volunteer_last_name:
                entry["last_name"] = volunteer_last_name
            entry["is_adult"] = is_adult
            if logo_url:
                entry["logo_url"] = logo_url
        else:
            entry = {
                "phone": volunteer_phone,
                "name": volunteer_name,
                "email": volunteer_email,
                "last_name": volunteer_last_name,
                "is_adult": is_adult,
                "logo_url": logo_url,
                "trainings": [training_info],
                "timer": None,
            }
            _pending_signups[volunteer_id] = entry

        # In test mode, flush immediately (no timer) so assertions work
        if getattr(app, 'testing', False):
            # Release lock before calling flush (it re-acquires it)
            pass  # will call flush outside lock block

    if getattr(app, 'testing', False):
        _flush_pending_signup(volunteer_id, app)
        return

    with _pending_lock:
        entry = _pending_signups.get(volunteer_id)
        if entry:
            # (Re)start timer
            timer = threading.Timer(
                SIGNUP_GRACE_PERIOD_SECONDS,
                _flush_pending_signup,
                args=[volunteer_id, app],
            )
            timer.daemon = True
            entry["timer"] = timer
            timer.start()


def _send_signup_email(
    volunteer_email: str,
    volunteer_first_name: str,
    volunteer_last_name: str,
    is_adult: bool,
    trainings: list[dict],
    logo_url: str,
) -> None:
    """Send consolidated signup confirmation email.

    Must be called within an app context.
    """
    from .models import EmailSettings, StoredFile
    from . import email_utils
    from .template_utils import render_template_string
    from pathlib import Path

    settings = EmailSettings.query.first()
    if not settings or not settings.registration_template:
        return

    # Build training info for template
    if len(trainings) == 1:
        t = trainings[0]
        training_str = f"{t['date']} w {t['location']}"
        cancel_link = t.get('cancel_link', '')
    else:
        parts = []
        for t in trainings:
            parts.append(f"{t['date']} w {t['location']}")
        training_str = "<br>".join(parts)
        cancel_link = trainings[0].get('cancel_link', '')

    data = {
        "first_name": volunteer_first_name,
        "last_name": volunteer_last_name,
        "training": training_str,
        "cancel_link": cancel_link,
        "date": trainings[0]["date"],
        "location": trainings[0]["location"],
        "logo": logo_url,
    }

    html_body = render_template_string(settings.registration_template, data)

    # Load attachments (once, regardless of how many trainings)
    attachments: list[tuple[str, str, bytes]] = []
    attachments_meta = (
        settings.registration_files_adult if is_adult
        else settings.registration_files_minor
    ) or []

    legacy_ids = [entry for entry in attachments_meta if isinstance(entry, int)]
    if legacy_ids:
        stored_files = StoredFile.query.filter(StoredFile.id.in_(legacy_ids)).all()
        stored_by_id = {f.id: f for f in stored_files}
        for file_id in legacy_ids:
            sf = stored_by_id.get(file_id)
            if sf:
                attachments.append((sf.filename, sf.content_type, sf.data))

    attachments_dir = Path(current_app.instance_path) / "attachments"
    for entry in attachments_meta:
        if not isinstance(entry, dict):
            continue
        stored_name = entry.get("stored_name")
        if not stored_name:
            continue
        file_path = attachments_dir / stored_name
        try:
            file_data = file_path.read_bytes()
        except OSError:
            current_app.logger.warning(
                "Attachment file %s referenced in settings is missing", file_path,
            )
            continue
        filename = entry.get("original_name") or entry.get("filename") or stored_name
        content_type = entry.get("content_type") or "application/octet-stream"
        attachments.append((filename, content_type, file_data))

    success, error = email_utils.send_email(
        "Potwierdzenie zgłoszenia",
        None,
        [volunteer_email],
        html_body=html_body,
        attachments=attachments,
    )
    if not success:
        current_app.logger.warning("Failed to send signup email to %s: %s", volunteer_email, error)


def _flush_pending_signup(volunteer_id: int, app) -> None:
    """Send the consolidated signup notification (WA + email) after the grace period."""
    with _pending_lock:
        entry = _pending_signups.pop(volunteer_id, None)
    if not entry:
        return

    with app.app_context():
        booking_count = get_volunteer_booking_count(volunteer_id)
        trainings = entry["trainings"]
        phone = entry.get("phone", "")
        name = entry.get("name", "")
        email = entry.get("email", "")
        last_name = entry.get("last_name", "")
        is_adult = entry.get("is_adult", True)
        logo_url = entry.get("logo_url", "")

        # --- Consolidated WhatsApp ---
        if phone:
            if len(trainings) == 1:
                t = trainings[0]
                notify_volunteer_signup_confirmation(
                    phone, name, t["date"], t["location"],
                    booking_count=booking_count,
                    coach_name=t.get("coach_name", ""),
                    coach_phone=t.get("coach_phone", ""),
                )
            else:
                notify_volunteer_signup_confirmation_multi(
                    phone, name, trainings,
                    booking_count=booking_count,
                )

        # --- Consolidated email ---
        if email:
            _send_signup_email(
                volunteer_email=email,
                volunteer_first_name=name,
                volunteer_last_name=last_name,
                is_adult=is_adult,
                trainings=trainings,
                logo_url=logo_url,
            )

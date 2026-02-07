"""WhatsApp integration using WAHA (WhatsApp HTTP API) selfhosted solution.

WAHA is a selfhosted WhatsApp API. Documentation: https://waha.devlike.pro/
Docker: devlikeapro/waha

Configuration environment variables:
- WHATSAPP_API_URL: WAHA API base URL (e.g. http://localhost:3000)
- WHATSAPP_SESSION: WAHA session name (default: default)
- WHATSAPP_API_KEY: WAHA API key (optional, if authentication enabled)
"""

import re
from flask import current_app
import requests
from typing import Optional


# Max length for user-provided text in WhatsApp messages
MAX_NAME_LENGTH = 100
MAX_LOCATION_LENGTH = 200


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


def notify_coach_new_signup(
    coach_phone: str,
    coach_name: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a coach about a new volunteer signup."""
    # Sanitize user-provided data
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "📋 Nowy wolontariusz zapisał się na trening!\n\n"
        "Cześć {trener}!\n\n"
        "👤 Wolontariusz: {wolontariusz}\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        "Pozdrawiamy,\n"
        "Fundacja Widzimy Inaczej"
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
    # Sanitize user-provided data
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)
    coach_name = sanitize_for_whatsapp(coach_name, MAX_NAME_LENGTH)

    formatted_coach_phone = format_phone_display(coach_phone)
    default = (
        "🎾 Przypomnienie o jutrzejszym wolontariacie!\n\n"
        "Cześć {imię}!\n\n"
        "Przypominamy, że jutro o {godzina} masz wolontariat:\n\n"
        "📍 Miejsce: {miejsce}\n"
        "👨‍🏫 Trener: {trener}\n"
        "📞 Telefon do trenera: {telefon}\n\n"
        "✅ Odpisz POTWIERDZAM jeśli będziesz\n"
        "❌ Odpisz REZYGNUJĘ jeśli nie możesz\n\n"
        "Fundacja Widzimy Inaczej"
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

    Note: This template is dynamic (per-training list) and does not use a
    DB template body directly. The header/footer wording mirrors the
    ``volunteer_reminder_multi`` DB template for consistency.
    """
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)

    lines = [
        f"🎾 Przypomnienie o jutrzejszych wolontariatach!\n",
        f"Cześć {volunteer_name}!\n",
        f"Jutro masz {len(trainings_info)} wolontariaty:\n",
    ]
    for i, t in enumerate(trainings_info, 1):
        loc = sanitize_for_whatsapp(t['location'], MAX_LOCATION_LENGTH)
        coach = sanitize_for_whatsapp(t['coach_name'], MAX_NAME_LENGTH)
        phone_fmt = format_phone_display(t['coach_phone'])
        lines.append(
            f"{i}. 🕐 {t['time']} — 📍 {loc}\n"
            f"   👨\u200d🏫 {coach}, 📞 {phone_fmt}"
        )

    lines.append("")
    if len(trainings_info) > 1:
        lines.append("✅ POTWIERDZAM — potwierdź wszystkie")
        lines.append("✅ POTWIERDZAM 1 — potwierdź tylko pierwszy")
        lines.append("❌ REZYGNUJĘ — zrezygnuj ze wszystkich")
    else:
        lines.append("✅ Odpisz POTWIERDZAM jeśli będziesz")
        lines.append("❌ Odpisz REZYGNUJĘ jeśli nie możesz")
    lines.append("\nFundacja Widzimy Inaczej")

    return send_whatsapp_message(volunteer_phone, "\n".join(lines))

def notify_volunteer_training_canceled(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a volunteer that their training has been canceled."""
    # Sanitize user-provided data
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "⚠️ Trening został odwołany\n\n"
        "Cześć {imię}!\n\n"
        "Niestety informujemy, że trening zaplanowany na:\n\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        "został odwołany.\n\n"
        "Przepraszamy za utrudnienia.\n"
        "Fundacja Widzimy Inaczej"
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
        "\u23f0 Zmiana godziny treningu!\n\n"
        "Cze\u015b\u0107 {imię}!\n\n"
        "Informujemy, \u017ce godzina Twojego treningu zosta\u0142a zmieniona:\n\n"
        "\ud83d\udcc5 Data: {data}\n"
        "\u274c Stara godzina: {stara_godzina}\n"
        "\u2705 Nowa godzina: {nowa_godzina}\n"
        "\ud83d\udccd Miejsce: {miejsce}\n\n"
        "\u2705 Odpisz POTWIERDZAM je\u015bli b\u0119dziesz o nowej godzinie\n"
        "\u274c Odpisz REZYGNUJ\u0118 je\u015bli nie mo\u017cesz\n\n"
        "Fundacja Widzimy Inaczej"
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


def notify_coach_volunteer_canceled(
    coach_phone: str,
    coach_name: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a coach that a volunteer has canceled their booking."""
    # Sanitize user-provided data
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "⚠️ Wolontariusz wypisał się z treningu\n\n"
        "Cześć {trener}!\n\n"
        "👤 Wolontariusz: {wolontariusz}\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        "Pozdrawiamy,\n"
        "Fundacja Widzimy Inaczej"
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


def notify_volunteer_signup_confirmation(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Send signup confirmation to volunteer with a note to check email."""
    # Sanitize user-provided data
    volunteer_name = sanitize_for_whatsapp(volunteer_name, MAX_NAME_LENGTH)
    training_location = sanitize_for_whatsapp(training_location, MAX_LOCATION_LENGTH)

    default = (
        "✅ Dziękujemy za zapisanie się!\n\n"
        "Cześć {imię}!\n\n"
        "Twój zapis na wolontariat został przyjęty:\n\n"
        "📅 Data: {data}\n"
        "📍 Miejsce: {miejsce}\n\n"
        "📧 Sprawdź swoją skrzynkę e-mail — wysłaliśmy Ci szczegółowe informacje oraz potrzebne dokumenty.\n\n"
        "Do zobaczenia! 🎾\n"
        "Fundacja Widzimy Inaczej"
    )
    body = _get_template_body("signup_confirmation", default)
    message = (
        body
        .replace("{imię}", volunteer_name)
        .replace("{data}", training_date)
        .replace("{miejsce}", training_location)
    )
    return send_whatsapp_message(volunteer_phone, message)

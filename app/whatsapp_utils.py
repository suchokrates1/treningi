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
    api_url: Optional[str] = None,
    session: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Send a WhatsApp message using WAHA API.
    
    Args:
        phone: Phone number (will be normalized)
        message: Message text to send
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
    message = (
        f"📋 Nowy wolontariusz zapisał się na trening!\n\n"
        f"👤 Wolontariusz: {volunteer_name}\n"
        f"📅 Data: {training_date}\n"
        f"📍 Miejsce: {training_location}\n\n"
        f"Pozdrawiamy,\nSystem zapisów Blind Tenis"
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
    formatted_coach_phone = format_phone_display(coach_phone)
    message = (
        f"🎾 Przypomnienie o jutrzejszym wolontariacie!\n\n"
        f"Cześć {volunteer_name}!\n\n"
        f"Przypominamy, że jutro o {training_time} masz wolontariat:\n\n"
        f"📍 Miejsce: {training_location}\n"
        f"👨‍🏫 Trener: {coach_name}\n"
        f"📞 Telefon do trenera: {formatted_coach_phone}\n\n"
        f"✅ Odpisz POTWIERDZAM jeśli będziesz\n"
        f"❌ Odpisz REZYGNUJĘ jeśli nie możesz\n\n"
        f"Fundacja Widzimy Inaczej"
    )
    return send_whatsapp_message(volunteer_phone, message)


def notify_volunteer_training_canceled(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Notify a volunteer that their training has been canceled."""
    message = (
        f"⚠️ Trening został odwołany\n\n"
        f"Cześć {volunteer_name}!\n\n"
        f"Niestety informujemy, że trening zaplanowany na:\n\n"
        f"📅 Data: {training_date}\n"
        f"📍 Miejsce: {training_location}\n\n"
        f"został odwołany.\n\n"
        f"Przepraszamy za utrudnienia.\n"
        f"Fundacja Widzimy Inaczej"
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
    message = (
        f"⚠️ Wolontariusz wypisał się z treningu\n\n"
        f"👤 Wolontariusz: {volunteer_name}\n"
        f"📅 Data: {training_date}\n"
        f"📍 Miejsce: {training_location}\n\n"
        f"System zapisów Blind Tenis"
    )
    return send_whatsapp_message(coach_phone, message)


def notify_volunteer_signup_confirmation(
    volunteer_phone: str,
    volunteer_name: str,
    training_date: str,
    training_location: str,
) -> tuple[bool, Optional[str]]:
    """Send signup confirmation to volunteer with a note to check email."""
    message = (
        f"✅ Dziękujemy za zapisanie się!\n\n"
        f"Cześć {volunteer_name}!\n\n"
        f"Twój zapis na wolontariat został przyjęty:\n\n"
        f"📅 Data: {training_date}\n"
        f"📍 Miejsce: {training_location}\n\n"
        f"📧 Sprawdź swoją skrzynkę e-mail - wysłaliśmy Ci szczegółowe informacje oraz potrzebne dokumenty.\n\n"
        f"Do zobaczenia!\n"
        f"Fundacja Widzimy Inaczej"
    )
    return send_whatsapp_message(volunteer_phone, message)

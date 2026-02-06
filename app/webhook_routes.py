"""WhatsApp webhook endpoint for receiving messages from WAHA."""

import re
import html
import json
import urllib.request
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta

from . import db
from .models import Volunteer, Booking, Training, Coach
from .whatsapp_utils import send_whatsapp_message, normalize_phone_number
from .ai_assistant import ask_gemini

webhook_bp = Blueprint('webhook', __name__)


def _find_volunteer_by_name(name: str) -> Volunteer | None:
    """Find a volunteer or coach by display name (for @lid contacts)."""
    if not name:
        return None
    parts = name.strip().split()
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        vol = Volunteer.query.filter(
            Volunteer.first_name.ilike(first),
            Volunteer.last_name.ilike(last),
        ).first()
        if vol:
            return vol
    return None


def _extract_phone_from_lid(lid_id: str) -> str | None:
    """Resolve @lid chat ID to phone number via WAHA chat name.

    WAHA stores the phone number (e.g. '+48 519 179 904') in the chat
    ``name`` field even when the chat ID uses the @lid format.
    """
    waha_url = current_app.config.get('WHATSAPP_API_URL') or 'http://waha:3000'
    waha_key = current_app.config.get('WHATSAPP_API_KEY') or ''
    session = current_app.config.get('WHATSAPP_SESSION') or 'default'
    try:
        req = urllib.request.Request(
            f'{waha_url}/api/{session}/chats',
            headers={'X-Api-Key': waha_key},
        )
        chats = json.loads(urllib.request.urlopen(req, timeout=5).read())
        for chat in chats:
            cid = chat.get('id', '')
            # id can be a dict (WEBJS) or a string
            if isinstance(cid, dict):
                serialized = cid.get('_serialized', '')
            else:
                serialized = str(cid)
            if serialized == lid_id:
                name = chat.get('name', '')
                # Name is often the phone in format "+48 519 179 904"
                digits = re.sub(r'\D', '', name)
                if len(digits) >= 9:
                    current_app.logger.info(
                        f'Resolved @lid {lid_id} to phone {digits} via chat name "{name}"'
                    )
                    return digits
    except Exception as exc:
        current_app.logger.warning(f'Failed to resolve @lid via WAHA chats: {exc}')
    return None


# Security: Max message length to process
MAX_MESSAGE_LENGTH = 500

# Security: Rate limiting (simple in-memory, per phone)
_rate_limit_cache: dict[str, list[datetime]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10


def is_rate_limited(phone: str) -> bool:
    """Check if phone number has exceeded rate limit."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    if phone not in _rate_limit_cache:
        _rate_limit_cache[phone] = []
    
    # Clean old entries
    _rate_limit_cache[phone] = [
        ts for ts in _rate_limit_cache[phone] if ts > window_start
    ]
    
    if len(_rate_limit_cache[phone]) >= RATE_LIMIT_MAX_REQUESTS:
        return True
    
    _rate_limit_cache[phone].append(now)
    return False


def sanitize_message(text: str) -> str:
    """Sanitize incoming message for safety."""
    if not text:
        return ""
    # Truncate to max length
    text = text[:MAX_MESSAGE_LENGTH]
    # Remove null bytes and control characters
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


# Patterns for confirmation/cancellation detection
CONFIRM_PATTERNS = [
    r'\bpotwierdzam\b',
    r'\bpotwierdz\b',
    r'\btak\b',
    r'\bbede\b',
    r'\bbędę\b',
    r'\bok\b',
    r'^\s*\+\s*$',
    r'^1$',
]

CANCEL_PATTERNS = [
    r'\brezygnuj[eę]\b',
    r'\brezygnacja\b',
    r'\bnie\s+(bede|będę)\b',
    r'\bodwo[łl]uj[eę]\b',
    r'\banuluj[eę]?\b',
    r'^2$',
]


def normalize_text(text: str) -> str:
    """Normalize text for pattern matching."""
    # Remove accents for easier matching
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    }
    text = text.lower().strip()
    for pl, en in replacements.items():
        text = text.replace(pl, en)
    return text


def detect_intent(message: str) -> str | None:
    """Detect user intent from message. Returns 'confirm', 'cancel', or None."""
    normalized = normalize_text(message)
    original_lower = message.lower().strip()
    
    for pattern in CONFIRM_PATTERNS:
        if re.search(pattern, normalized) or re.search(pattern, original_lower):
            return 'confirm'
    
    for pattern in CANCEL_PATTERNS:
        if re.search(pattern, normalized) or re.search(pattern, original_lower):
            return 'cancel'
    
    # Check for number selection (for multiple trainings)
    number_match = re.match(r'^(\d+)$', message.strip())
    if number_match:
        return f'select_{number_match.group(1)}'
    
    return None


def find_volunteer_by_phone(phone: str) -> Volunteer | None:
    """Find volunteer by phone number."""
    normalized = normalize_phone_number(phone)
    
    # Try different formats
    phone_variants = [
        normalized,
        normalized.lstrip('+'),
        normalized.replace('+48', ''),
    ]
    
    for variant in phone_variants:
        volunteer = Volunteer.query.filter(
            Volunteer.phone_number.ilike(f'%{variant[-9:]}%')
        ).first()
        if volunteer:
            return volunteer
    
    return None


def get_pending_bookings(volunteer: Volunteer) -> list[Booking]:
    """Get bookings for today and tomorrow that haven't been confirmed yet."""
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    tomorrow_end = datetime.combine(tomorrow, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    return Booking.query.join(Training).filter(
        Booking.volunteer_id == volunteer.id,
        Training.date >= now,
        Training.date <= tomorrow_end,
        Training.is_canceled.is_(False),
        Training.is_deleted.is_(False),
        Booking.is_confirmed.is_(None),
    ).order_by(Training.date).all()


def send_confirmation_response(phone: str, booking: Booking | list[Booking]) -> None:
    """Send confirmation response to volunteer.

    Accepts a single Booking or a list of Bookings (for multi-confirm).
    """
    bookings = booking if isinstance(booking, list) else [booking]
    today = datetime.now(timezone.utc).date()

    if len(bookings) == 1:
        training = bookings[0].training
        training_date = training.date.date() if hasattr(training.date, 'date') else training.date
        day_word = "dzisiaj" if training_date == today else "jutro"
        message = (
            f"✅ Dziękujemy za potwierdzenie!\n\n"
            f"Do zobaczenia {day_word} o {training.date.strftime('%H:%M')}\n"
            f"📍 {training.location.name}\n"
            f"👨‍🏫 Trener: {training.coach.first_name} {training.coach.last_name}\n"
            f"📞 Tel: {training.coach.phone_number}"
        )
    else:
        training_date = bookings[0].training.date.date()
        day_word = "dzisiaj" if training_date == today else "jutro"
        lines = [f"✅ Dziękujemy za potwierdzenie!\n\nDo zobaczenia {day_word}:\n"]
        for b in bookings:
            t = b.training
            lines.append(
                f"🕐 {t.date.strftime('%H:%M')} - 📍 {t.location.name} "
                f"(🏫 {t.coach.first_name} {t.coach.last_name}, 📞 {t.coach.phone_number})"
            )
        message = "\n".join(lines)

    send_whatsapp_message(phone, message)


def send_cancellation_response(phone: str, booking: Booking) -> None:
    """Send cancellation response to volunteer."""
    training = booking.training
    message = (
        f"❌ Twoja rezygnacja została przyjęta.\n\n"
        f"Trening: {training.date.strftime('%Y-%m-%d %H:%M')}\n"
        f"📍 {training.location.name}\n\n"
        f"Mamy nadzieję, że zobaczysz się z nami innym razem!\n"
        f"Fundacja Widzimy Inaczej"
    )
    send_whatsapp_message(phone, message)


def send_selection_prompt(phone: str, bookings: list[Booking]) -> None:
    """Send message asking user to select which training to confirm."""
    lines = ["📋 Masz kilka treningów jutro. Który potwierdzasz?\n"]
    
    for i, booking in enumerate(bookings, 1):
        training = booking.training
        lines.append(
            f"{i}. {training.date.strftime('%H:%M')} - {training.location.name}"
        )
    
    lines.append("\n✅ Odpisz numer (np. 1) aby potwierdzić")
    lines.append("❌ Odpisz 'rezygnuję z X' aby zrezygnować")
    
    send_whatsapp_message(phone, "\n".join(lines))


def send_unknown_response(phone: str, message: str = "", volunteer: Volunteer | None = None) -> None:
    """Send response when we don't understand the message.

    First tries Gemini AI for a conversational reply.  Falls back to a
    static help message when the AI is unavailable.
    """
    # Try AI response first
    if message:
        ai_reply = ask_gemini(message, volunteer=volunteer)
        if ai_reply:
            send_whatsapp_message(phone, ai_reply)
            return

    # Fallback: static help message
    fallback = (
        "Dostępne komendy:\n"
        "✅ POTWIERDZAM - potwierdź udział w treningu\n"
        "❌ REZYGNUJĘ - zrezygnuj z treningu\n\n"
        "Jeśli potrzebujesz pomocy, napisz do nas: biuro@widzimyinaczej.org.pl"
    )
    send_whatsapp_message(phone, fallback)


def send_no_booking_response(phone: str) -> None:
    """Send response when no pending booking found."""
    message = (
        "ℹ️ Nie znaleziono żadnego treningu do potwierdzenia na jutro.\n\n"
        "Jeśli uważasz, że to błąd, skontaktuj się z nami."
    )
    send_whatsapp_message(phone, message)


def send_not_found_response(phone: str) -> None:
    """Send response when phone number not found in database."""
    message = (
        "❓ Nie znaleziono Twojego numeru w naszej bazie.\n\n"
        "Jeśli jesteś zapisany/a na wolontariat, upewnij się, "
        "że podałeś/aś ten numer telefonu podczas rejestracji."
    )
    send_whatsapp_message(phone, message)


# Store for multi-step conversations (selection)
_pending_selections: dict[str, list[Booking]] = {}


@webhook_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from WAHA."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'no data'}), 200
        
        # WAHA sends different event types
        event_type = data.get('event')
        
        # We only care about incoming messages
        if event_type != 'message':
            return jsonify({'status': 'ignored', 'reason': 'not a message event'}), 200
        
        payload = data.get('payload', {})
        
        # Skip messages we sent ourselves
        if payload.get('fromMe'):
            return jsonify({'status': 'ignored', 'reason': 'own message'}), 200
        
        # Get message details
        message_body = sanitize_message(payload.get('body', ''))
        from_field = payload.get('from', '')
        
        # Log raw payload for debugging
        current_app.logger.info(f"Webhook payload from={from_field}, body={message_body[:80]}")
        
        # Extract phone number from WhatsApp ID
        phone_number = None
        
        # Format 1: 48123456789@c.us (standard)
        phone_match = re.match(r'^(\d{9,15})@c\.us$', from_field)
        if phone_match:
            phone_number = phone_match.group(1)
        
        # Format 2: XXXXX@lid (linked device ID - phone not in ID)
        # Try to get phone from _data.from or participant fields
        if not phone_number and '@lid' in from_field:
            _data = payload.get('_data', {})
            # Try author field
            author = _data.get('author', '')
            if author:
                author_match = re.match(r'^(\d{9,15})@', author)
                if author_match:
                    phone_number = author_match.group(1)
            # Try participant
            if not phone_number:
                participant = _data.get('participant', '') or payload.get('participant', '')
                if participant:
                    part_match = re.match(r'^(\d{9,15})@', participant)
                    if part_match:
                        phone_number = part_match.group(1)
            # Try chatId field
            if not phone_number:
                chat_id = payload.get('chatId', '') or payload.get('from', '')
                # For @lid chats, we need to look up which phone this lid maps to
                # Use WAHA contacts API or match by notify name
                notify_name = _data.get('notifyName', '') or payload.get('notifyName', '')
                if notify_name:
                    # Try to find volunteer by name
                    vol = _find_volunteer_by_name(notify_name)
                    if vol and vol.phone_number:
                        from .whatsapp_utils import normalize_phone_number
                        phone_number = normalize_phone_number(vol.phone_number).lstrip('+')
                        current_app.logger.info(
                            f"Matched @lid chat to {vol.first_name} {vol.last_name} via notifyName={notify_name}"
                        )

            # Last resort: look up @lid in WAHA chat list (name often has phone)
            if not phone_number:
                phone_number = _extract_phone_from_lid(from_field)
        
        if not phone_number:
            current_app.logger.warning(f"Could not extract phone from: {from_field}")
            return jsonify({'status': 'error', 'reason': 'invalid from field'}), 200
        
        # Rate limiting
        if is_rate_limited(phone_number):
            current_app.logger.warning(f"Rate limit exceeded for {phone_number}")
            return jsonify({'status': 'rate_limited'}), 429
        
        current_app.logger.info(
            f"Received WhatsApp message from {phone_number}: {message_body[:50]}..."
        )
        
        # Find volunteer by phone
        volunteer = find_volunteer_by_phone(phone_number)
        
        if not volunteer:
            send_not_found_response(phone_number)
            return jsonify({'status': 'ok', 'action': 'not_found'}), 200
        
        # Check if we're waiting for a selection from this user
        if phone_number in _pending_selections:
            bookings = _pending_selections[phone_number]
            
            # Try to parse number
            try:
                selection = int(message_body.strip())
                if 1 <= selection <= len(bookings):
                    booking = bookings[selection - 1]
                    booking.is_confirmed = True
                    db.session.commit()
                    send_confirmation_response(phone_number, booking)
                    del _pending_selections[phone_number]
                    return jsonify({'status': 'ok', 'action': 'confirmed_selection'}), 200
            except ValueError:
                pass
            
            # Check for cancel with number
            cancel_match = re.search(r'rezygnuj\w*\s+z?\s*(\d+)', message_body.lower())
            if cancel_match:
                try:
                    selection = int(cancel_match.group(1))
                    if 1 <= selection <= len(bookings):
                        booking = bookings[selection - 1]
                        booking.is_confirmed = False
                        db.session.commit()
                        send_cancellation_response(phone_number, booking)
                        del _pending_selections[phone_number]
                        return jsonify({'status': 'ok', 'action': 'cancelled_selection'}), 200
                except ValueError:
                    pass
            
            # Didn't understand, repeat the selection prompt
            send_selection_prompt(phone_number, bookings)
            return jsonify({'status': 'ok', 'action': 'selection_repeated'}), 200
        
        # Detect intent
        intent = detect_intent(message_body)
        
        if not intent:
            send_unknown_response(phone_number, message_body, volunteer)
            return jsonify({'status': 'ok', 'action': 'unknown'}), 200
        
        # Get pending bookings for tomorrow
        pending_bookings = get_pending_bookings(volunteer)
        
        if not pending_bookings:
            send_no_booking_response(phone_number)
            return jsonify({'status': 'ok', 'action': 'no_booking'}), 200
        
        # Handle single booking
        if len(pending_bookings) == 1:
            booking = pending_bookings[0]
            
            if intent == 'confirm':
                booking.is_confirmed = True
                db.session.commit()
                send_confirmation_response(phone_number, booking)
                return jsonify({'status': 'ok', 'action': 'confirmed'}), 200
            
            elif intent == 'cancel':
                booking.is_confirmed = False
                db.session.commit()
                send_cancellation_response(phone_number, booking)
                return jsonify({'status': 'ok', 'action': 'cancelled'}), 200
        
        # Multiple bookings
        else:
            if intent == 'confirm':
                # Confirm ALL pending bookings at once
                for booking in pending_bookings:
                    booking.is_confirmed = True
                db.session.commit()
                send_confirmation_response(phone_number, pending_bookings)
                return jsonify({'status': 'ok', 'action': 'confirmed_all'}), 200

            elif intent == 'cancel':
                # For cancellation, ask which one
                _pending_selections[phone_number] = pending_bookings
                send_selection_prompt(phone_number, pending_bookings)
                return jsonify({'status': 'ok', 'action': 'selection_requested'}), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error processing WhatsApp webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/whatsapp', methods=['GET'])
def whatsapp_webhook_verify():
    """Verify webhook endpoint (for testing)."""
    return jsonify({'status': 'ok', 'message': 'WhatsApp webhook is active'}), 200

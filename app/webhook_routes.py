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
]

CANCEL_PATTERNS = [
    r'\brezygnuj[eę]\b',
    r'\brezygnacja\b',
    r'\bnie\s+(bede|będę)\b',
    r'\bodwo[łl]uj[eę]\b',
    r'\banuluj[eę]?\b',

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
    """Detect user intent from message.

    Returns:
        'confirm'          – confirm all
        'confirm_N'        – confirm training number N (1-based)
        'cancel'           – cancel all
        'cancel_N'         – cancel training number N
        None               – unknown intent
    """
    normalized = normalize_text(message)
    original_lower = message.lower().strip()

    # --- Specific training number: "potwierdzam 1", "potwierdzam 2" ---
    num_confirm = re.search(r'potwierdzam\s+(\d+)', normalized) or re.search(r'potwierdzam\s+(\d+)', original_lower)
    if num_confirm:
        return f'confirm_{num_confirm.group(1)}'

    num_cancel = (
        re.search(r'rezygnuje?\s+z?\s*(\d+)', normalized)
        or re.search(r'rezygnuj[eę]\s+z?\s*(\d+)', original_lower)
    )
    if num_cancel:
        return f'cancel_{num_cancel.group(1)}'

    # --- "potwierdzam oba / wszystkie" → confirm all ---
    if re.search(r'potwierdzam\s+(oba|obydwa|wszystk)', normalized) or re.search(r'potwierdzam\s+(oba|obydwa|wszystk)', original_lower):
        return 'confirm'

    # --- Generic confirm ---
    for pattern in CONFIRM_PATTERNS:
        if re.search(pattern, normalized) or re.search(pattern, original_lower):
            return 'confirm'

    # --- Generic cancel ---
    for pattern in CANCEL_PATTERNS:
        if re.search(pattern, normalized) or re.search(pattern, original_lower):
            return 'cancel'

    # --- Bare number → confirm that training (e.g. user replies "1" or "2") ---
    bare_num = re.match(r'^(\d+)$', normalized)
    if bare_num:
        return f'confirm_{bare_num.group(1)}'

    return None


def find_volunteer_by_phone(phone: str) -> Volunteer | None:
    """Find volunteer by phone number.
    
    Handles phones stored with spaces/dashes (e.g. '607 575 408')
    by stripping non-digit characters before comparison.
    """
    normalized = normalize_phone_number(phone)
    
    # Extract last 9 digits (Polish phone without country code)
    digits_only = re.sub(r'\D', '', normalized)
    last9 = digits_only[-9:] if len(digits_only) >= 9 else digits_only
    
    if not last9:
        return None
    
    # Compare against phone_number with all non-digit chars stripped
    # This handles phones stored as '607 575 408', '607-575-408', etc.
    volunteer = Volunteer.query.filter(
        db.func.replace(
            db.func.replace(
                db.func.replace(Volunteer.phone_number, ' ', ''),
                '-', ''),
            '+', ''
        ).like(f'%{last9}%')
    ).first()
    
    return volunteer


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


def send_confirmation_response(chat_id: str, booking: Booking | list[Booking]) -> None:
    """Send confirmation response to volunteer.

    Accepts a single Booking or a list of Bookings (for multi-confirm).
    ``chat_id`` is the raw WhatsApp chatId (``@c.us`` or ``@lid``).
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

    send_whatsapp_message('', message, chat_id=chat_id)


def send_cancellation_response(chat_id: str, booking: Booking) -> None:
    """Send cancellation response to volunteer."""
    training = booking.training
    message = (
        f"❌ Twoja rezygnacja została przyjęta.\n\n"
        f"Trening: {training.date.strftime('%Y-%m-%d %H:%M')}\n"
        f"📍 {training.location.name}\n\n"
        f"Mamy nadzieję, że zobaczysz się z nami innym razem!\n"
        f"Fundacja Widzimy Inaczej"
    )
    send_whatsapp_message('', message, chat_id=chat_id)


def send_selection_prompt(chat_id: str, bookings: list[Booking]) -> None:
    """Send message asking user to select which training to confirm."""
    lines = ["📋 Masz kilka treningów jutro. Który potwierdzasz?\n"]
    
    for i, booking in enumerate(bookings, 1):
        training = booking.training
        lines.append(
            f"{i}. {training.date.strftime('%H:%M')} - {training.location.name}"
        )
    
    lines.append("\n✅ Odpisz numer (np. 1) aby potwierdzić")
    lines.append("❌ Odpisz 'rezygnuję z X' aby zrezygnować")
    
    send_whatsapp_message('', "\n".join(lines), chat_id=chat_id)


def send_unknown_response(chat_id: str, message: str = "", volunteer: Volunteer | None = None) -> None:
    """Send response when we don't understand the message.

    First tries Gemini AI for a conversational reply.  Falls back to a
    static help message when the AI is unavailable.
    ``chat_id`` is the raw WhatsApp chatId (``@c.us`` or ``@lid``).
    """
    # Try AI response first
    if message:
        print(f"[WEBHOOK] Calling ask_gemini with message={message[:50]}", flush=True)
        ai_reply = ask_gemini(message, volunteer=volunteer)
        print(f"[WEBHOOK] AI reply: {str(ai_reply)[:100] if ai_reply else 'None'}", flush=True)
        if ai_reply:
            send_whatsapp_message('', ai_reply, chat_id=chat_id)
            return

    # Fallback: static help message
    fallback = (
        "Dostępne komendy:\n"
        "✅ POTWIERDZAM - potwierdź udział w treningu\n"
        "❌ REZYGNUJĘ - zrezygnuj z treningu\n\n"
        "Jeśli potrzebujesz pomocy, napisz do nas: biuro@widzimyinaczej.org.pl"
    )
    send_whatsapp_message('', fallback, chat_id=chat_id)


def send_no_booking_response(chat_id: str) -> None:
    """Send response when no pending booking found."""
    message = (
        "ℹ️ Nie znaleziono żadnego treningu do potwierdzenia na jutro.\n\n"
        "Jeśli uważasz, że to błąd, skontaktuj się z nami."
    )
    send_whatsapp_message('', message, chat_id=chat_id)


def send_not_found_response(chat_id: str) -> None:
    """Send response when volunteer not found in database."""
    message = (
        "❓ Nie znaleziono Cię w naszej bazie.\n\n"
        "Jeśli jesteś zapisany/a na wolontariat, skontaktuj się z nami: "
        "biuro@widzimyinaczej.org.pl"
    )
    send_whatsapp_message('', message, chat_id=chat_id)


# Store for multi-step conversations (selection)
_pending_selections: dict[str, list[Booking]] = {}

# Deduplication: track recently processed message IDs
_processed_msg_ids: dict[str, float] = {}
DEDUP_WINDOW = 30  # seconds


@webhook_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from WAHA."""
    try:
        import sys, json as _json
        print(f"[WEBHOOK] Request received", flush=True)
        data = request.get_json(force=True, silent=True)
        
        if not data:
            print("[WEBHOOK] No JSON data!", flush=True)
            return jsonify({'status': 'no data'}), 200
        
        event_type = data.get('event')
        print(f"[WEBHOOK] event={event_type}", flush=True)
        
        if event_type != 'message':
            print(f"[WEBHOOK] Ignoring non-message event: {event_type}", flush=True)
            return jsonify({'status': 'ignored', 'reason': 'not a message event'}), 200
        
        payload = data.get('payload', {})
        from_me = payload.get('fromMe')
        from_field = payload.get('from', '')
        message_body = sanitize_message(payload.get('body', ''))
        msg_id = payload.get('id', '')
        
        # --- Deduplication: WAHA often sends the same message twice ---
        import time
        now_ts = time.time()
        # Clean old entries
        _processed_msg_ids.update({k: v for k, v in _processed_msg_ids.items() if now_ts - v < DEDUP_WINDOW})
        if msg_id and msg_id in _processed_msg_ids:
            print(f"[WEBHOOK] Duplicate msg_id={msg_id}, skipping", flush=True)
            return jsonify({'status': 'ignored', 'reason': 'duplicate'}), 200
        if msg_id:
            _processed_msg_ids[msg_id] = now_ts
        
        # Dump full payload keys for debugging
        print(f"[WEBHOOK] fromMe={from_me}, from={from_field}, body={message_body[:80]}, id={msg_id}", flush=True)
        print(f"[WEBHOOK] payload keys: {list(payload.keys())}", flush=True)
        _data = payload.get('_data', {})
        if _data:
            print(f"[WEBHOOK] _data keys: {list(_data.keys())}", flush=True)
            print(f"[WEBHOOK] _data.notifyName={_data.get('notifyName')}, author={_data.get('author')}, participant={_data.get('participant')}", flush=True)
        
        # Skip messages we sent ourselves
        if from_me:
            print(f"[WEBHOOK] Skipping own message", flush=True)
            return jsonify({'status': 'ignored', 'reason': 'own message'}), 200
        
        # Skip empty messages (e.g. user just opened the chat)
        if not message_body:
            print(f"[WEBHOOK] Skipping empty message", flush=True)
            return jsonify({'status': 'ignored', 'reason': 'empty message'}), 200
        
        # chat_id is the raw 'from' field – we'll use it to reply
        chat_id = from_field
        volunteer = None
        
        # --- Identify the volunteer ---
        if '@c.us' in from_field:
            # Standard format: 48123456789@c.us → extract phone, find volunteer
            phone_match = re.match(r'^(\d{9,15})@c\.us$', from_field)
            if phone_match:
                phone_number = phone_match.group(1)
                print(f"[WEBHOOK] Phone from @c.us: {phone_number}", flush=True)
                volunteer = find_volunteer_by_phone(phone_number)
        elif '@lid' in from_field:
            # Linked device format – find volunteer by display name
            print(f"[WEBHOOK] @lid detected, resolving volunteer...", flush=True)
            notify_name = _data.get('notifyName', '') or payload.get('notifyName', '')
            print(f"[WEBHOOK] notifyName={notify_name}", flush=True)
            if notify_name:
                volunteer = _find_volunteer_by_name(notify_name)
                print(f"[WEBHOOK] Volunteer by name: {volunteer}", flush=True)
            if not volunteer:
                # Try resolving @lid → phone → volunteer
                phone_number = _extract_phone_from_lid(from_field)
                if phone_number:
                    print(f"[WEBHOOK] Phone from lid lookup: {phone_number}", flush=True)
                    volunteer = find_volunteer_by_phone(phone_number)
        else:
            print(f"[WEBHOOK] Unknown from format: {from_field}", flush=True)
            return jsonify({'status': 'error', 'reason': 'unknown from format'}), 200
        
        print(f"[WEBHOOK] Volunteer resolved: {volunteer}", flush=True)
        
        if not volunteer:
            print(f"[WEBHOOK] Volunteer not found, sending not_found response to {chat_id}", flush=True)
            send_not_found_response(chat_id)
            return jsonify({'status': 'ok', 'action': 'not_found'}), 200
        
        # Rate limiting (use chat_id as key)
        if is_rate_limited(chat_id):
            print(f"[WEBHOOK] Rate limited: {chat_id}", flush=True)
            return jsonify({'status': 'rate_limited'}), 429
        
        print(f"[WEBHOOK] Processing: vol={volunteer.first_name} {volunteer.last_name}, msg={message_body[:50]}", flush=True)
        
        # Check if we're waiting for a selection from this user
        if chat_id in _pending_selections:
            bookings = _pending_selections[chat_id]
            
            # Try to parse number
            try:
                selection = int(message_body.strip())
                if 1 <= selection <= len(bookings):
                    booking = bookings[selection - 1]
                    booking.is_confirmed = True
                    db.session.commit()
                    send_confirmation_response(chat_id, booking)
                    del _pending_selections[chat_id]
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
                        send_cancellation_response(chat_id, booking)
                        del _pending_selections[chat_id]
                        return jsonify({'status': 'ok', 'action': 'cancelled_selection'}), 200
                except ValueError:
                    pass
            
            # Didn't understand, repeat the selection prompt
            send_selection_prompt(chat_id, bookings)
            return jsonify({'status': 'ok', 'action': 'selection_repeated'}), 200
        
        # Detect intent
        intent = detect_intent(message_body)
        print(f"[WEBHOOK] Intent: {intent}", flush=True)
        
        if not intent:
            print(f"[WEBHOOK] No intent detected, calling AI...", flush=True)
            send_unknown_response(chat_id, message_body, volunteer)
            print(f"[WEBHOOK] AI response sent", flush=True)
            return jsonify({'status': 'ok', 'action': 'unknown'}), 200
        
        # Get pending bookings for tomorrow
        pending_bookings = get_pending_bookings(volunteer)
        
        if not pending_bookings:
            send_no_booking_response(chat_id)
            return jsonify({'status': 'ok', 'action': 'no_booking'}), 200
        
        # --- Helper: confirm/cancel Nth booking -----------------------
        def _handle_nth(n: int, confirm: bool):
            """Confirm or cancel booking number *n* (1-based)."""
            if 1 <= n <= len(pending_bookings):
                bk = pending_bookings[n - 1]
                bk.is_confirmed = confirm
                db.session.commit()
                if confirm:
                    send_confirmation_response(chat_id, bk)
                else:
                    send_cancellation_response(chat_id, bk)
                return True
            return False

        # --- Handle confirm_N / cancel_N intents ----------------------
        num_match = re.match(r'(confirm|cancel)_(\d+)', intent or '')
        if num_match:
            action, idx = num_match.group(1), int(num_match.group(2))
            if _handle_nth(idx, confirm=(action == 'confirm')):
                return jsonify({'status': 'ok', 'action': f'{action}_{idx}'}), 200
            # Invalid number — fall through to selection prompt
            _pending_selections[chat_id] = pending_bookings
            send_selection_prompt(chat_id, pending_bookings)
            return jsonify({'status': 'ok', 'action': 'bad_number'}), 200

        # Handle single booking
        if len(pending_bookings) == 1:
            booking = pending_bookings[0]
            
            if intent == 'confirm':
                booking.is_confirmed = True
                db.session.commit()
                send_confirmation_response(chat_id, booking)
                return jsonify({'status': 'ok', 'action': 'confirmed'}), 200
            
            elif intent == 'cancel':
                booking.is_confirmed = False
                db.session.commit()
                send_cancellation_response(chat_id, booking)
                return jsonify({'status': 'ok', 'action': 'cancelled'}), 200
        
        # Multiple bookings
        else:
            if intent == 'confirm':
                # Confirm ALL pending bookings at once
                for booking in pending_bookings:
                    booking.is_confirmed = True
                db.session.commit()
                send_confirmation_response(chat_id, pending_bookings)
                return jsonify({'status': 'ok', 'action': 'confirmed_all'}), 200

            elif intent == 'cancel':
                # For cancellation, ask which one
                _pending_selections[chat_id] = pending_bookings
                send_selection_prompt(chat_id, pending_bookings)
                return jsonify({'status': 'ok', 'action': 'selection_requested'}), 200
        
    except Exception as e:
        import traceback
        print(f"[WEBHOOK] EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        current_app.logger.exception(f"Error processing WhatsApp webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/whatsapp', methods=['GET'])
def whatsapp_webhook_verify():
    """Verify webhook endpoint (for testing)."""
    return jsonify({'status': 'ok', 'message': 'WhatsApp webhook is active'}), 200

"""CLI commands for scheduled tasks."""

import click
import secrets
from flask import current_app
from flask.cli import with_appcontext
from datetime import datetime, timezone, timedelta

from . import db
from .models import Training, Booking, Volunteer, EmailSettings
from .whatsapp_utils import notify_volunteer_reminder, format_phone_display
from .email_utils import send_email
from .template_utils import render_template_string


# Minimum hours since signup before sending reminder
# (to avoid sending reminder right after signup confirmation)
MIN_HOURS_SINCE_SIGNUP = 4


@click.command('send-reminders')
@with_appcontext
def send_reminders_command():
    """Send WhatsApp reminders for tomorrow's trainings (run daily in evening)."""
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time()).replace(tzinfo=timezone.utc)
    tomorrow_end = datetime.combine(tomorrow, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    # Cutoff time: don't send reminders to people who signed up less than MIN_HOURS ago
    signup_cutoff = datetime.now(timezone.utc) - timedelta(hours=MIN_HOURS_SINCE_SIGNUP)

    trainings = Training.query.filter(
        Training.date >= tomorrow_start,
        Training.date <= tomorrow_end,
        Training.is_canceled.is_(False),
        Training.is_deleted.is_(False),
    ).all()

    if not trainings:
        click.echo("No trainings scheduled for tomorrow.")
        return

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for training in trainings:
        for booking in training.bookings:
            volunteer = booking.volunteer
            if not volunteer.phone_number:
                current_app.logger.info(
                    "Volunteer %s %s has no phone number, skipping WhatsApp reminder",
                    volunteer.first_name,
                    volunteer.last_name,
                )
                skipped_count += 1
                continue

            # Skip if already confirmed or declined
            if booking.is_confirmed is not None:
                current_app.logger.info(
                    "Booking for %s %s already has confirmation status, skipping",
                    volunteer.first_name,
                    volunteer.last_name,
                )
                skipped_count += 1
                continue
            
            # Skip if signed up recently (already got signup confirmation)
            if booking.timestamp and booking.timestamp > signup_cutoff:
                current_app.logger.info(
                    "Booking for %s %s is too recent (signed up %s), skipping reminder",
                    volunteer.first_name,
                    volunteer.last_name,
                    booking.timestamp.strftime('%Y-%m-%d %H:%M'),
                )
                skipped_count += 1
                continue

            volunteer_full_name = f"{volunteer.first_name} {volunteer.last_name}"
            coach_full_name = f"{training.coach.first_name} {training.coach.last_name}"

            success, error = notify_volunteer_reminder(
                volunteer_phone=volunteer.phone_number,
                volunteer_name=volunteer.first_name,
                training_date=training.date.strftime('%Y-%m-%d'),
                training_time=training.date.strftime('%H:%M'),
                training_location=training.location.name,
                coach_name=coach_full_name,
                coach_phone=training.coach.phone_number,
            )

            if success:
                sent_count += 1
                click.echo(f"✓ Reminder sent to {volunteer_full_name}")
            else:
                failed_count += 1
                click.echo(f"✗ Failed to send reminder to {volunteer_full_name}: {error}")

    click.echo(f"\nSummary: {sent_count} sent, {failed_count} failed, {skipped_count} skipped")


@click.command('send-phone-requests')
@click.option('--base-url', default='https://treningi.widzimyinaczej.org.pl', 
              help='Base URL for the application')
@with_appcontext
def send_phone_requests_command(base_url):
    """Send email to volunteers without phone numbers asking them to add their phone.
    
    Each volunteer receives this email only once (tracked by phone_request_sent flag).
    """
    # Znajdź wolontariuszy bez telefonu, którzy nie dostali jeszcze maila
    volunteers = Volunteer.query.filter(
        (Volunteer.phone_number.is_(None)) | (Volunteer.phone_number == ''),
        (Volunteer.phone_request_sent.is_(None)) | (Volunteer.phone_request_sent.is_(False)),
    ).all()

    if not volunteers:
        click.echo("No volunteers without phone numbers need to be contacted.")
        return

    click.echo(f"Found {len(volunteers)} volunteers without phone numbers to contact.")

    # Pobierz szablon email
    setting = EmailSettings.query.first()
    if not setting or not setting.phone_request_template:
        click.echo("Error: Phone request email template not configured in admin settings.")
        click.echo("Please go to Admin > Settings and configure the phone request template.")
        return

    template = setting.phone_request_template
    sent_count = 0
    failed_count = 0
    
    # Logo URL
    logo_url = f"{base_url}/static/logo.png"

    for volunteer in volunteers:
        # Generuj unikalny token
        token = secrets.token_urlsafe(32)
        volunteer.phone_update_token = token
        
        # Przygotuj dane do szablonu
        update_link = f"{base_url}/update-phone/{token}"
        data = {
            'first_name': volunteer.first_name,
            'last_name': volunteer.last_name,
            'email': volunteer.email,
            'update_link': update_link,
            'logo': logo_url,
        }
        
        try:
            html_body = render_template_string(template, data)
            success, error = send_email(
                "Dodaj numer telefonu - powiadomienia WhatsApp",
                None,
                [volunteer.email],
                html_body=html_body,
            )
            
            if success:
                # Oznacz że email został wysłany
                volunteer.phone_request_sent = True
                db.session.commit()
                sent_count += 1
                click.echo(f"✓ Email sent to {volunteer.first_name} {volunteer.last_name} ({volunteer.email})")
            else:
                # W razie błędu, nie oznaczaj - spróbuj ponownie następnym razem
                db.session.rollback()
                failed_count += 1
                click.echo(f"✗ Failed to send to {volunteer.email}: {error}")
        except Exception as e:
            db.session.rollback()
            failed_count += 1
            click.echo(f"✗ Error sending to {volunteer.email}: {str(e)}")

    click.echo(f"\nSummary: {sent_count} sent, {failed_count} failed")


@click.command("send-coach-summary")
@with_appcontext
def send_coach_summary_command():
    """Send WhatsApp summary to coaches about todays trainings (run daily in morning)."""
    from .whatsapp_utils import send_whatsapp_message, format_phone_display
    from .models import Coach

    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Get all trainings for today grouped by coach
    trainings = Training.query.filter(
        Training.date >= today_start,
        Training.date <= today_end,
        Training.is_canceled.is_(False),
        Training.is_deleted.is_(False),
    ).order_by(Training.date).all()

    if not trainings:
        click.echo("No trainings scheduled for today.")
        return

    # Group trainings by coach
    coach_trainings = {}
    for training in trainings:
        coach_id = training.coach_id
        if coach_id not in coach_trainings:
            coach_trainings[coach_id] = []
        coach_trainings[coach_id].append(training)

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for coach_id, coach_trainings_list in coach_trainings.items():
        coach = Coach.query.get(coach_id)
        if not coach or not coach.phone_number:
            current_app.logger.info(
                "Coach %s has no phone number, skipping summary",
                coach.first_name if coach else "Unknown",
            )
            skipped_count += 1
            continue

        # Build summary message
        message_lines = [
            f"Dzien dobry {coach.first_name}!",
            "",
            "Podsumowanie dzisiejszych treningow:",
            "",
        ]

        for training in coach_trainings_list:
            time_str = training.date.strftime("%H:%M")
            location = training.location.name

            # Get confirmed and pending volunteers
            confirmed_bookings = [b for b in training.bookings if b.is_confirmed is True]
            pending_bookings = [b for b in training.bookings if b.is_confirmed is None]

            message_lines.append(f"--- {time_str} - {location} ---")

            if confirmed_bookings:
                for booking in confirmed_bookings:
                    vol = booking.volunteer
                    phone_str = format_phone_display(vol.phone_number) if vol.phone_number else "brak tel."
                    message_lines.append(f"[OK] {vol.first_name} {vol.last_name} ({phone_str})")

            if pending_bookings:
                for booking in pending_bookings:
                    vol = booking.volunteer
                    phone_str = format_phone_display(vol.phone_number) if vol.phone_number else "brak tel."
                    message_lines.append(f"[?] {vol.first_name} {vol.last_name} ({phone_str})")

            if not confirmed_bookings and not pending_bookings:
                message_lines.append("  Brak zapisanych wolontariuszy")

            message_lines.append("")

        # Legenda
        message_lines.append("Legenda: [OK] potwierdzony, [?] oczekuje")
        message_lines.append("")
        message_lines.append("System zapisow Blind Tenis")
        message = "\n".join(message_lines)

        success, error = send_whatsapp_message(coach.phone_number, message)
        coach_name = f"{coach.first_name} {coach.last_name}"

        if success:
            sent_count += 1
            click.echo(f"OK Podsumowanie wyslane do {coach_name}")
        else:
            failed_count += 1
            click.echo(f"BLAD Nie udalo sie wyslac do {coach_name}: {error}")

    click.echo(f"\nPodsumowanie: {sent_count} wyslanych, {failed_count} bledow, {skipped_count} pominietych")


def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(send_reminders_command)
    app.cli.add_command(send_phone_requests_command)
    app.cli.add_command(send_coach_summary_command)

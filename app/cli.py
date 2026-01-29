"""CLI commands for scheduled tasks."""

import click
from flask import current_app
from flask.cli import with_appcontext
from datetime import datetime, timezone, timedelta

from . import db
from .models import Training, Booking
from .whatsapp_utils import notify_volunteer_reminder, format_phone_display


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


def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(send_reminders_command)

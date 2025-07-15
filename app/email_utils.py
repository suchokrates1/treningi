from flask import current_app
from .models import EmailSettings
import smtplib
from email.message import EmailMessage


def send_email(subject: str, body: str, recipients: list[str]) -> None:
    """Send a plain text email using stored SMTP settings."""
    settings = EmailSettings.query.get(1)
    host = (
        settings.server
        if settings and settings.server
        else current_app.config.get("SMTP_HOST")
    )
    username = (
        settings.login
        if settings and settings.login
        else current_app.config.get("SMTP_USERNAME")
    )
    password = (
        settings.password
        if settings and settings.password
        else current_app.config.get("SMTP_PASSWORD")
    )
    sender = (
        settings.sender
        if settings and settings.sender
        else current_app.config.get("SMTP_SENDER")
    )
    port = (
        settings.port
        if settings and settings.port
        else current_app.config.get("SMTP_PORT", 587)
    )
    use_tls = current_app.config.get("SMTP_USE_TLS", True)

    if not host:
        current_app.logger.warning("SMTP_HOST not configured; skipping email")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP(host, port) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)

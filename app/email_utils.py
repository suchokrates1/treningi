from flask import current_app
from .models import EmailSettings
import smtplib
from email.message import EmailMessage
import re


def send_email(
    subject: str,
    body: str | None,
    recipients: list[str],
    *,
    html_body: str | None = None,
) -> None:
    """Send an email using stored SMTP settings."""
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

    if not body and html_body:
        body = re.sub(r"<[^>]+>", "", html_body)

    msg.set_content(body or "")

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)

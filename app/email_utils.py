from flask import current_app
import smtplib
from email.message import EmailMessage


def send_email(subject: str, body: str, recipients: list[str]) -> None:
    """Send a plain text email using SMTP settings from app config."""
    host = current_app.config.get("SMTP_HOST")
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    sender = current_app.config.get("SMTP_SENDER")
    port = current_app.config.get("SMTP_PORT", 587)
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

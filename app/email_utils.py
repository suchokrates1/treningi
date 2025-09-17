from flask import current_app
from .models import EmailSettings
from . import db
import smtplib
from email.message import EmailMessage
import re
from collections.abc import Iterable


def send_email(
    subject: str,
    body: str | None,
    recipients: list[str],
    *,
    html_body: str | None = None,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    sender: str | None = None,
    encryption: str | None = None,
    use_tls: bool | None = None,
    attachments: Iterable[tuple[str, str, bytes]] | None = None,
) -> tuple[bool, str | None]:
    """Send an email using stored SMTP settings.

    Returns a tuple ``(success, error)`` where ``success`` is ``True`` when the
    message was sent and ``error`` contains the exception message on failure.
    """
    settings = db.session.get(EmailSettings, 1)
    host = host or (
        settings.server
        if settings and settings.server
        else current_app.config.get("SMTP_HOST")
    )
    username = username or (
        settings.login
        if settings and settings.login
        else current_app.config.get("SMTP_USERNAME")
    )
    password = password or (
        settings.password
        if settings and settings.password
        else current_app.config.get("SMTP_PASSWORD")
    )
    display_name = sender or (settings.sender if settings and settings.sender else None)
    address = current_app.config.get("SMTP_SENDER")
    port = port or (
        settings.port
        if settings and settings.port
        else current_app.config.get("SMTP_PORT", 587)
    )
    if encryption is None:
        if use_tls is not None:
            encryption = "tls" if use_tls else "none"
        else:
            encryption = (
                settings.encryption
                if settings and settings.encryption
                else current_app.config.get("SMTP_ENCRYPTION")
            )
    if not encryption:
        enc_env = current_app.config.get("SMTP_ENCRYPTION")
        if enc_env:
            encryption = enc_env
        else:
            encryption = "tls" if current_app.config.get("SMTP_USE_TLS", True) else "none"

    if not host:
        current_app.logger.warning("SMTP_HOST not configured; skipping email")
        return True, None

    if display_name and ("@" in display_name or "<" in display_name):
        sender_header = display_name
    elif address:
        sender_header = f"{display_name} <{address}>" if display_name else address
    else:
        sender_header = display_name or ""

    current_app.logger.info(
        "Sending email via %s:%s from %s to %s",
        host,
        port,
        sender_header,
        ", ".join(recipients),
    )
    if username:
        current_app.logger.debug("SMTP login: %s", username)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_header
    msg["To"] = ", ".join(recipients)

    if not body and html_body:
        body = re.sub(r"<[^>]+>", "", html_body)

    msg.set_content(body or "")

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if attachments:
        for filename, content_type, data in attachments:
            maintype, subtype = (content_type.split("/", 1) + [""])[:2]
            if not subtype:
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(
                data,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

    try:
        smtp_cls = smtplib.SMTP_SSL if encryption == "ssl" else smtplib.SMTP
        with smtp_cls(host, port) as smtp:
            if encryption == "tls":
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        current_app.logger.info("Email sent successfully")
        return True, None
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.exception("Email sending failed")
        return False, str(exc)

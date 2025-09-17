from flask import (
    Blueprint,
    current_app,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from datetime import datetime, timezone
import base64
import binascii
from pathlib import Path
from collections.abc import Iterable
from sqlalchemy import select
from .models import Training, Booking, Volunteer, EmailSettings, StoredFile
from .forms import VolunteerForm, CancelForm
from . import db
from .email_utils import send_email
from .template_utils import render_template_string


def _get_or_404(model, ident):
    instance = db.session.get(model, ident)
    if instance is None:
        abort(404)
    return instance


def _decode_attachment_payload(raw: object) -> bytes | None:
    """Convert a payload from JSON into raw bytes.

    Legacy rows may still store attachment contents inline (as base64 or plain
    text). The admin panel stores files on disk, so this is only used for
    backwards compatibility.
    """

    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        try:
            return base64.b64decode(raw, validate=True)
        except binascii.Error:
            return raw.encode("utf-8")
    if isinstance(raw, Iterable):
        try:
            return bytes(raw)
        except (TypeError, ValueError):
            return None
    return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            try:
                return int(stripped)
            except ValueError:
                return None
    return None


def _resolve_attachment_metadata(
    attachments_meta: Iterable[object],
) -> list[tuple[str, str, bytes]]:
    """Resolve attachments referenced in the email settings.

    Supports both the new metadata format stored by the admin panel and legacy
    entries that point to ``StoredFile`` rows or embed file contents directly in
    JSON. Missing files are ignored with a warning.
    """

    attachments: list[tuple[str, str, bytes]] = []
    legacy_ids: set[int] = set()
    file_metadatas: list[dict[str, object]] = []

    for entry in attachments_meta:
        if isinstance(entry, dict):
            stored_name = entry.get("stored_name")
            if stored_name:
                file_metadatas.append(entry)
                continue

            file_id = _coerce_int(
                entry.get("stored_file_id") or entry.get("id")
            )
            if file_id is not None:
                legacy_ids.add(file_id)
                continue

            payload = _decode_attachment_payload(entry.get("data"))
            if payload is None:
                current_app.logger.warning(
                    "Attachment metadata %s has no readable payload", entry
                )
                continue

            filename = (
                entry.get("original_name")
                or entry.get("filename")
                or "zalacznik"
            )
            content_type = entry.get("content_type") or "application/octet-stream"
            attachments.append((str(filename), str(content_type), payload))
            continue

        file_id = _coerce_int(entry)
        if file_id is not None:
            legacy_ids.add(file_id)

    if legacy_ids:
        stored_rows = db.session.scalars(
            select(StoredFile).where(StoredFile.id.in_(legacy_ids))
        ).all()
        stored_by_id = {row.id: row for row in stored_rows}
        for file_id in legacy_ids:
            stored_file = stored_by_id.get(file_id)
            if not stored_file:
                current_app.logger.warning(
                    "Stored file with id %s referenced in settings but missing",
                    file_id,
                )
                continue
            attachments.append(
                (
                    stored_file.filename,
                    stored_file.content_type,
                    stored_file.data,
                )
            )

    if file_metadatas:
        attachments_dir = Path(current_app.instance_path) / "attachments"
        for entry in file_metadatas:
            stored_name = entry.get("stored_name")
            if not stored_name:
                continue
            file_path = attachments_dir / str(stored_name)
            try:
                payload = file_path.read_bytes()
            except OSError:
                current_app.logger.warning(
                    "Attachment file %s referenced in settings is missing", file_path
                )
                continue
            filename = (
                entry.get("original_name")
                or entry.get("filename")
                or str(stored_name)
            )
            content_type = entry.get("content_type") or "application/octet-stream"
            attachments.append((str(filename), str(content_type), payload))

    return attachments

bp = Blueprint('routes', __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    form = VolunteerForm()

    if form.validate_on_submit():
        # Sprawdzenie, czy liczba wolontariuszy nie przekracza limitu
        try:
            training_id = int(form.training_id.data)
        except (TypeError, ValueError):
            flash("Niepoprawny ID treningu", "danger")
            return redirect(url_for("routes.index"))

        training = _get_or_404(Training, training_id)
        if training.is_canceled or training.is_deleted:
            flash("Ten trening został odwołany lub usunięty.", "danger")
            return redirect(url_for("routes.index"))
        current_count = Booking.query.filter_by(training_id=training.id).count()
        if current_count >= training.max_volunteers:
            flash(
                "Na ten trening nie można się już zapisać. "
                "Limit wolontariuszy został osiągnięty.",
                "danger",
            )
            return redirect(url_for("routes.index"))

        # Sprawdzenie, czy podany adres e-mail jest już zarejestrowany
        email = form.email.data.strip().lower()
        existing_volunteer = Volunteer.query.filter_by(
            email=email,
        ).first()

        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()

        if not existing_volunteer:
            existing_volunteer = Volunteer(
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            db.session.add(existing_volunteer)
        else:
            existing_volunteer.first_name = first_name
            existing_volunteer.last_name = last_name

        existing_volunteer.is_adult = form.is_adult.data

        if existing_volunteer.id is None:
            db.session.flush()

        existing_booking = Booking.query.filter_by(
            training_id=training.id,
            volunteer_id=existing_volunteer.id,
        ).first()

        if existing_booking:
            flash("Jesteś już zapisany na ten trening.", "warning")
            return redirect(url_for("routes.index"))

        booking = Booking(
            training_id=training.id,
            volunteer_id=existing_volunteer.id,
        )
        db.session.add(booking)
        db.session.commit()

        settings = db.session.get(EmailSettings, 1)
        if settings and settings.registration_template:
            cancel_link = url_for(
                "routes.cancel_booking",
                training_id=training.id,
                _external=True,
            )
            training_info = (
                f"{training.date.strftime('%Y-%m-%d %H:%M')} "
                f"w {training.location.name}"
            )
            data = {
                "first_name": existing_volunteer.first_name,
                "last_name": existing_volunteer.last_name,
                "training": training_info,
                "cancel_link": cancel_link,
                "date": training.date.strftime("%Y-%m-%d %H:%M"),
                "location": training.location.name,
                "logo": url_for("static", filename="logo.png", _external=True),
            }
            html_body = render_template_string(
                settings.registration_template, data
            )
            attachments: list[tuple[str, str, bytes]] = []
            if settings:
                attachments_meta = (
                    settings.registration_files_adult
                    if existing_volunteer.is_adult
                    else settings.registration_files_minor
                ) or []
                attachments.extend(
                    _resolve_attachment_metadata(attachments_meta)
                )

            success, error = send_email(
                "Potwierdzenie zgłoszenia",
                None,
                [existing_volunteer.email],
                html_body=html_body,
                attachments=attachments,
            )
            if not success:
                msg = "Nie udało się wysłać potwierdzenia"
                if error:
                    msg += f": {error}"
                flash(msg, "danger")
        flash("Zapisano na trening!", "success")
        return redirect(url_for('routes.index'))

    # Pogrupuj treningi według miesiąca
    trainings = (
        Training.query.filter_by(is_deleted=False)
        .filter(Training.date >= datetime.now(timezone.utc))
        .order_by(Training.date)
        .all()
    )
    trainings_by_month = {}

    for training in trainings:
        month_key = training.date.strftime("%Y-%m")
        trainings_by_month.setdefault(month_key, []).append(training)

    return render_template(
        "index.html",
        form=form,
        trainings_by_month=trainings_by_month,
    )


@bp.route("/cancel", methods=["GET", "POST"])
def cancel_booking():
    form = CancelForm()
    training_id = request.args.get("training_id", type=int)
    if training_id:
        form.training_id.data = training_id
    if form.validate_on_submit():
        try:
            training_id = int(form.training_id.data)
        except (TypeError, ValueError):
            flash("Niepoprawny ID treningu", "danger")
            return redirect(url_for("routes.cancel_booking"))

        email = form.email.data.strip().lower()
        volunteer = Volunteer.query.filter_by(
            email=email
        ).first()
        if volunteer:
            booking = Booking.query.filter_by(
                training_id=training_id,
                volunteer_id=volunteer.id,
            ).first()
            if booking:
                training = booking.training
                db.session.delete(booking)
                db.session.commit()

                settings = db.session.get(EmailSettings, 1)
                template = (
                    settings.cancellation_template
                    if settings and settings.cancellation_template
                    else "Twoje zgłoszenie na trening {training} zostało anulowane."
                )
                training_info = (
                    f"{training.date.strftime('%Y-%m-%d %H:%M')} "
                    f"w {training.location.name}"
                )
                data = {
                    "first_name": volunteer.first_name,
                    "last_name": volunteer.last_name,
                    "training": training_info,
                    "date": training.date.strftime("%Y-%m-%d %H:%M"),
                    "location": training.location.name,
                    "logo": url_for("static", filename="logo.png", _external=True),
                }
                html_body = render_template_string(template, data)
                success, error = send_email(
                    "Rezygnacja z treningu",
                    None,
                    [volunteer.email],
                    html_body=html_body,
                )
                if not success:
                    msg = "Nie udało się wysłać potwierdzenia"
                    if error:
                        msg += f": {error}"
                    flash(msg, "danger")

                flash("Zgłoszenie zostało usunięte.", "success")
                return redirect(url_for("routes.index"))
        flash("Nie znaleziono zapisu na ten trening.", "warning")
        return redirect(
            url_for("routes.cancel_booking", training_id=training_id)
        )

    training = None
    if training_id:
        training = _get_or_404(Training, training_id)

    return render_template(
        "cancel.html",
        form=form,
        training=training,
    )

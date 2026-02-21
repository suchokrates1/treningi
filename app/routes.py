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
from datetime import datetime, date, timezone
from pathlib import Path
from .models import Training, Booking, Volunteer, EmailSettings, StoredFile
from .forms import VolunteerForm, CancelForm, PhoneUpdateForm
from . import db
from .email_utils import send_email
from .template_utils import render_template_string
from .whatsapp_utils import (
    notify_coach_volunteer_canceled,
    schedule_signup_notification,
    format_phone_display,
    normalize_phone_number,
)

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

        training = db.session.get(Training, training_id)
        if training is None:
            abort(404)
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
        phone_number = form.phone_number.data.strip() if form.phone_number.data else None
        if phone_number:
            phone_number = normalize_phone_number(phone_number)

        if not existing_volunteer:
            existing_volunteer = Volunteer(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
            )
            db.session.add(existing_volunteer)
        else:
            existing_volunteer.first_name = first_name
            existing_volunteer.last_name = last_name
            existing_volunteer.phone_number = phone_number

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

        # Coach receives daily summary before training (send-coach-summary),
        # no individual signup notifications via WhatsApp.

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

                legacy_ids = [
                    entry for entry in attachments_meta if isinstance(entry, int)
                ]
                if legacy_ids:
                    stored = (
                        StoredFile.query.filter(StoredFile.id.in_(legacy_ids)).all()
                    )
                    stored_by_id = {file.id: file for file in stored}
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

                attachments_dir = Path(current_app.instance_path) / "attachments"
                for entry in attachments_meta:
                    if not isinstance(entry, dict):
                        continue
                    stored_name = entry.get("stored_name")
                    if not stored_name:
                        continue
                    file_path = attachments_dir / stored_name
                    try:
                        data = file_path.read_bytes()
                    except OSError:
                        current_app.logger.warning(
                            "Attachment file %s referenced in settings is missing",
                            file_path,
                        )
                        continue
                    filename = (
                        entry.get("original_name")
                        or entry.get("filename")
                        or stored_name
                    )
                    content_type = entry.get("content_type") or "application/octet-stream"
                    attachments.append((filename, content_type, data))

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

        # Schedule deferred WhatsApp signup confirmation (consolidates
        # back-to-back signups within the grace period).
        if existing_volunteer.phone_number:
            training_date_str = training.date.strftime('%Y-%m-%d %H:%M')
            schedule_signup_notification(
                volunteer_id=existing_volunteer.id,
                volunteer_phone=existing_volunteer.phone_number,
                volunteer_name=existing_volunteer.first_name,
                training_date=training_date_str,
                training_location=training.location.name,
                app=current_app._get_current_object(),
            )

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
                volunteer_full_name = f"{volunteer.first_name} {volunteer.last_name}"
                training_date_str = training.date.strftime('%Y-%m-%d %H:%M')

                # Smart cancel: only notify coach if training is today
                # or volunteer had already confirmed/declined (reminder was sent).
                training_is_today = training.date.date() == date.today()
                was_confirmed = booking.is_confirmed is not None

                db.session.delete(booking)
                db.session.commit()

                # Notify coach via WhatsApp only when relevant
                if training.coach.phone_number and (training_is_today or was_confirmed):
                    wa_success, wa_error = notify_coach_volunteer_canceled(
                        coach_phone=training.coach.phone_number,
                        coach_name=f"{training.coach.first_name} {training.coach.last_name}",
                        volunteer_name=volunteer_full_name,
                        training_date=training_date_str,
                        training_location=training.location.name,
                    )
                    if not wa_success and wa_error:
                        current_app.logger.warning("WhatsApp notification failed: %s", wa_error)

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
        training = db.session.get(Training, training_id)
        if training is None:
            abort(404)

    return render_template(
        "cancel.html",
        form=form,
        training=training,
    )


@bp.route("/update-phone/<token>", methods=["GET", "POST"])
def update_phone(token):
    """Strona do aktualizacji numeru telefonu wolontariusza."""
    # Znajdź wolontariusza po tokenie
    volunteer = Volunteer.query.filter_by(phone_update_token=token).first()
    
    if not volunteer:
        return render_template(
            "update_phone.html",
            error="Link jest nieprawidłowy lub wygasł.",
            form=None,
            volunteer=None,
            success=False,
        )
    
    # Jeśli wolontariusz już ma numer telefonu
    if volunteer.phone_number:
        return render_template(
            "update_phone.html",
            error="Twój numer telefonu jest już zapisany.",
            form=None,
            volunteer=volunteer,
            success=False,
        )
    
    form = PhoneUpdateForm()
    
    if form.validate_on_submit():
        # Zapisz numer telefonu
        phone_raw = form.phone_number.data.strip() if form.phone_number.data else None
        volunteer.phone_number = normalize_phone_number(phone_raw) if phone_raw else None
        # Wyczyść token - link jednorazowy
        volunteer.phone_update_token = None
        db.session.commit()
        
        return render_template(
            "update_phone.html",
            success=True,
            form=None,
            volunteer=volunteer,
            error=None,
        )
    
    return render_template(
        "update_phone.html",
        form=form,
        volunteer=volunteer,
        success=False,
        error=None,
    )


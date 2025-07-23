from flask import Blueprint, render_template, redirect, url_for, flash, request
from .models import Training, Booking, Volunteer, EmailSettings
from .forms import VolunteerForm, CancelForm
from . import db
from .email_utils import send_email
from .template_utils import render_template_string

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

        training = Training.query.get_or_404(training_id)
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

        if not existing_volunteer:
            existing_volunteer = Volunteer(
                first_name=form.first_name.data.strip(),
                last_name=form.last_name.data.strip(),
                email=email,
            )
            db.session.add(existing_volunteer)
            db.session.commit()

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
            success, error = send_email(
                "Potwierdzenie zgłoszenia",
                None,
                [existing_volunteer.email],
                html_body=html_body,
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
        training = Training.query.get_or_404(training_id)

    return render_template(
        "cancel.html",
        form=form,
        training=training,
    )

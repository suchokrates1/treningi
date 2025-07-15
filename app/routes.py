from flask import Blueprint, render_template, redirect, url_for, flash, request
from .models import Training, Booking, Volunteer
from .forms import VolunteerForm, CancelForm
from . import db

bp = Blueprint('routes', __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    form = VolunteerForm()

    if form.validate_on_submit():
        # Sprawdzenie, czy na dany trening jest już 2 wolontariuszy
        training_id = int(form.training_id.data)
        training = Training.query.get_or_404(training_id)
        if training.is_canceled:
            flash("Ten trening został odwołany.", "danger")
            return redirect(url_for("routes.index"))
        if len(training.bookings) >= 2:
            flash(
                "Na ten trening nie można się już zapisać. "
                "Limit wolontariuszy został osiągnięty.",
                "danger",
            )
            return redirect(url_for("routes.index"))

        # Sprawdzenie, czy podany adres e-mail jest już zarejestrowany
        existing_volunteer = Volunteer.query.filter_by(
            email=form.email.data.strip(),
        ).first()

        if not existing_volunteer:
            existing_volunteer = Volunteer(
                first_name=form.first_name.data.strip(),
                last_name=form.last_name.data.strip(),
                email=form.email.data.strip(),
            )
            db.session.add(existing_volunteer)
            db.session.commit()

        booking = Booking(
            training_id=training.id,
            volunteer_id=existing_volunteer.id,
        )
        db.session.add(booking)
        db.session.commit()
        flash("Zapisano na trening!", "success")
        return redirect(url_for('routes.index'))

    # Pogrupuj treningi według miesiąca
    trainings = Training.query.order_by(Training.date).all()
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
        training_id = int(form.training_id.data)
        volunteer = Volunteer.query.filter_by(
            email=form.email.data.strip()
        ).first()
        if volunteer:
            booking = Booking.query.filter_by(
                training_id=training_id,
                volunteer_id=volunteer.id,
            ).first()
            if booking:
                db.session.delete(booking)
                db.session.commit()
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

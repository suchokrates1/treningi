from flask import Blueprint, render_template, request, redirect, url_for, flash
from .models import Training, Booking, Volunteer, Coach
from .forms import VolunteerForm
from . import db
from sqlalchemy import func
from datetime import datetime

bp = Blueprint('routes', __name__)

@bp.route("/", methods=["GET", "POST"])
def index():
    form = VolunteerForm()

    if form.validate_on_submit():
        # Sprawdzenie, czy na dany trening jest już 2 wolontariuszy
        training_id = int(form.training_id.data)
        training = Training.query.get_or_404(training_id)
        if len(training.bookings) >= 2:
            flash("Na ten trening nie można się już zapisać. Limit wolontariuszy został osiągnięty.", "danger")
            return redirect(url_for('routes.index'))

        # Sprawdzenie, czy ten sam wolontariusz się nie zapisał już wcześniej
        existing_volunteer = Volunteer.query.filter_by(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone_number=form.phone_number.data.strip()
        ).first()

        if not existing_volunteer:
            existing_volunteer = Volunteer(
                first_name=form.first_name.data.strip(),
                last_name=form.last_name.data.strip(),
                phone_number=form.phone_number.data.strip()
            )
            db.session.add(existing_volunteer)
            db.session.commit()

        booking = Booking(training_id=training.id, volunteer_id=existing_volunteer.id)
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

    return render_template("index.html", form=form, trainings_by_month=trainings_by_month)

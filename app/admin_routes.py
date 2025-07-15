from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
import flask
from functools import wraps
from datetime import datetime

from . import db
from .forms import (
    CoachForm,
    TrainingForm,
    LoginForm,
    ImportTrainingsForm,
    LocationForm,
)
from .models import Coach, Training, Location

admin_bp = Blueprint("admin", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/")
def admin_root():
    """Redirect bare /admin to the trainings view."""
    return redirect(url_for("admin.manage_trainings"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        if form.password.data == current_app.config["ADMIN_PASSWORD"]:
            session["admin_logged_in"] = True
            flash("Zalogowano jako administrator.", "success")
            return redirect(url_for("admin.manage_trainings"))
        flash("Nieprawidłowe hasło.", "danger")

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    flash("Wylogowano.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/trainers", methods=["GET", "POST"])
@login_required
def manage_trainers():
    form = CoachForm()
    coaches = Coach.query.order_by(Coach.last_name).all()

    if form.validate_on_submit():
        new_coach = Coach(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone_number=form.phone_number.data.strip(),
        )
        db.session.add(new_coach)
        db.session.commit()
        flash("Dodano nowego trenera.", "success")
        return redirect(url_for("admin.manage_trainers"))

    return render_template("admin/trainers.html", form=form, coaches=coaches)


@admin_bp.route("/trainers/edit/<int:coach_id>", methods=["GET", "POST"])
@login_required
def edit_trainer(coach_id):
    coach = Coach.query.get_or_404(coach_id)
    form = CoachForm(obj=coach)

    if form.validate_on_submit():
        coach.first_name = form.first_name.data.strip()
        coach.last_name = form.last_name.data.strip()
        coach.phone_number = form.phone_number.data.strip()
        db.session.commit()
        flash("Zaktualizowano dane trenera.", "success")
        return redirect(url_for("admin.manage_trainers"))

    return render_template("admin/edit_trainer.html", form=form, coach=coach)


@admin_bp.route("/locations", methods=["GET", "POST"])
@login_required
def manage_locations():
    form = LocationForm()
    locations = Location.query.order_by(Location.name).all()

    if form.validate_on_submit():
        new_location = Location(name=form.name.data.strip())
        db.session.add(new_location)
        db.session.commit()
        flash("Dodano nowe miejsce.", "success")
        return redirect(url_for("admin.manage_locations"))

    return render_template(
        "admin/locations.html",
        form=form,
        locations=locations,
    )


@admin_bp.route("/locations/edit/<int:location_id>", methods=["GET", "POST"])
@login_required
def edit_location(location_id):
    location = Location.query.get_or_404(location_id)
    form = LocationForm(obj=location)

    if form.validate_on_submit():
        location.name = form.name.data.strip()
        db.session.commit()
        flash("Zaktualizowano miejsce.", "success")
        return redirect(url_for("admin.manage_locations"))

    return render_template(
        "admin/edit_location.html",
        form=form,
        location=location,
    )


@admin_bp.route("/trainings", methods=["GET", "POST"])
@login_required
def manage_trainings():
    form = TrainingForm()
    form.coach_id.choices = [
        (
            c.id,
            f"{c.first_name} {c.last_name}",
        )
        for c in Coach.query.order_by(Coach.last_name).all()
    ]
    form.location_id.choices = [
        (loc.id, loc.name)
        for loc in Location.query.order_by(Location.name).all()
    ]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    trainings_q = Training.query.filter(
        Training.date >= today
    ).order_by(Training.date)
    trainings = trainings_q.all()

    trainings_by_month = {}
    for t in trainings:
        month_key = t.date.strftime("%Y-%m")
        trainings_by_month.setdefault(month_key, []).append(t)

    if form.validate_on_submit():
        new_training = Training(
            date=form.date.data,
            location_id=form.location_id.data,
            coach_id=form.coach_id.data,
        )
        db.session.add(new_training)
        db.session.commit()
        flash("Dodano nowy trening.", "success")
        return redirect(url_for("admin.manage_trainings"))

    return render_template(
        "admin/trainings.html",
        form=form,
        trainings_by_month=trainings_by_month,
    )


@admin_bp.route("/export")
@login_required
def export_excel():
    from io import BytesIO
    from openpyxl import Workbook
    from flask import send_file

    wb = Workbook()
    ws = wb.active
    ws.title = "Treningi"

    ws.append([
        "Data",
        "Godzina",
        "Miejsce",
        "Trener",
        "Telefon trenera",
        "Wolontariusz 1",
        "Email 1",
        "Wolontariusz 2",
        "Email 2",
    ])

    trainings = Training.query.order_by(Training.date).all()

    for t in trainings:
        bookings = t.bookings[:2]
        v1 = bookings[0].volunteer if len(bookings) > 0 else None
        v2 = bookings[1].volunteer if len(bookings) > 1 else None

        ws.append([
            t.date.strftime("%Y-%m-%d"),
            t.date.strftime("%H:%M"),
            t.location.name,
            f"{t.coach.first_name} {t.coach.last_name}",
            t.coach.phone_number,
            f"{v1.first_name} {v1.last_name}" if v1 else "",
            v1.email if v1 else "",
            f"{v2.first_name} {v2.last_name}" if v2 else "",
            v2.email if v2 else "",
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"treningi_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


@admin_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_excel():
    form = ImportTrainingsForm()

    if form.validate_on_submit():
        from openpyxl import load_workbook

        file = form.file.data
        wb = load_workbook(file)
        ws = wb.active

        for row in ws.iter_rows(min_row=2, values_only=True):
            date_val, time_val, trainer_name, phone, place = row[:5]
            if not (date_val and time_val and phone and place):
                continue

            if isinstance(date_val, datetime):
                date_part = date_val.date()
            else:
                date_part = datetime.strptime(str(date_val), "%Y-%m-%d").date()

            if isinstance(time_val, datetime):
                time_part = time_val.time()
            else:
                time_part = datetime.strptime(str(time_val), "%H:%M").time()

            dt = datetime.combine(date_part, time_part)

            coach = Coach.query.filter_by(
                phone_number=str(phone).strip()
            ).first()
            if not coach:
                first, *rest = str(trainer_name).strip().split(" ", 1)
                last = rest[0] if rest else ""
                coach = Coach(
                    first_name=first,
                    last_name=last,
                    phone_number=str(phone).strip(),
                )
                db.session.add(coach)
                db.session.commit()

            location = Location.query.filter_by(
                name=str(place).strip()
            ).first()
            if not location:
                location = Location(name=str(place).strip())
                db.session.add(location)
                db.session.commit()

            training = Training(
                date=dt,
                coach_id=coach.id,
                location_id=location.id,
            )
            db.session.add(training)
        db.session.commit()
        flash("Zaimportowano treningi.", "success")
        return redirect(url_for("admin.manage_trainings"))

    return render_template("admin/import.html", form=form)


@admin_bp.route("/history")
@login_required
def history():
    """List past trainings with volunteer sign-ups."""
    page = flask.request.args.get("page", 1, type=int)
    trainings_q = Training.query.filter(
        Training.date < datetime.now()
    ).order_by(Training.date.desc())
    pagination = db.paginate(trainings_q, page=page, per_page=10)
    return render_template(
        "admin/history.html",
        trainings=pagination.items,
        pagination=pagination,
    )

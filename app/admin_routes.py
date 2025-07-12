from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from functools import wraps
from datetime import datetime

from . import db
from .forms import CoachForm, TrainingForm
from .models import Coach, Training

admin_bp = Blueprint("admin", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["admin_logged_in"] = True
            flash("Zalogowano jako administrator.", "success")
            return redirect(url_for("admin.manage_trainers"))
        flash("Nieprawidłowe hasło.", "danger")
    return render_template("admin/login.html")


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


@admin_bp.route("/trainings", methods=["GET", "POST"])
@login_required
def manage_trainings():
    form = TrainingForm()
    form.coach_id.choices = [
        (c.id, f"{c.first_name} {c.last_name}") for c in Coach.query.order_by(Coach.last_name).all()
    ]
    trainings = Training.query.order_by(Training.date).all()

    if form.validate_on_submit():
        new_training = Training(
            date=form.date.data,
            location=form.location.data.strip(),
            coach_id=form.coach_id.data,
        )
        db.session.add(new_training)
        db.session.commit()
        flash("Dodano nowy trening.", "success")
        return redirect(url_for("admin.manage_trainings"))

    return render_template("admin/trainings.html", form=form, trainings=trainings)


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
        "Telefon 1",
        "Wolontariusz 2",
        "Telefon 2",
    ])

    trainings = Training.query.order_by(Training.date).all()

    for t in trainings:
        bookings = t.bookings[:2]
        v1 = bookings[0].volunteer if len(bookings) > 0 else None
        v2 = bookings[1].volunteer if len(bookings) > 1 else None

        ws.append([
            t.date.strftime("%Y-%m-%d"),
            t.date.strftime("%H:%M"),
            t.location,
            f"{t.coach.first_name} {t.coach.last_name}",
            t.coach.phone_number,
            f"{v1.first_name} {v1.last_name}" if v1 else "",
            v1.phone_number if v1 else "",
            f"{v2.first_name} {v2.last_name}" if v2 else "",
            v2.phone_number if v2 else "",
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"treningi_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

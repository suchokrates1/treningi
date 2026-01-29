from . import db
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, event
from sqlalchemy import LargeBinary


class Coach(db.Model):
    __tablename__ = 'coaches'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f"<Coach {self.first_name} {self.last_name}>"


class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)

    def __repr__(self):
        return f"<Location {self.name}>"


class TrainingSeries(db.Model):
    __tablename__ = 'training_series'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    start_date = db.Column(db.DateTime(timezone=True), nullable=False)
    repeat = db.Column(db.Boolean, nullable=False, default=False)
    repeat_interval_weeks = db.Column(db.Integer, nullable=True)
    repeat_until = db.Column(db.Date, nullable=True)
    planned_count = db.Column(db.Integer, nullable=False, default=0)
    created_count = db.Column(db.Integer, nullable=False, default=0)
    skipped_dates = db.Column(db.JSON, nullable=False, default=list)
    coach_id = db.Column(db.Integer, db.ForeignKey('coaches.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    max_volunteers = db.Column(db.Integer, nullable=False)

    coach = db.relationship('Coach', backref=db.backref('training_series', lazy=True))
    location = db.relationship('Location', backref=db.backref('training_series', lazy=True))
    trainings = db.relationship('Training', back_populates='series', lazy=True)


class Training(db.Model):
    __tablename__ = 'trainings'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime(timezone=True), nullable=False)
    location_id = db.Column(
        db.Integer,
        db.ForeignKey('locations.id'),
        nullable=False,
    )
    coach_id = db.Column(
        db.Integer,
        db.ForeignKey('coaches.id'),
        nullable=False,
    )
    series_id = db.Column(
        db.Integer,
        db.ForeignKey('training_series.id'),
        nullable=True,
    )
    is_canceled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    max_volunteers = db.Column(
        db.Integer,
        nullable=False,
        default=2,
        server_default="2",
    )

    __table_args__ = (
        CheckConstraint(
            "(SELECT COUNT(*) FROM bookings WHERE bookings.training_id = id) <= max_volunteers",
            name="booking_limit",
            info={"skip_sqlite": True},
        ),
    )

    coach = db.relationship(
        'Coach',
        backref=db.backref('trainings', lazy=True),
    )
    location = db.relationship(
        'Location',
        backref=db.backref('trainings', lazy=True),
    )
    series = db.relationship(
        'TrainingSeries',
        back_populates='trainings',
    )

    def __repr__(self):
        return (
            f"<Training {self.date.strftime('%Y-%m-%d %H:%M')} at "
            f"{self.location.name}>"
        )


class Volunteer(db.Model):
    __tablename__ = 'volunteers'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(128), nullable=False, unique=True)
    phone_number = db.Column(db.String(20), nullable=True)
    is_adult = db.Column(db.Boolean, nullable=True)

    def __repr__(self):
        return f"<Volunteer {self.first_name} {self.last_name}>"


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(
        db.Integer,
        db.ForeignKey('trainings.id'),
        nullable=False,
    )
    volunteer_id = db.Column(
        db.Integer,
        db.ForeignKey('volunteers.id'),
        nullable=False,
    )
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    is_confirmed = db.Column(
        db.Boolean,
        nullable=True,
        default=None,
    )

    training = db.relationship(
        'Training',
        backref=db.backref(
            'bookings',
            cascade='all, delete-orphan',
            lazy=True,
        ),
    )
    volunteer = db.relationship(
        'Volunteer',
        backref=db.backref(
            'bookings',
            cascade='all, delete-orphan',
            lazy=True,
        ),
    )

    __table_args__ = (
        db.UniqueConstraint(
            'training_id',
            'volunteer_id',
            name='unique_booking',
        ),
    )

    def __repr__(self):
        return f"<Booking {self.training_id} by {self.volunteer_id}>"


class EmailSettings(db.Model):
    """Store SMTP configuration and email templates."""

    __tablename__ = "email_settings"

    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(128), nullable=True)
    port = db.Column(db.Integer, nullable=True)
    login = db.Column(db.String(128), nullable=True)
    password = db.Column(db.String(128), nullable=True)
    sender = db.Column(db.String(128), nullable=True)
    encryption = db.Column(db.String(10), nullable=True)
    registration_template = db.Column(db.Text, nullable=True)
    cancellation_template = db.Column(db.Text, nullable=True)
    registration_files_adult = db.Column(db.JSON, nullable=True)
    registration_files_minor = db.Column(db.JSON, nullable=True)


class StoredFile(db.Model):
    """Binary file stored in the database for email attachments."""

    __tablename__ = "stored_files"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    content_type = db.Column(db.String(128), nullable=False)
    data = db.Column(LargeBinary, nullable=False)


@event.listens_for(Training.__table__, "before_create")
def _skip_sqlite_check(table, connection, **kw):
    if connection.dialect.name == "sqlite":
        to_remove = [
            c
            for c in list(table.constraints)
            if isinstance(c, CheckConstraint) and c.info.get("skip_sqlite")
        ]
        for c in to_remove:
            table.constraints.remove(c)

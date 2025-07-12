from . import db
from datetime import datetime


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


class Training(db.Model):
    __tablename__ = 'trainings'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
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

    coach = db.relationship(
        'Coach',
        backref=db.backref('trainings', lazy=True),
    )
    location = db.relationship(
        'Location',
        backref=db.backref('trainings', lazy=True),
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
    phone_number = db.Column(db.String(20), nullable=False)

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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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

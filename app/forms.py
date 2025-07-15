from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    SelectField,
    PasswordField,
)
from wtforms.fields.datetime import DateTimeLocalField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Length, Email
from wtforms.fields import HiddenField, TelField
from wtforms import IntegerField, TextAreaField


class CoachForm(FlaskForm):
    first_name = StringField(
        'Imię', validators=[DataRequired(), Length(max=64)]
    )
    last_name = StringField(
        'Nazwisko', validators=[DataRequired(), Length(max=64)]
    )
    phone_number = TelField(
        'Telefon', validators=[DataRequired(), Length(max=20)]
    )
    submit = SubmitField('Zapisz')


class TrainingForm(FlaskForm):
    date = DateTimeLocalField(
        'Data i godzina treningu',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired()],
        render_kw={"placeholder": "dd/mm/rrrr gg:mm"},
    )
    location_id = SelectField(
        'Miejsce', coerce=int, validators=[DataRequired()]
    )
    coach_id = SelectField(
        'Trener', coerce=int, validators=[DataRequired()]
    )
    submit = SubmitField('Zapisz')


class VolunteerForm(FlaskForm):
    first_name = StringField(
        'Imię', validators=[DataRequired(), Length(max=64)]
    )
    last_name = StringField(
        'Nazwisko', validators=[DataRequired(), Length(max=64)]
    )
    email = StringField(
        'Email', validators=[DataRequired(), Email(), Length(max=128)]
    )
    training_id = HiddenField()  # ukryte pole – ID treningu
    submit = SubmitField('Zapisz się')


class LoginForm(FlaskForm):
    password = PasswordField('Hasło', validators=[DataRequired()])
    submit = SubmitField('Zaloguj się')


class ImportTrainingsForm(FlaskForm):
    file = FileField('Plik Excel', validators=[DataRequired()])
    submit = SubmitField('Importuj')


class LocationForm(FlaskForm):
    """Simple form for adding or editing locations."""

    name = StringField('Nazwa', validators=[DataRequired(), Length(max=128)])
    submit = SubmitField('Zapisz')


class CancelForm(FlaskForm):
    """Simple form for cancelling a volunteer booking."""

    email = StringField(
        'Email', validators=[DataRequired(), Email(), Length(max=128)]
    )
    training_id = HiddenField()
    submit = SubmitField('Wypisz się')


class SettingsForm(FlaskForm):
    """Form for configuring email settings."""

    server = StringField('Serwer SMTP', validators=[Length(max=128)])
    port = IntegerField('Port', validators=[DataRequired()])
    login = StringField('Login', validators=[Length(max=128)])
    password = StringField('Hasło', validators=[Length(max=128)])
    sender = StringField(
        'Nadawca', validators=[DataRequired(), Email(), Length(max=128)]
    )
    registration_template = TextAreaField('Szablon maila zapisu')
    cancellation_template = TextAreaField('Szablon maila odwołania')
    submit = SubmitField('Zapisz')

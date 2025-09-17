from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    SelectField,
    PasswordField,
)
from wtforms.fields.datetime import DateTimeLocalField
from flask_wtf.file import FileField, MultipleFileField
from wtforms.validators import DataRequired, Length, Email, Optional, NumberRange
from wtforms.fields import HiddenField, TelField
from wtforms import SelectMultipleField, widgets
from wtforms import IntegerField




class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


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
    max_volunteers = IntegerField(
        'Liczba miejsc',
        default=2,
        validators=[DataRequired(), NumberRange(min=1, max=20)],
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
    encryption = SelectField(
        'Szyfrowanie',
        choices=[('tls', 'STARTTLS'), ('ssl', 'SSL'), ('none', 'Brak')],
        validators=[DataRequired()],
    )
    login = StringField('Login', validators=[Length(max=128)])
    password = StringField('Hasło', validators=[Length(max=128)])
    sender = StringField(
        'Nazwa nadawcy',
        validators=[DataRequired(), Length(max=128)],
        description='Tekst pokazywany w polu From; adres jest pobierany z SMTP_SENDER.',
    )
    registration_template = HiddenField('Szablon maila zapisu')
    cancellation_template = HiddenField('Szablon maila odwołania')
    adult_attachments = MultipleFileField(
        'Załączniki (dorośli)', validators=[Optional()]
    )
    remove_adult_attachments = MultiCheckboxField(
        'Usuń załączniki (dorośli)',
        choices=[],
        coerce=str,
        validators=[Optional()],
    )
    minor_attachments = MultipleFileField(
        'Załączniki (nieletni)', validators=[Optional()]
    )
    remove_minor_attachments = MultiCheckboxField(
        'Usuń załączniki (nieletni)',
        choices=[],
        coerce=str,
        validators=[Optional()],
    )
    test_recipient = StringField(
        'Adres testowy', validators=[Optional(), Email(), Length(max=128)]
    )
    submit = SubmitField('Zapisz')
    send_test = SubmitField('Wyślij test')

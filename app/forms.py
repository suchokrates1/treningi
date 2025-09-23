from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    SelectField,
    PasswordField,
    RadioField,
)
from wtforms.fields.datetime import DateTimeLocalField
from flask_wtf.file import FileField, MultipleFileField
from wtforms.validators import (
    DataRequired,
    Length,
    Email,
    Optional,
    NumberRange,
    InputRequired,
)
from wtforms.fields import HiddenField, TelField
from wtforms import IntegerField
from wtforms.fields import DateField, TimeField
from wtforms import SelectMultipleField, widgets


class MultiCheckboxField(SelectMultipleField):
    """Render a set of checkboxes representing a multi-select field."""

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


class ScheduleForm(FlaskForm):
    days = MultiCheckboxField(
        'Dni tygodnia',
        choices=[
            ('0', 'Poniedziałek'),
            ('1', 'Wtorek'),
            ('2', 'Środa'),
            ('3', 'Czwartek'),
            ('4', 'Piątek'),
            ('5', 'Sobota'),
            ('6', 'Niedziela'),
        ],
        validators=[DataRequired(message='Wybierz co najmniej jeden dzień.')],
    )
    start_date = DateField(
        'Data początkowa',
        format='%Y-%m-%d',
        validators=[DataRequired()],
    )
    start_time = TimeField(
        'Godzina startu',
        format='%H:%M',
        validators=[DataRequired()],
    )
    interval_weeks = IntegerField(
        'Interwał (tygodnie)',
        default=1,
        validators=[DataRequired(), NumberRange(min=1, max=52)],
    )
    end_date = DateField(
        'Data końcowa',
        format='%Y-%m-%d',
        validators=[Optional()],
    )
    occurrences = IntegerField(
        'Liczba powtórzeń',
        validators=[Optional(), NumberRange(min=1, max=500)],
    )
    location_id = SelectField(
        'Miejsce', coerce=int, validators=[DataRequired()]
    )
    coach_id = SelectField(
        'Trener', coerce=int, validators=[DataRequired()]
    )
    max_volunteers = IntegerField(
        'Limit wolontariuszy',
        default=2,
        validators=[DataRequired(), NumberRange(min=1, max=20)],
    )
    preview = SubmitField('Podgląd')
    save = SubmitField('Zapisz harmonogram')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        if not self.end_date.data and not self.occurrences.data:
            message = 'Podaj datę końcową lub liczbę powtórzeń.'
            self.end_date.errors.append(message)
            self.occurrences.errors.append(message)
            return False

        if self.end_date.data and self.end_date.data < self.start_date.data:
            self.end_date.errors.append('Data końcowa musi być późniejsza od początkowej.')
            return False

        return True


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
    is_adult = RadioField(
        'Czy jesteś pełnoletni?',
        choices=[('true', 'Tak'), ('false', 'Nie')],
        coerce=lambda value: value == 'true',
        validators=[InputRequired()],
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
    test_recipient = StringField(
        'Adres testowy', validators=[Optional(), Email(), Length(max=128)]
    )
    registration_files_adult = MultipleFileField(
        'Załączniki - osoba pełnoletnia', validators=[Optional()]
    )
    registration_files_minor = MultipleFileField(
        'Załączniki - osoba niepełnoletnia', validators=[Optional()]
    )
    remove_adult_files = MultiCheckboxField(
        'Usuń załączniki (pełnoletni)', choices=[], validators=[Optional()]
    )
    remove_minor_files = MultiCheckboxField(
        'Usuń załączniki (niepełnoletni)', choices=[], validators=[Optional()]
    )
    submit = SubmitField('Zapisz')
    send_test = SubmitField('Wyślij test')

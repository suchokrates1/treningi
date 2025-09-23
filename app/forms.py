from datetime import timedelta

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    SelectField,
    PasswordField,
    RadioField,
    BooleanField,
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
    repeat = BooleanField('Powtarzaj')
    repeat_interval = IntegerField(
        'Odstęp (tygodnie)',
        default=1,
        validators=[Optional(), NumberRange(min=1, max=52)],
    )
    repeat_until = DateField(
        'Powtarzaj do',
        format='%Y-%m-%d',
        validators=[Optional()],
        render_kw={"placeholder": "rrrr-mm-dd"},
    )
    submit = SubmitField('Zapisz')

    def validate(self, extra_validators=None):
        is_valid = super().validate(extra_validators=extra_validators)

        if not is_valid:
            return False

        if self.repeat.data:
            repeat_ok = True

            if not self.repeat_interval.data:
                self.repeat_interval.errors.append(
                    'Podaj odstęp między treningami.'
                )
                repeat_ok = False

            if not self.repeat_until.data:
                self.repeat_until.errors.append('Podaj datę zakończenia powtórzeń.')
                repeat_ok = False
            elif self.date.data and self.repeat_until.data < self.date.data.date():
                self.repeat_until.errors.append(
                    'Data zakończenia musi być późniejsza niż początek.'
                )
                repeat_ok = False

            return repeat_ok

        return True

    def iter_occurrences(self):
        """Return a list of scheduled training datetimes based on the form."""

        if not self.date.data:
            return []

        occurrences = [self.date.data]

        if not (
            self.repeat.data
            and self.repeat_interval.data
            and self.repeat_interval.data > 0
            and self.repeat_until.data
        ):
            return occurrences

        interval = timedelta(weeks=self.repeat_interval.data)
        current = self.date.data

        while True:
            next_date = current + interval
            if next_date.date() > self.repeat_until.data:
                break
            occurrences.append(next_date)
            current = next_date

        return occurrences

    @property
    def occurrence_count(self):
        return len(self.iter_occurrences())


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


class ScheduleSeriesForm(FlaskForm):
    """Form for editing schedule series details."""

    time = TimeField('Godzina', format='%H:%M', validators=[InputRequired()])
    coach_id = SelectField('Trener', coerce=int, validators=[DataRequired()])
    location_id = SelectField('Miejsce', coerce=int, validators=[DataRequired()])
    max_volunteers = IntegerField(
        'Limit miejsc', validators=[DataRequired(), NumberRange(min=1, max=20)]
    )
    submit = SubmitField('Zapisz zmiany')


class ConfirmSeriesDeletionForm(FlaskForm):
    """Form requiring confirmation before deleting a series."""

    confirm = BooleanField('Potwierdzam usunięcie serii', validators=[DataRequired()])
    submit = SubmitField('Usuń serię')


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

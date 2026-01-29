from datetime import timedelta
import re
import html

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    SelectField,
    PasswordField,
    RadioField,
    BooleanField,
    ValidationError,
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
    Regexp,
)
from wtforms.fields import HiddenField, TelField
from wtforms import IntegerField
from wtforms.fields import DateField
from wtforms import SelectMultipleField, widgets


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    if not text:
        return text
    # Remove null bytes
    text = text.replace('\x00', '')
    # Escape HTML entities
    text = html.escape(text, quote=True)
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def validate_no_html(form, field):
    """Reject input containing HTML/script tags."""
    if field.data:
        # Check for potential HTML/script injection
        dangerous_patterns = [
            r'<[^>]*script',
            r'javascript:',
            r'on\w+\s*=',
            r'<[^>]*iframe',
            r'<[^>]*object',
            r'<[^>]*embed',
            r'<[^>]*form',
        ]
        text_lower = field.data.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, text_lower):
                raise ValidationError('Niedozwolone znaki w polu.')


def validate_polish_phone(form, field):
    """Walidator numeru telefonu (9 cyfr, opcjonalnie +48)."""
    import re
    phone = re.sub(r'[\s\-()]', '', field.data or '')
    if phone.startswith('+48'):
        phone = phone[3:]
    if not re.match(r'^\d{9}$', phone):
        raise ValidationError('Podaj poprawny numer telefonu (9 cyfr).')


def format_phone_number(phone):
    """Formatuje numer telefonu do postaci 000 000 000."""
    import re
    phone = re.sub(r'[\s\-()]', '', phone or '')
    if phone.startswith('+48'):
        phone = phone[3:]
    if len(phone) == 9:
        return f"{phone[:3]} {phone[3:6]} {phone[6:]}"
    return phone


class MultiCheckboxField(SelectMultipleField):
    """Render a set of checkboxes representing a multi-select field."""

    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class CoachForm(FlaskForm):
    first_name = StringField(
        'Imię', validators=[DataRequired(), Length(max=64), validate_no_html]
    )
    last_name = StringField(
        'Nazwisko', validators=[DataRequired(), Length(max=64), validate_no_html]
    )
    phone_number = TelField(
        'Telefon', validators=[DataRequired(), Length(max=20), validate_polish_phone]
    )
    submit = SubmitField('Zapisz')

    def validate(self, extra_validators=None):
        """Sanitize inputs before validation."""
        if self.first_name.data:
            self.first_name.data = sanitize_input(self.first_name.data)
        if self.last_name.data:
            self.last_name.data = sanitize_input(self.last_name.data)
        return super().validate(extra_validators=extra_validators)


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


class TrainingSeriesForm(FlaskForm):
    coach_id = SelectField(
        "Trener", coerce=int, validators=[DataRequired()]
    )
    location_id = SelectField(
        "Miejsce", coerce=int, validators=[DataRequired()]
    )
    max_volunteers = IntegerField(
        "Liczba miejsc",
        validators=[DataRequired(), NumberRange(min=1, max=20)],
    )
    submit = SubmitField("Zapisz")


class VolunteerForm(FlaskForm):
    first_name = StringField(
        'Imię', validators=[DataRequired(), Length(max=64), validate_no_html]
    )
    last_name = StringField(
        'Nazwisko', validators=[DataRequired(), Length(max=64), validate_no_html]
    )
    email = StringField(
        'Email', validators=[DataRequired(), Email(), Length(max=128)]
    )
    phone_number = TelField(
        'Telefon', validators=[DataRequired(), Length(max=20), validate_polish_phone]
    )

    def validate(self, extra_validators=None):
        """Sanitize inputs before validation."""
        # Sanitize text fields
        if self.first_name.data:
            self.first_name.data = sanitize_input(self.first_name.data)
        if self.last_name.data:
            self.last_name.data = sanitize_input(self.last_name.data)
        return super().validate(extra_validators=extra_validators)
    is_adult = RadioField(
        'Czy jesteś pełnoletni?',
        choices=[('true', 'Tak'), ('false', 'Nie')],
        coerce=lambda value: value == 'true',
        validators=[InputRequired()],
    )
    privacy_consent = BooleanField(
        'Zapoznałem/am się z <a href="https://widzimyinaczej.org.pl/polityka-prywatnosci/" '
        'target="_blank" rel="noopener noreferrer">polityką prywatności</a> '
        'i wyrażam zgodę na przetwarzanie moich danych osobowych w celu kontaktu '
        'związanego z wolontariatem.',
        validators=[DataRequired(message='Musisz wyrazić zgodę na przetwarzanie danych.')],
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

    name = StringField('Nazwa', validators=[DataRequired(), Length(max=128), validate_no_html])
    submit = SubmitField('Zapisz')

    def validate(self, extra_validators=None):
        """Sanitize inputs before validation."""
        if self.name.data:
            self.name.data = sanitize_input(self.name.data)
        return super().validate(extra_validators=extra_validators)


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
    phone_request_template = HiddenField('Szablon maila prośby o telefon')
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


class PhoneUpdateForm(FlaskForm):
    """Form for volunteers to update their phone number."""
    phone_number = TelField(
        'Numer telefonu',
        validators=[DataRequired(), Length(max=20), validate_polish_phone],
        render_kw={"placeholder": "np. 500 600 700", "class": "form-control form-control-lg"}
    )
    submit = SubmitField('Zapisz numer')

    def validate(self, extra_validators=None):
        """Sanitize and format phone number."""
        if self.phone_number.data:
            self.phone_number.data = sanitize_input(self.phone_number.data)
            self.phone_number.data = format_phone_number(self.phone_number.data)
        return super().validate(extra_validators=extra_validators)


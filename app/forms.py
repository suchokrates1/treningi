from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateTimeField, SelectField
from wtforms.validators import DataRequired, Length
from .models import Coach
from wtforms.fields import HiddenField

class CoachForm(FlaskForm):
    first_name = StringField('Imię', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Nazwisko', validators=[DataRequired(), Length(max=64)])
    phone_number = StringField('Telefon', validators=[DataRequired(), Length(max=20)])
    submit = SubmitField('Zapisz')

class TrainingForm(FlaskForm):
    date = DateTimeField('Data i godzina treningu', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    location = StringField('Miejsce', validators=[DataRequired(), Length(max=128)])
    coach_id = SelectField('Trener', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Dodaj trening')

class VolunteerForm(FlaskForm):
    first_name = StringField('Imię', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Nazwisko', validators=[DataRequired(), Length(max=64)])
    phone_number = StringField('Telefon', validators=[DataRequired(), Length(max=20)])
    training_id = HiddenField()  # ukryte pole – ID treningu
    submit = SubmitField('Zapisz się')

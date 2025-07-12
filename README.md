# Blind Tennis Training Sign-up

This project provides a simple web application for organizing blind tennis training sessions. It allows volunteers to register for upcoming trainings and includes an admin panel for managing coaches and session schedules.

## Features

- **Training schedule** – list upcoming trainings grouped by month.
- **Volunteer sign‑up** – each training accepts up to two volunteers; duplicate bookings are prevented.
- **Admin panel** – password‑protected dashboard to manage coaches and trainings.
- **Excel export** – administrators can download a spreadsheet with training data and volunteer contact details.
- **Dark mode** – a theme toggle available for convenience.

## Local setup

1. Create a virtual environment with Python 3.11 or newer and install the dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Set environment variables (see `.env` for an example). Required variables are:
   - `SECRET_KEY` – Flask secret key.
   - `ADMIN_PASSWORD` – password for the admin panel.
   Optional variables include `FLASK_ENV` and `FLASK_APP`.
3. Run the development server:
   ```bash
   flask run
   ```
   or
   ```bash
   python run.py
   ```
   The application will be available on `http://localhost:8000`.

### Docker

Alternatively, build and run with Docker:

```bash
docker build -t treningi .
docker run --env-file .env -p 8000:8000 treningi
```

You can also use `docker-compose up` which uses the provided `docker-compose.yml`.

## Admin login

The admin dashboard is accessible at `/admin/login`. Sign in using the password defined in the `ADMIN_PASSWORD` environment variable. Once logged in you can add or edit coaches, create trainings and export all data to Excel.


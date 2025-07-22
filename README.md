# Blind Tennis Training Sign-up

This project provides a simple web application for organizing blind tennis training sessions. It allows volunteers to register for upcoming trainings and includes an admin panel for managing coaches and session schedules.

## Features

- **Training schedule** – list upcoming trainings grouped by month.
- **Volunteer sign‑up** – each training accepts up to two volunteers; duplicate bookings are prevented. Volunteers register and cancel using their email address.
- **Admin panel** – password‑protected dashboard to manage coaches and trainings.
- **Excel export** – administrators can download a spreadsheet with training data and volunteer contact details.
- **Cancellation emails** – admins can mark a session as cancelled and all booked volunteers are notified via email.
- **Dark mode** – a theme toggle available for convenience.

## Requirements

- **Python** 3.11 or newer
- The packages listed in `requirements.txt`:
  - Flask
  - Flask-SQLAlchemy
  - Flask-WTF
  - WTForms
  - python-dotenv
  - openpyxl

### Environment variables

Create a `.env` file and define at least:
  - `SECRET_KEY` – Flask secret key.
  - `ADMIN_PASSWORD` – password for the admin panel.
  - `SMTP_HOST` – outgoing mail server.
  - `SMTP_USERNAME` and `SMTP_PASSWORD` – credentials for the server.
  - `SMTP_SENDER` – email address used for outgoing mail.
    The display name is configured in the admin panel.
  - `SMTP_ENCRYPTION` – `tls`, `ssl` or `none` to control the connection security.
Optional variables include `FLASK_ENV`, `FLASK_APP` and `LOG_LEVEL`.
`LOG_LEVEL` controls the verbosity of both the Flask logger and the
root Python logger. Valid values follow the standard Python logging
levels: `DEBUG`, `INFO`, `WARNING`, `ERROR` and `CRITICAL`. When this
variable is not defined Flask defaults to `WARNING`, which suppresses
informational messages. In a development environment
(`FLASK_ENV=development` or debug mode) Flask automatically switches to
`INFO`.

To see messages about sending emails and SMTP login, explicitly set
`LOG_LEVEL=INFO`. This enables the informational log lines describing
email delivery. When an email is sent you should see log entries like:

```text
INFO:app:Sending email via smtp.example.com:25 from Admin <noreply@example.com> to user@example.com
INFO:app:Email sent successfully
```

## Local setup

1. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and set your environment variables.
3. Run the development server:
   ```bash
   flask run
   ```
   or
   ```bash
   python run.py
   ```
   The application will be available on `http://localhost:8000`.

   Automatic migration only occurs when launching via `python run.py` or
   Docker. If you start the server with `flask run`, run `flask db upgrade`
   beforehand.

   The SQLite database resides in `app/instance/db.sqlite3`.

  Quill editor assets (version 2.0.3) are bundled in `static/vendor/quill` so they are served locally.

### Database migrations

Whenever you modify the models, generate and apply migrations:

```bash
flask db migrate -m "describe change"
flask db upgrade
```

The repository already includes a migration that adds an `email` column to the
`volunteers` table. Simply run `flask db upgrade` to apply it when you deploy
this version.

### Docker

Alternatively, build and run with Docker:

```bash
docker build -t treningi .
docker run --env-file .env -p 8000:8000 treningi
```

The container runs `python run.py`, so any pending migrations are upgraded
automatically when it starts.

You can also use `docker-compose up` which uses the provided `docker-compose.yml`.

### Troubleshooting

If `flask db upgrade` fails with an error like `table _alembic_tmp_volunteers already exists`,
the migration was interrupted and left a temporary table behind. Open
`app/instance/db.sqlite3` with any SQLite client and run:

```sql
DROP TABLE IF EXISTS _alembic_tmp_volunteers;
```

After dropping the table re-run the upgrade or start the application again.

## Admin login

The admin dashboard is accessible at `/admin/login`. Sign in using the password defined in the `ADMIN_PASSWORD` environment variable. Once logged in you can add or edit coaches, create trainings and export all data to Excel.

### Editing email templates

Visit `/admin/settings` to configure SMTP details, set the sender display name and edit the messages sent to volunteers. The WYSIWYG editor lets you insert variables such as `{first_name}`, `{last_name}`, `{training}`, `{cancel_link}`, `{date}` and `{location}`. Use the **Podgląd** button to preview a template with example data before saving. Clicking the button posts the current editor content to `/admin/settings/preview/<template>` so you can check the result without modifying the stored template.


# rosterizer

A simple tool for building curling teams based on data exported from Curling Club Manager. Intended features include attempting to balance player position requests and "plays with" requests against data regarding skill level and even past performance.

## Quick start

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # macOS / Linux
# .\venv\Scripts\activate     # Windows

# Install dependencies
pip install django mysqlclient beautifulsoup4 lxml pytest-django python-dotenv

# Apply database migrations
python manage.py migrate

# Create a superuser for the admin interface
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

Open http://127.0.0.1:8000 in your browser.

## Configuration

### Environment variables

Copy `.env.example` to `.env` in the project root and fill in your values:

```bash
cp .env.example .env
```

`.env` is gitignored; `.env.example` is checked in as a template.

| Variable | Description |
|---|---|
| `DJANGO_DEBUG` | Set to `True` for debug mode |
| `DJANGO_SECRET_KEY` | Required for production; generate with `python -c "import secrets; print(secrets.token_urlsafe(38))"` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated, e.g. `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated, e.g. `http://localhost:8000` |
| `DATABASE_ENGINE` | Database engine, e.g. `django.db.backends.mysql` |
| `DATABASE_NAME` | Database name (leave unset for SQLite) |
| `DATABASE_USER` | Database user |
| `DATABASE_PASSWORD` | Database password |
| `DATABASE_HOST` | Database host, e.g. `127.0.0.1` |
| `DATABASE_PORT` | Database port, e.g. `3306` |

By default (no `DATABASE_NAME` set), the project uses SQLite — a `db.sqlite3` file is created automatically in the project root. To use MySQL, set `DATABASE_NAME` and the related connection variables in your `.env`.

The database user needs permission to create databases in order for unit tests to work.

## Common commands

```bash
# Run database migrations
python manage.py migrate

# Create new migrations after model changes
python manage.py makemigrations

# Collect static files for production
python manage.py collectstatic

# Open the Django shell
python manage.py shell

# Create a superuser (admin login)
python manage.py createsuperuser

# Start the dev server
python manage.py runserver
```

The admin interface is available at `/admin/` (log in with the superuser credentials).

## Testing

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest -x           # Stop on first failure
pytest --pdb        # Drop into debugger on failure
```

Tests use a temporary SQLite database by default. All 35 tests create their own data — no pre-existing database is needed.

## Input file format

See `test_data/TestImport1.html` for a sample of the file output that Curling Club Manager produces. See `test_data/TestRosterCSVImport.csv` for a sample roster CSV import.

## URLs

| Path | Description |
|---|---|
| `/` | Home / index |
| `/sessions/` | List and manage sessions |
| `/players/` | List all players |
| `/rules/` | Manage player rules |
| `/session/<id>/teams/` | View teams for a session |
| `/admin/` | Django admin interface |
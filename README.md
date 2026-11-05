# rosterizer

A simple tool for building curling teams based on data exported from Curling Club Manager. Intended features include attempting to balance player position requests and "plays with" requests against data regarding skill level and even past performance.

## Quick start

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # macOS / Linux
# .\venv\Scripts\activate     # Windows

# Install dependencies (requirements.txt is the source of truth)
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create a superuser for the admin interface
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

Open http://127.0.0.1:8000 in your browser. Either `127.0.0.1:8000` or
`localhost:8000` works out of the box; both are in `DJANGO_ALLOWED_HOSTS`.

`requirements.txt` pins every version and is the authoritative dependency list
— including `gunicorn`, which `run.sh` needs and which an earlier version of
this file omitted. It uses the `mysql-connector-python` driver, which matches
`DATABASE_ENGINE` in `.env.example`. If you are only hacking on the code and do
not care about reproducibility, the unpinned equivalent is:

```bash
pip install django mysql-connector-python beautifulsoup4 lxml \
            python-dotenv pytest pytest-django gunicorn
```

## Configuration

### Environment variables

Copy `.env.example` to `.env` in the project root and fill in your values:

```bash
cp .env.example .env
```

`.env` is gitignored; `.env.example` is checked in as a template.

Every key in `.env` must be prefixed `DJANGO_` (or `DATABASE_`) and hold a
single line — `python-dotenv` cannot parse multi-line values, so a Python-style
list such as `CSRF_TRUSTED_ORIGINS = [...]` is silently dropped and the setting
falls back to its default.

| Variable | Description |
|---|---|
| `DJANGO_DEBUG` | Set to `True` for debug mode |
| `DJANGO_SECRET_KEY` | Required for production; generate with `python -c "import secrets; print(secrets.token_urlsafe(38))"` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated, no spaces, e.g. `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated, no spaces, e.g. `http://127.0.0.1:8000,http://localhost:8000` |
| `DATABASE_ENGINE` | Database engine, e.g. `mysql.connector.django` for MySQL |
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

Tests use a temporary SQLite database. All 207 tests create their own data — no
pre-existing database is needed.

One wrinkle: if your `.env` sets `DATABASE_NAME`, tests will try to use that
database instead and fail to connect. Force SQLite for a test run with:

```bash
DATABASE_NAME= pytest
```

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
| `/v2/sessions/<id>/generate/` | Roster Builder v2 configuration and generation |
| `/v2/sessions/<id>/review/` | Review and select a generated roster |
| `/v2/sessions/<id>/results/` | Enter wins/losses/ties for a session |
| `/admin/` | Django admin interface |

## Roster builder (v2)

The v2 roster builder is a second, independent way to build teams. It sits
alongside the original **Generate Teams** workflow, which still works exactly as
before — the two do not share code paths and neither replaces the other.

The v2 engine optimises team composition with a genetic algorithm rather than
the v1 greedy fill, and it factors in results from earlier sessions.

### What it optimises

Each candidate roster is scored on six criteria, shown individually so you can
see *why* a roster ranked where it did:

| Criterion | Meaning |
|---|---|
| Complete | Every registered player is placed |
| Position | Players are in their stated preferred positions |
| Variety | Fewer teammates repeated from earlier sessions |
| Play-with | Declared play-with partners share a team |
| Rules | `never_together` / `must_be_together` rules are respected |
| Balance | Team strength is even across teams |

Team strength is not raw experience. Each player gets an **ability** per
position from their past results, weighted so recent sessions count more, and
shrunk toward stated experience when there is little history. Positions are
then weighted by influence (Skip 1.00, Vice 0.85, Second 0.75, Lead 0.70), so a
player is worth what they contribute *at the position they actually play*.

### Entering results

Results make the balance criterion meaningful, and are entirely optional.

1. Build the teams for a past session.
2. Open **Enter Results** for that session and **commit** the roster. Committing
   records the current teams as that session's historical record, so
   regenerating teams later cannot change what a recorded result means.
3. Enter wins, losses and ties per team.

Recorded results are protected. Sessions and players referenced by results
cannot be deleted, and clearing a session's teams warns you first.

### Using the builder

From **Sessions**, choose **Roster Builder v2**. Set how many candidate rosters
to generate and press the button — generation runs in the browser with a
progress indicator. You then get one card per candidate, sorted best first,
with a colour-coded score per criterion (green 0.9+, amber 0.7+, red below).
Expand any card to see its teams and any constraints it does not satisfy, then
apply the one you want. Applying appends teams, leaving existing ones alone.

Play-with preferences, position preferences and player rules are always applied;
there is no toggle to disable them. Session variety influences ranking but is
not a requirement.

### Command line

```bash
# Generate and print candidate rosters with their scores
python manage.py generate_rosters_v2 --session-id 1 --candidates 5

# Reproduce a previous run exactly
python manage.py generate_rosters_v2 --session-id 1 --candidates 5 --seed 42
```

The command exits non-zero and explains the problem if the session data cannot
be used (for example a play-with reference to someone not registered, or a set
of players forced together that exceeds team size).

### Player substitution

When a registered player cannot play and a substitute is needed after teams are
already set, use the `substitute_player` command. It swaps the substitute into
every team position held by the outgoing player, updates the session
registration, and — if results are committed — updates the historical record
too. No need to clear teams and regenerate.

#### Workflow

The command runs as a dry-run first so you can confirm what will change before
anything is written. Always run without `--apply` first:

```bash
# Step 1 — preview
python manage.py substitute_player \
  --session-id 3 \
  --remove-player 42 \
  --add-player 99
```

The dry-run prints the session details, lists every PlayerSession, Team, and
TeamResult row that will be created or updated, and reminds you to add
`--apply`. If it looks correct, repeat with the flag:

```bash
# Step 2 — commit
python manage.py substitute_player \
  --session-id 3 \
  --remove-player 42 \
  --add-player 99 \
  --apply
```

Re-running after a successful substitution is safe — the command detects that
the swap is already done and exits cleanly.

#### Finding the IDs

Before you run the command, look up the session and player IDs:

```bash
# List every session by ID
python manage.py shell -c "
from rosterizer.models import Session
for s in Session.objects.all():
    print(f'{s.id}: {s}')
"

# Find a player by name fragment
python manage.py shell -c "
from rosterizer.models import Player
for p in Player.objects.filter(last_name__icontains='smith'):
    print(f'{p.id}: {p.full_name}')
"

# See every player registered in session 3
python manage.py shell -c "
from rosterizer.models import PlayerSession
for ps in PlayerSession.objects.filter(session_id=3).select_related('player'):
    print(f'  {ps.player.id}: {ps.player.full_name}')
"
```

#### Arguments

| Argument | Required | Description |
|---|---|---|
| `--session-id` | yes | Session to perform the substitution in |
| `--remove-player` | yes | Player ID to swap out |
| `--add-player` | yes | Player ID to swap in (must already exist in the database) |
| `--apply` | no | Commit the changes. Omit to preview only |

The substitute player does not need to be registered in the session beforehand —
the command creates the registration automatically. If they are already
registered, the existing registration is left alone.

The player being removed keeps their session registration. If you want to
deregister them, do it separately through the Django shell.

#### Production (Docker)

```bash
docker exec -it <container> python manage.py substitute_player \
  --session-id 3 --remove-player 42 --add-player 99 --apply
```
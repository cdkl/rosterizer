# Tasks

## 1. Core command

- [x] 1.1 Create `rosterizer/management/commands/substitute_player.py` with `--session-id`, `--remove-player`, `--add-player`, and `--apply` arguments, and verify `python manage.py substitute_player --help` prints usage
- [x] 1.2 Implement input validation that exits with `CommandError` when either player does not exist, and verify with `pytest` cases for missing players
- [x] 1.3 Implement input validation that exits with `CommandError` when the removed player is not registered in the session, and verify with a `pytest` case

## 2. Dry-run and apply logic

- [x] 2.1 Implement the dry-run path: query PlayerSession, Team, and TeamResult for the session, compute what would change, and print a summary without writing to the database. Verify with `pytest` cases that check the dry-run output matches expected counts
- [x] 2.2 Implement the apply path: create the substitute's PlayerSession if missing, swap the substitute into all Team positions held by the removed player, and swap TeamResult positions when results are committed. Verify with `pytest` cases that confirm the database state after apply
- [x] 2.3 Implement idempotency: re-running apply after a successful substitution detects no changes needed and exits cleanly. Verify with a `pytest` case

## 3. Edge cases

- [x] 3.1 Handle the case where the substitute is already registered in the session (skip PlayerSession creation). Verify with a `pytest` case
- [x] 3.2 Handle the case where the session has no teams (only PlayerSession is created/updated). Verify with a `pytest` case
- [x] 3.3 Handle the case where results are committed and the removed player appears in TeamResult rows. Verify with a `pytest` case that confirms TeamResult position fields are swapped
# Tasks

## 1. Model and migration

- [x] 1.1 Add `ConvenorPlayWith` model to `rosterizer/models.py` with session FK, two player FKs, and a `unique_together` constraint on `(session, player1, player2)`. Verify the model imports cleanly with `python manage.py check`.
- [x] 1.2 Create and apply the migration with `python manage.py makemigrations && python manage.py migrate`. Verify the new table exists in the database.
- [x] 1.3 Register `ConvenorPlayWith` in `rosterizer/admin.py`. Verify the model appears in the Django admin interface.

## 2. Build context integration

- [x] 2.1 In `build_context` (`rosterizer/roster_evaluation_v2.py`), query `ConvenorPlayWith.objects.filter(session_id=session_id)` and extract player pairs. Merge them into the `play_with_pairs` tuple before it is used for co-location group construction and stored on `LeagueContext`. Verify with a unit test that convenor pairs appear in `context.play_with_pairs`.
- [x] 2.2 Update the `co_location_edges` docstring to document convenor pairs as a third source. Verify the comment is accurate.

## 3. Validation

- [x] 3.1 Add a unit test verifying that `validate_session` rejects generation when convenor-declared pairs combine with player play-with declarations to form a group larger than team size. Verify the error message names the affected players.
- [x] 3.2 Add a unit test verifying that `validate_session` rejects generation when a convenor-declared pair spans a locked team (one player locked, one unassigned). Verify the error message names both players.

## 4. Scoring and violation reporting

- [x] 4.1 Add a unit test verifying that `evaluate_plays_with_adherence` penalises a split convenor-declared pair with the same multiplier (×0.5) as a split player-declared pair. Verify the score matches expected values.
- [x] 4.2 Add a unit test verifying that `collect_violations` reports an unsatisfied convenor-declared pair with the same structure (type, player_ids, team_indices, message) as a player-declared pair.

## 5. UI

- [x] 5.1 Add view logic in `rosterizer/views_v2.py` to list existing convenor pairs for the current session, add a new pair (two-player selection), and delete a pair. Verify the endpoints return correct HTTP status codes with a view test.
- [x] 5.2 Add a template section to the v2 generation page (`/v2/sessions/<id>/generate/`) that lists current convenor pairs with remove buttons and provides a form to add a new pair by selecting two players from a dropdown. Verify the section renders with `pytest rosterizer/test_views_v2.py`.
- [x] 5.3 Add URL routes for pair management (add, delete) in `rosterizer/urls.py`. Verify the routes resolve with Django's `resolve()`.

## 6. Integration

- [x] 6.1 Add an integration test that creates convenor pairs for a session, runs `generate_rosters_v2`, and asserts the paired players appear on the same team in every candidate. Verify with `pytest rosterizer/test_integration_v2.py`.
- [x] 6.2 Add an integration test that creates two overlapping convenor pairs (A,B) and (B,C) to express a trio, runs generation, and asserts all three players appear on the same team. Verify the test passes.
- [x] 6.3 Run the full test suite with `pytest` and verify all tests pass (including existing tests — no regressions).
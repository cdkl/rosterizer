# Tasks

## 1. Data model

- [ ] 1.1 Add `TeamResult` model to `models.py`: session FK (PROTECT), team_number, skip/vice/second/lead FKs to Player (PROTECT, nullable), wins/losses/ties (default 0), optional points_for/points_against, notes, `unique_together` on [session, team_number]. Verify with `python manage.py makemigrations` then `python manage.py migrate`
- [ ] 1.2 Add `results_committed` BooleanField (default False) to `Session` and generate the migration. Verify with `python manage.py migrate --check` reporting no pending changes
- [ ] 1.3 Register `TeamResult` in `admin.py`. Verify it appears in the Django admin with a list display showing session, team number, and record
- [ ] 1.4 Add tests confirming a second result for the same session and team number raises an integrity error, and that deleting a session referenced by a result is blocked. Verify with `pytest rosterizer/test_results_model.py`

## 2. Strength rating

- [ ] 2.1 Implement `experience_score(years_curled, k=4.0)` returning `1 - exp(-years/k)`, clamped to [0,1]. Verify with a test asserting the curve values at 0, 1, 2, 3, 5, 10, and 20 years, and asserting diminishing returns between 5–10 and 15–20
- [ ] 2.2 Implement session ordering and age: build the ordered session list by `(year, session_number)` and return a result's age as its index distance from the current session minus one. Verify with a test proving a Session 3 result from the previous year has greater age than a Session 2 result from the current year
- [ ] 2.3 Implement `median_games_per_session(session_id)` from recorded results, returning None when no results exist. Verify with tests for single session, multiple sessions, and the empty case
- [ ] 2.4 Implement `position_ability(player, position, context)` implementing the shrunk blend `(n·win_rate + m·experience_score)/(n + m)` where `m = 0.5 × median_games_per_session`, with time-decayed weights and ties counted as half a win. Verify with tests for zero history, sparse history, extensive history, and tie handling, plus a test proving the shrinkage strength is identical across two leagues that differ in games per session
- [ ] 2.5 Implement `build_player_abilities(session_id)` returning ability for every registered player at all four positions. Verify it returns a value for every player and position, all within [0,1]

## 3. Evaluation context

- [ ] 3.1 Define a frozen `LeagueContext` dataclass holding registered players, preferences, play-with pairs, player rules, historical team compositions per session, and precomputed abilities. Verify it is constructible from a test session
- [ ] 3.2 Implement `build_context(session_id)` issuing a fixed number of queries regardless of league size. Verify by asserting the query count does not grow when the number of players doubles
- [ ] 3.3 Rewrite every scoring function to take `context` instead of `session_id` and perform no database queries. Verify with `django_assert_num_queries(0)` around a full roster evaluation

## 4. Roster scoring

- [ ] 4.1 Implement `evaluate_completeness` and `evaluate_position_preference`. Verify with tests covering all players assigned, 1/2/3+ missing, first preference (1.0), second preference (0.5), no match (0.0)
- [ ] 4.2 Implement `evaluate_team_continuity` across three lookbacks with play-with exemption. Verify with tests covering each lookback, the exemption, and no prior history
- [ ] 4.3 Implement `evaluate_plays_with_adherence` and `evaluate_player_rules`. Verify with tests covering satisfied pairings, missing partners, never_together and must_be_together violations, and weight application
- [ ] 4.4 Implement `team_strength(team, context)` as the sum of position-weighted contributions, and `evaluate_team_balance` as the coefficient of variation of team strength. Verify with tests for perfectly balanced teams, imbalanced teams, and the no-results fallback
- [ ] 4.5 Implement `evaluate_roster` returning a weighted mean composite with each criterion clamped to a floor of 0.05, plus per-criterion scores and a list of constraint violations. Verify with tests that a perfect roster scores 1.0, that two differently-flawed rovers receive different scores, and that realistic scores stay spread enough to rank
- [ ] 4.6 Add tests proving the composite distinguishes rosters that a multiplicative composite would tie at zero. Verify with two rosters differing only in the number of criteria violated

## 5. Co-location grouping and validation

- [ ] 5.1 Implement play-with pairing as a symmetric matching: derive pairs from either direction, reject a player declared as partner by two different players. Verify with tests for one-directional declarations, mutual declarations, and conflicting declarations
- [ ] 5.2 Implement union-find over play-with edges and must-be-together rule edges to form co-location groups. Verify with tests for a plain pair, a pair merged by a rule, and a group exceeding team size
- [ ] 5.3 Implement `validate_session(session_id)` checking for conflicting play-with declarations, partners not registered in the session, and oversized co-location groups. Verify with tests covering each blocking condition and a clean session
- [ ] 5.4 Structure the grouping code to accept co-location edges as an input list rather than reading `play_with` directly, so additional modalities can contribute edges without changing grouping or validation. Verify by passing a synthetic edge list through the same code path

## 6. Team generation

- [ ] 6.1 Implement constructive initialization: place co-location groups as indivisible units, then fill remaining slots by position preference. Verify the output assigns every player exactly once and satisfies all hard constraints
- [ ] 6.2 Implement tournament selection and position-preserving mutation, verifying mutations keep every co-location group intact
- [ ] 6.3 Implement team-swap crossover that repairs conflicts by swapping whole groups rather than individual players. Verify children are valid rosters with no player appearing twice and no group split
- [ ] 6.4 Implement the GA main loop over the precomputed context with elitism, verifying scores improve across generations under a fixed seed
- [ ] 6.5 Implement `generate_rosters_v2(session_id, num_candidates, seed=None)` returning distinct candidates plus per-candidate scores and violations. Verify with tests for candidate count, distinctness, and reporting a reduced count when variety is exhausted
- [ ] 6.6 Add a benchmark test generating rosters for a 48-player session and asserting completion within the performance target

## 7. Results entry and deletion protection

- [ ] 7.1 Implement `commit_roster(session_id)` snapshotting the current teams into results-ready state and setting `results_committed`. Verify with a test that committing records the current composition
- [ ] 7.2 Implement the results entry view: GET renders one row per team with pre-filled values, POST upserts on [session, team_number]. Verify with tests for creating results, updating existing results, and re-submitting the same values
- [ ] 7.3 Implement `enter_results` template with a per-team row showing players and wins/losses/ties inputs. Verify it renders committed session data correctly
- [ ] 7.4 Guard the v1 `delete_session` and `clear_player_list` views against deleting sessions or players referenced by results, returning a clear message. Verify with tests that deletion is blocked and the response explains why
- [ ] 7.5 Guard the v1 `clear_teams` view with a warning when the session has results, proceeding on confirmation. Verify with tests for both the warning and the confirmed path

## 8. Web workflow

- [ ] 8.1 Vendor HTMX 2.x into the static directory and load it from `base.html`. Verify it is served locally and no external script host is referenced
- [ ] 8.2 Implement the generation view and template: candidate count input, results-coverage summary, `hx-post` submission, loading indicator, in-place result swap. Verify no full page reload occurs, the loading indicator appears during generation, and the coverage line correctly reports partial and absent results
- [ ] 8.3 Implement continuity scoring against live prior-session `Team` rows while results read frozen `TeamResult` snapshots, and verify the two diverge correctly: regenerating a prior session's teams changes continuity scores but leaves computed abilities unchanged. Verify with a test asserting both halves
- [ ] 8.4 Build `_roster_cards.html` rendering composite score, color-coded per-criterion indicators, and constraint violations. Verify the partial renders and indicator thresholds apply at the specified boundaries
- [ ] 8.5 Build `_team_detail.html` with the four-column team grid. Verify it renders when expanded via `hx-get`
- [ ] 8.6 Build `roster_review.html` composing the partials with per-card selection and an apply action. Verify cards render sorted by composite score descending
- [ ] 8.7 Add URL patterns and the session list entry point for the v2 builder and results entry, leaving v1 URLs untouched. Verify with a URL-routing test covering every new and existing pattern
- [ ] 8.8 Surface validation problems from `validate_session` in the generation view instead of generating. Verify with a test that a blocking problem returns an explanatory error and creates no candidates

## 9. CLI command

- [ ] 9.1 Implement `generate_rosters_v2` accepting `--session-id`, `--candidates`, and `--seed`. Verify with `python manage.py help generate_rosters_v2`
- [ ] 9.2 Wire the command to validate, generate, and print scores, team assignments, and violations per candidate. Verify with a command test asserting candidate count in the output
- [ ] 9.3 Verify the command reports validation problems and exits non-zero without generating. Verify with a command test against an invalid session

## 10. Integration and documentation

- [ ] 10.1 Run the full workflow end-to-end: seed a prior session with committed teams and results, generate rosters for the current session, confirm balance uses the recorded results, review and apply a roster, and confirm the new teams persist
- [ ] 10.2 Run the existing test suite with `pytest` and confirm no regressions
- [ ] 10.3 Update README.md with results entry, the new CLI command, the v2 UI entry point, and a note that v1 remains available
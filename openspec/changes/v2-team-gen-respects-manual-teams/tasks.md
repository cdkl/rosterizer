# Tasks

## 1. Context: split locked vs available players

- [x] 1.1 In `build_context`, query current-session `Team` rows once and derive the set of already-placed player ids. Verify with `django_assert_num_queries` that query count stays flat compared to the pre-change count
- [x] 1.2 Add `locked_player_ids`, `locked_team_count`, and an available-only `registered_player_ids` to `LeagueContext`, with `team_count` computed from available players. Verify by constructing a context for a session with 2 locked teams (8 players) and 22 unassigned players and asserting `team_count == 6` and `len(registered_player_ids) == 22`
- [x] 1.3 Compute `mean_contribution` over the available pool only. Verify with a test that placement cost balances new teams against each other when locked players are present
- [x] 1.4 Add `test_context_locked_split.py` covering: no locked teams (behaviour unchanged), some locked, and all locked (`team_count == 0`)

## 2. Validation: reject spanning constraints

- [x] 2.1 In `validate_session`, detect a play-with pair or `must_be_together` group with one member locked and one available, and a group whose locked members sit on different teams, raising `ValidationProblem`. Verify with tests for the play-with-spanning case and the split-locked-group case
- [x] 2.2 Accept the benign case where a pairing is entirely inside a locked team. Verify `validate_session` returns a context with no problem and the group is dropped from generation
- [x] 2.3 Accept a session with locked teams but no spanning constraints. Verify generation proceeds and produces candidate rosters

## 3. Generation behaviour

- [x] 3.1 Ensure `initialise_roster` and the GA cover only available players with no operator changes, and confirm a generated roster never contains a locked player. Verify with an integration test that locks 2 teams and asserts no locked player id appears in any candidate
- [x] 3.2 Define the `team_count == 0` path: `generate_rosters_v2` returns an empty candidate list with `shortfall` set rather than raising. Verify with a test that a fully-placed session returns zero candidates

## 4. Scoring scope

- [x] 4.1 Verify `evaluate_completeness` scores locked players as satisfied, returning 1.0 when all available players are placed even while locked players exist. Verify with a fixture mixing locked and unassigned players
- [x] 4.2 Verify `evaluate_team_balance` ignores locked teams and still yields a valid score in [0.0, 1.0]. Verify with a test that balance reflects only generated teams

## 5. UI reporting

- [x] 5.1 Add a helper computing locked-team count and unassigned count for a session and show it on the generation form. Verify the template renders "2 teams already created" and "22 players remain" for the standard fixture
- [x] 5.2 Render the spanning-conflict message and affected players on the generation form when `validate_session` raises. Verify the template shows the conflict and does not render candidate cards
- [x] 5.3 Handle the fully-placed session with a friendly "no players remain to assign" message instead of a blank review page. Verify the response contains that message

## 6. CLI reporting

- [x] 6.1 Report locked-team and unassigned counts from `generate_rosters_v2`. Verify the command output includes the counts for a session with locked teams
- [x] 6.2 Report a spanning conflict and exit non-zero without generating. Verify with a command test against the conflict fixture
- [x] 6.3 Report the no-unassigned-players state and exit cleanly. Verify with a command test on a fully-placed session

## 7. Integration and regression

- [x] 7.1 Run the full pre-existing suite with `pytest` and confirm no regressions (including the original 35 v1 tests and the existing v2 tests)
- [x] 7.2 Run `openspec validate v2-team-gen-respects-manual-teams --strict` and `python manage.py check` and confirm both pass

## 8. Scope player rules to session players

- [x] 8.1 In `build_context`, load only `PlayerRule` rows whose both players are registered in the session, so out-of-session rules never enter grouping, validation, or scoring
- [x] 8.2 Remove the `validate_session` check that reports a player rule referencing an unregistered player as a blocking problem
- [x] 8.3 Add tests that a `never_together` rule referencing an unregistered player does not block generation and is not enforced, and that an in-session rule is still enforced

## 9. Scope play-with reporting to the generated pool

- [x] 9.1 In `evaluate_plays_with_adherence`, ignore play-with pairs that are not fully within the unassigned pool, so locked pairings do not penalise generated teams
- [x] 9.2 In `collect_violations`, ignore play-with pairs involving a locked player and report each unsatisfied unassigned pair once for the roster instead of once per team
- [x] 9.3 Add tests that a play-with pair satisfied inside a locked team is not reported and yields full adherence, and that a split unassigned pair is reported exactly once
# Tasks

## 1. Update position influence weights

- [x] 1.1 Change `POSITION_INFLUENCE` values in `position_strength.py` to `{Skip: 0.38, Vice: 0.27, Second: 0.20, Lead: 0.15}` and add `THREE_PLAYER_INFLUENCE_SUM = 0.85` constant. Verify `contribution()` returns the new values by testing `contribution(ability=1.0, 'Skip') == 0.38`.
- [x] 1.2 Add a `contribution_rescaled(ability, position)` helper that divides by `THREE_PLAYER_INFLUENCE_SUM` for 3-player teams. Verify with a unit test that Skip on a 3-player team contributes `0.38/0.85 ≈ 0.447`.
- [x] 1.3 Update `assign_positions` in `team_generation_v2.py` to use rescaled weights when computing `_assignment_strength` for 3-player teams. Verify by generating a 10-player league and checking the 3-player team's strength uses rescaled weights.

## 2. Add .500 ability backfill for sparse data

- [x] 2.1 Modify `position_ability` in `position_strength.py` to compute `missing = max(0, prior_games − weighted_games)` and add `missing × 0.5` to the numerator and `missing` to the denominator. Verify with a unit test that a player with zero observed games and 20 years experience returns `(0.5 + 0.993) / 2 = 0.746` instead of 0.993.
- [x] 2.2 Add test `test_ability_backfill_zero_games` verifying the backfill formula for a player with no observations at a position. Verify the test passes.
- [x] 2.3 Add test `test_ability_backfill_sparse_data` verifying a player with 1.7 weighted games (below the 3.5 prior) gets a proportional adjustment. Verify the test passes.
- [x] 2.4 Add test `test_ability_backfill_established_player_unchanged` verifying a player with weighted games above the prior (e.g., 16.6 games) is unchanged from the current formula. Verify the test passes.
- [x] 2.5 Add test `test_ability_backfill_novice_rates_at_floor` verifying a 0-year player with no observations returns 0.25. Verify the test passes.

## 3. Update GA heuristics that reference positional contribution

- [x] 3.1 Verify `_max_contribution` and `_placement_cost` in `team_generation_v2.py` automatically pick up the new weights (they call `context.abilities.player_contribution()` which reads `POSITION_INFLUENCE`). Run `test_initialise_places_every_player_once` and confirm it passes.
- [x] 3.2 Verify `_team_strength` (both in `team_generation_v2.py` and `roster_evaluation_v2.py`) and `team_strength` (in `position_strength.py`) return correctly scaled values. Run `test_team_strength_sums_contributions` and confirm it passes.

## 4. Update tests

- [x] 4.1 Update `test_position_strength.py` tests that reference specific influence values: `test_influence_descends_from_skip_to_lead`, `test_same_ability_worth_more_at_higher_influence_position`, `test_promotion_priced_against_ability_loss`, `test_team_strength_sums_contributions`, `test_team_strength_skips_empty_positions`. Verify all pass with `python -m pytest rosterizer/test_position_strength.py -v`.
- [x] 4.2 Update `test_roster_evaluation_v2.py` tests that reference specific balance or contribution values: `test_balance_perfect_when_teams_equivalent`, `test_balance_reflects_positional_influence`. Verify all pass.
- [x] 4.3 Run `test_team_generation_v2.py` and verify all balance-related tests pass: `test_ga_improves_or_matches_initial_score`, `test_position_optimizer_balance_tiebreak`, `test_twelve_team_league_generates_within_time_budget`. Verify all pass.
- [x] 4.4 Add test `test_three_player_team_uses_rescaled_weights` verifying that a 3-player team's contributions use weights that sum to 1.0. Verify the test passes.

## 5. Integration verification

- [x] 5.1 Run the full test suite with `python -m pytest rosterizer/ -v` and verify all tests pass.
- [x] 5.2 Generate rosters for Session 26 and verify: (a) team strengths are on the 0–1 scale, (b) unknown players rate at `(0.5 + exp)/2`, (c) established players with sufficient data are unchanged.
- [x] 5.3 Verify the per-player contribution badges in the UI display correctly scaled values on the 0–1 range.
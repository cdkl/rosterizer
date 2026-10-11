# Tasks

## 1. Position assignment optimizer

- [x] 1.1 Implement `assign_positions(membership_team, context, running_mean)` that enumerates all valid position assignments for a team's members, keeps those achieving the maximum `(first_pref_count, second_pref_count)` tuple, and returns the one whose contribution sum best maintains balance against the running mean. Verify by calling on the Session 26 Team 1 membership `{Jane, Tom, Curtis, Ainsley}` and asserting Jane gets Second (her first preference) and Tom gets Skip (his first preference).
- [x] 1.2 Add `assign_roster_positions(membership_roster, context)` that iterates teams in order, calls `assign_positions` per team, updates the running mean, and returns the positioned list-of-dicts. Verify with a 2-team test roster where the second team's assignment compensates for the first team's strength.
- [x] 1.3 Add a position-assignment cache keyed by `frozenset(member_ids)` cleared per GA run, and verify via `_cache_hits` counter that repeated team compositions hit the cache during a `run_ga` call.

## 2. Membership-only GA chromosome

- [x] 2.1 Replace `initialise_roster` to produce a list of `frozenset` (one per team) of player ids. Place co-location groups first (largest first), then individuals (most-constrained first), into teams with enough capacity, respecting never-together against existing occupants. Verify via `assert_valid_roster_membership` that every player appears exactly once, groups stay intact, and never-together pairs land on different teams.
- [x] 2.2 Replace `mutate` to swap two players between randomly chosen teams (or one player and an empty slot on a 3-player team) at membership level, validating group integrity and never-together after the swap. Verify with a 2-team 8-player setup that a swap leaving groups intact passes and a swap splitting a group is rejected.
- [x] 2.3 Replace `crossover` to take a prefix of teams from one parent and suffix from the other, operating on membership frozensets. Verify that the child contains every player exactly once after repair, and play-with pairs are never split.
- [x] 2.4 Replace `repair` to remove duplicate players (keeping first occurrence) and re-place missing players (and their co-location groups) into available slots, respecting never-together. Verify with the existing duplicate/missing test patterns adapted for membership shape.

## 3. Evaluation integration

- [x] 3.1 Add `evaluate_membership_roster(membership_roster, context)` that calls `assign_roster_positions` then delegates to the existing `evaluate_roster`. Verify the composite score matches calling `evaluate_roster` with a manually positioned equivalent of the same membership.
- [x] 3.2 Update `run_ga` to accept and evaluate membership rosters using `evaluate_membership_roster`. Verify `test_ga_improves_or_matches_initial_score` and `test_ga_is_deterministic_for_a_seed` pass with the new representation.

## 4. Candidate diversity selection

- [x] 4.1 Implement `select_diverse_candidates(scored_population, num_wanted, lambda_penalty, min_difference)` that greedily selects roster N maximising `composite_score − λ × max(Jaccard_co_team_pairs_to_already_chosen)`, skipping any roster whose max similarity to already-chosen exceeds `1.0 − min_difference`. Verify on Session 26 that 10 candidates have pairwise co-team Jaccard ≤ 0.85 (i.e., at least 15% different).
- [x] 4.2 Integrate `select_diverse_candidates` into `generate_rosters_v2` after `run_ga`. Verify `test_generate_candidates_are_distinct` still passes and `test_generate_reports_shortfall_when_variety_exhausted` correctly reports shortfall under diversity constraints.

## 5. Test updates and new coverage

- [x] 5.1 Update all existing `test_team_generation_v2.py` tests that reference the positioned-roster representation (`initialise_roster`, `mutate`, `crossover`, `repair`, `run_ga`, `generate_rosters_v2` helpers) to work with the membership shape. Verify the full test file passes with `python -m pytest rosterizer/test_team_generation_v2.py -v`.
- [x] 5.2 Add test `test_position_optimizer_maximises_first_preferences` with a 4-player team where two members share Skip as first preference, asserting both get Skip/Second rather than one falling back arbitrarily. Verify the test passes.
- [x] 5.3 Add test `test_position_optimizer_balance_tiebreak` with two 2-player teams of equal composition where only balance distinguishes assignments. Verify the balanced assignment is chosen over the unbalanced one.
- [x] 5.4 Add test `test_candidates_differ_in_composition` on a 12-player league verifying the 6 returned candidates have pairwise co-team Jaccard similarity below a measured threshold. Verify the test passes.
- [x] 5.5 Add test `test_three_player_team_leaves_lead_empty` with a 10-player session (3 teams, one with 3 players) and verify the 3-player team's Lead position is None and all other positions are filled. Verify the test passes.

## 6. Integration verification

- [x] 6.1 Run the full test suite with `python -m pytest rosterizer/ -v` and verify all tests pass.
- [x] 6.2 Run the CLI command `./venv/bin/python manage.py generate_rosters_v2 --session-id 26 --candidates 10 --seed 1` and verify Jane Smith is assigned Second or Lead (not Skip) in every candidate, and the position_preference score is ≥ 0.75.
- [x] 6.3 Verify the 12-team performance budget test still passes with `python -m pytest rosterizer/test_team_generation_v2.py::test_twelve_team_league_generates_within_time_budget -v`.
- [x] 6.4 Verify that `python -m pytest rosterizer/test_roster_evaluation_v2.py -v` and `python -m pytest rosterizer/test_integration_v2.py -v` pass unchanged (scoring and integration contracts preserved).
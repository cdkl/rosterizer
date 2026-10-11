# Tasks

## 1. Extend scoring engine with per-team and per-player detail

- [x] 1.1 Add `evaluate_roster` output extension: compute a `details` dict with per-team criterion scores (plays-with, rules, continuity per lookback, team strength) and per-player stats (years curled, ability at assigned position, contribution). Verify with a unit test that the new `details` key is present and contains the correct number of teams and players.
- [x] 1.2 Extend `collect_violations` to return structured violation data alongside human-readable strings: each violation dict includes `type`, `player_ids`, and `team_indices`. Verify with a unit test that a split play-with pair produces a structured violation with both player IDs and team indices.
- [x] 1.3 Verify existing evaluation tests still pass with `python -m pytest rosterizer/test_roster_evaluation_v2.py -v`.

## 2. Pass detail data through views and session storage

- [x] 2.1 Update `roster_review` view to store the full evaluation result (including `details`) per candidate when calling `evaluate_roster`. Verify the stored session data includes `details` keys.
- [x] 2.2 Update `generate_rosters` view to store the full evaluation result (including `details`) in the session. Verify the stored data includes `details` after generation.
- [x] 2.3 Update `team_detail` view to read the candidate's `details` and pass them to the template along with a player-name lookup map. Verify the view context includes `details` and `player_names`.

## 3. Rewrite team detail template

- [x] 3.1 Rewrite `_team_detail.html` to display per-team scoring badges (plays-with, rules, continuity) alongside the player table using small coloured `<span>` badges. Verify the rendered HTML includes score values for each team.
- [x] 3.2 Add per-player stats section below the team table showing each player's years curled, ability rating, and contribution value in a compact `<dl>` or table row. Verify all 4 players per team have stats rendered.
- [x] 3.3 Add violation highlight rows below affected teams showing the specific players involved (using the structured violation data) and a brief explanation. Verify a test roster with a split play-with pair renders the affected players' names next to their teams.
- [x] 3.4 Add continuity detail notes below teams that share prior-session teammates, naming the players and which session they shared. Verify a team with prior overlap renders the player names and session identifier.

## 4. Update tests

- [x] 4.1 Update `test_workflow_v2.py` tests for team detail (`test_team_detail_fragment_lists_players`) to verify the new template renders scoring badges, player stats, and violation details. Verify the test passes.
- [x] 4.2 Add test `test_team_detail_shows_per_player_stats` that verifies the team detail HTML contains years curled, ability, and contribution for each player. Verify the test passes.
- [x] 4.3 Add test `test_team_detail_shows_violation_players` that generates a roster with a deliberately split play-with pair and verifies the team detail HTML names the affected players. Verify the test passes.
- [x] 4.4 Add test `test_evaluation_detail_has_structured_violations` verifying the `details` dict from `evaluate_roster` includes structured violation data with player IDs and team indices. Verify the test passes.

## 5. Integration verification

- [x] 5.1 Run the full test suite with `python -m pytest rosterizer/ -v` and verify all tests pass.
- [x] 5.2 Generate rosters for Session 26 via the CLI and verify the evaluation output includes `details` with per-team and per-player data by inspecting the returned dict programmatically.
- [x] 5.3 Manually verify in the browser that expanding a candidate card shows per-team scoring badges, per-player stats, and any violation details with named players.
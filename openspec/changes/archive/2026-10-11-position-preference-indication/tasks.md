# Tasks

## 1. Extend evaluation detail output

- [x] 1.1 Add `preference_fit`, `preferred_position1`, and `preferred_position2` to each entry in `details.players` in `evaluate_roster`. Verify by running `test_evaluation_detail_has_structured_violations` and checking the new fields are present.
- [x] 1.2 Verify all existing evaluation tests still pass: `python -m pytest rosterizer/test_roster_evaluation_v2.py -v`.

## 2. Thread preference data through the view

- [x] 2.1 In `team_detail`, add `pref_fit` to each `player_cells` entry in `team_summaries` for the main table indicator. Add `preferred_position1`, `preferred_position2`, and `preference_fit` to each entry in `team_player_stats` for the expandable section. Verify the view context includes the new fields.
- [x] 2.2 Verify existing workflow tests pass: `python -m pytest rosterizer/test_workflow_v2.py -v -k "team_detail"`.

## 3. Update template

- [x] 3.1 Add a preference indicator token (`1st`/`2nd`/`—`) as a small colored badge in each player cell of the main roster table, between the name and the contribution badge. Verify the rendered HTML contains the indicator for each player.
- [x] 3.2 Add "Preference" and "Fulfilled" columns to the "Player experience & ability" expandable section showing the stated preference pair and whether it was met. Verify the rendered HTML contains preference information.

## 4. Update tests

- [x] 4.1 Update `test_team_detail_shows_scoring_badges` to also verify preference indicators are present in the rendered HTML. Verify the test passes.
- [x] 4.2 Update `test_team_detail_shows_per_player_stats` to verify the preference columns in the expandable section. Verify the test passes.
- [x] 4.3 Run the full relevant suite: `python -m pytest rosterizer/test_workflow_v2.py rosterizer/test_roster_evaluation_v2.py -v` and verify all tests pass.
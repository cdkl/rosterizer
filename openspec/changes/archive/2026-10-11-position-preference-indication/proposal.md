# Proposal

## Why

The team detail panel shows per-team scoring badges, player contribution values, and player experience stats — but gives no indication of whether each player is in their preferred position. The convenor knows the roster's aggregate `position_preference` score (e.g., 0.89), but cannot see which individual players got their first choice, second choice, or neither. When a high-scoring roster still places a player at their second-preference position, the convenor has no way to discover that without memorising the original player list.

## What Changes

- **Preference fulfillment indicators in the team roster table**: Each player name in the team table gains a compact, color-coded indicator showing whether they received their first preference, second preference, or neither.
- **Preference detail in the expandable stats section**: The "Player experience & ability" panel adds each player's stated preferences and whether they were fulfilled, so the convenor can see the complete picture when digging into a candidate.
- **Evaluation detail extended**: The `details.players` output from `evaluate_roster` gains `preference_fit`, `preferred_position1`, and `preferred_position2` fields — data the scoring engine already computes but does not currently expose.

## Capabilities

### Modified Capabilities
- `roster-workflow`: "Review candidate rosters with score breakdown" — the team detail panel now includes per-player preference fulfillment indicators.

## Impact

- **`roster_evaluation_v2.py`**: `evaluate_roster` adds three fields to each entry in `details.players`: `preference_fit` (1.0, 0.5, or 0.0), `preferred_position1`, `preferred_position2`.
- **`views_v2.py`**: `team_detail` threads the new fields into both the `team_summaries.player_cells` (for the main table indicator) and `team_player_stats` (for the expandable section).
- **`_team_detail.html`**: Main roster table gains a preference indicator column/badge. Expandable stats section gains preference columns.
- **Tests**: `test_workflow_v2.py` — existing team detail tests updated to verify preference indicators render. `test_roster_evaluation_v2.py` — existing evaluation detail test updated to verify new fields.
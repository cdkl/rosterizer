# Proposal

## Why

The v2 roster review page shows a composite score badge, six color-coded criterion bars, and a table of player names by position — but none of these explain *why* a team scored the way it did. When the play-with score is low, the convenor cannot see which pairs were split. When a team is unbalanced, there is no indication of which players are carrying or dragging the team. The convenor needs per-team and per-player scoring transparency to make an informed roster selection from the candidates.

## What Changes

- **Per-team scoring breakdown in the team detail panel**: When expanding a candidate card to view teams, each team row now includes its individual criterion scores (continuity, play-with adherence, rules, and contribution to balance) alongside the player names, so the convenor can see which teams are strong or weak on which dimensions.
- **Player-level ability and contribution data**: Each player shown in the team detail includes their stated experience (years curled), their ability rating at their assigned position (0-1), and their contribution to the team's positional strength, so the convenor can see how experience and past results shape team composition.
- **Named play-with and rule violations**: When a candidate has unsatisfied play-with pairs or violated player rules, the team detail names the specific players involved and the teams they ended up on, instead of just showing a generic violation string. The affected players are highlighted in the team table.
- **Per-team continuity reporting**: For teams with returning teammates from prior sessions, the detail shows which players played together before and in which session, explaining a low continuity score.
- **Structured evaluation detail in the scoring engine**: The `evaluate_roster` function gains a new `details` section in its output containing per-team criterion data and per-player ability breakdowns, computed once and reused by the UI without additional queries.

## Capabilities

### Modified Capabilities
- `roster-workflow`: The "Review candidate rosters with score breakdown" requirement expands the team detail panel to include per-team criterion scores, per-player ability information, and named violation details instead of just a table of player names.
- `roster-evaluation`: A new requirement is added for the scoring engine to produce per-team and per-player scoring detail as structured data alongside the existing aggregate scores and violation strings.

## Impact

- **`roster_evaluation_v2.py`**: `evaluate_roster` gains a `details` key in its return dict with per-team criterion breakdowns and per-player ability/contribution data. The `collect_violations` function is extended to return structured violation data (player IDs, team indices) alongside human-readable strings.
- **`views_v2.py`**: `team_detail` view passes the expanded evaluation data (from the stored candidates) to the template.
- **`_team_detail.html`**: Rewritten from a simple player table to a richer layout including per-team scoring, per-player stats, and violation highlights.
- **`_roster_cards.html` / `roster_review.html`**: Minor updates to pass evaluation detail data through to the team detail endpoint.
- **Tests**: `test_workflow_v2.py` — new tests for team detail rendering with scoring breakdown; `test_roster_evaluation_v2.py` — new tests for structured evaluation detail output.
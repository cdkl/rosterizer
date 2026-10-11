# Design

## Context

The v2 roster review page (`roster_review.html` and `_roster_cards.html`) renders each candidate as a card with a composite score badge, six color-coded criterion progress bars, and an expandable team detail panel. The team detail (`_team_detail.html`) is loaded via HTMX and currently shows only a table of player names by position — no scores, no ability data, no violation context.

The scoring engine (`roster_evaluation_v2.py`) already computes per-team scores internally (each criterion function returns per-team values that are averaged into the aggregate). The per-team data and per-player ability data exist but are discarded before the result reaches the template.

The `LeagueContext.abilities` (an `AbilityTable` instance) already precomputes every player's ability and contribution at every position. It is available in the review view but not passed through to the team detail endpoint.

See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Surface per-team criterion scores in the team detail panel
- Show each player's experience, assigned-position ability, and contribution
- Name the specific players involved in each violation, with their team numbers
- Identify which prior-session teammates are causing a continuity penalty
- Keep the existing card layout and HTMX loading pattern intact
- No additional database queries — all data comes from the evaluation output or the cached `LeagueContext`

**Non-Goals:**
- Changing the scoring criteria or weights
- Real-time editing of team assignments from the review page
- Adding charts or visualisations beyond color-coded text/numbers
- Changing the review page's overall card layout

## Decisions

### Decision 1: Extend `evaluate_roster` output, not a separate pass

**Choice**: Add a `details` key to the dict returned by `evaluate_roster` containing per-team criterion breakdowns, per-player stats, and structured violation data. Compute it during the same pass that computes criteria and violations.

**Rationale**: The per-team data is already computed inside the criterion functions. Collecting and returning it costs O(1) memory and no additional computation. A separate evaluation pass would add complexity and risk inconsistency if the roster was somehow modified between calls.

**Details**: The `details` dict has this shape:

```python
{
    'teams': [
        {
            'plays_with': float,       # this team's plays-with score
            'player_rules': float,     # this team's rules score
            'continuity': [float, …],  # per-lookback continuity scores
            'strength': float,         # team positional strength
        },
        …
    ],
    'players': [
        {
            'position': str,
            'years_curled': int,
            'ability': float,
            'contribution': float,
        },
        …
    ],
    'structured_violations': [
        {
            'type': 'split_pair' | 'never_together' | 'must_be_together',
            'player_ids': [int, …],
            'team_indices': [int, …],
            'message': str,  # human-readable, reused from existing violations
        },
        …
    ],
}
```

### Decision 2: Team detail receives precomputed data via the candidate dict

**Choice**: Expand the candidate objects stored in the Django session to include the `details` dict from evaluation. The `team_detail` view reads the candidate at the requested index and passes `details` to the template, along with a player name lookup.

**Rationale**: The review view already calls `evaluate_roster` on each stored roster (line 248-249 of `views_v2.py`). Storing the `details` along with the existing criteria/violations/roster keys means the team detail endpoint has everything it needs without re-evaluating or hitting the database again.

### Decision 3: Template structure — stacked sections within the team table

**Choice**: The expanded team detail panel renders as a set of stacked `<section>` elements within each team row:

1. **Team scoring row**: A compact summary below each team's player names showing that team's plays-with, rules, and continuity scores as small coloured badges.
2. **Player stats overlay**: Each player name is a small `<span>` with a `title` tooltip showing their years curled, ability at their position, and contribution value. For a more accessible view, an additional row below the team table lists per-player stats in a compact `<dl>`.
3. **Violations alert**: If a team has violations, an amber `<div>` below that team's row names the affected players and explains the issue.
4. **Continuity detail**: When a team shares prior-session teammates, a note below the team row names which players and which session.

**Rationale**: Stacking within the team row keeps the relationship between a team and its scores visually obvious. It also lets the HTMX partial replace just the team detail area without touching the card header. The tooltip + optional detail row pattern gives the convenor a quick glance (hover) and a fuller view (scroll) without cluttering the main table.

**Alternatives considered**:
- *Separate "details" tab per candidate*: More complex UI state; the user already has a mental model of "click to expand → see teams."
- *Modal/popover per player*: JS dependency; fragile on mobile.
- *Dedicated "scoring breakdown" page*: Extra navigation step; the convenor wants to compare candidates quickly.

### Decision 4: Structured violations reuse existing `collect_violations` logic

**Choice**: Extend `collect_violations` to return both the existing list of human-readable strings AND a parallel list of structured dicts with player IDs and team indices. The human-readable strings continue to render in the card's violation alert; the structured data feeds the team detail template.

**Rationale**: The violation strings are already computed with sufficient information to extract player IDs and team indices. Rather than duplicating the logic, the function is extended to capture the structured data during the same pass.

## Risks / Trade-offs

- **[Risk] Team detail payload size**: A 9-team roster with 36 players and per-player stats roughly doubles the HTML fragment size from ~2KB to ~5KB. For 10 candidates this is still well within HTMX norms.
  → Mitigation: The fragment is loaded on-demand per candidate, not all at once.
- **[Risk] Player names in violation messages may not match the display**: Violation strings use player IDs internally; the template resolves them to names using the same lookup the team table uses.
- **[Trade-off] Tooltip for ability information on mobile**: Hover tooltips don't work on touch devices.
  → Mitigation: The detail row below the table provides the same information in a touch-accessible format.

## Migration Plan

1. Extend `evaluate_roster` output with the `details` key.
2. Extend `collect_violations` to return structured data alongside strings.
3. Update `team_detail` view to pass `details` and a name map to the template.
4. Rewrite `_team_detail.html` with the new sections.
5. Update `roster_review` and `generate_rosters` views to store the full evaluation data including `details` in the session.
6. Add tests for the new evaluation output and the enhanced team detail template.
7. No database migration, no new dependencies, no URL changes.

## Open Questions

- Whether the per-player stats row should be collapsible or always visible. Default: always visible, since it adds value without clutter.
- Whether continuity detail should name the prior session explicitly (e.g., "2025 Session 2") or just say "previous session." Default: use session year and number from `context.session_ages`.
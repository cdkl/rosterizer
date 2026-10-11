# Design

## Context

The team detail fragment (`_team_detail.html`) shows player names with contribution badges, per-team scoring badges (plays-with, rules, continuity), team strength, and an expandable "Player experience & ability" section. The scoring engine already computes position preference fit via `context.prefers(player_id, position)` (1.0 first / 0.5 second / 0.0 other, 1.0 when no preference stated), and the player's stated preferences are available in `context.preference_by_player`. Neither is currently exposed to the template.

See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Show, per player, whether they got their first, second, or no preference
- Surface the stated preference pair for full transparency
- Keep the change data-driven with no new queries

**Non-Goals:**
- Changing position preference scoring logic
- Changing the GA's preference maximisation
- Adding preference indicators to the roster-level card header (only the team detail)

## Decisions

### Decision 1: Add three fields to `details.players`

**Choice**: In `evaluate_roster`, extend each entry in the `player_details` list with:

- `preference_fit`: `context.prefers(player_id, position)` — 1.0, 0.5, or 0.0.
- `preferred_position1`: the player's first stated preference (or empty string).
- `preferred_position2`: the player's second stated preference (or empty string).

**Rationale**: All three values are already computed or available in `LeagueContext`. No new queries. Adding them to the details dict makes them flow through the same path as ability and contribution.

### Decision 2: Preference indicator in the main roster table

**Choice**: In the team roster table, each player cell gains a compact text indicator after the name and before the contribution badge. The indicator text is `1st`, `2nd`, or `—` (for neither/no preference). Use the existing `score_class` colour mapping applied to a small badge.

**Rationale**: The main table is glanceable. A single short token (`1st`/`2nd`/`—`) tells the convenor at a glance whether the roster is preference-optimal, without clutter. The full detail lives in the expandable section.

### Decision 3: Preference detail in the expandable stats section

**Choice**: The "Player experience & ability" section gains a "Preference" column showing the stated pair (e.g., `Skip / Vice`) plus a mark showing fulfillment (`1st`, `2nd`, or `none`).

**Rationale**: The expandable section already shows per-player details grouped by team. Adding the stated preferences here gives the convenor the complete picture — what the player wanted vs. what they got — without crowding the main table.

## Risks / Trade-offs

- **[Risk] Indicator overload in the main table**: Adding a token to every cell could clutter the already dense table.
  → Mitigation: The token is a single short word in a small badge; the contribution badge stays on the same line. Full preference detail remains in the expandable section.
- **[Trade-off] "No preference" vs "neither" ambiguity**: A player with no stated preference is currently scored as 1.0 (unconstrained). Displaying `—` for both "no preference" and "did not get preference" conflates the two.
  → Mitigation: The expandable section shows the stated preferences explicitly, so `—` in the main table reads as "not a first or second choice" and the detail disambiguates "none stated" vs "neither fulfilled".

## Migration Plan

1. Extend `player_details` in `evaluate_roster` with the three new fields.
2. In `team_detail`, thread the new fields into `team_summaries.player_cells` and `team_player_stats`.
3. Update `_team_detail.html` with the indicator token and the preference column.
4. Update existing tests and add coverage for the new fields and rendering.
5. No database migration, no URL changes, no new dependencies.
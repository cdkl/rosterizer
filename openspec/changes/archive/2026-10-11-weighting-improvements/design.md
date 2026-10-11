# Design

## Context

Current issues in `position_strength.py`:

**Position influence** uses ordinal weights — Skip 1.00, Vice 0.85, Second 0.75, Lead 0.70. These encode "Skip matters most" without measured magnitudes. Team strength ranges 0–3.3.

**Ability fallback** (line 170-171 of `position_ability`) returns pure `experience_score` when `weighted_games <= 0`. A 20-year veteran with no Skip history rates 0.993 — above the league's best proven Skip (0.869). A returning player with old decayed data (Alex Morgan, 1.7 weighted games) rates 0.765 — near his experience score because decayed observations can't overcome the 3.5-game experience prior.

See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Replace ordinal influence weights with convenor-specified percentages (38/27/20/15)
- Rescale 3-player team weights proportionally
- Replace pure-experience ability fallback with .500 backfill for sparse data
- Established players with sufficient data are unchanged

**Non-Goals:**
- Cross-position inference (ability at one position inferring ability at another)
- Changing position preference logic, play-with, or player-rules scoring

## Decisions

### Decision 1: Direct weight replacement in `POSITION_INFLUENCE`

**Choice**: Change the dict values to `{Skip: 0.38, Vice: 0.27, Second: 0.20, Lead: 0.15}`. For 3-player teams, compute rescaled weights as `weight / 0.85` (the sum of Skip+Vice+Second).

**Rationale**: Sums to 1.0 for 4-player teams — a team of ability-1.0 players has strength 1.0. 3-player rescaling keeps strengths comparable across team sizes. Every consumer picks up the new weights automatically.

### Decision 2: `.500 backfill` for sparse data

**Choice**: Modify `position_ability` to fill the gap between observed games and the shrinkage prior with .500 performance rather than pure experience:

```
missing = max(0, prior_games − weighted_games)
ability = (weighted_wins + missing × 0.5 + prior_games × experience)
        / (weighted_games + missing + prior_games)
```

When `weighted_games ≥ prior_games`, `missing = 0` and the formula is identical to today.

**Rationale**: The shrinkage prior `m` (3.5 games, half a session) already represents "how much we trust the data." When data is insufficient, the gap between actual data and the trust threshold should default to .500 — the league average — not to the player's stated experience. This produces:

| Scenario | weighted_games | Before | After |
|---|---|---|---|
| 20yr unknown Skip | 0.0 | 0.993 | **0.746** |
| 8yr unknown Skip | 0.0 | 0.865 | **0.683** |
| 0yr novice | 0.0 | 0.00 | **0.250** |
| Alex Morgan (returning) | 1.7 | 0.765 | **0.703** |
| Sam Rivera (established) | 16.6 | 0.750 | 0.750 |


### Decision 3: No cross-position inference

**Choice**: The `.500 backfill` combined with the experience score is the only mechanism linking ability across positions. A player with no data at a position gets `(0.5 + exp)/2` regardless of their performance at other positions.

**Rationale**: The experience score already provides a position-independent baseline — a 15-year curler gets 0.976 experience everywhere. The backfill blends this with .500 to produce a reasonable default (0.738). Adding a position-to-position transfer matrix would require 16 made-up parameters with no data to validate them. The right time is after results data shows systematic over/under-performance.

### Decision 4: No change to balance scoring formula

**Choice**: `evaluate_team_balance` still uses `1.0 − CV`. No change needed.

**Rationale**: CV is scale-invariant.

## Risks / Trade-offs

- **[Risk] GA finds different optima**: New weights and backfill-adjusted abilities change the fitness landscape.
  → Mitigation: Intended behavior. The GA searches the new landscape.
- **[Risk] Backfill may rate some returning players too low**: A player who left the league and returned may have real-world development not captured.
  → Mitigation: Experience score provides a floor. A 20-year veteran never rates below `(0.5 + 0.993)/2 = 0.746` at any position.

## Migration Plan

1. Change `POSITION_INFLUENCE` and add `THREE_PLAYER_INFLUENCE_SUM`.
2. Modify `position_ability` to add the `.500` backfill term.
3. Update all affected tests with new expected values.
4. No database migration, no template change.
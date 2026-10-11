# Proposal

## Why

Two separate flaws in the current scoring system produce incorrect player ratings:

**Position influence** uses ordinal weights (Skip 1.00, Vice 0.85, Second 0.75, Lead 0.70) that encode only "Skip matters most" without reflecting the actual distribution of impact. The convenor has specified percentages — 38/27/20/15 — derived from the principle that higher positions are supersets of lower positions: a strong skip would make a very good lead, but a lead's ability to swing games is inherently capped by the position's influence.

**Ability calculation** falls back entirely to stated experience when a player has no observed games at a position. A 20-year veteran who has never played Skip gets rated 0.993 — above the league's best Skip (0.869). An 8-year unknown Skip rates 0.865 — also above the best proven Skip. Players with old, decayed data (Alex Morgan, 1.7 weighted games at Skip across sessions 6+ sessions ago) are rated 0.765 — near their experience score, because decayed observations can't overcome the experience prior. The common thread: sparse or absent data defaults to experience, which overrates veterans at positions they've never proven themselves in.

## What Changes

### Part 1: Position influence rescaling
- **Replace ordinal weights with explicit percentages**: `POSITION_INFLUENCE` changes from `{Skip: 1.00, Vice: 0.85, Second: 0.75, Lead: 0.70}` to `{Skip: 0.38, Vice: 0.27, Second: 0.20, Lead: 0.15}`.
- **Proportional rescaling for 3-player teams**: Skip/Vice/Second rescaled to sum to 1.0 (Skip: 0.447, Vice: 0.318, Second: 0.235).
- **Team strength on 0–1 scale**: Balance scoring via coefficient of variation is scale-invariant and unaffected.

### Part 2: Ability backfill for sparse data
- **Replace pure-experience fallback with .500 backfill**: When a player has less observed data at a position than the shrinkage prior (`weighted_games < prior_games`), the gap is filled with .500 performance rather than pure experience. Formula:
  ```
  missing = max(0, prior_games − weighted_games)
  ability = (weighted_wins + missing × 0.5 + prior_games × expectation)
          / (weighted_games + missing + prior_games)
  ```
  When `weighted_games ≥ prior_games`, `missing = 0` and the formula is **identical to today**.
- **Effect**: Unknowns rate `(0.5 + expectation) / 2` (e.g., 20-year unknown Skip drops from 0.993 to 0.746). Returning players with sparse old data get proportional adjustment (e.g., Alex Morgan drops from 0.765 to 0.703). Established players with sufficient data are **unchanged**.
- **No cross-position inference**: The backfill + experience score is the only cross-position mechanism. A novice with 0 years curls rates 0.25 at every position (0.5 blended with 0.0 experience). The position influence weights then differentiate contribution.

## Capabilities

### Modified Capabilities
- `team-generation`: "Balance teams by positional strength" — positional influence weights updated to explicit percentages; 3-player team rescaling added.
- `roster-evaluation`: "Evaluate team balance by positional strength" — influence weights updated to percentage values; ability fallback for sparse data replaced with .500 backfill.

## Impact

- **`position_strength.py`**: `POSITION_INFLUENCE` values changed; `position_ability` function modified to add `.500` backfill for weighted_games < prior_games.
- **`team_generation_v2.py`**: `assign_positions` balance tie-break picks up new weights and backfill-driven abilities automatically via `context.abilities.player_contribution()`.
- **`roster_evaluation_v2.py`**: Balance scoring reads new weights; ability table provides backfill-adjusted abilities.
- **Tests**: `test_position_strength.py` — influence and ability tests updated with new expected values. `test_roster_evaluation_v2.py` — balance and contribution tests updated. `test_team_generation_v2.py` — balance score thresholds may shift.
- **UI**: Contribution badges display on 0–1 scale; player ability numbers reflect .500 backfill for unproven positions.
# Proposal

## Why

The v2 team generation engine produces rosters where a player's position is permanently frozen at initialisation — the genetic algorithm can only swap players between teams at the same position, never move a player to a different position. This causes a co-location group (play-with pair) with mismatched preferences to lock one member into the wrong slot in every candidate: Ingrid Kebbel-Beer wants Second/Lead but is placed at Skip in all 10 generated candidates because her partner (Bob Beer, wants Skip) sorts first. The `position_preference` criterion achieves only 2 distinct values across the entire 100-individual GA population, confirming the engine has effectively no gradient on this criterion. Additionally, the 10 returned candidates share 80%+ of their co-team player pairs — they are near-clones with trivial swaps, not meaningfully distinct alternatives.

## What Changes

- **Decouple team membership from position assignment**: The GA chromosome will represent only which players are on each team (membership), not which position each holds. A deterministic position-assignment step runs inside each evaluation, assigning every team's members to positions to maximise stated preferences as a near-hard constraint, with balance as a tie-breaker.
- **Make position preferences near-hard**: First-preference assignment is treated as a requirement the system must satisfy whenever a per-team assignment exists that achieves it. Only when first preferences are infeasible does the system fall back to second preferences. This elevates the "first preference whenever possible" language in the spec from aspirational to enforceable.
- **Explicit candidate diversity**: After the GA converges, candidates are selected greedily by `composite_score − λ × max_similarity_to_already_chosen`, with a minimum-difference floor. This guarantees the returned rosters differ meaningfully in team composition, not just in incidental position swaps.
- **Position optimizer with caching**: The per-team assignment enumerates ≤24 valid configurations and picks the lexicographically best (max first-prefs, then max second-prefs, then best balance contribution). Cached by team-membership key for performance across repeated evaluations.

## Capabilities

### Modified Capabilities
- `team-generation`: The "Honor position preferences" requirement is strengthened to near-hard: the system SHALL maximise first-preference assignments per team before considering second preferences. The "Generate multiple candidate rosters" requirement adds an explicit diversity guarantee: candidates SHALL differ meaningfully in team composition, not merely in incidental swaps. The generation algorithm's internal representation changes to a membership-only chromosome with deterministic position assignment, but the external contract (positioned roster output) is unchanged.

## Impact

- **`team_generation_v2.py`**: Representation changes throughout — `initialise_roster` builds membership-only teams, `mutate` swaps players between teams regardless of position, `crossover`/`repair` operate on membership, `run_ga` calls a wrapper that assigns positions before scoring. Group-anchor/slot-assignment code is removed and replaced with the deterministic position optimizer.
- **`roster_evaluation_v2.py`**: `evaluate_roster` gets a membership-aware variant that runs the position optimizer before evaluating criteria. Individual criterion functions are unchanged; only the entry point gains a pre-processing step.
- **Tests**: `test_team_generation_v2.py` — membership-shape updates to existing initialise/mutate/crossover/repair tests, new tests for position optimizer correctness, near-hard preference enforcement, and candidate diversity selection. Other test files unchanged.
- **Views, CLI, `apply_roster`, locked-team handling**: Unaffected — output remains the positioned list-of-dicts.
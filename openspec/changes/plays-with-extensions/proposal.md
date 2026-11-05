# Proposal

## Why

Play-with declarations come only from players and are limited to a single partner. The convenor frequently needs to add pairings that players didn't declare — assigning themselves with a new club member, accommodating an exceptional trio request — without creating permanent PlayerRules or fully locking a manual team. Today the only workaround is editing imported player data or pre-creating teams, both of which constrain the GA more than necessary.

## What Changes

- Add a `ConvenorPlayWith` model that stores session-scoped player pairs declared by the convenor
- Feed those pairs into the existing co-location pipeline alongside player-declared play-with pairs and must-be-together rules, so the GA treats them identically
- A trio (three players together) is expressed as two or three overlapping pairs; union-find merges them into one co-location group automatically
- Provide a UI on the session page for the convenor to add and remove these pairs
- Scoring and violation reporting treat convenor pairs the same as player-declared pairs — they contribute to the plays-with adherence criterion and appear in violations when unsatisfied

## Capabilities

### New Capabilities
- `convenor-play-with`: The convenor can declare session-scoped play-with pairs that feed into team generation alongside player-declared pairs. Pairs combine via union-find, enabling groups larger than two players when overlapping pairs are declared.

### Modified Capabilities
- `team-generation`: The co-location edge pipeline now accepts convenor-declared pairs as a third source alongside player-declared play-with and must-be-together rules. The "Honor play-with pairings" requirement extends to cover these pairs.
- `roster-workflow`: The generation UI provides controls for the convenor to add, review, and remove convenor play-with pairs before starting generation.

## Impact

- **New model**: `ConvenorPlayWith` (session FK, two player FKs, unique together)
- **Affected code**: `build_context` (one new query, edge injection), `co_location_edges` (third source parameter), session generation view and template (UI for pair management)
- **No changes to**: GA operators, position optimizer, scoring functions, results tracking, PlayerRules, v1 team generation
- **Database**: one new table, one migration
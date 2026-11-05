# Proposal

## Why

A convenor occasionally needs to swap one registered player for another after rosters are generated—for example, when an expected player drops out and a substitute is available. Today there is no supported way to do this: the convenor must either clear all teams and regenerate, or manually manipulate the database. A management command gives the convenor a safe, auditable, one-step substitution without touching the database directly.

## What Changes

- New Django management command `substitute_player` that accepts a session, the player to remove, and the player to add.
- The command registers the substitute in the session (creating a `PlayerSession`) and optionally deregisters the removed player.
- If teams exist for the session, the command swaps the substitute into every team position currently held by the removed player.
- If results have been committed, the command applies the same swap to `TeamResult` rows so the historical record stays accurate.
- The command is read-only by default (`--dry-run`) and requires an explicit `--apply` flag to commit changes, protecting against accidents.

## Capabilities

### New Capabilities
- `player-substitution`: Replace one registered player with another in a session, propagating the swap to teams and committed results.

### Modified Capabilities
<!-- None — this is a new administrative operation that does not alter existing spec-level behavior. -->

## Impact

- Affected code: new file `rosterizer/management/commands/substitute_player.py`
- No model, view, or URL changes
- No dependency changes
- No breaking changes
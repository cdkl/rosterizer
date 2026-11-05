# Design

## Context

The project already has three management commands (`import_players`, `import_roster`, `generate_rosters_v2`) following the standard Django `BaseCommand` pattern with `add_arguments` and `handle`. All use `--session-id` for session targeting. The data model links players to sessions via `PlayerSession`, and teams reference players directly via foreign keys on `Team.skip`, `Team.vice`, `Team.second`, `Team.lead`. `TeamResult` stores an independent copy of the same four position fields for historical durability.

## Goals / Non-Goals

**Goals:**
- A CLI-only tool for one-off player substitutions in a session
- Safe by default: dry-run mode shows what will change before committing
- Covers the full data footprint: PlayerSession, Team, and TeamResult

**Non-Goals:**
- No web UI for substitutions
- No bulk substitution (one pair at a time)
- No automatic deregistration of the removed player (the convenor decides separately)
- No position-aware swap (the substitute fills the exact same position slots)

## Decisions

### Decision 1: Management command over Django admin action

A management command fits the existing pattern (`generate_rosters_v2`, `import_roster`) and is easier to run in production via `docker exec` or SSH than registering new admin models. It also keeps the change self-contained—one new file, no URL or template changes.

**Alternatives considered:**
- Django admin action: requires registering `PlayerSession` and `Team` in admin, adding custom actions, and testing the admin UI. More code, more surface area, no clear benefit for a tool used a handful of times per season.
- Shell script calling Django ORM: fragile, no validation, no dry-run.

### Decision 2: Dry-run by default with `--apply` flag

The command prints planned changes without modifying the database unless `--apply` is passed. This mirrors tools like `makemigrations` vs `migrate` and prevents accidents. The dry-run output lists each affected row by model and ID.

**Alternative considered:** Require `--dry-run` and make apply the default. Rejected because the cost of an accidental substitution (scrambling team composition) outweighs the convenience of fewer keystrokes.

### Decision 3: Position field swap via dynamic attribute access

The four position fields (`skip`, `vice`, `second`, `lead`) are identical in shape on both `Team` and `TeamResult`. The command iterates over the field names with `getattr`/`setattr` rather than repeating the same logic four times. This keeps the code compact and guarantees consistency between Team and TeamResult updates.

### Decision 4: Leave removed player's PlayerSession intact

The command does not delete the removed player's `PlayerSession`. The convenor may want to keep the registration for record-keeping, or the player may return. Removing the registration would also remove the player from the generation pool on the next regenerate—a side effect the command shouldn't assume is desired.

## Risks / Trade-offs

- **Risk:** The command updates Team rows in-place without notifying the convenor that regenerating rosters will overwrite those manual edits. → **Mitigation:** The dry-run output is explicit about which teams are modified. The command is for emergency substitutions after teams are set; the convenor should not regenerate after applying a substitution.
- **Risk:** If the removed player appears in multiple position slots on the same team (data anomaly), both get swapped. → **Mitigation:** This is correct behavior for a true substitution; duplicates indicate bad data the convenor should fix separately.
- **Risk:** `TeamResult` rows use `on_delete=models.PROTECT` for player FKs, so the removed player cannot be deleted after substitution if they appear in results. → **Mitigation:** This is existing behavior and unrelated to the substitution command. The command swaps the FK values; the old player ID simply becomes unreferenced.
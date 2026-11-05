# Design

## Context

See proposal.md for motivation. The key architectural constraint is that the co-location pipeline (`co_location_edges` → `build_co_location_groups` → GA operators) already accepts edges from multiple sources and was designed for extension. The docstring on `co_location_edges` reads: *"Taking them as an input list rather than reading the models directly is what lets a future play-with modality contribute edges without changing grouping, validation, or the genetic operators."*

The existing sources are:
- Player-declared play-with pairs (from `PlayerSession.play_with`, resolved by `resolve_play_with_pairs`)
- Must-be-together rules (from `PlayerRule`)

Both produce pairwise edges. Union-find merges connected edges into co-location groups. The GA treats groups as atomic units — mutation, crossover, repair, and initialisation all respect group integrity.

## Goals / Non-Goals

**Goals:**
- Let the convenor declare session-scoped pairs that the GA treats identically to player-declared pairs
- Support trios (3-person groups) via overlapping pairs + union-find, with no new group-size logic
- Integrate into existing validation, scoring, and violation reporting with minimal code change

**Non-Goals:**
- Position locking within groups (use manual teams for that)
- Ad-hoc never-together overrides (PlayerRules already cover permanent never-together)
- Soft/weighted convenor pairs (these are hard co-location constraints, same as play-with)
- Changing the scoring or diversity selection algorithms

## Decisions

### Decision 1: Store convenor pairs as a new model, not as extended play-with fields

**Chosen**: New `ConvenorPlayWith` model with session FK and two player FKs.

**Alternatives considered**:
- **Extend `PlayerSession.play_with`** to accept multiple partners. Rejected because `play_with` is a single free-text name resolved by `resolve_play_with_pairs`, which enforces a one-partner invariant. Changing it would require rearchitecting the resolution logic and would not distinguish player intent from convenor overrides.
- **Reuse `PlayerRule` with session scope**. Rejected because PlayerRules are permanent and apply across all sessions. Mixing session-scoped and permanent constraints in one table would complicate filtering, validation, and deletion semantics.
- **JSON field on Session**. Rejected because it would hide the data from queries, migrations, and the admin interface.

### Decision 2: Feed convenor pairs as edges into co_location_edges, not as pre-built groups

**Chosen**: Convert each convenor pair to a tuple edge and append to the existing edge list in `co_location_edges`.

**Rationale**: This is the extension point the pipeline was designed for. Union-find naturally merges overlapping pairs into larger groups — a trio expressed as (A,B) and (B,C) becomes {A,B,C} with zero new code. No changes to `build_co_location_groups`, validation, or GA operators.

**Alternatives considered**:
- **Build groups separately and merge**. Rejected as more complex and less testable. Union-find is already correct for merging edges from different sources.

### Decision 3: Score convenor pairs under the existing plays_with_adherence criterion

**Chosen**: Convenor pairs flow through `evaluate_plays_with_adherence` and `collect_violations` with the same logic as player-declared pairs. No new criterion.

**Rationale**: A split convenor pair is the same outcome as a split player pair — two people who should be together are apart. A separate criterion would add a column to the review cards for a violation type that should be rare (the GA enforces these as hard co-location groups).

### Decision 4: UI on the generation page, not the session management page

**Chosen**: Add convenor pair management to the v2 generation page (`/v2/sessions/<id>/generate/`), where the convenor already configures and triggers generation.

**Rationale**: The convenor declares these pairs as part of the generation workflow. Showing them alongside the candidate count and locked-team summary keeps the workflow linear. A separate management page would add navigation friction.

## Risks / Trade-offs

- **Union-find merging can surprise**: If the convenor adds (A,B) and (B,C) intending two separate pairs with a shared player, union-find merges them into a trio. In practice this is the desired behavior — it's how trios are intentionally created. The UI should label the pairs list clearly so the convenor sees what they've added.
- **No symmetry enforcement at model level**: The model stores ordered (player1, player2). The UI must normalise order or query both directions. Mitigation: the `build_context` query fetches all pairs for the session and converts to unordered edges, so direction doesn't matter at query time.

## Migration Plan

1. Create migration for `ConvenorPlayWith` table
2. Deploy — no data migration needed (new optional table, no existing data to convert)
3. Rollback: remove the migration, revert code changes. No data loss risk since convenor pairs are advisory constraints, not persistent records like TeamResult.

## Open Questions

None. All design decisions are resolved.
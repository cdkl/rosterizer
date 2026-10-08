# Design

## Context

See proposal.md — Why. The v2 engine lives in `roster_evaluation_v2.py` (builds a frozen `LeagueContext`, scores rosters), `team_generation_v2.py` (initialises, mutates, crosses over, and runs the GA over a roster of `{position: player_session_id}` dicts), and `views_v2.py` (generation workflow plus `apply_roster`). Today `build_context` reads every `PlayerSession` for the session and never looks at the session's `Team` rows, so the GA always produces a full roster for all registered players and `apply_roster` appends duplicates of anyone already placed.

## Goals / Non-Goals

**Goals:**
- Exclude players already on a session's teams from the generated roster, matching v1
- Detect and reject, as blocking validation, a play-with or `must_be_together` relation that spans a locked team
- Report locked-team count and unassigned count to the convenor (UI and CLI)
- Do all of this without changing the GA representation or operators

**Non-Goals:**
- Rebalancing, modifying, or filling locked teams (they are fixed, including empty positions)
- Validating or correcting `never_together` violations that occur wholly inside a locked team
- A new "regenerate from scratch" toggle — starting over stays `clear_teams` first, then generate

## Decisions

### Decision 1: Locked teams are handled at context build, not inside the GA

**Choice**: Compute the set of already-placed players in `build_context` and make the generated roster cover only the unassigned remainder. The GA never sees locked teams as part of its representation.

**Rationale**: The generated roster is a list of new-team dicts. If locked teams are excluded from the player pool up front, every existing GA operator (mutation, crossover, repair, balance placement cost) works unchanged — there are no locked slots for them to corrupt, so no operator needs a "frozen" case. This also mirrors v1 exactly, which removes already-placed players from its `player_sessions` list and only generates additional teams.

**Alternatives considered**:
- *Pre-seed a combined roster with locked teams and mark immutable indices*: requires every operator to skip frozen indices, is error-prone (crossover splits at team boundaries), and complicates repair.
- *Generate full rosters but filter at apply time*: duplicates the problem at generation time — the GA would optimise around players it then drops, wasting fitness pressure and producing degenerate candidates when many players are locked.

### Decision 2: Context carries an available pool and the locked map

**Choice**: `build_context` queries current-session `Team` rows once, derives:
- `locked_team_numbers`: count of existing teams
- `locked_player_ids`: the set of player pks already placed
- `available_player_ids`: registered players minus locked
- `team_count`: `team_count_for(len(available_player_ids))`

The existing `registered_player_ids` field is repurposed for the available pool so completeness, position-preference, balance, and the placement heuristic all operate on the unassigned set without further changes. `mean_contribution` is computed over the available pool so the placement cost balances new teams against each other.

**Rationale**: One place (context build) carries the locked/available distinction; the ~20 downstream read sites keep working unchanged because they already key off `registered_player_ids`. Query count stays flat — one extra `Team` query is added, contrary to nothing in the current fixed-count guarantee being violated.

### Decision 3: Spanning co-location conflicts are blocking

**Choice**: After `build_co_location_groups` runs over the (already registered-wide) play-with and must-together edges, `validate_session` checks each group's members against the locked map. A group is a conflict if it contains both locked and available players, or if its locked members are spread across different existing teams. Both cases raise `ValidationProblem`.

**Rationale**: v2's existing contract is "structural problems are rejected before generation, never silently broken." A play-with pair split by locking is exactly the kind of unsatisfiable constraint that would otherwise surface mid-GA as an unexplained invalid roster. Locked play-with partners already on the same team is the benign case and passes.

**How it composes with grouping**: groups that are entirely locked (all members on one existing team) are simply dropped from the generation grouping; groups entirely available are generated as before. Only the mixed case fails.

### Decision 4: "Nothing left to generate" is a defined, non-error state

**Choice**: When `team_count` is zero, generation returns an empty candidate list and the view / CLI report "no players remain to assign" rather than raising.

**Rationale**: A session where the convenor has already manually placed everyone is valid, not broken. The UI already has an empty-results path for the no-roster redirect; extending it with an explicit message avoids a confusing blank review screen.

### Decision 5: Player rules are scoped to the session's registered players

**Choice**: `build_context` loads only `PlayerRule` rows whose two players are both registered in the session (`player1_id__in` / `player2_id__in` the session's player ids). Rules touching an unregistered player are dropped before grouping, validation, and scoring; `validate_session` no longer reports them.

**Rationale**: A rule exists to prevent a situation between players. If either player is not in this session, the situation cannot arise, so the rule is irrelevant. The previous behaviour loaded every rule globally and refused to generate when any referenced a non-session player, which made unrelated league-wide rules block an otherwise valid session.

**Alternatives considered**:
- *Keep loading all rules but skip unregistered ones during validation*: leaves phantom pairs in `must_together_pairs` / `never_together_pairs` that scoring and co-location grouping would still consume, so the rule would silently affect results even though it was reported as ignored.
- *Delete rules that reference unregistered players*: destroys league-level data that is valid for other sessions.

### Decision 6: Play-with adherence and violations are scoped to the generated pool

**Choice**: `evaluate_plays_with_adherence` and `collect_violations` consider only play-with pairs whose members are both in the unassigned pool. Locked pairings are treated as satisfied by their existing team. Each unsatisfied pairing is reported once for the roster rather than once per team.

**Rationale**: Locked players never appear in a generated roster, so a pair satisfied inside a locked team would otherwise be flagged as "split across teams" by every generated team -- producing the duplicated "not satisfied" spam, and unfairly multiplying every team's play-with penalty. A pairing is a roster-wide property, so reporting it per team was always redundant; multiple unsplit pairs on different teams should not each be reported against unrelated teams.

**Alternatives considered**:
- *Collapse duplicates at display time only*: leaves the skew in the `plays_with_adherence` criterion, so the GA still optimises around locked pairings it cannot affect.
- *Drop locked pairs from `context.play_with_pairs` entirely*: breaks the co-location grouping and the locked-team spanning validation, which both need the full registered-wide pairing set.

## Risks / Trade-offs

- **[Risk] Balance is scoped to new teams, so a league with strong locked teams and weak new teams can end up top-heavy overall**
  → Mitigation: Accepted as a documented limitation. You cannot rebalance a locked team by definition; the convenor locked it deliberately. Surfacing locked-team strengths on the form is a possible future refinement, not part of this change.

- **[Risk] A `must_be_together` rule spanning a locked team now blocks generation that v1 silently tolerated**
  → Mitigation: This is intentional and consistent with v2's stricter contract. The error names the affected players so the convenor can clear or adjust the teams.

- **[Risk] `never_together` inside a locked team is invisible**
  → Mitigation: Locked teams are not scored, so the violation does not affect results; leaving it is a scope decision rather than a reliability risk. Documented as a non-goal.

- **[Risk] The `registered_player_ids` repurpose could silently break a reader that still expects "all registered"**
  → Mitigation: Renamed semantics are the central change; tests assert completeness and balance against locked+unassigned fixtures. The field is rename-verified in code review rather than left implicit.

## Migration Plan

1. Add the `Team` query and locked/available split to `build_context`; adjust `team_count` and `mean_contribution`. No data model change, so no migration.
2. Scope the `PlayerRule` query to players registered in the session; drop the unregistered-rule validation error.
3. Extend `validate_session` with the spanning-conflict check.
4. Update the view and CLI reporting; handle the zero-team state.
5. Rollback is reverting these code changes — no schema or data is altered, and `apply_roster` already deduplicates.

## Open Questions

None — the scope (append-only, locked-immutable, balance-among-new-teams) is fully determined by matching v1 and the convenor's stated intent.
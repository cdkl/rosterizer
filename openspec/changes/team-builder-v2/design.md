# Design

## Context

Rosterizer is a Django monolith using SQLite (or MySQL in production). The existing v1 team generation (`team_generation.py`) uses a greedy positional fill with random selection — it fills all Skips, then all Vices, etc., picking randomly from candidates who prefer that position. The v1 code and UI must remain untouched. The v2 engine reuses the existing models (`Player`, `Session`, `PlayerSession`, `Team`, `PlayerRule`) and adds `TeamResult` for historical results.

## Goals / Non-Goals

**Goals:**
- Replace random/greedy assignment with a genetic algorithm that optimizes across all criteria simultaneously
- Derive position-specific player ability from historical results, weighted so recent results count more
- Value a player's contribution at each position so promotions are priced correctly
- Balance teams on positional strength rather than raw player totals
- Protect manually entered results from accidental deletion
- Provide per-criterion score transparency so the convenor understands trade-offs
- Keep v1 and v2 as separate, independently functional code paths and UI flows
- Support CLI generation for scripting and automation

**Non-Goals:**
- Real-time or interactive team editing during generation
- Multi-session planning (optimizing across sessions at once)
- REST API (the CLI + Django views are sufficient)
- Guessing at outcomes from points scored (wins/losses/ties only feed ratings)

## Non-Functional Requirements

- **Testing**: Every new module gets a corresponding test file using pytest. Tests cover happy path and edge cases. Existing tests must continue to pass.
- **Error handling**: No bare exceptions. Views catch and surface errors to the user. Structural problems are detected before generation starts rather than producing invalid output.
- **Logging**: Use Python `logging` (already established in v1). Log population initialization, generation milestones, final scores, and roster selection.
- **Performance**: GA completes within a few seconds for 12 teams. See Decision 2 — this requires the evaluation context to be precomputed in memory, with no database access inside the GA inner loop.
- **Code conventions**: Follow existing project patterns — Django function-based views, template inheritance from `base.html`, `_v2` suffix for new modules.
- **No new Python dependencies**: Pure Python standard library + Django.
- **UI dependencies**: HTMX 2.x, vendored locally as a static file rather than loaded from a CDN, so the workflow does not silently degrade when the network is unavailable.
- **Data integrity**: `TeamResult` never depends on a mutable `Team` row. Migrations are additive only. Sessions and players referenced by results cannot be deleted.

## Decisions

### Decision 1: Genetic Algorithm for Team Generation

**Choice**: Use a genetic algorithm (GA) with tournament selection, team-swap crossover, and position-swapping mutation. Fitness is the composite score described in Decision 4.

**Rationale**: The problem is combinatorial optimization with multiple soft objectives and a few hard constraints. A GA maps naturally to multi-criterion scoring and produces multiple distinct candidates as a side effect of population diversity. It requires no external dependencies.

**Alternatives considered**:
- *Constraint programming (OR-Tools)*: More precise for hard constraints, but adds a heavy dependency and requires modeling the problem in CP-SAT syntax. Overkill for a 12-team league.
- *Simulated annealing with restarts*: Simpler, but produces correlated candidates from the same neighborhood; GA population diversity serves the "generate N distinct rosters" requirement better.
- *Integer linear programming*: Requires a solver dependency, and the multi-objective nature is harder to express as a single objective.

### Decision 2: Precompute an Immutable Evaluation Context

**Choice**: Build a frozen in-memory context once per generation run, containing every input the scorer needs: player ability per position, preference rankings, play-with pairs, player rules, historical team compositions per prior session, and the registered player list. Scoring functions read only from this context and perform no database queries.

**Rationale**: The GA evaluates 100 individuals across 200 generations — 20,000 roster evaluations. The v1 scorer issues hundreds of queries per evaluation because it calls `PlayerSession.objects.get()` inside per-team loops. Reusing that pattern would mean millions of queries and would make the sub-5-second target unreachable. Precomputing also makes the scorer a pure function, which makes it trivially testable and lets the GA loop avoid repeated ORM overhead.

**Details**: A `LeagueContext` dataclass built by a single `build_context(session_id)` call. `evaluate_roster(roster, context)` replaces the v1 signature that threads `session_id` through every function. Query count is O(1) per generation run rather than O(evaluations).

### Decision 3: Hard Constraints and Co-Location Grouping

**Choice**: Play-with preferences are a permanent hard constraint, always applied. They are modeled as a **matching** — disjoint pairs — not arbitrary chains. Must-be-together rules are also hard constraints. Both are combined into co-location groups via union-find, and generation refuses to start if any group exceeds team size.

**Rationale**: Only one play-with modality is supported: a player either has no preference or is paired with exactly one other person. Modeling this as a matching rather than a graph of arbitrary edges makes chains structurally impossible, which removes an entire class of unsatisfiable configurations. Chains of three or more could only arise when a player was declared as the partner of two different people, which is invalid input and is reported as such.

Because play-with pairs alone can never exceed team size, the only source of an oversized group is a must-be-together rule spanning or merging pairs. Checking the combined partition catches that, which a play-with-only chain check would miss.

**Future modalities**: The union-find operates on a list of co-location edges rather than reading `play_with` directly. Adding a modality (for example, "play with anyone in group X") means contributing additional edges to that list, with no change to grouping, validation, or the GA.

**Details**:
- Initialize by placing co-location groups into teams as indivisible units, then filling remaining slots by position preference
- Mutation only proposes swaps that keep every co-location group intact
- Crossover repairs violations by swapping whole groups between teams rather than individual players, so a repair can never split a pair
- never_together violations are rejected outright; they are not scored

### Decision 4: Composite Score as a Weighted Mean with a Floor

**Choice**: Compute the composite score as a weighted arithmetic mean of criterion scores, where each criterion is first clamped to a floor of 0.05.

**Rationale**: The v1 approach multiplied all criteria together. With eight criteria in [0,1] this fails in two ways. Magnitude collapse: candidates scoring 0.9 on everything reach 0.43, while candidates at 0.8 reach 0.17 — differences too small for a convenor to read off a score badge. Exact-zero ties: a weight-1.0 `never_together` violation zeroes a criterion, so every violating candidate scores exactly 0.0, and tournament selection and elitism receive no gradient to climb out of.

Clamping to 0.05 before averaging keeps violating candidates distinguishable from each other while still ranking them well below compliant ones. The arithmetic mean also preserves the intuitive property that improving any single criterion improves the score.

**Criterion weights** (default, tunable): completeness 1.0, position preference 1.0, team continuity 1.0, plays-with adherence 1.0, player rules 1.0, team balance 1.0. Continuity sub-scores for older sessions are folded into a single continuity criterion with decreasing internal weight.

### Decision 5: Experience Rating on a Saturating Curve

**Choice**: Convert years curled to a 0–1 experience score using `1 - exp(-years / k)` with `k = 4`.

| Years | Score |
|---|---|
| 0 | 0.00 |
| 1 | 0.22 |
| 2 | 0.39 |
| 3 | 0.53 |
| 5 | 0.71 |
| 10 | 0.92 |
| 20 | 0.99 |

**Rationale**: Dividing by the league maximum (the earlier draft) compresses everyone below the most experienced player — a 20-year player in a league whose maximum is 40 scores 0.5 despite being well above median. Curling experience is also not linear: the difference between a novice and a beginner is much larger than between an experienced club curler and a veteran. A saturating curve with a single parameter captures both properties and is trivially refinable later without changing its consumers.

### Decision 6: Position-Specific Ability with Shrinkage

**Choice**: Ability at a position is a shrunk blend of observed win rate and experience expectation:

```
ability(player, P) = (n · win_rate + m · experience_score) / (n + m)
```

where `n` is the time-weighted number of games played at position P, and `m` is a prior strength expressed in games. `win_rate = (wins + 0.5 · ties) / games`.

`m` is derived rather than fixed: `m = shrinkage_fraction × median_games_per_session`, where `median_games_per_session` is computed from recorded results and `shrinkage_fraction` defaults to 0.5. A fixed game-count prior would make the shrinkage behave differently purely because of league format — with `m = 4` a 4-game bonspiel and a 20-game schedule trust a single season by noticeably different margins, despite the same underlying evidence. Scaling by the median keeps the shrinkage strength constant relative to what constitutes "a season's worth of evidence" for this league. When no results exist the median is undefined, but neither is `n`, so the formula collapses cleanly to the experience score.

**Rationale**: Sparse results are the common case, not an edge case. A binary fallback — use results if any exist, otherwise use experience — treats a single 8-0 season as fully reliable evidence and mixes measured and imputed values on the same scale without distinguishing them. Shrinkage handles both failure modes smoothly: zero history returns exactly the experience score, and one anomalous season moves the result only partway. It is also the standard remedy for the small-sample problem noted in Risks.

**Time decay**: Sessions are ordered by `(year, session_number)`. A result's age is its index distance from the current session in that ordering, minus one, so the most recent prior session carries weight `decay^0 = 1.0`, the one before it `decay^1`, and so on. Using the index distance rather than subtracting `session_number` directly is what makes cross-year weighting correct — the earlier draft's formula gave a Session 3 result from the previous year the same weight as the current Session 3.

**Weighting**: `weight = decay_factor ^ age`, `decay_factor = 0.7` by default. A result from two sessions back carries 0.49 of the weight of the most recent.

**Two sources of historical team data, deliberately.** Results read the frozen snapshot on `TeamResult`, while team continuity reads live `Team` rows for prior sessions. This is intentional, not an oversight. A recorded result is a historical fact about a specific roster and must not shift if teams are later cleared and regenerated. Continuity is a live preference about how much to mix people up relative to how teams are *currently* recorded, so if a past session's teams are regenerated, continuity should follow the new lineup. Regenerating history correctly weakens continuity and leaves results untouched.

### Decision 7: Position Influence and Team Strength

**Choice**: Weight each position by its influence on the outcome: Skip 1.00, Vice 0.85, Second 0.75, Lead 0.70.

```
contribution(player, P) = ability(player, P) × influence(P)
team_strength(team)     = Σ contribution(player, position) over filled positions
```

**Rationale**: A player who is a solid Second but a weak Vice is worth more at Second, and promoting them should be priced accordingly. Without positional weighting, a roster's strength depends only on which four players are present, so the engine has no reason to put strong players at Skip and would treat a strong-Skip/weak-Lead team as equal to the reverse. Weighting by influence lets the engine see that a promotion from Vice to Skip trades a higher-influence position for a player's demonstrated ability at that position — and that trade is only worth making when ability holds up.

With the example numbers: a player at 0.8 Vice and 0.6 Skip contributes 0.68 at Vice and 0.60 at Skip, so the engine keeps them at Vice unless the balance benefit elsewhere outweighs the 0.08 loss. This is the behavior the convenor described wanting, and it falls out of the model rather than needing a special rule.

The weights are deliberately coarse. They encode "Skip matters most, Lead matters least" without pretending to precision the data cannot support. Team strength ranges roughly 0–3.3, and balance is the coefficient of variation of team strength across teams.

### Decision 8: Results Anchored to a Committed Snapshot, Not to Team Rows

**Choice**: `TeamResult` stores its own copy of the roster composition — a team number plus the four player foreign keys — and links to `Session`, not to `Team`. A `results_committed` flag on `Session` records that the convenor has confirmed the roster as the historical record.

```
TeamResult:
  session: FK(Session, on_delete=PROTECT)
  team_number: IntegerField
  skip, vice, second, lead: FK(Player, null=True, on_delete=PROTECT)
  wins, losses, ties: IntegerField (default 0)
  points_for, points_against: IntegerField (optional)
  notes: TextField (optional)
  unique_together: [session, team_number]

Session:
  results_committed: BooleanField(default=False)
```

**Rationale**: `Team` is a volatile row. The v1 workflow appends teams with incrementing numbers, `clear_teams` deletes them, and regenerating creates new rows reusing the same numbers. A foreign key to `Team` therefore has three failure modes: deleting teams cascades away results the convenor entered; clear-then-regenerate reattaches historical results to a different lineup; and the recorded position strength silently changes because it was derived from a roster that no longer exists. Storing the composition directly makes results self-describing and permanently correct as history.

**Ties**: The model includes `ties` because curling produces them, and a tie is half a win for rating purposes. Omitting it would force the convenor to record ties as losses.

**Deletion protection**: `PROTECT` on both the session and player foreign keys makes deletion fail at the database level rather than depending on view-layer checks. The v1 `delete_session`, `clear_player_list`, and `clear_teams` views gain guards that surface a clear message; `clear_teams` warns rather than blocking, since clearing teams does not endanger the results themselves, only the live view of them.

### Decision 9: HTMX for Dynamic UI Interactions

**Choice**: Vendor HTMX 2.x as a local static file and use it for generation with a loading state, expandable candidate details, and inline results saving.

**Rationale**: The GA takes a few seconds for a 12-team league. A full-page POST means the user stares at a blank tab with no feedback. HTMX gives a loading indicator and in-place result replacement with one attribute on the form tag, and pairs naturally with Django template partials.

**CDN rejected**: Loading from a CDN means a blocked or offline environment turns every `hx-*` attribute into a silent no-op, degrading the workflow with no error. Vendoring costs one 14KB file.

### Risks / Trade-offs

- **[Risk] GA may converge slowly for large leagues (12+ teams)**
  → Mitigation: Population size scales with team count. Default 100 individuals, 200 generations — acceptable for a batch operation run a few times per year.

- **[Risk] Ability ratings are unreliable with sparse results**
  → Mitigation: Shrinkage (Decision 6) pulls sparse observations toward the experience expectation, so a single unusual season cannot dominate. The prior strength `m` is the tuning knob if ratings prove too jumpy.

- **[Risk] Position influence weights are coarse guesses**
  → Mitigation: They encode ordinal importance, not measured magnitudes. Overstating the Skip weight could push the engine toward imbalanced rosters; the balance score and the convenor's review of candidates are the safety net. Revisit once real result data exists.

- **[Risk] Must-be-together rules can make generation infeasible**
  → Mitigation: Pre-flight validation refuses to start and names the conflicting players, instead of failing obscurely mid-run.

- **[Risk] V1 and V2 diverge if the Team model changes**
  → Mitigation: Both code paths share the same `Team` model. v2 respects existing teams when applying a roster.

- **[Trade-off] GA produces approximate solutions, not guaranteed optimal**
  → Acceptable: The convenor reviews multiple candidates and picks. League team building is a "good enough" problem.

- **[Trade-off] Two generation workflows coexist**
  → Acceptable: The convenor explicitly requested a separate entry point. v1 can be deprecated once v2 proves itself.

## Migration Plan

1. Add the `TeamResult` model and the `Session.results_committed` field (additive migration).
2. Ship the evaluation and strength modules with tests, no UI surface yet.
3. Ship the GA and CLI command, verify output manually.
4. Ship the v2 web workflow.
5. Existing v1 behavior is unchanged throughout; rollback is reverting the new URL patterns and templates.

## Open Questions

- Whether the experience curve constant `k = 4` matches this league's actual experience distribution — refinable in one place once real data exists.
- Whether the position influence weights should shift once several sessions of results have been recorded.
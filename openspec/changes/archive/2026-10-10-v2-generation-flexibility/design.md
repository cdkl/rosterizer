# Design

## Context

The current v2 engine (see `team_generation_v2.py`) models a roster as a list-of-dicts mapping each position to a `PlayerSession` id. The GA chromosome is the full positioned roster. The mutation operator swaps occupants at the *same* position between teams; crossover copies whole teams position-for-position. As a result, a player's position is determined once at initialisation and never changed by evolution. The `position_preference` criterion has effectively zero gradient: the live Session 26 population produces only 2 distinct `position_preference` values across 100 individuals.

Co-location groups (play-with pairs and must-be-together rules) are slotted by zipping `sorted(group)` against a slot list derived from one anchor's preference, ignoring individual members' preferences entirely. This produces assignments that are wrong for both members — including the anchor itself.

The 10 candidates returned by `generate_rosters_v2` are the top-N distinct rosters from a single converged population. Distinctness is defined by `roster_key`, which checks team-position assignments — two rosters with the same membership but a single position swap are "distinct." Co-team pair Jaccard similarity between candidate 1 and candidates 2–10 ranges from 0.5 to 0.8, so the candidates are minor variations on the same theme.

See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Give the GA freedom to explore different position assignments alongside team composition
- Make first-preference adherence a near-hard constraint that is satisfied whenever possible
- Produce candidates that are meaningfully different in who plays with whom
- Keep the external contract unchanged: output is still a positioned list-of-dicts

**Non-Goals:**
- Changing scoring criteria or weights
- Changing the v1 engine or its UI
- Supporting position changes within an already-locked team
- Global position optimization across teams (per-team is sufficient and decomposable)

## Decisions

### Decision 1: Membership-only chromosome with deterministic position assignment

**Choice**: The GA chromosome represents only which players belong to each team — a list of tuples of player ids, with no positions. Before each evaluation, a deterministic optimizer assigns positions to every team's members. The GA operators (initialise, mutate, crossover, repair) operate on membership only and never touch positions.

**Rationale**: This is the cleanest separation: the GA searches team composition (the expensive combinatorial part), and position assignment is a cheap per-team optimization (≤24 configurations per 4-player team) that can be solved exactly. It also makes the GA operators simpler — mutate swaps any two unassigned players between teams without worrying about position compatibility.

**Alternatives considered**:
- *Add position-swap mutation to the existing chromosome*: Would fix the gradient problem but still requires initialization to guess positions, and the GA searches a larger space (composition × positions) with operators that only affect one dimension at a time. The mutation that swaps two players at different positions is also harder to validate for group integrity.
- *Evolve membership and positions together in a single chromosome, but add a crossover operator that can exchange positions*: More complex operators, and the position space is small enough that exact optimization per team is viable.

### Decision 2: Lexicographic preference maximisation per team

**Choice**: For each team, enumerate all valid position-to-member assignments (all permutations, ≤24 for 4 members, ≤6 for 3). Score each by a tuple `(first_pref_count, second_pref_count)`. Keep only those with the maximum tuple. Among survivors, select the one whose contribution sum best balances the roster — specifically, the one that brings the cumulative mean team strength closest to the running global mean. This is computed greedily team-by-team using a running average of already-assigned team strengths.

**Rationale**: This makes "first preference whenever possible" genuinely enforceable. The lexicographic tuple means a single first-pref gain always beats any number of second-pref gains. Balance tie-breaking means the optimizer still distinguishes between equally-good preference assignments — important when several players on the same team have no preference or identical preferences.

"Maximise first preferences" is the spec-level behavior. The tie-break is implementation detail: it picks the assignment that helps balance without contradicting the preference maximisation.

**Alternatives considered**:
- *Weighted score (pref × weight + balance × weight)*: Makes preferences soft — a strong balance gain could displace a Skip-wanting player to Lead, which the user explicitly does not want.
- *Global ILP across all teams simultaneously*: Heavier, requires a solver dependency, and the per-team problem is small enough to solve exactly.

### Decision 3: Performance — caching assignments by team composition key

**Choice**: Cache the position-assignment result keyed by `frozenset(member_ids)`, so the same composition across different rosters or within a converged population is assigned only once. The cache is cleared per GA run (not across runs, since context can differ).

**Rationale**: Without caching, the optimizer runs once per roster evaluation (~20,000 × 0.3ms ≈ 6s for 100 pop × 200 gen × 9 teams). In a converged population many team compositions repeat. Even modest cache hit rates keep the total under 3s, well within the 5s target. The cache is cheap to implement — a dict cleared per `run_ga` call.

**Alternatives considered**:
- *Skip caching, accept longer runtime*: 6s is borderline but acceptable for a batch tool. Caching is simple enough to include at no real cost.
- *Cache by full roster key*: Less effective hit rate, since the GA rarely evaluates the exact same roster twice (crossover and mutation produce variation).

### Decision 4: Greedy diversity selection with Jaccard penalty

**Choice**: After the GA produces its sorted final population, build the candidate list greedily:

1. Take the best-scoring roster.
2. For each subsequent candidate, pick the roster that maximises `composite_score − λ × max_similarity_to_already_chosen`, where similarity is the Jaccard index of co-team player pairs (pairs of players who are on the same team together).
3. Stop when `len(candidates) == num_candidates` or no remaining roster exceeds the diversity floor.

Default `λ = 0.1` and minimum Jaccard difference of `0.15` between candidates (so they must differ by at least this much from every previously chosen candidate). These are tunable but not user-facing yet.

**Rationale**: Jaccard on co-team pairs directly measures "how different is the experience for the players?" — the thing the convenor cares about. The penalty is a soft diversity force that still allows the best roster through. The minimum-difference floor prevents the greedy algorithm from accepting near-clones when the penalty is too weak.

**Alternatives considered**:
- *Multiple independent GA runs with different seeds*: Diversity would be incidental; the GA converges to the same optimum regardless of seed given enough generations. The run we reproduced had 100% Jaccard similarity across the top candidates.
- *Fitness sharing / niching inside the GA*: Adds complexity to the GA core (distance metrics inside tournament selection, sharing radius tuning). Greedy post-processing is simpler and gives explicit control over the diversity-quality trade-off.

### Decision 5: Membership representation in operators

**Choice**: Each team is a `tuple` of player ids (or `frozenset` for group placement). The roster is a list of `frozenset`s. Initialisation places groups (whole units, largest first) and individuals (most-constrained first) into teams using a balance-aware greedy heuristic. Mutation swaps two players (or one player and an empty slot on a 3-player team) between teams, validated for group integrity and never-together. Crossover takes a prefix of teams from one parent and suffix from the other; repair removes duplicates and re-places missing players (and their groups) with a balance-aware greedy fill.

Because positions are assigned afterward, these operators are simpler than the current ones — no position slot logic, no `_slots_for`, no anchor selection based on preference. Group placement just needs enough open capacity on a team, with never-together checking against existing occupants.

**Rationale**: Membership-only operators are strictly simpler and need only two validation checks: group integrity and never-together. Position compatibility is handled deterministically afterward.

## Risks / Trade-offs

- **[Risk] Per-team greedy position assignment is not globally optimal for balance**: A team's position assignment considers the running average of prior teams' strengths. The first team optimises purely for preferences (no prior teams), and later teams can compensate. This is a heuristic, not a global optimum, but in practice the balance score improved in the prototype (0.846→0.896 for Session 26) because the current frozen-position engine is worse.
  → Mitigation: The GA still searches team membership, which is where the bulk of balance variation comes from. The position optimizer's balance tie-break is a refinement, not the primary mechanism.
- **[Risk] Preference maximisation may conflict with never-together rules**: Two players who both want Skip and have a never-together rule between them will be on different teams, so the per-team optimizer never sees both. No conflict.
- **[Risk] Diversity penalty could select a significantly worse roster**: λ=0.1 means a roster scoring 0.02 lower but completely different composition beats a near-clone of candidate 1. This is a trade-off the convenor explicitly wants (10 different options, not 10 copies).
  → Mitigation: λ and the minimum-difference floor are tunable constants. The convenor still sees scores and can judge.
- **[Trade-off] Caching key does not include the running balance context**: Two teams with identical membership may get different position assignments depending on which team was assigned first (different running average). A cache keyed only on members would return the same assignment regardless of order.
  → Mitigation: The balance tie-break within the optimizer is fine-grained enough that order dependence is small. If it matters, the cache can be disabled or keyed on `(members, running_mean_rounded)`.

## Migration Plan

1. Introduce the membership representation and position optimizer in `team_generation_v2.py` behind the existing `generate_rosters_v2` entry point.
2. Replace the positioned-chromosome operators with membership operators.
3. Add the diversity selection step after `run_ga`.
4. Update tests to match the new representation.
5. No database migration, no API change, no template change.
6. Rollback: revert `team_generation_v2.py` to the prior commit. No persistent state is affected.

## Open Questions

- Whether λ=0.1 produces the right diversity/quality balance across different league sizes (8 teams vs 12 teams). Tunable in a follow-up if needed.
- Whether the position optimizer should be exposed as a standalone utility for manually adjusting generated rosters. Out of scope for this change.
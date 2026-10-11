"""
Team assignment for the v2 roster builder.

The genetic algorithm operates on *membership-only* rosters — each team is a
frozenset of player ids with no positions.  A deterministic position optimizer
(assign_positions) runs inside every evaluation, assigning each team's members
to positions that maximise stated first-preference counts as a near-hard
constraint, then second-preferences, then balance as a tie-breaker.

Because positions are assigned deterministically, the GA explores team
composition independently of position slots and can reassign players to any
position without needing a position-swap mutation operator.

Constraints are modelled as co-location groups — sets of players that must
share a team — derived from play-with pairings and must-be-together rules via
union-find. Groups are the unit of movement for the genetic operators, so
neither crossover repair nor mutation can split a pair.
"""

import itertools
import random

from .position_strength import POSITIONS, contribution_rescaled
from .roster_evaluation_v2 import (
    build_context,
    evaluate_roster,
)

TEAM_SIZE = 4

DEFAULT_POPULATION = 120
DEFAULT_GENERATIONS = 80
DEFAULT_ELITE = 2
DEFAULT_CANDIDATES = 10
TOURNAMENT_SIZE = 3
MUTATION_RATE = 0.25
CROSSOVER_RATE = 0.7

# ---------------------------------------------------------------------------
# position-assignment cache — cleared per GA run
# ---------------------------------------------------------------------------

_position_cache = {}

# Exposed for verification in tests.
_cache_hits = 0
_cache_misses = 0


def _clear_position_cache():
    global _position_cache, _cache_hits, _cache_misses
    _position_cache.clear()
    _cache_hits = 0
    _cache_misses = 0


# ---------------------------------------------------------------------------
# position optimizer
# ---------------------------------------------------------------------------

def _first_pref_count(assignment, context):
    """How many members in ``assignment`` got their first preference."""
    return sum(1 for pid, pos in assignment.items()
               if context.prefers(pid, pos) == 1.0)


def _second_pref_count(assignment, context):
    """How many members in ``assignment`` got their second preference."""
    return sum(1 for pid, pos in assignment.items()
               if context.prefers(pid, pos) == 0.5)


def _assignment_strength(assignment, context, n_members=4):
    """Sum of contributions for this assignment.

    For 3-player teams (n_members=3) the Skip/Vice/Second weights are
    rescaled proportionally so they sum to 1.0.
    """
    total = 0.0
    for pid, pos in assignment.items():
        ability = context.abilities.ability(pid, pos)
        if n_members == 3:
            total += contribution_rescaled(ability, pos)
        else:
            total += context.abilities.player_contribution(pid, pos)
    return total


def assign_positions(membership_team, context):
    """
    Best position assignment for one team's members.

    Enumerates all valid position-to-member matchings and returns the one that:

    1. Maximises the number of first-preference assignments.
    2. Among those, maximises second-preference assignments.
    3. Among those, minimises |team_strength − context.mean_contribution × N|,
       i.e. keeps team strength closest to the global per-slot mean.

    For a 3-member team the Lead position is excluded — only Skip, Vice and
    Second are available.

    Args:
        membership_team (frozenset): player ids on this team.
        context (LeagueContext): precomputed session data.

    Returns:
        dict: ``{position: player_id}``.  Does NOT include PlayerSession ids;
        the caller converts those later.
    """
    members = sorted(membership_team)  # stable order for deterministic output
    n = len(members)
    if n == 0:
        return {}
    positions = list(POSITIONS[:n])  # Skip,…Lead omitted for 3-player teams

    best_assignments = []
    best_first = -1
    best_second = -1

    for perm in itertools.permutations(positions):
        assignment = dict(zip(members, perm))
        first = _first_pref_count(assignment, context)
        second = _second_pref_count(assignment, context)

        if (first, second) > (best_first, best_second):
            best_first, best_second = first, second
            best_assignments = [assignment]
        elif (first, second) == (best_first, best_second):
            best_assignments.append(assignment)

    # Balance tie-break: pick the assignment whose strength is closest to
    # the per-team target (mean_contribution × team_size).  Using a
    # constant target instead of a running mean makes the cache correct
    # regardless of evaluation order.
    target = context.mean_contribution * n

    def _balance_dist(assignment):
        return abs(_assignment_strength(assignment, context, n) - target)

    best_assignments.sort(key=_balance_dist)
    return best_assignments[0]


def _membership_to_positioned(membership_roster, context):
    """
    Convert a membership roster into the positioned list-of-dicts.

    Uses the per-team position optimizer.  The result maps each position
    to the PlayerSession id so it is ready for ``evaluate_roster`` and the
    public API.
    """
    global _cache_hits, _cache_misses
    positioned = []

    for members in membership_roster:
        key = frozenset(members)
        if key in _position_cache:
            _cache_hits += 1
            assignment = _position_cache[key]
        else:
            _cache_misses += 1
            assignment = assign_positions(members, context)
            _position_cache[key] = assignment

        # Build the positioned team with PlayerSession ids.
        # assignment maps player_id → position.
        positioned_team = {}
        for player_id, pos in assignment.items():
            positioned_team[pos] = context.player_session_id(player_id)
        # Any unfilled positions (Lead on 3-player teams) stay None.
        for pos in POSITIONS:
            if pos not in positioned_team:
                positioned_team[pos] = None
        positioned.append(positioned_team)

    return positioned


def evaluate_membership_roster(membership_roster, context):
    """
    Assign positions to a membership roster, then score it.

    Returns the same dict as ``evaluate_roster``, with the positioned
    roster under the ``'roster'`` key.
    """
    positioned = _membership_to_positioned(membership_roster, context)
    result = evaluate_roster(positioned, context)
    result['roster'] = positioned
    return result


# ---------------------------------------------------------------------------
# validation  (unchanged from the positioned-chromosome era)
# ---------------------------------------------------------------------------

class ValidationProblem(ValueError):
    """Blocking structural problem in session data."""


def validate_session(session_id):
    """
    Check session data for structural problems before generating.

    Returns the LeagueContext when the data is sound. Raises ValidationProblem
    listing every problem found, rather than failing obscurely mid-generation.
    """
    problems = []
    try:
        context = build_context(session_id)
    except ValueError as exc:
        raise ValidationProblem(str(exc)) from exc

    for group in context.co_location_groups:
        if len(group) > TEAM_SIZE:
            problems.append(
                f'Players {sorted(group)} must all share a team, but a team holds '
                f'only {TEAM_SIZE}')

    # A co-location group that crosses a locked team cannot be satisfied without
    # modifying that team. A group entirely inside one locked team is benign and
    # simply drops out of generation; a group split across locked teams is just
    # as unsatisfiable as one spanning locked and unassigned players.
    locked = context.locked_player_ids
    available = context.registered_player_ids
    for group in context.co_location_groups:
        locked_members = group & locked
        available_members = group & available
        if locked_members and available_members:
            problems.append(
                f'Players {sorted(group)} must share a team, but '
                f'{sorted(locked_members)} are already on an existing team and '
                f'{sorted(available_members)} are still unassigned')
        elif len({context.locked_team_by_player.get(pid)
                  for pid in locked_members}) > 1:
            problems.append(
                f'Players {sorted(group)} must share a team, but their locked '
                f'members {sorted(locked_members)} are on different teams')

    all_registered = frozenset(ps.player_id for ps in context.player_sessions)
    for pair in context.play_with_pairs:
        for player_id in pair:
            if player_id not in all_registered:
                problems.append(f'Play-with pair references unregistered player {player_id}')

    if problems:
        raise ValidationProblem('; '.join(problems))
    return context


# ---------------------------------------------------------------------------
# membership-only construction
# ---------------------------------------------------------------------------

def _empty_membership_roster(team_count):
    """List of empty sets, one per team."""
    return [set() for _ in range(team_count)]


def _team_capacity(team):
    """How many more players this team can hold."""
    return TEAM_SIZE - len(team)


def _team_has_conflict(team, player_id, context):
    """True if placing *player_id* on this team would violate never-together."""
    for other in team:
        if frozenset((other, player_id)) in context.never_together_pairs:
            return True
    return False


def _group_fits_team(team, group, context):
    """
    True if every member of *group* can be placed on *team*.

    Checks capacity and never-together conflicts against existing occupants
    (not against other arriving members, since co-location groups have no
    internal never-together rules by construction).
    """
    if _team_capacity(team) < len(group):
        return False
    for pid in group:
        if pid in team:
            continue
        if _team_has_conflict(team, pid, context):
            return False
    return True


def _best_team_for_group(roster, group, context, rng):
    """
    Find a team that can hold the entire group, preferring less-full teams.

    Returns the team index, or None if no team can hold the group.
    """
    candidates = [(i, t) for i, t in enumerate(roster)
                  if _group_fits_team(t, group, context)]
    if not candidates:
        return None
    # Prefer teams with fewer players (balance group load across teams).
    candidates.sort(key=lambda item: len(item[1]))
    # Among equally-empty teams, pick randomly.
    best_capacity = len(candidates[0][1])
    tied = [item for item in candidates if len(item[1]) == best_capacity]
    return rng.choice(tied)[0]


def group_units(context):
    """
    Co-location groups as placement units, largest first.

    Largest-first matters: placing the biggest unit first leaves small slots
    behind for individuals, rather than stranding singles against a full team.
    """
    units = [frozenset(pid for pid in g if pid in context.registered_player_ids)
             for g in context.co_location_groups]
    units = [u for u in units if u]
    units.sort(key=lambda members: (-len(members), sorted(members)))
    return units


def _constraint_degree(player_id, context):
    """How many never-together rules restrict this player."""
    return sum(1 for pair in context.never_together_pairs if player_id in pair)


def _max_contribution(player_id, context):
    return max(context.abilities.player_contribution(player_id, p) for p in POSITIONS)


def _best_team_for_player(roster, player_id, context, rng):
    """
    Find the best team for an individual player.

    Prefers teams with fewer players (for even distribution), respecting
    never-together constraints.
    """
    candidates = [(i, t) for i, t in enumerate(roster)
                  if _team_capacity(t) > 0
                  and not _team_has_conflict(t, player_id, context)]
    if not candidates:
        return None
    candidates.sort(key=lambda item: len(item[1]))
    best_capacity = len(candidates[0][1])
    tied = [item for item in candidates if len(item[1]) == best_capacity]
    return rng.choice(tied)[0]


def initialise_roster(context, rng):
    """
    Construct a valid membership-only roster.

    Places co-location groups first (largest first), then individuals
    (most-constrained first), into teams with enough capacity.  Respects
    never-together constraints.  No positions are assigned — that happens
    at evaluation time.

    Returns:
        list: one ``frozenset`` of player ids per team.
    """
    roster = _empty_membership_roster(context.team_count)
    placed = set()

    # Place groups.
    for group in group_units(context):
        idx = _best_team_for_group(roster, group, context, rng)
        if idx is None:
            raise ValidationProblem(
                f'Cannot place players {sorted(group)} on one team of {TEAM_SIZE}')
        roster[idx] |= set(group)
        placed |= set(group)

    # Place individuals — most constrained first.
    singles = [pid for pid in context.registered_player_ids if pid not in placed]
    rng.shuffle(singles)
    # Stable multi-key sort: constraint degree (desc), then contribution (desc).
    singles.sort(key=lambda pid: (-_constraint_degree(pid, context),
                                  -_max_contribution(pid, context)))

    for player_id in singles:
        idx = _best_team_for_player(roster, player_id, context, rng)
        if idx is None:
            raise ValidationProblem(f'Could not place player {player_id}')
        roster[idx].add(player_id)

    return [frozenset(t) for t in roster]


# ---------------------------------------------------------------------------
# membership-only genetic operators
# ---------------------------------------------------------------------------

def tournament_select(population, fitness, rng, k=TOURNAMENT_SIZE):
    """Pick the fittest of k sampled individuals."""
    contenders = rng.sample(range(len(population)), min(k, len(population)))
    return population[max(contenders, key=lambda i: fitness[i])]


def _team_ids(team):
    """Player ids in a membership team (handles both frozenset and dict)."""
    if isinstance(team, frozenset):
        return team
    return set(team)  # fallback for tests


def mutate(roster, context, rng, rate=MUTATION_RATE):
    """
    Swap two players between randomly chosen teams.

    Operates at membership level — any player can swap with any other,
    regardless of position.  Validates that groups stay intact and
    never-together pairs are respected after the swap.
    """
    if len(roster) < 2:
        return roster

    result = [set(t) for t in roster]
    for _ in range(max(1, int(len(result) * rate))):
        a, b = rng.sample(range(len(result)), 2)
        if not result[a] or not result[b]:
            continue

        player_a = rng.choice(sorted(result[a]))
        player_b = rng.choice(sorted(result[b]))

        # Simulate swap.
        result[a].remove(player_a)
        result[a].add(player_b)
        result[b].remove(player_b)
        result[b].add(player_a)

        # Validate.
        if not _team_membership_satisfies(result[a], context):
            # Revert.
            result[a].remove(player_b)
            result[a].add(player_a)
            result[b].remove(player_a)
            result[b].add(player_b)
            continue
        if not _team_membership_satisfies(result[b], context):
            result[a].remove(player_b)
            result[a].add(player_a)
            result[b].remove(player_a)
            result[b].add(player_b)
            continue

    return [frozenset(t) for t in result]


def _team_membership_satisfies(team_members, context):
    """
    True if a team's membership respects never-together and group integrity.

    ``team_members`` is a set of player ids.
    """
    for pair in context.never_together_pairs:
        if pair <= team_members:
            return False
    for group in context.co_location_groups:
        overlap = group & team_members
        if overlap and overlap != group:
            return False
    return True


def crossover(parent_a, parent_b, context, rng):
    """
    Take a prefix of teams from one parent and the remainder from the other.

    Operates on membership frozensets.  Conflicts are repaired by moving
    whole co-location groups so no pair is ever split.
    """
    if len(parent_a) < 2:
        return [frozenset(t) for t in parent_a]

    split = rng.randrange(1, len(parent_a))
    child = [frozenset(t) for t in parent_a[:split]] + \
            [frozenset(t) for t in parent_b[split:]]
    return repair(child, context, rng)


def repair(roster, context, rng):
    """
    Resolve duplicate and missing players in a membership roster.

    Duplicates (players appearing on multiple teams) are removed from all but
    the first occurrence.  Missing players (and their co-location groups) are
    placed into teams with available capacity.
    """
    roster = [set(t) for t in roster]
    seen = set()
    for team in roster:
        to_remove = [pid for pid in team if pid in seen]
        team.difference_update(to_remove)
        seen |= team

    present = set().union(*roster)
    missing = context.registered_player_ids - present

    for player_id in sorted(missing, key=lambda pid: -len(context.group_of(pid))):
        group = context.group_of(player_id)
        if len(group) > 1 and group & present:
            # Some group members are placed; place the rest with them.
            continue
        _place_group_membership(group & missing, context, roster, rng)

    return [frozenset(t) for t in roster]


def _place_group_membership(group, context, roster, rng):
    """Place a co-location group (or singleton) into a team with capacity."""
    members = sorted(group)
    size = len(members)
    if size == 0:
        return

    candidates = [(i, t) for i, t in enumerate(roster)
                  if _team_capacity(t) >= size
                  and not any(_team_has_conflict(t, pid, context) for pid in members)]
    if not candidates:
        # Fallback: try placing individually.
        for pid in members:
            idx = _best_team_for_player(roster, pid, context, rng)
            if idx is not None:
                roster[idx].add(pid)
        return

    rng.shuffle(candidates)
    # Prefer less-full teams.
    candidates.sort(key=lambda item: len(item[1]))
    candidates[0][1].update(members)


def _player_session_id(player_id, context):
    value = context.player_session_id(player_id)
    if value is None:
        raise ValidationProblem(f'No player session for player {player_id}')
    return value


# ---------------------------------------------------------------------------
# GA loop  (membership-only, with position assignment inside evaluation)
# ---------------------------------------------------------------------------

def run_ga(context, seed=None, population_size=DEFAULT_POPULATION,
           generations=DEFAULT_GENERATIONS, elite=DEFAULT_ELITE):
    """
    Evolve membership rosters against the composite score.

    Positions are assigned inside ``evaluate_membership_roster`` — the GA
    sees only membership.  Elitism keeps the best few unchanged.

    Collects snapshots of top rosters throughout the run so the final
    pool contains diverse intermediate solutions, not just the converged
    population.

    Returns:
        list: ``[(composite, membership_roster), …]`` sorted best-first.
    """
    _clear_position_cache()
    rng = random.Random(seed)
    population = [initialise_roster(context, rng) for _ in range(population_size)]

    snapshots = []

    for generation in range(generations):
        scored = [(evaluate_membership_roster(r, context)['composite'], r)
                  for r in population]
        scored.sort(key=lambda item: item[0], reverse=True)
        population = [r for _, r in scored]

        # Snapshot the top few rosters every N generations.
        if generation % 20 == 0 or generation == generations - 1:
            for s, r in scored[:elite + 5]:
                snapshots.append((s, r))

        for i in range(elite, population_size):
            parent_a = tournament_select(population, [s for s, _ in scored], rng)
            if rng.random() < CROSSOVER_RATE:
                parent_b = tournament_select(population, [s for s, _ in scored], rng)
                child = crossover(parent_a, parent_b, context, rng)
            else:
                child = [frozenset(t) for t in parent_a]
            population[i] = mutate(child, context, rng)

    final = [(evaluate_membership_roster(r, context)['composite'], r) for r in population]
    final.sort(key=lambda item: item[0], reverse=True)
    all_rosters = final + snapshots
    all_rosters.sort(key=lambda item: item[0], reverse=True)
    return all_rosters


def membership_key(roster):
    """
    Stable signature for a membership roster, used for dedup and diversity.

    Sorts teams by their sorted player ids for a canonical representation.
    """
    return tuple(
        tuple(sorted(team))
        for team in sorted(roster, key=lambda t: tuple(sorted(t)))
    )


def roster_key(roster):
    """Stable signature for a positioned roster (backward compat)."""
    return tuple(
        tuple(sorted((p, t.get(p)) for p in POSITIONS if t.get(p) is not None))
        for t in roster)


# ---------------------------------------------------------------------------
# candidate diversity selection
# ---------------------------------------------------------------------------

def _co_team_pairs(roster):
    """
    Set of unordered player-id pairs that share a team.

    ``roster`` is either membership (frozensets) or positioned (dicts).
    """
    pairs = set()
    for team in roster:
        ids = _team_ids(team)
        sorted_ids = sorted(ids)
        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                pairs.add((sorted_ids[i], sorted_ids[j]))
    return pairs


def _jaccard_similarity(pairs_a, pairs_b):
    """Jaccard similarity between two sets of co-team pairs."""
    if not pairs_a and not pairs_b:
        return 0.0
    intersection = len(pairs_a & pairs_b)
    union = len(pairs_a | pairs_b)
    if union == 0:
        return 0.0
    return intersection / union


def select_diverse_candidates(scored_population, num_wanted,
                              lambda_penalty=0.1, min_difference=0.15):
    """
    Greedily select diverse candidates from a scored population.

    Each successive candidate maximises::

        composite_score − λ × max(Jaccard_co_team_pairs_to_already_chosen)

    and must differ from every already-chosen candidate by at least
    ``min_difference`` in Jaccard co-team-pair similarity (i.e. similarity
    ≤ 1.0 − min_difference).

    Args:
        scored_population: ``[(composite, membership_roster), …]``
        num_wanted: target number of candidates.
        lambda_penalty: diversity penalty weight.
        min_difference: minimum Jaccard difference between candidates.

    Returns:
        list: ``[(composite, membership_roster), …]`` selected candidates.
    """
    if not scored_population:
        return []

    remaining = list(scored_population)
    # Precompute co-team pairs for every roster.
    remaining_pairs = [(_co_team_pairs(r), r, c) for c, r in remaining]

    chosen = []
    chosen_pairs = []

    # First candidate: best score.
    _, best_r, best_c = remaining_pairs[0]
    chosen.append((best_c, best_r))
    chosen_pairs.append(_co_team_pairs(best_r))

    while len(chosen) < num_wanted and remaining_pairs:
        best_idx = None
        best_value = -float('inf')

        for idx, (pairs, roster, composite) in enumerate(remaining_pairs):
            max_sim = max((_jaccard_similarity(pairs, cp)
                           for cp in chosen_pairs), default=0.0)
            if max_sim > 1.0 - min_difference:
                continue
            value = composite - lambda_penalty * max_sim
            if value > best_value:
                best_value = value
                best_idx = idx

        if best_idx is None:
            break

        pairs, roster, composite = remaining_pairs.pop(best_idx)
        chosen.append((composite, roster))
        chosen_pairs.append(pairs)

    return chosen


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def generate_rosters_v2(session_id, num_candidates=DEFAULT_CANDIDATES, seed=None,
                        context=None):
    """
    Generate distinct, diverse candidate rosters for a session.

    Runs multiple independent GA trials with different seeds, collects the
    top individuals from each, and selects diverse candidates from the
    merged pool.  A single GA run converges to one membership optimum;
    independent runs with different random paths produce different local
    optima that give the diversity selector enough variety to work with.

    Returns:
        dict: ``{'candidates': [ {composite, criteria, violations, roster} ],
                'requested': int, 'shortfall': int}``
    """
    context = context or validate_session(session_id)

    # Everyone is already on a locked team: there is nothing to generate, and
    # that is a valid state rather than an error.
    if context.team_count == 0:
        return {
            'candidates': [],
            'requested': num_candidates,
            'shortfall': max(0, num_candidates),
        }

    # Run several independent GA trials and collect the top individuals.
    # Each trial converges from a different random starting point, giving
    # us a diverse set of membership compositions to choose from.
    trials = max(1, min(5, num_candidates))

    # Normalise seed: may be int, str, or None (web forms pass strings).
    if seed is not None:
        seed_val = int(seed)
    else:
        seed_val = random.randint(0, 2**31 - 1)

    pool = []  # (composite, membership_roster)
    seen_keys = set()
    for i in range(trials):
        trial_seed = seed_val + i * 1000
        population = run_ga(context, seed=trial_seed)

        # Collect the best few distinct rosters from this trial.
        trial_added = 0
        for composite, roster in population:
            key = membership_key(roster)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            pool.append((composite, roster))
            trial_added += 1
            if trial_added >= 15:
                break

    # Sort merged pool by score.
    pool.sort(key=lambda item: item[0], reverse=True)

    # Select diverse candidates from the merged pool.
    selected = select_diverse_candidates(pool, num_candidates)

    candidates = []
    for composite, membership_roster in selected:
        result = evaluate_membership_roster(membership_roster, context)
        result['composite'] = composite
        candidates.append(result)

    return {
        'candidates': candidates,
        'requested': num_candidates,
        'shortfall': max(0, num_candidates - len(candidates)),
    }
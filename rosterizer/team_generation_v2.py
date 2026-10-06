"""
Team assignment for the v2 roster builder.

Constraints are modelled as co-location groups -- sets of players that must share
a team -- derived from play-with pairings and must-be-together rules via
union-find. Because play-with is a matching, chains of three or more cannot
arise; the only way a group exceeds team size is a must-be-together rule
spanning or merging pairs. Checking the combined partition catches that, which a
play-with-only chain check would miss.

Groups are the unit of movement for the genetic operators: crossover repairs
conflicts by swapping whole groups, and mutation only proposes moves that leave
every group intact, so neither can split a pair.
"""

import random

from .position_strength import POSITIONS
from .roster_evaluation_v2 import (
    build_context,
    evaluate_roster,
)

TEAM_SIZE = 4

DEFAULT_POPULATION = 100
DEFAULT_GENERATIONS = 200
DEFAULT_ELITE = 2
DEFAULT_CANDIDATES = 10
TOURNAMENT_SIZE = 3
MUTATION_RATE = 0.15
CROSSOVER_RATE = 0.7


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

    registered = context.registered_player_ids
    for pair in context.play_with_pairs:
        for player_id in pair:
            if player_id not in registered:
                problems.append(f'Play-with pair references unregistered player {player_id}')
    for pair in context.must_together_pairs | context.never_together_pairs:
        for player_id in pair:
            if player_id not in registered:
                problems.append(f'Player rule references unregistered player {player_id}')

    if problems:
        raise ValidationProblem('; '.join(problems))
    return context


# --------------------------------------------------------------------------
# construction
# --------------------------------------------------------------------------

def empty_roster(team_count):
    return [{position: None for position in POSITIONS} for _ in range(team_count)]


def group_units(context):
    """
    Co-location groups as placement units, largest first.

    Largest-first matters: placing the biggest unit first leaves small slots
    behind for individuals, rather than stranding singles against a full team.
    """
    units = [sorted(group) for group in context.co_location_groups]
    units.sort(key=lambda members: (-len(members), members))
    return units


def _preferred_slot(team, context, player_id):
    """Best empty position for a player, by stated preference."""
    prefs = context.preference_by_player.get(player_id)
    if prefs:
        for position in POSITIONS:
            if position in prefs and team[position] is None:
                return position
    for position in POSITIONS:
        if team[position] is None:
            return position
    return None


def _team_for_group(roster, size, context):
    """Team with enough room for a whole co-location group, or None."""
    for team in roster:
        if _open_slots(team) >= size:
            return team
    return None


def _open_slots(team):
    return sum(team[position] is None for position in POSITIONS)


def initialise_roster(context, rng):
    """
    Construct a valid roster: co-location groups first, then fill by preference.

    Guarantees every player is placed exactly once, every group stays intact, and
    never-together pairs are kept apart.
    """
    roster = empty_roster(context.team_count)
    placed = set()

    # Units larger than one must not be split.
    for members in group_units(context):
        members = [pid for pid in members if pid in context.registered_player_ids]
        if not members:
            continue
        size = len(members)
        # Prefer the position its strongest member wants.
        anchor = max(members, key=lambda pid: context.abilities.player_contribution(pid, 'Skip'))
        preferred = context.preference_by_player.get(anchor, ('', ''))
        first_choice = next((p for p in preferred if p), None)

        target = None
        if first_choice:
            for team in roster:
                if (team[first_choice] is None
                        and _open_slots(team) >= size
                        and _group_fits(team, members, first_choice, size, context)):
                    target = team
                    break
        if target is None:
            target = _team_for_group(roster, size, context)
        if target is None:
            raise ValidationProblem(
                f'Cannot place players {sorted(members)} on one team of {TEAM_SIZE}')

        slots = _slots_for(target, size, first_choice)
        for position, player_id in zip(slots, members):
            target[position] = _player_session_id(player_id, context)
        placed.update(members)

    # Individuals fill whatever remains, honouring preferences.
    #
    # Order matters. Players carrying a never-together rule have fewer legal
    # slots than everyone else, so placing them last can strand them: by then
    # the one remaining hole may sit on the team holding their forbidden
    # partner. Placing the most constrained first keeps that from happening.
    singles = [pid for pid in context.registered_player_ids if pid not in placed]
    rng.shuffle(singles)
    singles.sort(key=lambda pid: -_constraint_degree(pid, context))
    singles.sort(key=lambda pid: -_max_contribution(pid, context))

    for player_id in singles:
        if _place_individual(player_id, context, roster):
            continue
        if not _force_place(player_id, context, roster):
            raise ValidationProblem(f'Could not place player {player_id}')

    return roster


def _constraint_degree(player_id, context):
    """How many never-together rules restrict this player."""
    return sum(1 for pair in context.never_together_pairs if player_id in pair)


def _force_place(player_id, context, roster):
    """
    Last-resort placement: take a free slot, displacing someone who can move.

    Greedy placement can fill the final hole on a team holding a forbidden
    partner. Rather than fail, move that occupant to another free slot.
    """
    ps_id = context.player_session_id(player_id)
    if ps_id is None:
        return False

    for team_index, team in enumerate(roster):
        for position in POSITIONS:
            if team[position] is not None:
                continue
            blocker = _blocking_occupant(team, player_id, context)
            if blocker is None:
                team[position] = ps_id
                return True
            blocker_position, blocker_id = blocker
            for other_index, other_team in enumerate(roster):
                if other_index == team_index:
                    continue
                for other_position in POSITIONS:
                    if other_team[other_position] is not None:
                        continue
                    if _never_together_conflict(other_team, blocker_id, context):
                        continue
                    if frozenset((blocker_id, player_id)) in context.never_together_pairs:
                        continue
                    team[blocker_position] = None
                    other_team[other_position] = context.player_session_id(blocker_id)
                    team[position] = ps_id
                    return True
    return False


def _blocking_occupant(team, player_id, context):
    """The (position, player_id) in this team that forbids `player_id`, if any."""
    for position in POSITIONS:
        value = team[position]
        if value is None:
            continue
        other = context.player_id(value)
        if other is not None and frozenset((other, player_id)) in context.never_together_pairs:
            return position, other
    return None


def _max_contribution(player_id, context):
    return max(context.abilities.player_contribution(player_id, p) for p in POSITIONS)


def _slots_for(team, size, preferred):
    """Positions to fill for a unit, putting the anchor in its preferred slot."""
    order = list(POSITIONS)
    if preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    return [p for p in order if team[p] is None][:size]


def _group_fits(team, members, preferred, size, context):
    slots = _slots_for(team, size, preferred)
    if len(slots) < size:
        return False
    return not _conflicts(team, slots, members, context)


def _conflicts(team, slots, members, context):
    """True if seating these members here would break a never-together rule."""
    member_ids = set(members)
    for position in slots:
        existing = team[position]
        if existing is None:
            continue
        existing_id = context.player_id(existing)
        if existing_id is None:
            continue
        if any(frozenset((existing_id, pid)) in context.never_together_pairs
               for pid in member_ids):
            return True
    return False


def _player_session_id(player_id, context):
    value = context.player_session_id(player_id)
    if value is None:
        raise ValidationProblem(f'No player session for player {player_id}')
    return value


def _place_individual(player_id, context, roster):
    """Place one player on the team whose open slot suits them best."""
    ps_id = _player_session_id(player_id, context)
    prefs = context.preference_by_player.get(player_id, ('', ''))
    order = [p for p in POSITIONS if p in prefs] + \
            [p for p in POSITIONS if p not in prefs]

    for position in order:
        best = None
        best_cost = None
        for team in roster:
            if team[position] is not None:
                continue
            if _never_together_conflict(team, player_id, context):
                continue
            cost = _placement_cost(team, player_id, position, context)
            if best_cost is None or cost < best_cost:
                best, best_cost = team, cost
        if best is not None:
            best[position] = ps_id
            return True
    return False


def _never_together_conflict(team, player_id, context):
    for position in POSITIONS:
        existing = team[position]
        if existing is None:
            continue
        other = context.player_id(existing)
        if other is not None and frozenset((other, player_id)) in context.never_together_pairs:
            return True
    return False


def _placement_cost(team, player_id, position, context):
    """
    Prefer positions and teams that leave the roster balanced.

    Cost combines the imbalance this placement would create against the current
    team strengths, which is what steers initialisation toward balanced rosters
    before the GA even starts.
    """
    strength = context.abilities.player_contribution(player_id, position)
    projected = _team_strength(team, context) + strength
    imbalance = abs(projected - context.mean_contribution)
    openness = -_open_slots(team)
    return imbalance + openness * 0.01


def _team_strength(team, context):
    total = 0.0
    for position in POSITIONS:
        value = team.get(position)
        if value is None:
            continue
        player_id = context.player_id(value)
        if player_id is None:
            continue
        total += context.abilities.player_contribution(player_id, position)
    return total


# --------------------------------------------------------------------------
# genetic operators
# --------------------------------------------------------------------------

def tournament_select(population, fitness, rng, k=TOURNAMENT_SIZE):
    """Pick the fittest of k sampled individuals."""
    contenders = rng.sample(range(len(population)), min(k, len(population)))
    return population[max(contenders, key=lambda i: fitness[i])]


def mutate(roster, context, rng, rate=MUTATION_RATE):
    """
    Swap two players at the same position between different teams.

    Restricting swaps to a single position preserves how well the roster matches
    stated preferences while still exploring different team compositions. Moves
    that would split a co-location group or violate never-together are skipped.
    """
    if len(roster) < 2:
        return roster

    result = [dict(team) for team in roster]
    for _ in range(max(1, int(len(result) * rate))):
        position = rng.choice(POSITIONS)
        a, b = rng.sample(range(len(result)), 2)
        if result[a][position] is None or result[b][position] is None:
            continue
        if _would_break_groups(result, a, b, position, context):
            continue
        result[a][position], result[b][position] = \
            result[b][position], result[a][position]
    return result


def _would_break_groups(roster, a, b, position, context):
    """
    True if swapping this position between two teams would break a constraint.

    A same-position swap preserves how well stated preferences are met, but it
    is not automatically safe. The arriving player must be checked against
    everyone already on the destination team -- not just the player being
    displaced -- and both players' co-location groups must stay whole.
    """
    moving = roster[b][position]
    other = roster[a][position]
    if moving is None or other is None:
        return False
    player_moving = context.player_id(moving)
    player_other = context.player_id(other)
    if player_moving is None or player_other is None:
        return False

    # Simulate the swap, then validate both resulting teams outright. Checking
    # only the swapped pair would miss the arriving player landing beside
    # someone they are forbidden to share a team with.
    team_a = dict(roster[a])
    team_b = dict(roster[b])
    team_a[position], team_b[position] = moving, other

    if not _team_satisfies(team_a, context):
        return True
    if not _team_satisfies(team_b, context):
        return True

    # Both players must still be with their co-location group.
    if not _group_lands_whole(context, team_a, player_moving):
        return True
    if not _group_lands_whole(context, team_b, player_other):
        return True
    return False


def _team_satisfies(team, context):
    """No never-together pair and no split co-location group on this team."""
    ids = {context.player_id(v) for v in team.values() if v is not None}
    for pair in context.never_together_pairs:
        if pair <= ids:
            return False
    for group in context.co_location_groups:
        members_here = group & ids
        if members_here and members_here != group:
            return False
    return True


def _group_lands_whole(context, team, arriving_player):
    """Is the arriving player's co-location group entirely on this team?"""
    group = context.group_of(arriving_player)
    if len(group) <= 1:
        return True
    team_players = {context.player_id(v) for v in team.values() if v is not None}
    return group <= team_players


def crossover(parent_a, parent_b, context, rng):
    """
    Take a prefix of teams from one parent and the remainder from the other.

    Conflicts (a player appearing twice, or going missing because they were only
    in the discarded halves) are repaired by moving whole co-location groups
    rather than individual players, so a repair can never split a pair.
    """
    if len(parent_a) < 2:
        return [dict(t) for t in parent_a]

    split = rng.randrange(1, len(parent_a))
    child = [dict(t) for t in parent_a[:split]] + [dict(t) for t in parent_b[split:]]
    return repair(child, context, rng)


def repair(roster, context, rng):
    """Resolve duplicate and missing players, moving whole groups where needed."""
    roster = [dict(t) for t in roster]

    # Collect every assignment, keeping the first occurrence.
    seen = set()
    duplicates = []
    for team in roster:
        for position in POSITIONS:
            value = team[position]
            if value is None:
                continue
            if value in seen:
                team[position] = None
                duplicates.append(value)
            else:
                seen.add(value)

    # Only genuinely absent players need re-placing. A duplicate's *extra* copy
    # was just cleared, but the player still occupies their other slot -- so
    # re-placing them would double-place them and starve a player who is truly
    # missing. The hole count equals the missing count, so capacity lines up
    # exactly.
    present_players = {context.player_id(v) for v in seen if context.player_id(v) is not None}
    missing = sorted(context.registered_player_ids - present_players)

    for player_id in missing:
        value = context.player_session_id(player_id)
        group = context.group_of(player_id)
        if not _place_group_as_unit(group, context, roster, rng):
            _place_individual(player_id, context, roster)

    return roster


def _place_group_as_unit(group, context, roster, rng):
    """Move an entire co-location group into a team that can hold it."""
    members = sorted(group)
    size = len(members)
    if size == 1:
        return _place_individual(members[0], context, roster)

    ids = [_player_session_id(pid, context) for pid in members]
    anchor = context.preference_by_player.get(members[0], ('', ''))
    first_choice = next((p for p in anchor if p), None)

    candidates = [t for t in roster if _open_slots(t) >= size]
    rng.shuffle(candidates)
    for team in candidates:
        slots = _slots_for(team, size, first_choice)
        if len(slots) < size:
            continue
        if any(team[p] is not None for p in slots):
            continue
        for position, value in zip(slots, ids):
            team[position] = value
        return True
    return False


def run_ga(context, seed=None, population_size=DEFAULT_POPULATION,
           generations=DEFAULT_GENERATIONS, elite=DEFAULT_ELITE):
    """
    Evolve rosters against the composite score.

    Returns the final population sorted best-first, with each individual's
    fitness. Elitism keeps the best few unchanged so scores never regress.
    """
    rng = random.Random(seed)
    population = [initialise_roster(context, rng) for _ in range(population_size)]

    for generation in range(generations):
        scored = [(evaluate_roster(r, context)['composite'], r) for r in population]
        scored.sort(key=lambda item: item[0], reverse=True)
        population = [r for _, r in scored]

        for i in range(elite, population_size):
            parent_a = tournament_select(population, [s for s, _ in scored], rng)
            if rng.random() < CROSSOVER_RATE:
                parent_b = tournament_select(population, [s for s, _ in scored], rng)
                child = crossover(parent_a, parent_b, context, rng)
            else:
                child = [dict(t) for t in parent_a]
            population[i] = mutate(child, context, rng)

    final = [(evaluate_roster(r, context)['composite'], r) for r in population]
    final.sort(key=lambda item: item[0], reverse=True)
    return final


def roster_key(roster):
    """Stable signature for a roster, used to detect duplicates."""
    return tuple(
        tuple(sorted((p, t.get(p)) for p in POSITIONS if t.get(p) is not None))
        for t in roster)


def generate_rosters_v2(session_id, num_candidates=DEFAULT_CANDIDATES, seed=None,
                        context=None):
    """
    Generate distinct candidate rosters for a session.

    Returns:
        dict: {'candidates': [ {composite, criteria, violations, roster} ],
               'requested': int, 'shortfall': int}
    """
    context = context or validate_session(session_id)
    population = run_ga(context, seed=seed)

    seen = set()
    candidates = []
    for composite, roster in population:
        key = roster_key(roster)
        if key in seen:
            continue
        seen.add(key)
        result = evaluate_roster(roster, context)
        result['roster'] = roster
        result['composite'] = composite
        candidates.append(result)
        if len(candidates) >= num_candidates:
            break

    return {
        'candidates': candidates,
        'requested': num_candidates,
        'shortfall': max(0, num_candidates - len(candidates)),
    }
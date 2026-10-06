"""
Roster scoring for the v2 roster builder.

Every scoring function takes a LeagueContext and performs no database queries.
The genetic algorithm evaluates thousands of candidate rosters, so the v1
approach of threading ``session_id`` through each function and hitting the ORM
inside per-team loops is not viable here -- see design Decision 2.
"""

from dataclasses import dataclass
from statistics import fmean

from .models import PlayerRule, PlayerSession, Team, TeamResult
from .position_strength import POSITIONS, build_ability_table, ordered_sessions

# Each criterion is clamped to this floor before averaging. Without it, a
# weight-1.0 rule violation would zero a criterion, and every violating candidate
# would tie at exactly the same composite score -- leaving the GA with no
# gradient to climb out of. See design Decision 4.
CRITERION_FLOOR = 0.05

# Relative importance of each criterion in the composite. Flat by default;
# exposed as a dict so weights can be tuned without touching the scoring code.
CRITERION_WEIGHTS = {
    'completeness': 1.0,
    'position_preference': 1.0,
    'team_continuity': 1.0,
    'plays_with_adherence': 1.0,
    'player_rules': 1.0,
    'team_balance': 1.0,
}

# Older sessions influence continuity less.
CONTINUITY_LOOKBACK_WEIGHTS = (0.5, 0.3, 0.2)
CONTINUITY_LOOKBACKS = (1, 2, 3)


def normalise_name(name):
    """Normalise a free-text player name for comparison.

    ``play_with`` is typed by hand during CSV import, so casing and stray
    whitespace are routine. Matching is done in Python rather than left to the
    database so behaviour is identical on SQLite (case-sensitive) and MySQL
    (case-insensitive collation).
    """
    if name is None:
        return ''
    return ' '.join(str(name).split()).casefold()


@dataclass(frozen=True)
class LeagueContext:
    """
    Everything the scorer needs, fetched once per generation run.

    Frozen so a scoring function cannot accidentally mutate shared state while
    the GA is iterating over a population.
    """

    session_id: int
    player_sessions: tuple
    player_id_by_player_session: dict
    player_session_by_player: dict
    preference_by_player: dict
    registered_player_ids: frozenset
    play_with_pairs: tuple
    must_together_pairs: frozenset
    never_together_pairs: frozenset
    player_rule_weights: dict
    co_location_groups: tuple
    abilities: object
    historical_teams: dict
    session_ages: dict
    team_count: int = 0
    mean_contribution: float = 0.0

    def player_id(self, player_session_id):
        return self.player_id_by_player_session.get(player_session_id)

    def player_session_id(self, player_id):
        return self.player_session_by_player.get(player_id)

    def group_of(self, player_id):
        """The co-location group a player belongs to, or a singleton."""
        for group in self.co_location_groups:
            if player_id in group:
                return group
        return frozenset({player_id})

    def all_player_session_ids(self):
        return tuple(self.player_id_by_player_session)

    def prefers(self, player_id, position):
        """How well `position` matches the player's stated preferences.

        1.0 for the first preference, 0.5 for the second, 0.0 otherwise. Players
        with no stated preference are treated as unconstrained rather than
        penalised.
        """
        prefs = self.preference_by_player.get(player_id)
        if not prefs:
            return 1.0
        first, second = prefs
        if first == position:
            return 1.0
        if second == position:
            return 0.5
        return 0.0


def resolve_play_with_pairs(player_sessions):
    """
    Resolve free-text play-with declarations into disjoint pairs.

    The relation is symmetric: if either member names the other, they are
    paired. A player may have at most one partner, so declarations are a
    matching rather than an arbitrary graph -- which makes chains of three or
    more structurally impossible.

    Returns:
        tuple: (pairs, problems) where pairs is a tuple of frozensets of player
        ids and problems is a list of human-readable strings.
    """
    by_name = {}
    for ps in player_sessions:
        by_name.setdefault(normalise_name(ps.player.full_name), []).append(ps.player_id)

    wanted_by_player = {}
    problems = []
    for ps in player_sessions:
        wanted = normalise_name(ps.play_with)
        if not wanted:
            continue
        candidates = by_name.get(wanted, [])
        if not candidates:
            problems.append(
                f'{ps.player.full_name} wants to play with "{ps.play_with}", '
                'who is not registered for this session')
            continue
        if len(candidates) > 1:
            problems.append(
                f'{ps.player.full_name} wants to play with "{ps.play_with}", '
                'which matches more than one registered player')
            continue
        partner = candidates[0]
        if partner == ps.player_id:
            problems.append(
                f'{ps.player.full_name} lists themselves as a play-with partner')
            continue
        wanted_by_player.setdefault(ps.player_id, set()).add(partner)

    # Symmetrise: if A names B, the pair exists regardless of what B names.
    # Snapshot the keys first -- setdefault below mutates the dict.
    for player_id in list(wanted_by_player):
        for partner in wanted_by_player[player_id]:
            wanted_by_player.setdefault(partner, set()).add(player_id)

    # A player named by more than one other is ambiguous: drop every pair
    # involving them rather than emit contradictory pairings. The problem is
    # reported and blocks generation upstream.
    ambiguous = {pid for pid, partners in wanted_by_player.items() if len(partners) > 1}
    for player_id in sorted(ambiguous):
        problems.append(
            f'Player {player_id} is named as the play-with partner of '
            f'{len(wanted_by_player[player_id])} different people; '
            'a player may have only one partner')

    seen = set()
    pairs = []
    for player_id in sorted(wanted_by_player):
        if player_id in ambiguous:
            continue
        partner = next(iter(wanted_by_player[player_id]))
        if partner in ambiguous:
            continue
        key = frozenset((player_id, partner))
        if key not in seen:
            seen.add(key)
            pairs.append(key)

    return tuple(pairs), problems


def co_location_edges(play_with_pairs, must_together_pairs):
    """
    All edges that force players onto the same team.

    Taking them as an input list rather than reading the models directly is what
    lets a future play-with modality contribute edges without changing grouping,
    validation, or the genetic operators.
    """
    return [tuple(pair) for pair in play_with_pairs] + \
           [tuple(pair) for pair in must_together_pairs]


def build_co_location_groups(edges):
    """
    Partition players into groups that must share a team, via union-find.

    Args:
        edges (iterable): pairs of player ids that must co-locate.

    Returns:
        tuple: frozensets of player ids.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for edge in edges:
        a, b = edge
        union(a, b)

    groups = {}
    for node in parent:
        groups.setdefault(find(node), set()).add(node)
    return tuple(frozenset(members) for members in groups.values())


def build_context(session_id):
    """
    Fetch everything the scorer needs using a fixed number of queries.

    Query count does not grow with league size: one pass per model regardless of
    how many players, teams, or results exist.

    Args:
        session_id (int): session being generated.

    Returns:
        LeagueContext: frozen, ready for repeated in-memory scoring.
    """
    sessions = ordered_sessions()
    current = next(s for s in sessions if s.pk == session_id)
    prior = [s for s in sessions
             if (s.year, s.session_number) < (current.year, current.session_number)]
    prior_ids = [s.pk for s in prior]

    index = {s.pk: i for i, s in enumerate(sessions)}
    current_index = index[current.pk]
    ages = {s.pk: current_index - i - 1 for i, s in enumerate(sessions) if i < current_index}

    player_sessions = tuple(
        PlayerSession.objects.filter(session_id=session_id).select_related('player'))
    rules = tuple(PlayerRule.objects.select_related('player1', 'player2'))

    historical = {}
    for team in Team.objects.filter(session_id__in=prior_ids).prefetch_related():
        historical.setdefault(team.session_id, []).append(
            frozenset(p.pk for p in team.get_players()))

    results = tuple(
        TeamResult.objects.filter(session_id__in=prior_ids).select_related(
            'skip', 'vice', 'second', 'lead'))

    play_with_pairs, problems = resolve_play_with_pairs(player_sessions)
    if problems:
        raise ValueError('; '.join(problems))

    must_together = frozenset(
        frozenset((r.player1_id, r.player2_id))
        for r in rules if r.rule_type == 'must_be_together')
    never_together = frozenset(
        frozenset((r.player1_id, r.player2_id))
        for r in rules if r.rule_type == 'never_together')

    abilities = build_ability_table(session_id)
    mean_contribution = (
        sum(max(abilities.player_contribution(pid, p) for p in POSITIONS)
            for pid in (ps.player_id for ps in player_sessions))
        / len(player_sessions)) if player_sessions else 0.0

    return LeagueContext(
        session_id=session_id,
        player_sessions=player_sessions,
        player_id_by_player_session={ps.pk: ps.player_id for ps in player_sessions},
        player_session_by_player={ps.player_id: ps.pk for ps in player_sessions},
        preference_by_player={
            ps.player_id: (ps.preferred_position1, ps.preferred_position2)
            for ps in player_sessions},
        registered_player_ids=frozenset(ps.player_id for ps in player_sessions),
        play_with_pairs=play_with_pairs,
        must_together_pairs=must_together,
        never_together_pairs=never_together,
        player_rule_weights={
            frozenset((r.player1_id, r.player2_id)): r.weight for r in rules},
        co_location_groups=build_co_location_groups(
            co_location_edges(play_with_pairs, must_together)),
        abilities=abilities,
        historical_teams=historical,
        session_ages=ages,
        team_count=team_count_for(len(player_sessions)),
        mean_contribution=mean_contribution,
    )


def team_count_for(player_count, team_size=4):
    """Number of teams needed, with 3-player teams absorbing any remainder."""
    if player_count <= 0:
        return 0
    return (player_count + team_size - 1) // team_size


# --------------------------------------------------------------------------
# individual criteria
# --------------------------------------------------------------------------

def _roster_player_ids(roster, context):
    assigned = set()
    for team in roster:
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is not None:
                assigned.add(player_id)
    return assigned


def evaluate_completeness(roster, context):
    """Proportion of registered players the roster actually places."""
    registered = len(context.registered_player_ids)
    if registered == 0:
        return 1.0
    assigned = len(_roster_player_ids(roster, context))
    missing = registered - assigned
    if missing <= 0:
        return 1.0
    if missing == 1:
        return 0.7
    if missing == 2:
        return 0.4
    return 0.0


def evaluate_position_preference(roster, context):
    """Average preference fit across every placed player."""
    placed = 0
    total = 0.0
    for team in roster:
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is None:
                continue
            total += context.prefers(player_id, position)
            placed += 1
    if placed == 0:
        return 0.0
    return total / placed


def _continuity_score(team_player_ids, prior_teams, context, exempt_play_with):
    """Best (lowest overlap) match against any prior team."""
    best_overlap = 0
    for prior in prior_teams:
        common = team_player_ids & prior
        overlap = len(common)
        if exempt_play_with and overlap == 2:
            pair = frozenset(common)
            if any(frozenset(pair) == pw for pw in context.play_with_pairs):
                overlap = 1
        best_overlap = max(best_overlap, overlap)
    return best_overlap


def _overlap_to_score(overlap):
    if overlap <= 1:
        return 1.0
    if overlap == 2:
        return 0.66
    if overlap == 3:
        return 0.33
    return 0.0


def evaluate_team_continuity(roster, context, session_lookback=1,
                             exempt_play_with=True):
    """Per-team penalty for repeating prior teammates."""
    age = context.session_ages
    target_age = session_lookback - 1
    target_sessions = [pk for pk, a in age.items() if a == target_age]
    prior_teams = []
    for session_pk in target_sessions:
        prior_teams.extend(context.historical_teams.get(session_pk, []))

    if not prior_teams:
        return [1.0] * len(roster)

    scores = []
    for team in roster:
        ids = set()
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is not None:
                ids.add(player_id)
        scores.append(_overlap_to_score(
            _continuity_score(ids, prior_teams, context, exempt_play_with)))
    return scores


def evaluate_folded_continuity(roster, context):
    """Continuity across lookbacks, with older sessions weighted less."""
    parts = []
    for lookback, weight in zip(CONTINUITY_LOOKBACKS, CONTINUITY_LOOKBACK_WEIGHTS):
        scores = evaluate_team_continuity(roster, context, lookback)
        parts.append((weight, fmean(scores) if scores else 1.0))
    total_weight = sum(w for w, _ in parts)
    return sum(w * v for w, v in parts) / total_weight


def evaluate_plays_with_adherence(roster, context):
    """Per-team score for keeping declared partners together."""
    scores = []
    for team in roster:
        ids = set()
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is not None:
                ids.add(player_id)
        score = 1.0
        for pair in context.play_with_pairs:
            # Each unmet pair penalises once, not once per member.
            if not pair <= ids:
                score *= 0.5
        scores.append(score)
    return scores


def evaluate_player_rules(roster, context):
    """Per-team score for PlayerRule compliance."""
    scores = []
    for team in roster:
        ids = set()
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is not None:
                ids.add(player_id)
        score = 1.0
        for pair in context.never_together_pairs:
            if pair <= ids:
                score *= (1.0 - _rule_weight(pair, context))
        for pair in context.must_together_pairs:
            if pair <= ids:
                continue
            if len(pair & ids) == 1:
                score *= (1.0 - _rule_weight(pair, context))
        scores.append(score)
    return scores


def _rule_weight(pair, context):
    """Configured weight for a rule, defaulting to full severity."""
    return context.player_rule_weights.get(pair, 1.0)


def evaluate_team_balance(roster, context):
    """
    Evenness of team strength across the roster.

    Uses the coefficient of variation of team strength: standard deviation over
    mean. CV is scale-invariant, so the score does not depend on the absolute
    range of abilities in the league.
    """
    strengths = [team_strength(team, context) for team in roster]
    if len(strengths) < 2:
        return 1.0
    mean = fmean(strengths)
    if mean <= 0:
        return 0.0
    variance = fmean([(s - mean) ** 2 for s in strengths])
    cv = variance ** 0.5 / mean
    return max(0.0, 1.0 - cv)


def team_strength(team, context):
    """Sum of each player's positional contribution at their assigned position."""
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
# composite
# --------------------------------------------------------------------------

def collect_violations(roster, context):
    """Specific unmet constraints, so a low score can be explained."""
    violations = []
    for index, team in enumerate(roster):
        ids = set()
        for position in POSITIONS:
            value = team.get(position)
            if value is None:
                continue
            player_id = context.player_id(value)
            if player_id is not None:
                ids.add(player_id)
        for pair in context.play_with_pairs:
            if not pair <= ids:
                violations.append(
                    f'Team {index + 1}: play-with pair {sorted(pair)} split across teams')
        for pair in context.never_together_pairs:
            if pair <= ids:
                violations.append(f'Team {index + 1}: never-together rule violated {sorted(pair)}')
        for pair in context.must_together_pairs:
            if len(pair & ids) == 1:
                violations.append(f'Team {index + 1}: must-be-together rule violated {sorted(pair)}')
    missing = context.registered_player_ids - _roster_player_ids(roster, context)
    if missing:
        violations.append(f'Unassigned players: {sorted(missing)}')
    return violations


def evaluate_roster(roster, context, weights=None):
    """
    Score one roster.

    Returns a dict of per-criterion scores, a clamped weighted-mean composite,
    and the specific constraint violations present.
    """
    weights = weights or CRITERION_WEIGHTS
    criteria = {
        'completeness': evaluate_completeness(roster, context),
        'position_preference': evaluate_position_preference(roster, context),
        'team_continuity': evaluate_folded_continuity(roster, context),
        'plays_with_adherence': fmean(
            evaluate_plays_with_adherence(roster, context) or [1.0]),
        'player_rules': fmean(evaluate_player_rules(roster, context) or [1.0]),
        'team_balance': evaluate_team_balance(roster, context),
    }

    clamped = {k: max(CRITERION_FLOOR, min(1.0, v)) for k, v in criteria.items()}
    total_weight = sum(weights.get(k, 1.0) for k in clamped)
    composite = sum(clamped[k] * weights.get(k, 1.0) for k in clamped) / total_weight

    return {
        'composite': composite,
        'criteria': criteria,
        'violations': collect_violations(roster, context),
    }


def evaluate_rosters(rosters, context, weights=None):
    """Score several rosters, best first."""
    scored = [evaluate_roster(r, context, weights) | {'roster': r} for r in rosters]
    scored.sort(key=lambda r: r['composite'], reverse=True)
    return scored
"""
Player strength rating for the v2 roster builder.

Turns raw league data -- stated years curled and historical team results -- into
a 0..1 ability rating per player per position, and a positional contribution
used for team balancing.

All database access lives in the query helpers near the bottom. The rating
functions themselves take already-fetched records so the genetic algorithm can
evaluate thousands of candidate rosters without touching the database.
"""

import math
from statistics import median

from .models import Player, PlayerSession, Session, TeamResult

POSITIONS = ('Skip', 'Vice', 'Second', 'Lead')

# How much each position influences the team's outcome. Skip calls the game and
# sets shot percentages, so their contribution carries the most weight; Lead has
# the least influence on the final score.
#
# These encode ordinal importance, not measured magnitudes. They are deliberately
# coarse: a player's contribution is ability * influence, so a promotion from
# Vice to Skip only pays off when the player holds up at Skip.
POSITION_INFLUENCE = {
    'Skip': 1.00,
    'Vice': 0.85,
    'Second': 0.75,
    'Lead': 0.70,
}

# Model field name for each position. Positions are capitalised throughout the
# generation code (they mirror the v1 roster dict keys), while the TeamResult
# and Team columns are lower-case Django fields.
POSITION_FIELD = {
    'Skip': 'skip',
    'Vice': 'vice',
    'Second': 'second',
    'Lead': 'lead',
}

# Experience saturates rather than growing linearly: the gap between a novice
# and a beginner matters far more than the gap between an experienced club
# curler and a veteran. k controls where the curve flattens.
EXPERIENCE_K = 4.0

# Recent results count more than older ones. The most recent prior session gets
# weight 1.0, the one before it DECAY_FACTOR, and so on.
DECAY_FACTOR = 0.7

# Strength of the prior that pulls sparse results toward stated experience,
# as a multiple of the median number of games in a session. Scaling by the
# median rather than using a fixed count keeps shrinkage consistent across
# leagues that play different numbers of games per session.
SHRINKAGE_FRACTION = 0.5

def experience_score(years_curled, k=EXPERIENCE_K):
    """
    Stated experience as a 0..1 score on a saturating curve.

        experience_score(0) = 0.0
        experience_score(1) = 0.22
        experience_score(3) = 0.53
        experience_score(10) = 0.92

    Args:
        years_curled (int): years the player has been curling.
        k (float): curve constant; larger means slower saturation.

    Returns:
        float: score in [0, 1].
    """
    if years_curled is None or years_curled < 0:
        return 0.0
    if k <= 0:
        raise ValueError('k must be positive')
    return min(1.0, max(0.0, 1.0 - math.exp(-years_curled / k)))


def position_influence(position):
    """Influence weight for a position. Unrecognised positions get 0.0."""
    return POSITION_INFLUENCE.get(position, 0.0)


def ordered_sessions(sessions=None):
    """
    All sessions ordered chronologically by (year, session_number).

    Ordering by the pair rather than session_number alone is what makes
    cross-year decay correct: Session 3 of the previous year is one step before
    Session 1 of this year, not the same distance as Session 3 of this year.
    """
    if sessions is None:
        sessions = list(Session.objects.all())
    return sorted(sessions, key=lambda s: (s.year, s.session_number))


def session_ages(current_session, all_sessions=None):
    """
    Age of each prior session relative to the current one.

    The most recent prior session has age 0 (full weight); the one before it has
    age 1, and so on. Returns a mapping of session id to age.
    """
    if all_sessions is None:
        all_sessions = ordered_sessions()
    order = {s.pk: i for i, s in enumerate(all_sessions)}
    current_index = order.get(current_session.pk)
    if current_index is None:
        raise ValueError(f'Session {current_session} is not in the supplied session list')

    ages = {}
    for session in all_sessions:
        index = order[session.pk]
        distance = current_index - index
        if 0 < distance:
            ages[session.pk] = distance - 1
    return ages


def decay_weight(age, decay_factor=DECAY_FACTOR):
    """Weight for a result of the given age. Age 0 weighs 1.0."""
    if age < 0:
        raise ValueError('age must not be negative')
    return decay_factor ** age


def shrinkage_prior(games_per_session, fraction=SHRINKAGE_FRACTION):
    """
    Prior strength in games, scaled to what a session's worth of evidence is
    for this league.

    Returns 0.0 when no games have been recorded, in which case ability falls
    back entirely to stated experience.
    """
    if not games_per_session:
        return 0.0
    return fraction * games_per_session


def position_ability(years_curled, observations, prior_games=0.0):
    """
    Ability at one position, blending observed results with stated experience.

    Observations are (weight, win_rate, games) triples, where weight comes from
    time decay. Rather than falling back to experience only when no results
    exist -- which would treat a single 8-0 season as fully reliable -- the
    observed rate is shrunk toward the experience expectation in proportion to
    how little history there is.

        ability = (n * win_rate + m * experience_score) / (n + m)

    where n is the weighted game count and m the prior strength in games.

    Args:
        years_curled (int): stated experience for this player.
        observations (list): (weight, win_rate, games) per prior session.
        prior_games (float): m, the prior strength in games.

    Returns:
        float: ability in [0, 1].
    """
    expectation = experience_score(years_curled)

    weighted_games = sum(weight * games for weight, _, games in observations)
    weighted_wins = sum(weight * win_rate * games for weight, win_rate, games in observations)

    if weighted_games <= 0:
        return expectation

    # A zero prior means "trust the observations fully", which is the correct
    # reading of m=0 -- not "ignore the observations".
    numerator = weighted_wins + prior_games * expectation
    denominator = weighted_games + prior_games
    if denominator <= 0:
        return expectation
    return min(1.0, max(0.0, numerator / denominator))


def contribution(ability, position):
    """
    What a player adds to a team at a given position.

    This is what makes a promotion priceable: a player strong at Vice and weak
    at Skip contributes more at Vice, so the engine only moves them up when the
    balance gain elsewhere outweighs the drop.
    """
    return ability * position_influence(position)


def team_strength(team, ability_table):
    """
    Total strength of a team: the sum of each player's contribution at the
    position they occupy.

    Args:
        team (dict): maps position to PlayerSession id (or None).
        ability_table (AbilityTable): precomputed ratings.

    Returns:
        float: summed strength across filled positions.
    """
    total = 0.0
    for position in POSITIONS:
        player_session_id = team.get(position)
        if player_session_id is None:
            continue
        player_id = ability_table.player_id_for(player_session_id)
        if player_id is None:
            continue
        total += ability_table.player_contribution(player_id, position)
    return total


def median_games_per_session():
    """Median games per session across recorded results, or None if none exist."""
    totals = [result.games for result in TeamResult.objects.all() if result.games > 0]
    if not totals:
        return None
    return median(totals)


class AbilityTable:
    """
    Ability and contribution lookups for every player at every position.

    Ratings are precomputed once per generation run and read many times by the
    genetic algorithm, so lookups are plain dict access with no database calls.
    """

    def __init__(self, player_sessions, results, current_session, decay_factor=DECAY_FACTOR,
                 shrinkage_fraction=SHRINKAGE_FRACTION, all_sessions=None):
        """
        Args:
            player_sessions (list): PlayerSession records for the session.
            results (list): TeamResult records across all sessions.
            current_session (Session): session being generated.
            decay_factor (float): time decay for older results.
            shrinkage_fraction (float): prior strength as a multiple of median games.
            all_sessions (list): sessions for ordering; queried if omitted.
        """
        self._player_id_by_player_session = {
            ps.pk: ps.player_id for ps in player_sessions
        }
        self._player_by_player_session = {
            ps.pk: ps.player_id for ps in player_sessions
        }
        self._player_ids = [ps.player_id for ps in player_sessions]
        self._years_curled = {ps.player_id: ps.years_curled for ps in player_sessions}

        self._current_session = current_session
        self._decay_factor = decay_factor
        self._shrinkage_fraction = shrinkage_fraction

        sessions = all_sessions if all_sessions is not None else ordered_sessions()
        self._ages = _ages_excluding(current_session, sessions)

        self._results_by_session = {}
        for result in results:
            self._results_by_session.setdefault(result.session_id, []).append(result)

        games = [r.games for r in results if r.games > 0]
        self._median_games = median(games) if games else None
        self._prior_games = shrinkage_prior(self._median_games, shrinkage_fraction)

        self._abilities = {}
        self._contributions = {}
        self._observations = {}
        for player_id in self._player_ids:
            for position in POSITIONS:
                observations = self._observations_for(player_id, position)
                self._observations[(player_id, position)] = observations
                ability = position_ability(
                    self._years_curled.get(player_id), observations, self._prior_games)
                self._abilities[(player_id, position)] = ability
                self._contributions[(player_id, position)] = contribution(ability, position)

    @property
    def prior_games(self):
        return self._prior_games

    @property
    def median_games(self):
        return self._median_games

    def ability(self, player_id, position):
        return self._abilities.get((player_id, position), 0.0)

    def player_contribution(self, player_id, position):
        return self._contributions.get((player_id, position), 0.0)

    def observations(self, player_id, position):
        """(weight, win_rate, games) triples backing this player's ability."""
        return self._observations.get((player_id, position), [])

    def player_id_for(self, player_session_id):
        return self._player_id_by_player_session.get(player_session_id)

    def player_ids(self):
        return list(self._player_ids)

    def _observations_for(self, player_id, position):
        """Time-decayed (weight, win_rate, games) for one player at one position."""
        observations = []
        for session_id, age in self._ages.items():
            weight = decay_weight(age, self._decay_factor)
            for result in self._results_by_session.get(session_id, []):
                player = getattr(result, POSITION_FIELD[position], None)
                if player is None or player.pk != player_id:
                    continue
                win_rate = result.win_rate
                if win_rate is None or result.games <= 0:
                    continue
                observations.append((weight, win_rate, result.games))
        return observations


def _ages_excluding(current_session, sessions):
    """Age of every session strictly before the current one."""
    order = {s.pk: i for i, s in enumerate(sessions)}
    current_index = order.get(current_session.pk)
    if current_index is None:
        raise ValueError(f'Session {current_session} is not in the supplied session list')
    return {
        s.pk: current_index - i - 1
        for i, s in enumerate(sessions)
        if i < current_index
    }


def build_ability_table(session_id, decay_factor=DECAY_FACTOR,
                        shrinkage_fraction=SHRINKAGE_FRACTION):
    """
    Precompute ability and contribution for every player in a session.

    Runs a fixed handful of queries regardless of league size.

    Args:
        session_id (int): session being generated.

    Returns:
        AbilityTable: ratings for every registered player at every position.
    """
    sessions = ordered_sessions()
    current_session = next(s for s in sessions if s.pk == session_id)

    player_sessions = list(
        PlayerSession.objects.filter(session_id=session_id).select_related('player'))

    prior_ids = [s.pk for s in sessions if (s.year, s.session_number)
                 < (current_session.year, current_session.session_number)]
    results = list(
        TeamResult.objects.filter(session_id__in=prior_ids).select_related(
            'skip', 'vice', 'second', 'lead'))

    return AbilityTable(
        player_sessions=player_sessions,
        results=results,
        current_session=current_session,
        decay_factor=decay_factor,
        shrinkage_fraction=shrinkage_fraction,
        all_sessions=sessions,
    )
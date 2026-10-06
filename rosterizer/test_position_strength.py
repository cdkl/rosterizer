import math

import pytest

from .models import Player, PlayerSession, Session, Team, TeamResult
from .position_strength import (
    DECAY_FACTOR,
    POSITION_INFLUENCE,
    SHRINKAGE_FRACTION,
    build_ability_table,
    contribution,
    decay_weight,
    experience_score,
    median_games_per_session,
    ordered_sessions,
    position_ability,
    session_ages,
    shrinkage_prior,
    team_strength,
)


# --------------------------------------------------------------------------
# 2.1 experience curve
# --------------------------------------------------------------------------

def test_experience_score_at_documented_points():
    assert experience_score(0) == pytest.approx(0.0)
    assert experience_score(1) == pytest.approx(0.2212, abs=1e-3)
    assert experience_score(2) == pytest.approx(0.3935, abs=1e-3)
    assert experience_score(3) == pytest.approx(0.5276, abs=1e-3)
    assert experience_score(5) == pytest.approx(0.7135, abs=1e-3)
    assert experience_score(10) == pytest.approx(0.9179, abs=1e-3)
    assert experience_score(20) == pytest.approx(0.9933, abs=1e-3)


def test_experience_score_stays_in_unit_range():
    for years in [0, 1, 5, 25, 60, 200]:
        assert 0.0 <= experience_score(years) <= 1.0


def test_experience_score_is_monotonic():
    scores = [experience_score(y) for y in range(0, 30)]
    assert scores == sorted(scores)


def test_experience_gain_diminishes_over_time():
    early = experience_score(3) - experience_score(1)
    late = experience_score(20) - experience_score(15)
    assert late < early


def test_experience_score_treats_negative_as_zero():
    assert experience_score(-5) == 0.0
    assert experience_score(None) == 0.0


def test_experience_score_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        experience_score(5, k=0)


# --------------------------------------------------------------------------
# 2.2 session ordering and age
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_sessions_ordered_across_year_boundary():
    s = [
        Session.objects.create(year=2025, session_number=2),
        Session.objects.create(year=2024, session_number=3),
        Session.objects.create(year=2025, session_number=1),
        Session.objects.create(year=2024, session_number=1),
    ]
    order = [(x.year, x.session_number) for x in ordered_sessions(s)]
    assert order == [(2024, 1), (2024, 3), (2025, 1), (2025, 2)]


@pytest.mark.django_db
def test_session_ages_count_real_distance():
    sessions = ordered_sessions([
        Session.objects.create(year=2024, session_number=3),
        Session.objects.create(year=2025, session_number=1),
        Session.objects.create(year=2025, session_number=2),
    ])
    current = sessions[-1]
    ages = session_ages(current, all_sessions=sessions)
    # sessions[1] is the immediately preceding session (age 0, full weight);
    # sessions[0] is one step further back (age 1).
    assert ages[sessions[1].pk] == 0
    assert ages[sessions[0].pk] == 1


@pytest.mark.django_db
def test_cross_year_result_is_older_than_within_year_result():
    """Session 3 of last year precedes Session 2 of this year."""
    sessions = ordered_sessions([
        Session.objects.create(year=2024, session_number=3),
        Session.objects.create(year=2025, session_number=2),
    ])
    current, last_year = sessions[1], sessions[0]
    ages = session_ages(current, all_sessions=sessions)
    assert ages[last_year.pk] == 0, 'the immediately preceding session has age 0'
    assert decay_weight(ages[last_year.pk]) > decay_weight(1)


def test_decay_weight_age_zero_is_full_weight():
    assert decay_weight(0) == 1.0
    assert decay_weight(1) == pytest.approx(DECAY_FACTOR)
    assert decay_weight(2) == pytest.approx(DECAY_FACTOR ** 2)
    assert decay_weight(2) < decay_weight(1) < decay_weight(0)


def test_decay_weight_rejects_negative_age():
    with pytest.raises(ValueError):
        decay_weight(-1)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def players(db):
    return [Player.objects.create(first_name=f'P{i}', last_name='X') for i in range(8)]


@pytest.fixture
def prior_session(db):
    return Session.objects.create(year=2024, session_number=1)


@pytest.fixture
def current_session(db, prior_session):
    return Session.objects.create(year=2025, session_number=1)


def make_player_sessions(session, players, years=10):
    """Create PlayerSessions and return them in the same order as `players`."""
    out = []
    for i, player in enumerate(players):
        out.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=years,
            preferred_position1='Skip' if i % 4 == 0 else '',
            preferred_position2='',
            play_with=''))
    return out


# --------------------------------------------------------------------------
# 2.3 median games per session
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_median_games_none_when_no_results(db):
    assert median_games_per_session() is None


@pytest.mark.django_db
def test_median_games_across_sessions(db, players):
    s1 = Session.objects.create(year=2024, session_number=1)
    s2 = Session.objects.create(year=2024, session_number=2)
    TeamResult.objects.create(session=s1, team_number=1, wins=4, losses=4)   # 8
    TeamResult.objects.create(session=s1, team_number=2, wins=6, losses=2)   # 8
    TeamResult.objects.create(session=s2, team_number=1, wins=3, losses=3)   # 6

    assert median_games_per_session() == 8


@pytest.mark.django_db
def test_median_games_ignores_zero_game_results(db):
    s = Session.objects.create(year=2024, session_number=1)
    TeamResult.objects.create(session=s, team_number=1, wins=0, losses=0)
    TeamResult.objects.create(session=s, team_number=2, wins=5, losses=3)
    assert median_games_per_session() == 8


def test_shrinkage_prior_scales_with_median():
    assert shrinkage_prior(10) == pytest.approx(10 * SHRINKAGE_FRACTION)
    assert shrinkage_prior(None) == 0.0
    assert shrinkage_prior(0) == 0.0


# --------------------------------------------------------------------------
# 2.4 position ability
# --------------------------------------------------------------------------

def test_ability_with_no_history_is_experience():
    assert position_ability(10, [], prior_games=5.0) == pytest.approx(experience_score(10))
    assert position_ability(10, [], prior_games=0.0) == pytest.approx(experience_score(10))


def test_ability_with_sparse_history_sits_between_expectation_and_observation():
    expectation = experience_score(5)
    observations = [(1.0, 1.0, 4)]        # 4 undefeated games
    ability = position_ability(5, observations, prior_games=8.0)
    assert expectation < ability < 1.0
    # Closer to expectation than to the raw observation, since history is thin.
    assert (ability - expectation) < (1.0 - ability)


def test_ability_with_substantial_history_approaches_observation():
    observations = [(1.0, 0.9, 40)]
    ability = position_ability(5, observations, prior_games=4.0)
    assert ability == pytest.approx(0.9, abs=0.05)


def test_ability_applies_time_decay_to_older_results():
    """A recent result must pull harder than an equally-sized older one."""
    years = 0
    # Most recent session undefeated (age 0, weight 1.0), the session before it
    # winless (age 1, weight 0.7). The recent win must win.
    observations = [(1.0, 1.0, 4), (0.7, 0.0, 4)]
    assert position_ability(years, observations, prior_games=0.0) > 0.5

    # Mirror image: recent loss, older win. The recent loss must dominate.
    observations = [(1.0, 0.0, 4), (0.7, 1.0, 4)]
    assert position_ability(years, observations, prior_games=0.0) < 0.5


def test_ability_is_bounded():
    observations = [(1.0, 1.0, 1000)]
    assert position_ability(50, observations, prior_games=1.0) <= 1.0
    observations = [(1.0, 0.0, 1000)]
    assert position_ability(0, observations, prior_games=1.0) >= 0.0


@pytest.mark.django_db
def test_ability_table_reads_results_for_the_played_position(db, players, prior_session, current_session):
    make_player_sessions(current_session, players, years=10)
    winner, loser = players[0], players[1]
    TeamResult.objects.create(session=prior_session, team_number=1,
                              skip=winner, wins=9, losses=1)

    table = build_ability_table(current_session.pk)

    # 9-1 is a 0.9 win rate; the experience prior is ~0.918, so the shrunk
    # result lands between the two and closer to the observation.
    expected = experience_score(10)
    skip_ability = table.ability(winner.pk, 'Skip')
    assert 0.9 < skip_ability < expected
    # A player with no results at this position gets the expectation exactly.
    assert table.ability(loser.pk, 'Skip') == pytest.approx(expected)


@pytest.mark.django_db
def test_ability_is_position_specific(db, players, prior_session, current_session):
    make_player_sessions(current_session, players, years=2)
    star = players[0]
    TeamResult.objects.create(session=prior_session, team_number=1,
                              skip=star, wins=9, losses=1)
    table = build_ability_table(current_session.pk)

    # Results at Skip must not leak into Lead, which has no history and so
    # falls back to the experience expectation.
    assert table.ability(star.pk, 'Skip') > table.ability(star.pk, 'Lead')
    assert table.ability(star.pk, 'Lead') == pytest.approx(experience_score(2))


@pytest.mark.django_db
def test_ability_ignores_results_from_the_current_session(db, players, current_session):
    """A session's own results are not yet evidence about its players."""
    make_player_sessions(current_session, players, years=10)
    TeamResult.objects.create(session=current_session, team_number=1,
                              skip=players[0], wins=9, losses=1)  # same session, must be ignored
    table = build_ability_table(current_session.pk)
    assert table.ability(players[0].pk, 'Skip') == pytest.approx(experience_score(10))


@pytest.mark.django_db
def test_ties_reduce_observed_win_rate(db, players, prior_session, current_session):
    make_player_sessions(current_session, players, years=0)
    p = players[0]
    TeamResult.objects.create(session=prior_session, team_number=1,
                              skip=p, wins=0, losses=0, ties=8)
    table = build_ability_table(current_session.pk, shrinkage_fraction=0.0)
    # 8 ties -> win rate 0.5, not 1.0
    assert table.ability(p.pk, 'Skip') == pytest.approx(0.5)


def _ability_in_league(players, games_per_session):
    """Ability for a player with a .500 record in a league of the given size.

    Isolated per test so the global median-games figure reflects one league.
    """
    prior = Session.objects.create(year=2030, session_number=1)
    cur = Session.objects.create(year=2031, session_number=1)
    ps = [PlayerSession.objects.create(
        player=pl, session=cur, years_curled=0,
        preferred_position1='', preferred_position2='', play_with='')
        for pl in players]
    wins = games_per_session // 2
    TeamResult.objects.create(session=prior, team_number=1,
                              skip=ps[0].player, wins=wins,
                              losses=games_per_session - wins)
    return build_ability_table(cur.pk).ability(ps[0].player_id, 'Skip')


@pytest.mark.django_db
def test_shrinkage_is_proportional_in_small_league(db, players):
    # 4 games at .500, prior 2 games at .000 -> (2 + 0) / 6 = 1/3
    assert _ability_in_league(players, 4) == pytest.approx(1 / 3, abs=1e-6)


@pytest.mark.django_db
def test_shrinkage_is_proportional_in_large_league(db, players):
    # 20 games at .500, prior 10 games at .000 -> (10 + 0) / 30 = 1/3
    assert _ability_in_league(players, 20) == pytest.approx(1 / 3, abs=1e-6)


def test_shrinkage_result_is_format_independent():
    """A fixed game-count prior would trust these two seasons differently."""
    small_prior, small_games = 0.5 * 4, 4
    large_prior, large_games = 0.5 * 20, 20
    small = (small_games * 0.5 + small_prior * 0.0) / (small_games + small_prior)
    large = (large_games * 0.5 + large_prior * 0.0) / (large_games + large_prior)
    assert small == pytest.approx(large, abs=1e-9)


# --------------------------------------------------------------------------
# 2.5 build_player_abilities
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_table_covers_every_player_and_position(db, players, current_session):
    make_player_sessions(current_session, players)
    table = build_ability_table(current_session.pk)

    assert sorted(table.player_ids()) == sorted(p.pk for p in players)
    for player_id in table.player_ids():
        for position in POSITION_INFLUENCE:
            assert 0.0 <= table.ability(player_id, position) <= 1.0
            assert 0.0 <= table.player_contribution(player_id, position) <= 1.0


@pytest.mark.django_db
def test_table_without_results_uses_experience_alone(db, players, current_session):
    make_player_sessions(current_session, players, years=7)
    table = build_ability_table(current_session.pk)

    assert table.prior_games == 0.0
    assert table.median_games is None
    for player_id in table.player_ids():
        assert table.ability(player_id, 'Skip') == pytest.approx(experience_score(7))


# --------------------------------------------------------------------------
# contribution and team strength (Decision 7)
# --------------------------------------------------------------------------

def test_influence_descends_from_skip_to_lead():
    assert POSITION_INFLUENCE['Skip'] > POSITION_INFLUENCE['Vice']
    assert POSITION_INFLUENCE['Vice'] > POSITION_INFLUENCE['Second']
    assert POSITION_INFLUENCE['Second'] > POSITION_INFLUENCE['Lead']


def test_same_ability_worth_more_at_higher_influence_position():
    at_skip = contribution(0.8, 'Skip')
    at_lead = contribution(0.8, 'Lead')
    assert at_skip > at_lead


def test_promotion_priced_against_ability_loss():
    """Strong Vice, weak Skip: keeping them at Vice yields more."""
    at_vice = contribution(0.8, 'Vice')
    at_skip = contribution(0.6, 'Skip')
    assert at_vice > at_skip


def test_unknown_position_has_no_influence():
    assert contribution(0.9, 'Fifth') == 0.0


@pytest.mark.django_db
def test_team_strength_sums_contributions(db, players, current_session):
    make_player_sessions(current_session, players, years=10)
    table = build_ability_table(current_session.pk)
    team_sessions = list(PlayerSession.objects.filter(session=current_session).order_by('pk'))

    team = {'Skip': team_sessions[0].pk, 'Vice': team_sessions[1].pk,
            'Second': team_sessions[2].pk, 'Lead': team_sessions[3].pk}
    expected = sum(table.player_contribution(
        table.player_id_for(ps_id), pos) for pos, ps_id in team.items())
    assert team_strength(team, table) == pytest.approx(expected)


@pytest.mark.django_db
def test_team_strength_skips_empty_positions(db, players, current_session):
    make_player_sessions(current_session, players, years=10)
    table = build_ability_table(current_session.pk)
    team_sessions = list(PlayerSession.objects.filter(session=current_session).order_by('pk'))

    team = {'Skip': team_sessions[0].pk, 'Vice': team_sessions[1].pk,
            'Second': team_sessions[2].pk, 'Lead': None}
    assert team_strength(team, table) == pytest.approx(
        contribution(table.ability(team_sessions[0].player_id, 'Skip'), 'Skip')
        + contribution(table.ability(team_sessions[1].player_id, 'Vice'), 'Vice')
        + contribution(table.ability(team_sessions[2].player_id, 'Second'), 'Second'))
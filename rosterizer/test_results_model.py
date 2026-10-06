import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from .models import Player, PlayerSession, Session, Team, TeamResult


@pytest.fixture
def players(db):
    return [
        Player.objects.create(first_name=f'Player{i}', last_name='Test')
        for i in range(8)
    ]


@pytest.fixture
def session(db):
    return Session.objects.create(year=2025, session_number=1)


@pytest.fixture
def committed_session(session):
    session.results_committed = True
    session.save()
    return session


def test_result_stores_own_roster_composition(session, players):
    result = TeamResult.objects.create(
        session=session,
        team_number=1,
        skip=players[0], vice=players[1], second=players[2], lead=players[3],
        wins=5, losses=3, ties=0)

    assert result.session == session
    assert result.get_players() == players[0:4]
    assert result.games == 8
    assert result.win_rate == pytest.approx(0.625)


def test_duplicate_session_team_number_rejected(session, players):
    TeamResult.objects.create(session=session, team_number=1, wins=4, losses=4)
    with pytest.raises(IntegrityError):
        TeamResult.objects.create(session=session, team_number=1, wins=2, losses=6)


def test_same_team_number_allowed_across_sessions(db, players):
    s1 = Session.objects.create(year=2024, session_number=3)
    s2 = Session.objects.create(year=2025, session_number=3)

    TeamResult.objects.create(session=s1, team_number=1, wins=5, losses=3)
    TeamResult.objects.create(session=s2, team_number=1, wins=6, losses=2)

    assert TeamResult.objects.filter(team_number=1).count() == 2


def test_deleting_session_with_results_blocked(committed_session, players):
    TeamResult.objects.create(session=committed_session, team_number=1, wins=4, losses=4)

    with pytest.raises(ProtectedError):
        committed_session.delete()


def test_deleting_player_with_results_blocked(committed_session, players):
    TeamResult.objects.create(
        session=committed_session, team_number=1, skip=players[0], wins=4, losses=4)

    with pytest.raises(ProtectedError):
        players[0].delete()


def test_clearing_teams_does_not_delete_results(committed_session, players):
    Team.objects.create(session=committed_session, team_number=1,
                        skip=players[0], vice=players[1], second=players[2], lead=players[3])
    TeamResult.objects.create(
        session=committed_session, team_number=1,
        skip=players[0], vice=players[1], second=players[2], lead=players[3],
        wins=5, losses=3)

    Team.objects.filter(session=committed_session).delete()

    result = TeamResult.objects.get(session=committed_session, team_number=1)
    assert result.get_players() == players[0:4]
    assert result.win_rate == pytest.approx(0.625)


def test_results_survive_regenerated_teams_with_reused_numbers(session, players):
    """Team rows are volatile; a recorded result must stay bound to its own roster."""
    Team.objects.create(session=session, team_number=1,
                        skip=players[0], vice=players[1], second=players[2], lead=players[3])
    TeamResult.objects.create(
        session=session, team_number=1,
        skip=players[0], vice=players[1], second=players[2], lead=players[3],
        wins=5, losses=3)

    # Clear and regenerate: same team number, entirely different lineup.
    Team.objects.filter(session=session).delete()
    Team.objects.create(session=session, team_number=1,
                        skip=players[4], vice=players[5], second=players[6], lead=players[7])

    result = TeamResult.objects.get(session=session, team_number=1)
    assert result.get_players() == players[0:4], 'result reattached to the wrong lineup'


def test_ties_count_as_half_a_win(session):
    # 4W + 2L + 2T over 8 games: (4 + 0.5*2) / 8 = 5/8 = 0.625
    result = TeamResult.objects.create(session=session, team_number=1, wins=4, losses=2, ties=2)
    assert result.games == 8
    assert result.win_rate == pytest.approx(0.625)


def test_win_rate_none_when_no_games(session):
    assert TeamResult.objects.create(session=session, team_number=1).win_rate is None


def test_partial_team_result_tolerates_missing_positions(session, players):
    result = TeamResult.objects.create(session=session, team_number=1, skip=players[0], wins=3, losses=1)
    assert result.get_players() == [players[0]]
    assert result.lead is None


def test_results_committed_defaults_false(session):
    assert session.results_committed is False


def test_deleting_session_without_results_allowed(db):
    session = Session.objects.create(year=2025, session_number=9)
    session.delete()
    assert not Session.objects.filter(pk=session.pk).exists()
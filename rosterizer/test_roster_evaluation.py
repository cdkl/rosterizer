import pytest

from rosterizer.models import Player, PlayerSession, Session, Team
from .roster_evaluation import evaluate_completeness, evaluate_incomplete_teams, evaluate_team_continuity

def generate_test_roster(players):
    '''Generate a test roster from the Mock PlayerSession objects'''
    roster = []
    teams = {}
    for player in players:
        if player.team.pk not in teams:
            teams[player.team.pk] = []
        teams[player.team.pk].append(player.pk)

    for team_players in teams.values():
        team = {}
        for i, position in enumerate(POSITIONS()):
            if i < len(team_players):
                team[position] = team_players[i]
            else:
                team[position] = None
        roster.append(team)
    return roster

def POSITIONS():
    return ['Skip', 'Vice', 'Second', 'Lead']

@pytest.fixture
def mock_player_session(monkeypatch):
    class MockQuerySet:
        def __init__(self, players):
            self.players = players

        def exclude(self, pk):
            return MockQuerySet([player for player in self.players if player.pk != pk])

        def filter(self, **kwargs):
            return MockQuerySet([player for player in self.players if all(getattr(player, k) == v for k, v in kwargs.items())])

        def get(self, pk):
            for player in self.players:
                if player.pk == pk:
                    return player
            raise ValueError("Player not found")

        def exists(self):
            return bool(self.players)

        def __len__(self):
            return len(self.players)

        def __iter__(self):
            return iter(self.players)

    class MockPlayer:
        def __init__(self, pk):
            self.pk = pk

    class MockTeam:
        def __init__(self, pk):
            self.pk = pk

    class MockPlayerSession:
        def __init__(self, pk, session_id, player, team):
            self.pk = pk
            self.session_id = session_id
            self.player = player
            self.team = team

    players_store = {'current': [], 'previous': []}

    def mock_filter(session_id):
        if session_id == 1:
            return MockQuerySet(players_store['current'])
        elif session_id == 0:
            return MockQuerySet(players_store['previous'])

    monkeypatch.setattr('rosterizer.models.PlayerSession.objects.filter', mock_filter)
    monkeypatch.setattr('rosterizer.models.PlayerSession.objects.get', lambda pk: MockPlayerSession(pk, 1, MockPlayer(pk), MockTeam(pk)))
    monkeypatch.setattr('rosterizer.models.Team.objects.get', lambda pk: MockTeam(pk))
    monkeypatch.setattr('rosterizer.roster_evaluation.get_previous_session', lambda session_id: 0 if session_id == 1 else None)
    return players_store, MockPlayerSession, MockPlayer, MockTeam

def test_evaluate_completeness_no_players(mock_player_session):
    players_store, _, _, _ = mock_player_session
    players_store['current'] = []
    roster = [{'Skip': None, 'Vice': None, 'Second': None, 'Lead': None}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 1.0

def test_evaluate_completeness_one_player(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), MockPlayerSession(5, 1, None, None)]
    roster = [{'Skip': 1, 'Vice': 2, 'Second': 3, 'Lead': 4}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.7

def test_evaluate_completeness_two_players(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), 
                                MockPlayerSession(5, 1, None, None), MockPlayerSession(6, 1, None, None)]
    roster = [{'Skip': 2, 'Vice': 3, 'Second': 4, 'Lead': 5}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.4

def test_evaluate_completeness_more_than_two_players(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), 
                                MockPlayerSession(5, 1, None, None), MockPlayerSession(6, 1, None, None), MockPlayerSession(7, 1, None, None)]
    roster = [{'Skip': 1, 'Vice': 3, 'Second': 4, 'Lead': 7}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.0

def test_evaluate_incomplete_teams_one_critical_team(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), MockPlayerSession(5, 1, None, None)]
    roster = [
        {'Skip': None, 'Vice': None, 'Second': 4, 'Lead': 5}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 0

def test_evaluate_incomplete_teams_one_incomplete_team(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), MockPlayerSession(5, 1, None, None)]
    roster = [
        {'Skip': 3, 'Vice': 2, 'Second': 4, 'Lead': None}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 0.9

def test_evaluate_incomplete_teams_no_incomplete_teams(mock_player_session):
    players_store, MockPlayerSession, _, _ = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, None, None), MockPlayerSession(2, 1, None, None), MockPlayerSession(3, 1, None, None), MockPlayerSession(4, 1, None, None), MockPlayerSession(5, 1, None, None)]
    roster = [
        {'Skip': 3, 'Vice': 2, 'Second': 4, 'Lead': 5}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 1.0

def test_evaluate_team_continuity_no_previous_session(mock_player_session):
    players_store, _, _, _ = mock_player_session
    players_store['current'] = [mock_player_session[1](1, 0, mock_player_session[2](1), mock_player_session[3](1)), 
                                mock_player_session[1](2, 0, mock_player_session[2](2), mock_player_session[3](2))]
    roster = [{'Skip': 1, 'Vice': 2, 'Second': None, 'Lead': None}]
    session_id = 0
    assert evaluate_team_continuity(roster, session_id) == [1.0]

@pytest.fixture
def default_sessions():
    previous_session = Session.objects.create(pk=1, year=2020, session_number=1)
    current_session= Session.objects.create(pk=2, year=2020, session_number=2)
    return [previous_session, current_session]

@pytest.fixture
def default_players(default_sessions):
    players = [
        Player.objects.create(pk=i) for i in range(1, 9)
    ]
    # Create PlayerSession entries
    for i, player in enumerate(players[:8]):
        PlayerSession.objects.create(pk=player.pk, session_id=default_sessions[1].pk, player=player, years_curled=1)

    return players

@pytest.mark.django_db
def test_evaluate_team_continuity_no_players_together(default_sessions, default_players):

    # Create mock players and teams
    team1 = Team.objects.create(pk=1, team_number=1, session=default_sessions[0], 
                                skip=default_players[0], vice=default_players[1], second=default_players[2], lead=default_players[3])

    roster = [{'Skip': 5, 'Vice': 6, 'Second': 7, 'Lead': 8 }]

    assert evaluate_team_continuity(roster, default_sessions[1].pk) == [1.0]

@pytest.mark.django_db
def test_evaluate_team_continuity_two_players_together(default_sessions, default_players):
    team1 = Team.objects.create(pk=1, team_number=1, session=default_sessions[0],
                                skip=default_players[0], vice=default_players[1], second=default_players[2], lead=default_players[3])
    
    roster = [{'Skip': 1, 'Vice': 2, 'Second': 5, 'Lead': 6}]
    assert evaluate_team_continuity(roster, default_sessions[1].pk) == [0.66]

@pytest.mark.django_db
def test_evaluate_team_continuity_three_players_together(default_sessions, default_players):
    team1 = Team.objects.create(pk=1, team_number=1, session=default_sessions[0],
                                skip=default_players[0], vice=default_players[1], second=default_players[2], lead=default_players[3])
    
    roster = [{'Skip': 1, 'Vice': 2, 'Second': 4, 'Lead': 6}]
    assert evaluate_team_continuity(roster, default_sessions[1].pk) == [0.33]

@pytest.mark.django_db
def test_evaluate_team_continuity_all_players_together(default_sessions, default_players):
    team1 = Team.objects.create(pk=1, team_number=1, session=default_sessions[0],
                                skip=default_players[0], vice=default_players[1], second=default_players[2], lead=default_players[3])
    
    roster = [{'Skip': 1, 'Vice': 2, 'Second': 4, 'Lead': 3}]
    assert evaluate_team_continuity(roster, default_sessions[1].pk) == [0]

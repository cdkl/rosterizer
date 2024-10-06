import pytest
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

def test_evaluate_team_continuity_no_players_together(mock_player_session):
    players_store, MockPlayerSession, MockPlayer, MockTeam = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, MockPlayer(1), MockTeam(1)), MockPlayerSession(2, 1, MockPlayer(2), MockTeam(1)), 
                                MockPlayerSession(3, 1, MockPlayer(3), MockTeam(1)), MockPlayerSession(4, 1, MockPlayer(4), MockTeam(1))]
    players_store['previous'] = [MockPlayerSession(5, 0, MockPlayer(5), MockTeam(2)), MockPlayerSession(6, 0, MockPlayer(6), MockTeam(2)), 
                                 MockPlayerSession(7, 0, MockPlayer(7), MockTeam(2)), MockPlayerSession(8, 0, MockPlayer(8), MockTeam(2))]
    roster = generate_test_roster(players_store['current'])
    session_id = 1
    assert evaluate_team_continuity(roster, session_id) == [1.0]

def test_evaluate_team_continuity_two_players_together(mock_player_session):
    players_store, MockPlayerSession, MockPlayer, MockTeam = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, MockPlayer(1), MockTeam(1)), MockPlayerSession(2, 1, MockPlayer(2), MockTeam(1)), 
                                MockPlayerSession(3, 1, MockPlayer(3), MockTeam(1)), MockPlayerSession(4, 1, MockPlayer(4), MockTeam(1))]
    players_store['previous'] = [MockPlayerSession(1, 0, MockPlayer(1), MockTeam(2)), MockPlayerSession(2, 0, MockPlayer(2), MockTeam(2)), 
                                 MockPlayerSession(5, 0, MockPlayer(5), MockTeam(3)), MockPlayerSession(6, 0, MockPlayer(6), MockTeam(3))]
    roster = generate_test_roster(players_store['current'])
    session_id = 1
    assert evaluate_team_continuity(roster, session_id) == [0.66]

def test_evaluate_team_continuity_three_players_together(mock_player_session):
    players_store, MockPlayerSession, MockPlayer, MockTeam = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, MockPlayer(1), MockTeam(1)), MockPlayerSession(2, 1, MockPlayer(2), MockTeam(1)), 
                                MockPlayerSession(3, 1, MockPlayer(3), MockTeam(1)), MockPlayerSession(4, 1, MockPlayer(4), MockTeam(1))]
    players_store['previous'] = [MockPlayerSession(1, 0, MockPlayer(1), MockTeam(2)), MockPlayerSession(2, 0, MockPlayer(2), MockTeam(2)), 
                                 MockPlayerSession(3, 0, MockPlayer(3), MockTeam(2)), MockPlayerSession(5, 0, MockPlayer(5), MockTeam(3))]
    roster = generate_test_roster(players_store['current'])
    session_id = 1
    assert evaluate_team_continuity(roster, session_id) == [0.33]

def test_evaluate_team_continuity_all_players_together(mock_player_session):
    players_store, MockPlayerSession, MockPlayer, MockTeam = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, MockPlayer(1), MockTeam(1)), MockPlayerSession(2, 1, MockPlayer(2), MockTeam(1)), 
                                MockPlayerSession(3, 1, MockPlayer(3), MockTeam(1)), MockPlayerSession(4, 1, MockPlayer(4), MockTeam(1))]
    players_store['previous'] = [MockPlayerSession(1, 0, MockPlayer(1), MockTeam(2)), MockPlayerSession(2, 0, MockPlayer(2), MockTeam(2)), 
                                 MockPlayerSession(3, 0, MockPlayer(3), MockTeam(2)), MockPlayerSession(4, 0, MockPlayer(4), MockTeam(2))]
    roster = generate_test_roster(players_store['current'])
    session_id = 1
    assert evaluate_team_continuity(roster, session_id) == [0.0]

def test_evaluate_team_continuity_one_team_none_together_one_team_three_together(mock_player_session):
    players_store, MockPlayerSession, MockPlayer, MockTeam = mock_player_session
    players_store['current'] = [MockPlayerSession(1, 1, MockPlayer(1), MockTeam(1)), MockPlayerSession(2, 1, MockPlayer(2), MockTeam(1)), 
                                MockPlayerSession(3, 1, MockPlayer(3), MockTeam(1)), MockPlayerSession(4, 1, MockPlayer(4), MockTeam(1)),
                                MockPlayerSession(5, 1, MockPlayer(5), MockTeam(2)), MockPlayerSession(6, 1, MockPlayer(6), MockTeam(2)), 
                                MockPlayerSession(7, 1, MockPlayer(7), MockTeam(2)), MockPlayerSession(8, 1, MockPlayer(8), MockTeam(2)),
                                MockPlayerSession(9, 1, MockPlayer(9), MockTeam(3)), MockPlayerSession(10, 1, MockPlayer(10), MockTeam(3)),
                                MockPlayerSession(11, 1, MockPlayer(11), MockTeam(3)), MockPlayerSession(12, 1, MockPlayer(12), MockTeam(3)),
                                MockPlayerSession(13, 1, MockPlayer(13), MockTeam(4)), MockPlayerSession(14, 1, MockPlayer(14), MockTeam(4)),
                                MockPlayerSession(15, 1, MockPlayer(15), MockTeam(4)), MockPlayerSession(16, 1, MockPlayer(16), MockTeam(4))]
    players_store['previous'] = [MockPlayerSession(1, 0, MockPlayer(1), MockTeam(3)), MockPlayerSession(5, 0, MockPlayer(5), MockTeam(3)), 
                                 MockPlayerSession(9, 0, MockPlayer(9), MockTeam(3)), MockPlayerSession(13, 0, MockPlayer(13), MockTeam(3)),
                                 MockPlayerSession(2, 0, MockPlayer(2), MockTeam(4)), MockPlayerSession(3, 0, MockPlayer(3), MockTeam(4)), 
                                 MockPlayerSession(4, 0, MockPlayer(4), MockTeam(4)), MockPlayerSession(8, 0, MockPlayer(8), MockTeam(4))]
    roster = generate_test_roster(players_store['current'])
    session_id = 1
    assert evaluate_team_continuity(roster, session_id) == [0.33, 1.0, 1.0, 1.0]


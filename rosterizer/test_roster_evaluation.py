import pytest
from .roster_evaluation import evaluate_completeness, evaluate_incomplete_teams

@pytest.fixture
def mock_player_session(monkeypatch):
    class MockQuerySet:
        def __init__(self, players):
            self.players = players

        def exclude(self, pk):
            return MockQuerySet([player for player in self.players if player.pk != pk])

        def __len__(self):
            return len(self.players)

    class MockPlayerSession:
        def __init__(self, pk):
            self.pk = pk

    players_store = {'players': []}

    def mock_filter(session_id):
        return MockQuerySet(players_store['players'])

    monkeypatch.setattr('rosterizer.models.PlayerSession.objects.filter', mock_filter)
    return players_store, MockPlayerSession

def test_evaluate_completeness_no_players(mock_player_session):
    players_store, _ = mock_player_session
    players_store['players'] = []
    roster = [{'Skip': None, 'Vice': None, 'Second': None, 'Lead': None}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 1.0

def test_evaluate_completeness_one_player(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), MockPlayerSession(5)]
    roster = [{'Skip': 1, 'Vice': 2, 'Second': 3, 'Lead': 4}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.7

def test_evaluate_completeness_two_players(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), 
                                MockPlayerSession(5), MockPlayerSession(6)]
    roster = [{'Skip': 2, 'Vice': 3, 'Second': 4, 'Lead': 5}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.4

def test_evaluate_completeness_more_than_two_players(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), 
                                MockPlayerSession(5), MockPlayerSession(6), MockPlayerSession(7)]
    roster = [{'Skip': 1, 'Vice': 3, 'Second': 4, 'Lead': 7}]
    session_id = 1
    assert evaluate_completeness(roster, session_id) == 0.0

def test_evaluate_incomplete_teams_one_critical_team(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), MockPlayerSession(5)]
    roster = [
        {'Skip': None, 'Vice': None, 'Second': 4, 'Lead': 5}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 0

def test_evaluate_incomplete_teams_one_incomplete_team(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), MockPlayerSession(5)]
    roster = [
        {'Skip': 3, 'Vice': 2, 'Second': 4, 'Lead': None}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 0.9

def test_evaluate_incomplete_teams_no_incomplete_teams(mock_player_session):
    players_store, MockPlayerSession = mock_player_session
    players_store['players'] = [MockPlayerSession(1), MockPlayerSession(2), MockPlayerSession(3), MockPlayerSession(4), MockPlayerSession(5)]
    roster = [
        {'Skip': 3, 'Vice': 2, 'Second': 4, 'Lead': 5}
    ]
    session_id = 1
    assert evaluate_incomplete_teams(roster, session_id) == 1.0


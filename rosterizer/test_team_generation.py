import json
import pytest
from .team_generation import generate_multiple_rosters, generate_team_assignments, generate_teams_for_session, hydrate_rosters, set_team_player
from .team_generation import select_player_for_position
from .models import Player, PlayerSessionDecoder, PlayerSessionEncoder, Session, PlayerSession, Team
from django.core import serializers

@pytest.fixture
def players():
    player1 = Player(first_name='John', last_name='Doe')
    player2 = Player(first_name='Jane', last_name='Smith')
    player3 = Player(first_name='Bob', last_name='Jones')
    player4 = Player(first_name='Alice', last_name='Johnson')
    player5 = Player(first_name='Charlie', last_name='Brown')
    player6 = Player(first_name='David', last_name='White')
    player7 = Player(first_name='Eve', last_name='Black')
    player8 = Player(first_name='Frank', last_name='Green')
    return [player1, player2, player3, player4, player5, player6, player7, player8]

@pytest.fixture
def session():
    return Session(year=2024, session_number=1)

@pytest.fixture
def player_sessions_rich(players, session):
    player_session1 = PlayerSession(pk=1, player=players[0], session=session, years_curled=5, preferred_position1='Skip', preferred_position2='Vice', play_with='Jane Smith')
    player_session2 = PlayerSession(pk=2, player=players[1], session=session, years_curled=10, preferred_position1='Vice', preferred_position2='Skip', play_with='John Doe')
    player_session3 = PlayerSession(pk=3, player=players[2], session=session, years_curled=15, preferred_position1='Second', preferred_position2='Lead', play_with='Alice Johnson')
    player_session4 = PlayerSession(pk=4, player=players[3], session=session, years_curled=20, preferred_position1='Lead', preferred_position2='Second', play_with='Bob Jones')
    player_session5 = PlayerSession(pk=5, player=players[4], session=session, years_curled=25, preferred_position1='Skip', preferred_position2='Vice', play_with='David white')
    player_session6 = PlayerSession(pk=6, player=players[5], session=session, years_curled=30, preferred_position1='Vice', preferred_position2='Skip', play_with='Charie Brown')
    player_session7 = PlayerSession(pk=7, player=players[6], session=session, years_curled=35, preferred_position1='Second', preferred_position2='Lead', play_with='Frank Green')
    player_session8 = PlayerSession(pk=8, player=players[7], session=session, years_curled=40, preferred_position1='Lead', preferred_position2='Second', play_with='Eve Black')
    return [player_session1, player_session2, player_session3, player_session4, player_session5, player_session6, player_session7, player_session8]

@pytest.fixture
def player_sessions_sparse(players, session):
    player_session1 = PlayerSession(pk=1, player=players[0], session=session, years_curled=5, preferred_position1='Skip', preferred_position2='', play_with='')
    player_session2 = PlayerSession(pk=2, player=players[1], session=session, years_curled=10, preferred_position1='Vice', preferred_position2='', play_with='Eve Black')
    player_session3 = PlayerSession(pk=3, player=players[2], session=session, years_curled=15, preferred_position1='Second', preferred_position2='', play_with='')
    player_session4 = PlayerSession(pk=4, player=players[3], session=session, years_curled=20, preferred_position1='Lead', preferred_position2='', play_with='')
    player_session5 = PlayerSession(pk=5, player=players[4], session=session, years_curled=25, preferred_position1='', preferred_position2='Skip', play_with='')
    player_session6 = PlayerSession(pk=6, player=players[5], session=session, years_curled=30, preferred_position1='', preferred_position2='Vice', play_with='')
    player_session7 = PlayerSession(pk=7, player=players[6], session=session, years_curled=35, preferred_position1='', preferred_position2='Second', play_with='Jane Smith')
    player_session8 = PlayerSession(pk=8, player=players[7], session=session, years_curled=40, preferred_position1='', preferred_position2='Lead', play_with='')
    return [player_session1, player_session2, player_session3, player_session4, player_session5, player_session6, player_session7, player_session8] 

@pytest.mark.django_db
def test_roster_serialization(players, player_sessions_rich, session):
    for p in players: p.save()
    session.save()
    for ps in player_sessions_rich: ps.save()

    rosters = generate_team_assignments(player_sessions_rich)
    rosters_json = json.dumps(rosters)
      #serializers.serialize('json', rosters)

    new_rosters = json.loads(rosters_json)
    assert new_rosters == rosters

def test_select_player_for_position(player_sessions_rich, player_sessions_sparse):
    assert select_player_for_position('Skip', player_sessions_rich) in {player_sessions_rich[0], player_sessions_rich[4]}
    assert select_player_for_position('Vice', player_sessions_rich) in {player_sessions_rich[1], player_sessions_rich[5]}
    assert select_player_for_position('Second', player_sessions_rich) in {player_sessions_rich[2], player_sessions_rich[6]}
    assert select_player_for_position('Lead', player_sessions_rich) in {player_sessions_rich[3], player_sessions_rich[7]}

    assert select_player_for_position('Skip', player_sessions_sparse) == player_sessions_sparse[0]
    assert select_player_for_position('Vice', player_sessions_sparse) == player_sessions_sparse[1]
    assert select_player_for_position('Second', player_sessions_sparse) == player_sessions_sparse[2]
    assert select_player_for_position('Lead', player_sessions_sparse) == player_sessions_sparse[3]

    assert select_player_for_position('Skip', player_sessions_sparse[4:]) == player_sessions_sparse[4]
    assert select_player_for_position('Vice', player_sessions_sparse[4:]) == player_sessions_sparse[5]
    assert select_player_for_position('Second', player_sessions_sparse[4:]) == player_sessions_sparse[6]
    assert select_player_for_position('Lead', player_sessions_sparse[4:]) == player_sessions_sparse[7]

    assert select_player_for_position('Skip', []) == None
    assert select_player_for_position('Vice', []) == None
    assert select_player_for_position('Second', []) == None
    assert select_player_for_position('Lead', []) == None

def test_set_team_player(player_sessions_rich):
    team = {'Skip': None, 'Vice': None, 'Second': None, 'Lead': None}
    player_sessions = player_sessions_rich.copy()

    set_team_player(team, 'Skip', player_sessions_rich[0], player_sessions)
    assert team['Skip'] == player_sessions_rich[0].pk
    assert team['Skip'] not in player_sessions
    set_team_player(team, 'Vice', player_sessions_rich[1], player_sessions)
    assert team['Vice'] == player_sessions_rich[1].pk
    assert team['Vice'] not in player_sessions
    set_team_player(team, 'Second', player_sessions_rich[2], player_sessions)
    assert team['Second'] == player_sessions_rich[2].pk
    assert team['Second'] not in player_sessions
    set_team_player(team, 'Lead', player_sessions_rich[3], player_sessions)
    assert team['Lead'] == player_sessions_rich[3].pk
    assert team['Lead'] not in player_sessions

@pytest.mark.django_db
def test_generate_team_assignments(players, player_sessions_sparse, session):
    for p in players: p.save()
    session.save()
    for ps in player_sessions_sparse: ps.save()

    player_sessions = player_sessions_sparse.copy()
    teams = generate_team_assignments(player_sessions, False)
    assert len(teams) == 2
    assert teams[0]['Skip'] == player_sessions_sparse[0].pk
    assert teams[0]['Vice'] == player_sessions_sparse[1].pk
    assert teams[0]['Second'] == player_sessions_sparse[2].pk
    assert teams[0]['Lead'] == player_sessions_sparse[3].pk
    assert teams[1]['Skip'] == player_sessions_sparse[4].pk
    assert teams[1]['Vice'] == player_sessions_sparse[5].pk
    assert teams[1]['Second'] == player_sessions_sparse[6].pk
    assert teams[1]['Lead'] == player_sessions_sparse[7].pk
    assert player_sessions == []

    player_sessions = player_sessions_sparse.copy()
    teams = generate_team_assignments(player_sessions, True)
    assert len(teams) == 2
    assert teams[0]['Skip'] == player_sessions_sparse[0].pk
    assert teams[0]['Vice'] == player_sessions_sparse[1].pk
    assert teams[0]['Second'] == player_sessions_sparse[6].pk
    assert teams[0]['Lead'] == player_sessions_sparse[3].pk
    assert teams[1]['Skip'] == player_sessions_sparse[4].pk
    assert teams[1]['Vice'] == player_sessions_sparse[5].pk
    assert teams[1]['Second'] == player_sessions_sparse[2].pk
    assert teams[1]['Lead'] == player_sessions_sparse[7].pk
    assert player_sessions == []

@pytest.mark.django_db
def test_generate_teams_for_session(players, player_sessions_sparse, session):
    for p in players: p.save()
    session.save()
    for ps in player_sessions_sparse: ps.save()

    generate_teams_for_session(session.id, use_play_with=True)
    assert Team.objects.count() == 2
    assert Team.objects.filter(session=session).count() == 2
    team1 = Team.objects.filter(session=session)[0]
    team2 = Team.objects.filter(session=session)[1]
    assert team1.skip == player_sessions_sparse[0].player
    assert team1.vice == player_sessions_sparse[1].player
    assert team1.second == player_sessions_sparse[6].player
    assert team1.lead == player_sessions_sparse[3].player
    assert team2.skip == player_sessions_sparse[4].player
    assert team2.vice == player_sessions_sparse[5].player
    assert team2.second == player_sessions_sparse[2].player
    assert team2.lead == player_sessions_sparse[7].player

@pytest.mark.django_db
def test_hydrate_rosters(players, player_sessions_sparse, session):
    for p in players: p.save()
    session.save()
    for ps in player_sessions_sparse: ps.save()

    rosters = generate_multiple_rosters(session.pk, 2, False)
    hydrated_rosters = hydrate_rosters(rosters)
    assert len(hydrated_rosters) == 2
    assert hydrated_rosters[0][0]['Skip'] == player_sessions_sparse[0]
    assert hydrated_rosters[0][0]['Vice'] == player_sessions_sparse[1]
    assert hydrated_rosters[0][0]['Second'] == player_sessions_sparse[2]
    assert hydrated_rosters[0][0]['Lead'] == player_sessions_sparse[3]
    assert hydrated_rosters[1][1]['Skip'] == player_sessions_sparse[4]
    assert hydrated_rosters[1][1]['Vice'] == player_sessions_sparse[5]
    assert hydrated_rosters[1][1]['Second'] == player_sessions_sparse[6]
    assert hydrated_rosters[1][1]['Lead'] == player_sessions_sparse[7]



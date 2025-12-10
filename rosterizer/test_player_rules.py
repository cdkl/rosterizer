import pytest
from rosterizer.models import Player, PlayerSession, Session, Team, PlayerRule
from rosterizer.roster_evaluation import evaluate_player_rules, evaluate_rosters


@pytest.fixture
def test_session():
    """Create a test session"""
    session = Session.objects.create(year=2024, session_number=1)
    return session


@pytest.fixture
def test_players():
    """Create test players"""
    players = []
    for i in range(1, 9):
        player = Player.objects.create(
            first_name=f"Player{i}",
            last_name=f"Last{i}"
        )
        players.append(player)
    return players


@pytest.fixture
def test_player_sessions(test_session, test_players):
    """Create player sessions for the test session"""
    player_sessions = []
    for player in test_players:
        ps = PlayerSession.objects.create(
            player=player,
            session=test_session,
            years_curled=1,
            preferred_position1='Skip',
            preferred_position2='Vice',
            play_with=''
        )
        player_sessions.append(ps)
    return player_sessions


@pytest.mark.django_db
def test_player_rule_model_creation(test_players):
    """Test creating a player rule"""
    rule = PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0,
        notes='Test rule'
    )
    
    assert rule.rule_type == 'never_together'
    assert rule.player1 == test_players[0]
    assert rule.player2 == test_players[1]
    assert rule.weight == 1.0
    assert rule.notes == 'Test rule'
    assert str(rule) == f"{test_players[0].full_name} and {test_players[1].full_name} - Never Together"


@pytest.mark.django_db
def test_evaluate_player_rules_no_rules(test_session, test_player_sessions):
    """Test evaluation with no rules defined"""
    roster = [
        {
            'Skip': test_player_sessions[0].pk,
            'Vice': test_player_sessions[1].pk,
            'Second': test_player_sessions[2].pk,
            'Lead': test_player_sessions[3].pk
        },
        {
            'Skip': test_player_sessions[4].pk,
            'Vice': test_player_sessions[5].pk,
            'Second': test_player_sessions[6].pk,
            'Lead': test_player_sessions[7].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # With no rules, all teams should get perfect score
    assert len(scores) == 2
    assert scores[0] == 1.0
    assert scores[1] == 1.0


@pytest.mark.django_db
def test_evaluate_player_rules_never_together_violation(test_session, test_player_sessions, test_players):
    """Test never_together rule with a violation"""
    # Create rule: player 0 and player 1 should never be together
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,  # player 0
            'Vice': test_player_sessions[1].pk,  # player 1 - VIOLATION!
            'Second': test_player_sessions[2].pk,
            'Lead': test_player_sessions[3].pk
        },
        {
            'Skip': test_player_sessions[4].pk,
            'Vice': test_player_sessions[5].pk,
            'Second': test_player_sessions[6].pk,
            'Lead': test_player_sessions[7].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # First team has violation, should score 0.0 (1.0 - 1.0)
    # Second team has no violation, should score 1.0
    assert scores[0] == 0.0
    assert scores[1] == 1.0


@pytest.mark.django_db
def test_evaluate_player_rules_never_together_no_violation(test_session, test_player_sessions, test_players):
    """Test never_together rule without violation"""
    # Create rule: player 0 and player 1 should never be together
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,  # player 0
            'Vice': test_player_sessions[2].pk,  # player 2 - no violation
            'Second': test_player_sessions[3].pk,
            'Lead': test_player_sessions[4].pk
        },
        {
            'Skip': test_player_sessions[1].pk,  # player 1 on different team
            'Vice': test_player_sessions[5].pk,
            'Second': test_player_sessions[6].pk,
            'Lead': test_player_sessions[7].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # Both teams should have perfect scores
    assert scores[0] == 1.0
    assert scores[1] == 1.0


@pytest.mark.django_db
def test_evaluate_player_rules_weighted_penalty(test_session, test_player_sessions, test_players):
    """Test rule with custom weight (soft constraint)"""
    # Create rule with 0.5 weight (soft preference)
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=0.5
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,
            'Vice': test_player_sessions[1].pk,  # Violation with 0.5 weight
            'Second': test_player_sessions[2].pk,
            'Lead': test_player_sessions[3].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # Score should be 0.5 (1.0 - 0.5)
    assert scores[0] == 0.5


@pytest.mark.django_db
def test_evaluate_player_rules_multiple_violations(test_session, test_player_sessions, test_players):
    """Test multiple rule violations on same team"""
    # Create two rules
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=0.5
    )
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[2],
        player2=test_players[3],
        weight=0.5
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,  # player 0
            'Vice': test_player_sessions[1].pk,  # player 1 - violation 1
            'Second': test_player_sessions[2].pk,  # player 2
            'Lead': test_player_sessions[3].pk  # player 3 - violation 2
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # Score should be (1.0 - 0.5) * (1.0 - 0.5) = 0.25
    assert scores[0] == 0.25


@pytest.mark.django_db
def test_evaluate_player_rules_must_be_together_satisfied(test_session, test_player_sessions, test_players):
    """Test must_be_together rule when satisfied"""
    # Create must_be_together rule
    PlayerRule.objects.create(
        rule_type='must_be_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,  # player 0
            'Vice': test_player_sessions[1].pk,  # player 1 - together, good!
            'Second': test_player_sessions[2].pk,
            'Lead': test_player_sessions[3].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # Both players together, rule satisfied
    assert scores[0] == 1.0


@pytest.mark.django_db
def test_evaluate_player_rules_must_be_together_violated(test_session, test_player_sessions, test_players):
    """Test must_be_together rule when violated"""
    # Create must_be_together rule
    PlayerRule.objects.create(
        rule_type='must_be_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,  # player 0
            'Vice': test_player_sessions[2].pk,  # not player 1
            'Second': test_player_sessions[3].pk,
            'Lead': test_player_sessions[4].pk
        },
        {
            'Skip': test_player_sessions[1].pk,  # player 1 on different team - VIOLATION
            'Vice': test_player_sessions[5].pk,
            'Second': test_player_sessions[6].pk,
            'Lead': test_player_sessions[7].pk
        }
    ]
    
    scores = evaluate_player_rules(roster, test_session.pk)
    
    # Both teams have one player from the pair, both get penalty
    assert scores[0] == 0.0
    assert scores[1] == 0.0


@pytest.mark.django_db
def test_evaluate_rosters_integration(test_session, test_player_sessions, test_players):
    """Test that player rules are integrated into overall roster evaluation"""
    # Create a never_together rule
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    roster = [
        {
            'Skip': test_player_sessions[0].pk,
            'Vice': test_player_sessions[1].pk,  # Violation
            'Second': test_player_sessions[2].pk,
            'Lead': test_player_sessions[3].pk
        },
        {
            'Skip': test_player_sessions[4].pk,
            'Vice': test_player_sessions[5].pk,
            'Second': test_player_sessions[6].pk,
            'Lead': test_player_sessions[7].pk
        }
    ]
    
    roster_scores = evaluate_rosters([roster], test_session.pk)
    
    # Check that player_rules key exists in the result
    assert 'player_rules' in roster_scores[0]
    # Check that it contains scores for both teams
    assert len(roster_scores[0]['player_rules']) == 2
    # First team should have violation (score 0.0)
    assert roster_scores[0]['player_rules'][0] == 0.0
    # Second team should be clean (score 1.0)
    assert roster_scores[0]['player_rules'][1] == 1.0


@pytest.mark.django_db
def test_player_rule_unique_constraint(test_players):
    """Test that duplicate rules are prevented"""
    PlayerRule.objects.create(
        rule_type='never_together',
        player1=test_players[0],
        player2=test_players[1],
        weight=1.0
    )
    
    # Try to create duplicate rule
    with pytest.raises(Exception):  # Will raise IntegrityError
        PlayerRule.objects.create(
            rule_type='never_together',
            player1=test_players[0],
            player2=test_players[1],
            weight=0.5
        )

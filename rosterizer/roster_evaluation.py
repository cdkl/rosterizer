from statistics import fmean
from rosterizer.models import PlayerSession, Team
from .utilities import get_previous_session

def evaluate_rosters(rosters, session_id):
    # Calculate a score for each roster
    roster_scores = [{'score': 0} for _ in range(len(rosters))]
    for i, roster in enumerate(rosters):
        roster_scores[i]['completeness'] = evaluate_completeness(roster, session_id)
        roster_scores[i]['incomplete_teams'] = evaluate_incomplete_teams(roster, session_id)
        roster_scores[i]['position_preference'] = evaluate_position_preference(roster, session_id)
        roster_scores[i]['team_continuity_1'] = evaluate_team_continuity(roster, session_id, exempt_plays_with=True, session_lookback=1)
        roster_scores[i]['team_continuity_2'] = evaluate_team_continuity(roster, session_id, exempt_plays_with=True, session_lookback=2)
        roster_scores[i]['team_continuity_3'] = evaluate_team_continuity(roster, session_id, exempt_plays_with=True, session_lookback=3)
        roster_scores[i]['score'] = (roster_scores[i]['completeness'] * 
                                     roster_scores[i]['incomplete_teams'] * 
                                     roster_scores[i]['position_preference'] * 
                                     fmean(roster_scores[i]['team_continuity_1']) *
                                     (0.33 + fmean(roster_scores[i]['team_continuity_2'])*.67) * # weaken the effect of team continuity 2
                                     (0.67 + fmean(roster_scores[i]['team_continuity_3'])*.33))  # weaken the effect of team continuity 3 even more
    
    # Return the evaluated rosters
    return roster_scores 

def evaluate_completeness(roster, session_id):
    # Evaluate the completeness of a roster
    player_sessions = PlayerSession.objects.filter(session_id=session_id)
    for team in roster:
        for player_session_id in team.values():
            if player_session_id:
                player_sessions = player_sessions.exclude(pk=player_session_id)

    if( len(player_sessions) == 0):
        return 1.0
    elif( len(player_sessions) == 1):
        return 0.7
    elif( len(player_sessions) == 2):
        return 0.4
    else:
        return 0.0

def evaluate_incomplete_teams(roster, session_id):
    # Evaluate the number of incomplete teams in a roster
    incomplete_teams = 0
    critical_teams = 0
    for team in roster:
        position_count = sum(team[position] is not None for position in ['Skip', 'Vice', 'Second', 'Lead'])
        if position_count < 3:
            critical_teams += 1
        if position_count < 4:
            incomplete_teams += 1

    score = 1.0
    if critical_teams > 0:
        score = 0.0
    elif incomplete_teams > 3:
        score = 0.5
    elif incomplete_teams > 0:
        score = 1.0 - (incomplete_teams * 0.1)

    return score

def evaluate_position_preference(roster, session_id):
    # Evaluate the position preference of players in a roster
    player_sessions = PlayerSession.objects.filter(session_id=session_id)
    preference_score = 0
    for team in roster:
        for position, player_session_id in team.items():
            if player_session_id:
                player_session = player_sessions.get(pk=player_session_id)
                if player_session.preferred_position1 == position:
                    preference_score += 1
                elif player_session.preferred_position2 == position:
                    preference_score += 0.5
                elif player_session.preferred_position1 not in ('Skip', 'Vice', 'Second', 'Lead') and player_session.preferred_position2 not in ('Skip', 'Vice', 'Second', 'Lead'):
                    preference_score += 1

    player_count = len(player_sessions)
    total_preference = preference_score / player_count
    return total_preference

def evaluate_team_continuity(roster, session_id, exempt_plays_with=False, session_lookback=1):
    previous_session = get_previous_session(session_id=session_id, session_lookback=session_lookback)
    if previous_session is None:
        return [1.0] * len(roster)  # If no previous session, all teams get a score of 1.0

    current_player_sessions = PlayerSession.objects.filter(session_id=session_id)

    previous_teams_pk = []
    for team in Team.objects.filter(session_id=previous_session.pk):
        player_pks = [player.pk for player in team.get_players()]
        previous_teams_pk.append(frozenset(player_pks))

    team_scores = []

    for team in roster:
        current_team_players = set()
        current_team_players_pk = set()
        for player_session_id in team.values():
            if player_session_id is not None:
                if exempt_plays_with:
                    # only add the player to the compare list if their play with partner isn't already there -they count only as 1
                    player_session = PlayerSession.objects.get(pk=player_session_id)
                    if any(player_session.play_with in p.full_name for p in current_team_players):
                        continue
                player = PlayerSession.objects.get(pk=player_session_id).player
                current_team_players.add(player)
                current_team_players_pk.add(player.pk)

        max_players_together = 0
        for previous_team_players_pk in previous_teams_pk:
            players_together = len(current_team_players_pk & previous_team_players_pk)
            if players_together > max_players_together:
                max_players_together = players_together

        if max_players_together <= 1:
            score = 1.0
        elif max_players_together == 2:
            score = 0.66
        elif max_players_together == 3:
            score = 0.33
        else:
            score = 0.0

        team_scores.append(score)

    return team_scores

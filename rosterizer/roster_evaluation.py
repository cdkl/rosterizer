from rosterizer.models import PlayerSession

def evaluate_rosters(rosters, session_id):
    # Calculate a score for each roster
    roster_scores = [{'score': 0} for _ in range(len(rosters))]
    for i, roster in enumerate(rosters):
        roster_scores[i]['completeness'] = evaluate_completeness(roster, session_id)
        roster_scores[i]['incomplete_teams'] = evaluate_incomplete_teams(roster, session_id)
        roster_scores[i]['position_preference'] = evaluate_position_preference(roster, session_id)
        roster_scores[i]['score'] = roster_scores[i]['completeness'] * roster_scores[i]['incomplete_teams'] * roster_scores[i]['position_preference']
    
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

# your_app/team_generation.py

import logging
import random
from django.core import serializers
from .models import PlayerSession, Player, Team


# Generate multiple candidate rosters and return them
def generate_multiple_rosters(session_id, num_rosters=10, use_play_with=True):
    rosters = []
    player_sessions_query = PlayerSession.objects.filter(session_id=session_id)

    for _ in range(num_rosters):
        rosters.append(generate_team_assignments(list(player_sessions_query), use_play_with=use_play_with))

    return rosters

# Generate and save teams for a given session ID
def generate_teams_for_session(session_id, use_play_with=True):
    # Retrieve all PlayerSession instances for the given session ID
    player_sessions_query = PlayerSession.objects.filter(session_id=session_id)
    
    # Calculate the number of teams
    teams = generate_team_assignments(list(player_sessions_query), use_play_with=use_play_with)

    # Commit teams to the database
    apply_team_roster(session_id, teams)
    return f"Teams generated for session {session_id} with play with: {use_play_with}"

def apply_team_roster(session_id, teams):
    team_number = 1
    for team in teams:
        # Create a new Team object
        new_team = Team()
        new_team.session_id = session_id
        new_team.team_number = team_number
        team_number += 1
        skip = PlayerSession.objects.get(pk=team['Skip']) if team['Skip'] else None
        vice = PlayerSession.objects.get(pk=team['Vice']) if team['Vice'] else None
        second = PlayerSession.objects.get(pk=team['Second']) if team['Second'] else None
        lead = PlayerSession.objects.get(pk=team['Lead']) if team['Lead'] else None

        new_team.set_players_from_player_sessions(skip, vice, second, lead)

        # Save the team to the database
        new_team.save()

# Generate team assignments - this function will return a list of teams, each with a skip, vice, second, and lead
# Internal function
def generate_team_assignments(player_sessions, use_play_with=True):
    num_teams = len(player_sessions) // 4
    
    # Initialize teams
    teams = [{position: None for position in ['Skip', 'Vice', 'Second', 'Lead']} for _ in range(num_teams)]
    
    # Assign skip to teams
    for team in teams:
        if team['Skip'] is None:
            # Select a skip
            skip = select_player_for_position('Skip', player_sessions)
            if skip:
                set_team_player(team, 'Skip', skip, player_sessions)
                if use_play_with: add_play_with_players_to_team(team, player_sessions)
        if team['Skip'] is None:
            logging.warning(f'Unable to assign a skip to team {team}')
    
    # Assign vice to teams
    for team in teams:
        if team['Vice'] is None:
            # Select a vice
            vice = select_player_for_position('Vice', player_sessions)
            if vice:
                set_team_player(team, 'Vice', vice, player_sessions)
                if use_play_with: add_play_with_players_to_team(team, player_sessions)
        if team['Vice'] is None:
            logging.warning(f'Unable to assign a vice to team {team}')
        
    # Assign second to teams
    for team in teams:
        if team['Second'] is None:
            # Select a second
            second = select_player_for_position('Second', player_sessions)
            if second:
                set_team_player(team, 'Second', second, player_sessions)
                if use_play_with: add_play_with_players_to_team(team, player_sessions)
        if team['Second'] is None:
            logging.warning(f'Unable to assign a second to team {team}')

    # Assign lead to teams
    for team in teams:
        if team['Lead'] is None:
            # Select a lead
            lead = select_player_for_position('Lead', player_sessions)
            if lead:
                set_team_player(team, 'Lead', lead, player_sessions)
                if use_play_with: add_play_with_players_to_team(team, player_sessions)
        if team['Lead'] is None:
            logging.warning(f'Unable to assign a lead to team {team}')

    # at this point we should have no more player sessions to assign
    if len(player_sessions) > 0:
        logging.warning(f'Unable to assign all players to teams: {player_sessions}')
    
    return teams

# Helper function to select a player for a position
def select_player_for_position(position, player_sessions):
    candidates = [ps for ps in player_sessions if ps.preferred_position1 == position]
    if not candidates:
        candidates = [ps for ps in player_sessions if ps.preferred_position2 == position]
    if candidates:
        selected = random.choice(candidates)
        return selected
    return None

# Helper function to assign play with players to an existing team
def add_play_with_players_to_team(team, player_sessions):
    for _, team_position_player_session_id in team.items():
        team_position_player_session = PlayerSession.objects.get(pk=team_position_player_session_id) if team_position_player_session_id else None
        if team_position_player_session is not None:
            preferred_player = next((ps for ps in player_sessions if ps.player.get_full_name() == team_position_player_session.play_with), None)
            if preferred_player:
                if preferred_player.preferred_position1 and team[preferred_player.preferred_position1] is None:
                    set_team_player(team, preferred_player.preferred_position1, preferred_player, player_sessions)
                    logging.info(f"Added {team_position_player_session.player} partner {preferred_player.player} to team {team} at preferred position 1 {preferred_player.preferred_position1}")
                elif preferred_player.preferred_position2 and team[preferred_player.preferred_position2] is None:
                    set_team_player(team, preferred_player.preferred_position2, preferred_player, player_sessions)
                    logging.info(f"Added {team_position_player_session.player} partner {preferred_player.player} to team {team} at preferred position 2 {preferred_player.preferred_position2}")
                else:
                    logging.warning(f"Unable to add {preferred_player.player} to team {team} at either preferred position")

# utility function to set a player to a team position and remove the player from the list of player sessions                
def set_team_player(team, position, player_session, player_sessions):
    team[position] = player_session.id
    player_sessions.remove(player_session)
    logging.info(f"Assigned skip {player_session.player} to team {team}")

# utility function to hydrate the rosters with PlayerSession objects
def hydrate_rosters(rosters):
    hydrated_rosters = []
    for roster in rosters:
        hydrated_roster = []
        for team in roster:
            hydrated_team = {
                'Skip': PlayerSession.objects.get(pk=team['Skip']) if team['Skip'] else None,
                'Vice': PlayerSession.objects.get(pk=team['Vice']) if team['Vice'] else None,
                'Second': PlayerSession.objects.get(pk=team['Second']) if team['Second'] else None,
                'Lead': PlayerSession.objects.get(pk=team['Lead']) if team['Lead'] else None,
            }
            hydrated_roster.append(hydrated_team)
        hydrated_rosters.append(hydrated_roster)
    return hydrated_rosters


def evaluate_rosters(rosters, session_id):
    # Calculate a score for each roster
    roster_scores = [{'score': 0} for _ in range(len(rosters))]
    for i, roster in enumerate(rosters):
        roster_scores[i]['score'] = random.randint(1, 100)
    
    # Return the evaluated rosters
    return roster_scores 

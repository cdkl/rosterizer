# your_app/team_generation.py

from functools import reduce
import logging
from operator import mul
import random
from django.core import serializers

from rosterizer.roster_evaluation import evaluate_plays_with_adherence, evaluate_team_continuity
from .models import PlayerSession, Player, Team


# Generate multiple candidate rosters and return them
def generate_multiple_rosters(session_id, num_rosters=10, use_play_with=True, full_play_with_adherence=False, full_last_session_uniqueness=False):
    rosters = []
    player_sessions_query = PlayerSession.objects.filter(session_id=session_id)

    for i in range(num_rosters):
        logging.info(f'Generating roster # {i}')
        roster = generate_team_assignments(list(player_sessions_query), session_id, use_play_with=use_play_with)
        if use_play_with and full_play_with_adherence:
            team_scores = evaluate_plays_with_adherence(roster, session_id)
            if team_scores.count(1.0) < len(team_scores):
                logging.warning(f'Full play with adherence not achieved: {team_scores}')
                continue
        if full_last_session_uniqueness:
            team_scores = evaluate_team_continuity(roster, session_id, use_play_with, 1)
            total_score = reduce(mul, team_scores)
            if total_score < 0.4:
                logging.warning(f'Full team uniqueness from last session not achieved: {total_score} @ {team_scores}')
                continue

        rosters.append(roster)

    return rosters

# Generate and save teams for a given session ID
def generate_teams_for_session(session_id, use_play_with=True):
    # Retrieve all PlayerSession instances for the given session ID
    player_sessions_query = PlayerSession.objects.filter(session_id=session_id)
    
    # Calculate the number of teams
    teams = generate_team_assignments(list(player_sessions_query), session_id, use_play_with=use_play_with)

    # Commit teams to the database
    apply_team_roster(session_id, teams)
    return f"Teams generated for session {session_id} with play with: {use_play_with}"

def apply_team_roster(session_id, teams):
    # Get existing teams
    existing_teams = Team.objects.filter(session_id=session_id)
    existing_team_numbers = {team.team_number for team in existing_teams}
    
    # Find the next available team number
    team_number = 1
    while team_number in existing_team_numbers:
        team_number += 1

    # Convert existing teams to dictionary format for comparison
    existing_team_dicts = []
    for team in existing_teams:
        team_dict = {
            'Skip': team.skip.playersession_set.get(session_id=session_id).id if team.skip else None,
            'Vice': team.vice.playersession_set.get(session_id=session_id).id if team.vice else None,
            'Second': team.second.playersession_set.get(session_id=session_id).id if team.second else None,
            'Lead': team.lead.playersession_set.get(session_id=session_id).id if team.lead else None
        }
        existing_team_dicts.append(team_dict)

    # Only create teams that don't already exist
    for team in teams:
        if team not in existing_team_dicts:
            new_team = Team()
            new_team.session_id = session_id
            new_team.team_number = team_number
            team_number += 1
            
            skip = PlayerSession.objects.get(pk=team['Skip']) if team['Skip'] else None
            vice = PlayerSession.objects.get(pk=team['Vice']) if team['Vice'] else None
            second = PlayerSession.objects.get(pk=team['Second']) if team['Second'] else None
            lead = PlayerSession.objects.get(pk=team['Lead']) if team['Lead'] else None

            new_team.set_players_from_player_sessions(skip, vice, second, lead)
            new_team.save()
            logging.info(f"Created new team {new_team.team_number}")

# Generate team assignments - this function will return a list of teams, each with a skip, vice, second, and lead
# Internal function
def generate_team_assignments(player_sessions, session_id, use_play_with=True):
    # Get existing teams for this session
    existing_teams = Team.objects.filter(session_id=session_id)
    
    # Convert existing teams to the same dictionary format used for new teams
    teams = []
    max_team_number = 0
    for team in existing_teams:
        team_dict = {
            'Skip': team.skip.playersession_set.get(session_id=session_id).id if team.skip else None,
            'Vice': team.vice.playersession_set.get(session_id=session_id).id if team.vice else None,
            'Second': team.second.playersession_set.get(session_id=session_id).id if team.second else None,
            'Lead': team.lead.playersession_set.get(session_id=session_id).id if team.lead else None
        }
        teams.append(team_dict)
        max_team_number = max(max_team_number, team.team_number)

    # Remove players who are already on teams from player_sessions
    for team in teams:
        for position in ['Skip', 'Vice', 'Second', 'Lead']:
            if team[position]:
                player_sessions = [ps for ps in player_sessions if ps.id != team[position]]

    # Calculate number of additional teams needed
    remaining_players = len(player_sessions)
    additional_teams_needed = remaining_players // 4

    # Initialize new teams
    new_teams = [{position: None for position in ['Skip', 'Vice', 'Second', 'Lead']} 
                 for _ in range(additional_teams_needed)]
    teams.extend(new_teams)

    # Rest of the team assignment logic remains similar, but only for unassigned positions
    for position in ['Skip', 'Vice', 'Second', 'Lead']:
        for team in teams:
            if team[position] is None:
                player = select_player_for_position(position, player_sessions)
                if player:
                    set_team_player(team, position, player, player_sessions)
                    if use_play_with:
                        add_play_with_players_to_team(team, player_sessions)

    # Handle remaining players as before
    if len(player_sessions) > 0:
        logging.info(f"Players remaining: {player_sessions}, beginning to fill holes in rosters")
        for team_player_count in range(1, 4):
            for team in teams:
                if len(player_sessions) > 0 and sum(team[position] is not None for position in ['Skip', 'Vice', 'Second', 'Lead']) == team_player_count:
                    player_session = random.choice(player_sessions)
                    for position in ['Lead', 'Second', 'Vice', 'Skip']:
                        if team[position] is None:
                            set_team_player(team, position, player_session, player_sessions)
                            break

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

# Helper function to select a player with no preference - possibly not needed but we'll hold onto it for now
# def select_no_preference_player(player_sessions):
#     candidates = [ps for ps in player_sessions if not ps.preferred_position1 and not ps.preferred_position2]
#     if candidates:
#         selected = random.choice(candidates)
#         logging.info(f"Selected no preference player {selected.player} as last resort")
#         return selected
#     return None

# Helper function to assign play with players to an existing team
def add_play_with_players_to_team(team, player_sessions):
    for _, team_position_player_session_id in team.items():
        team_position_player_session = PlayerSession.objects.get(pk=team_position_player_session_id) if team_position_player_session_id else None
        if team_position_player_session is not None:
            preferred_player = next((ps for ps in player_sessions if ps.player.full_name == team_position_player_session.play_with), None)
            if preferred_player:
                if preferred_player.preferred_position1 and team[preferred_player.preferred_position1] is None:
                    set_team_player(team, preferred_player.preferred_position1, preferred_player, player_sessions)
                    logging.info(f"Added {team_position_player_session.player} partner {preferred_player.player} to team {team} at preferred position 1 {preferred_player.preferred_position1}")
                elif preferred_player.preferred_position2 and team[preferred_player.preferred_position2] is None:
                    set_team_player(team, preferred_player.preferred_position2, preferred_player, player_sessions)
                    logging.info(f"Added {team_position_player_session.player} partner {preferred_player.player} to team {team} at preferred position 2 {preferred_player.preferred_position2}")
                elif not preferred_player.preferred_position1 and not preferred_player.preferred_position2 and any(team[position] is None for position in ['Vice', 'Second', 'Lead']):
                    for position in ['Lead', 'Second', 'Vice']:
                        if team[position] is None:
                            set_team_player(team, position, preferred_player, player_sessions)
                            logging.info(f"Added {team_position_player_session.player} partner {preferred_player.player} without preferred position to team {team} at first available position {position}")
                            break
                else:
                    logging.warning(f"Unable to add {preferred_player.player} to team {team} at either preferred position")

# utility function to set a player to a team position and remove the player from the list of player sessions                
def set_team_player(team, position, player_session, player_sessions):
    team[position] = player_session.id
    player_sessions.remove(player_session)
    logging.info(f"Assigned {position} {player_session.player} to team {team}")

# utility function to hydrate the rosters with PlayerSession objects
def hydrate_rosters(rosters):
    hydrated_rosters = []
    for roster in rosters:
        hydrated_roster = []
        for team in roster:
            hydrated_team = hydrate_team(team)
            hydrated_roster.append(hydrated_team)
        hydrated_rosters.append(hydrated_roster)
    return hydrated_rosters

def hydrate_team(team):
    hydrated_team = {
                'Skip': PlayerSession.objects.get(pk=team['Skip']) if team['Skip'] else None,
                'Vice': PlayerSession.objects.get(pk=team['Vice']) if team['Vice'] else None,
                'Second': PlayerSession.objects.get(pk=team['Second']) if team['Second'] else None,
                'Lead': PlayerSession.objects.get(pk=team['Lead']) if team['Lead'] else None,
            }   
    return hydrated_team


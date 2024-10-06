import logging

from .models import Player, PlayerSession, Session

def parse_name(full_name):
    """
    Parses a full name into first name and last name.

    Args:
        full_name (str): The full name to be parsed.

    Returns:
        tuple: A tuple containing the first name and last name.

    Raises:
        None

    Examples:
        >>> parse_name('Doe, John')
        ('John', 'Doe')
    """
    first_name = ''
    last_name = ''
    try:
        last_name, first_name = full_name.split(', ')
    except ValueError:
        logging.warning(f'Could not parse name: {full_name}')
    finally:
        return first_name,last_name

def get_previous_session(session_id):
    """
    Retrieves the previous session object based on the given session.
    Args:
        session (Session): The current session object.
    Returns:
        Session: The previous session object, or None if no previous session exists.
    """
    try:
        session = Session.objects.get(pk=session_id)
    except Session.DoesNotExist:
        raise ValueError(f'Session with id {session_id} does not exist')
    
    previous_session = None
    previous_sessions = Session.objects.filter(year=session.year, session_number__lt=session.session_number).order_by('session_number')
    if previous_sessions.exists():
        previous_session = previous_sessions.last()
    else:
        previous_sessions = Session.objects.filter(year=session.year-1).order_by('session_number')
        if previous_sessions.exists():
            previous_session = previous_sessions.last()
        else:
            previous_session = None

    return previous_session

def check_player_issues(session):
    """
    Checks for issues with players in the given session.

    Args:
        session (Session): The session to check.

    Returns:
        list: A list of issues with the players in the session.

    Examples:
        >>> check_player_issues(Session.objects.first())
        ['Player John Doe is missing a phone number']
    """
    issues = []
    player_sessions = PlayerSession.objects.filter(session_id=session.pk)
    players = Player.objects.all()
    for player_session in player_sessions:
        if player_session.preferred_position1 and player_session.preferred_position1 not in ['Skip', 'Vice', 'Second', 'Lead']:
            issues.append(f'Player {player_session.player.full_name} has an invalid preferred position 1 ({player_session.preferred_position1})')
        if player_session.preferred_position2 and player_session.preferred_position2 not in ['Skip', 'Vice', 'Second', 'Lead']:
            issues.append(f'Player {player_session.player.full_name} has an invalid preferred position 2 ({player_session.preferred_position2})')
        if player_session.play_with and not any(player_session.play_with in player.full_name for player in players):
            issues.append(f'Player {player_session.player.full_name} has an invalid play with ({player_session.play_with})')
        elif player_session.play_with and not any(player_session.play_with in ps.player.full_name for ps in player_sessions):
            issues.append(f'Player {player_session.player.full_name} has play with not registered in session ({player_session.play_with})')
    return issues
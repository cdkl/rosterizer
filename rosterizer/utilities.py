import logging

from .models import Session

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

def get_previous_session(session):
    """
    Retrieves the previous session object based on the given session.
    Args:
        session (Session): The current session object.
    Returns:
        Session: The previous session object, or None if no previous session exists.
    """
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
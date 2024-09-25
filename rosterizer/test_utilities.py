import pytest
from django.test import RequestFactory
from .utilities import get_previous_session
from .models import Session

@pytest.mark.django_db
def test_get_previous_session():
    sessions = [
        Session(year=2020, session_number=1),
        Session(year=2020, session_number=2),
        Session(year=2021, session_number=1),
        Session(year=2021, session_number=3),
        Session(year=2022, session_number=2),
        Session(year=2022, session_number=3),
        Session(year=2023, session_number=1),
        Session(year=2023, session_number=2),
        Session(year=2023, session_number=3),
    ]
    Session.objects.bulk_create(sessions)

    assert get_previous_session(sessions[0]) is None
    assert str(get_previous_session(sessions[1])) == str(sessions[0])
    assert str(get_previous_session(sessions[2])) == str(sessions[1])
    assert str(get_previous_session(sessions[3])) == str(sessions[2])
    assert str(get_previous_session(sessions[4])) == str(sessions[3])
    assert str(get_previous_session(sessions[5])) == str(sessions[4])
    assert str(get_previous_session(sessions[6])) == str(sessions[5])
    assert str(get_previous_session(sessions[7])) == str(sessions[6])
    assert str(get_previous_session(sessions[8])) == str(sessions[7])


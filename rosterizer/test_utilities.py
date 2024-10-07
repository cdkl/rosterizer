import pytest
from django.test import RequestFactory
from .utilities import get_previous_session
from .models import Session

@pytest.mark.django_db
def test_get_previous_session():
    sessions = Session.objects.bulk_create(
        [
            Session(pk=1, year=2020, session_number=1),
            Session(pk=2, year=2020, session_number=2),
            Session(pk=3, year=2021, session_number=1),
            Session(pk=4, year=2021, session_number=3),
            Session(pk=5, year=2022, session_number=2),
            Session(pk=6, year=2022, session_number=3),
            Session(pk=7, year=2023, session_number=1),
            Session(pk=8, year=2023, session_number=2),
            Session(pk=9, year=2023, session_number=3),
        ]
    )

    assert get_previous_session(sessions[0].pk) is None
    assert str(get_previous_session(sessions[1].pk)) == str(sessions[0])
    assert str(get_previous_session(sessions[2].pk)) == str(sessions[1])
    assert str(get_previous_session(sessions[3].pk)) == str(sessions[2])
    assert str(get_previous_session(sessions[4].pk)) == str(sessions[3])
    assert str(get_previous_session(sessions[5].pk)) == str(sessions[4])
    assert str(get_previous_session(sessions[6].pk)) == str(sessions[5])
    assert str(get_previous_session(sessions[7].pk)) == str(sessions[6])
    assert str(get_previous_session(sessions[8].pk)) == str(sessions[7])

    assert get_previous_session(sessions[0].pk, 2) is None
    assert get_previous_session(sessions[1].pk, 2) is None
    assert str(get_previous_session(sessions[2].pk, 2)) == str(sessions[0])
    assert str(get_previous_session(sessions[3].pk, 2)) == str(sessions[1])
    assert str(get_previous_session(sessions[4].pk, 2)) == str(sessions[2])
    assert str(get_previous_session(sessions[5].pk, 2)) == str(sessions[3])
    assert str(get_previous_session(sessions[6].pk, 2)) == str(sessions[4])
    assert str(get_previous_session(sessions[7].pk, 2)) == str(sessions[5])
    assert str(get_previous_session(sessions[8].pk, 2)) == str(sessions[6])

    assert get_previous_session(sessions[0].pk, 3) is None
    assert get_previous_session(sessions[1].pk, 3) is None
    assert get_previous_session(sessions[2].pk, 3) is None
    assert str(get_previous_session(sessions[3].pk, 3)) == str(sessions[0])
    assert str(get_previous_session(sessions[4].pk, 3)) == str(sessions[1])
    assert str(get_previous_session(sessions[5].pk, 3)) == str(sessions[2])
    assert str(get_previous_session(sessions[6].pk, 3)) == str(sessions[3])
    assert str(get_previous_session(sessions[7].pk, 3)) == str(sessions[4])
    assert str(get_previous_session(sessions[8].pk, 3)) == str(sessions[5])
    

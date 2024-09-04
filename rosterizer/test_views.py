import pytest
from django.test import RequestFactory

from rosterizer.models import Player, PlayerSession, Session
from .views import create_session, delete_session, import_players
from .forms import SessionForm

@pytest.fixture
def rf():
    return RequestFactory()

@pytest.mark.django_db
def test_create_session_and_delete_session(rf):
    assert Session.objects.count() == 0
    request = rf.post('/create_session/', {'year': '2024', 'session_number': '1'})  # Form data
    response = create_session(request)
    assert response.status_code == 302  # Check if the response is a redirect
    assert response.url == '/rosterizer/sessions/'  # Check if the redirect URL is correct
    assert Session.objects.count() == 1
    assert Session.objects.first().year == 2024
    assert Session.objects.first().session_number == 1
    session_id = Session.objects.first().id
    request = rf.post(f'/delete_session/{session_id}/')
    response = delete_session(request, session_id)
    assert Session.objects.count() == 0

@pytest.mark.django_db
def test_create_session_invalid_form(rf):
    request = rf.post('/create_session/', {})  # Empty form data
    response = create_session(request)
    assert response.status_code == 200  # Check if the response is a success
    assert 'This field is required.' in response.content.decode()

@pytest.mark.django_db
def test_import_players_with_invalid_file(rf):
    # create a session
    request = rf.post('/create_session/', {'year': '2024', 'session_number': '1'})
    response = create_session(request)
    session_id = Session.objects.first().id
    request = rf.post(f'/import_players/{session_id}/', {})
    response = import_players(request, session_id)
    assert response.status_code == 200
    assert 'This field is required.' in response.content.decode()
    assert Player.objects.count() == 0

@pytest.mark.django_db
def test_import_players_with_valid_file(rf):
    # create a session
    request = rf.post('/create_session/', {'year': '2024', 'session_number': '1'})
    response = create_session(request)
    session_id = Session.objects.first().id
    from django.core.files.uploadedfile import SimpleUploadedFile
    
    file_path = 'rosterizer/test_data/TestImport1.html'
    file = open(file_path, 'rb')
    uploaded_file = SimpleUploadedFile(file.name, file.read())
    
    request = rf.post(f'/import_players/{session_id}/', {'html_file': uploaded_file})
    response = import_players(request, session_id)
    print(response.content.decode())
 #   assert response.status_code == 302
 #   assert response.url == '/rosterizer/sessions/'
    assert Player.objects.count() == 8
    assert Player.objects.first().first_name == 'John'
    assert Player.objects.first().last_name == 'Smith'
    assert Player.objects.first().home_phone == '555-123-4567'
    assert Player.objects.first().work_phone == '555-234-5678'
    assert Player.objects.first().cell_phone == '555-345-6789'
    assert Player.objects.first().email == 'john.smith@example.com'
    assert Player.objects.first().gender == 'M'
    assert PlayerSession.objects.count() == 8
    assert PlayerSession.objects.filter(player=Player.objects.first(), session=Session.objects.first()).count() == 1
    playerSession = PlayerSession.objects.filter(player=Player.objects.first(), session=Session.objects.first()).first()
    print(playerSession)

    assert playerSession.years_curled == 5
    assert playerSession.preferred_position1 == 'Skip'
    assert playerSession.preferred_position2 == 'Vice'
    assert playerSession.play_with == 'Jane Doe'




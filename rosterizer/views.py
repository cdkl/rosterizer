from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .forms import SessionForm
from .models import Player, Session
from bs4 import BeautifulSoup

# Create your views here.

def create_session(request):
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('session_list')  # Redirect to a session list view or another appropriate view
    else:
        form = SessionForm()
    return render(request, 'create_session.html', {'form': form})

def session_list(request):
    sessions = Session.objects.all()
    return render(request, 'session_list.html', {'sessions': sessions})

def index(request):
    return render(request, 'index.html')

def delete_session(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if request.method == 'POST':
        session.delete()
        return redirect('session_list')
    return render(request, 'delete_session.html', {'session': session})

def import_players(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if request.method == 'POST' and request.FILES.get('player_file'):
        player_file = request.FILES['player_file']
        soup = BeautifulSoup(player_file, 'lxml')

        table = soup.find('table', class_='adminlist')
        rows = table.find('tbody').find_all('tr')

        for row in rows:
            cols = row.find_all('td')
            name = cols[1].text.strip()
            last_name, first_name = map(str.strip, name.split(','))

            player_data = {
                'first_name': first_name,
                'last_name': last_name,
                'home_phone': cols[2].text.strip() or None,
                'work_phone': cols[3].text.strip() or None,
                'cell_phone': cols[4].text.strip() or None,
                'email': cols[5].text.strip() or None,
                'gender': cols[6].text.strip()[0],  # Assuming gender is a single character (M/F)
            }

            Player.objects.create(**player_data)

        return redirect('session_list')
    return render(request, 'import_players.html', {'session': session})

def player_list(request):
    players = Player.objects.all()
    return render(request, 'player_list.html', {'players': players})
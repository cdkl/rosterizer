from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from bs4 import BeautifulSoup
from .forms import SessionForm, PlayerImportForm
from .models import Player, Session
from .management.commands.import_players import ImportPlayersCommand

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
    session = Session.objects.get(id=session_id)

    if request.method == 'POST':
        form = PlayerImportForm(request.POST, request.FILES)
        if form.is_valid():
            html_file = request.FILES['html_file']
            fs = FileSystemStorage()
            filename = fs.save(html_file.name, html_file)
            uploaded_file_path = fs.path(filename)

            # Invoke the import logic
            import_command = ImportPlayersCommand()
            import_command.handle(html_file=uploaded_file_path, session_id=session_id)

            # messages.success(request, 'Players imported successfully')
            return redirect('session_list')  # Adjust the redirect as needed
    else:
        form = PlayerImportForm()

    return render(request, 'import_players.html', {'form': form, 'session': session})

def player_list(request):
    players = Player.objects.all()
    return render(request, 'player_list.html', {'players': players})

def clear_player_list(request):
    if request.method == 'POST':
        Player.objects.all().delete()
        # messages.success(request, 'All players have been cleared.')
        return redirect('player_list')  # Adjust the redirect as needed

    return render(request, 'clear_player_list.html')

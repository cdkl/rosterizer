from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.contrib import messages

from rosterizer.management.commands.import_players import ImportPlayersCommand
from rosterizer.management.commands.import_roster import ImportRosterHtmlCommand, ImportRosterCsvCommand
from .forms import SessionForm, PlayerImportForm, RosterImportForm
from .models import Player, PlayerSession, Session, Team
from .team_generation import apply_team_roster, evaluate_rosters, generate_multiple_rosters, generate_teams_for_session, hydrate_rosters

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

def import_roster(request, session_id):
    session = get_object_or_404(Session, id=session_id)

    if request.method == 'POST':
        form = RosterImportForm(request.POST, request.FILES)
        if form.is_valid():
            roster_file = request.FILES['roster_file']
            fs = FileSystemStorage()
            filename = fs.save(roster_file.name, roster_file)
            uploaded_file_path = fs.path(filename)

            import_command = ImportRosterCsvCommand()
            import_command.handle(roster_file=uploaded_file_path, session_id=session_id)

            # messages.success(request, 'Roster imported successfully')
            return redirect('session_list')  # Adjust the redirect as needed
    else:
        form = RosterImportForm()

    return render(request, 'import_roster.html', {'form': form, 'session': session})

def players_in_session(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    player_sessions = PlayerSession.objects.filter(session=session).select_related('player')
    return render(request, 'players_in_session.html', {'session': session, 'player_sessions': player_sessions})

def generate_teams_form(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    return render(request, 'generate_teams.html', {'session': session})

def generate_teams(request, session_id):
    if request.method == 'POST':
        use_play_with = request.POST.get('use_play_with', 'on')
        num_rosters = int(request.POST.get('num_rosters', 1))
        if num_rosters == 1:
            result = generate_teams_for_session(session_id, use_play_with)  # Call the function
            # messages.success(request, 'Teams have been generated successfully')
            return redirect('team_list', session_id=session_id)
        else:
            rosters = generate_multiple_rosters(session_id, num_rosters, use_play_with)

            request.session['generated_rosters'] = rosters
            return redirect('roster_review', session_id=session_id)
    else:
        return redirect('session_list')

def roster_review(request, session_id):
    rosters = request.session.get('generated_rosters', [])
    if not rosters:
        return redirect('session_list')  # Handle the case where rosters are not found
    print(rosters)
    roster_scores = evaluate_rosters(rosters, session_id)
    print(roster_scores)

    return render(request, 'roster_review.html', {'session_id': session_id, 'rosters': zip(hydrate_rosters(rosters), roster_scores)})

def select_roster(request, session_id):
    if request.method == 'POST':
        selected_roster_index = int(request.POST.get('selected_roster'))

        rosters = request.session.get('generated_rosters', [])
        if not rosters:
            return redirect('session_list')  # Handle the case where rosters are not found

        selected_roster = rosters[selected_roster_index]
        apply_team_roster(session_id, selected_roster)        

        return redirect('team_list', session_id=session_id)
    else:
        return redirect('session_list')

def team_list(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    teams = Team.objects.filter(session=session)
    return render(request, 'team_list.html', {'session': session, 'teams': teams})

def clear_teams(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    Team.objects.filter(session=session).delete()
    # messages.success(request, 'Teams have been cleared successfully')
    return redirect('team_list', session_id=session_id)

def player_session_detail(request, pk):
    try:
        player_session = PlayerSession.objects.get(pk=pk)
        data = player_session.to_dict()
        return JsonResponse(data)
    except PlayerSession.DoesNotExist:
        return JsonResponse({'error': 'PlayerSession not found'}, status=404)
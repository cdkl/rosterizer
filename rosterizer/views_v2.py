"""
Django views for the v2 roster workflow.

Kept separate from views.py so the v1 team-generation path stays untouched.
"""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS
from .roster_evaluation_v2 import evaluate_roster, build_context
from .team_generation_v2 import ValidationProblem, generate_rosters_v2, validate_session

DEFAULT_CANDIDATES = 10
MAX_CANDIDATES = 50


def commit_roster(session):
    """
    Confirm a session's current teams as its historical record.

    Results are entered against a committed roster so that regenerating teams
    afterwards cannot change what a recorded result is understood to mean.
    """
    teams = list(Team.objects.filter(session=session).order_by('team_number'))
    for team in teams:
        TeamResult.objects.update_or_create(
            session=session,
            team_number=team.team_number,
            defaults={
                'skip_id': team.skip_id,
                'vice_id': team.vice_id,
                'second_id': team.second_id,
                'lead_id': team.lead_id,
            })
    session.results_committed = True
    session.save(update_fields=['results_committed'])
    return teams


def results_coverage(session):
    """
    How much result history exists, so thin ratings can be explained up front.
    """
    prior = Session.objects.filter(
        year__lt=session.year) | Session.objects.filter(
        year=session.year, session_number__lt=session.session_number)
    prior_ids = list(prior.values_list('pk', flat=True))

    results = TeamResult.objects.filter(session_id__in=prior_ids)
    covered_sessions = set(results.values_list('session_id', flat=True))
    team_counts = {}
    for session_id in covered_sessions:
        team_counts[session_id] = results.filter(session_id=session_id).count()

    return {
        'sessions_with_results': len(covered_sessions),
        'total_sessions': len(prior_ids),
        'per_session': team_counts,
        'any_results': bool(covered_sessions),
    }


def commit_roster_view(request, session_id):
    """Confirm the session's current teams as its historical record."""
    session = get_object_or_404(Session, pk=session_id)
    if request.method != 'POST':
        return redirect('enter_results', session_id=session.pk)

    if not Team.objects.filter(session=session).exists():
        messages.error(request, 'Create the teams before committing them.')
        return redirect('generate_rosters_form', session_id=session.pk)

    teams = commit_roster(session)
    messages.success(
        request,
        f'Committed {len(teams)} teams for {session}. Results can now be entered.')
    return redirect('enter_results', session_id=session.pk)


def enter_results(request, session_id):
    """Enter or update wins/losses/ties for each team in a committed session."""
    session = get_object_or_404(Session, pk=session_id)

    if request.method == 'POST':
        if not session.results_committed:
            messages.error(request, 'Commit the roster before entering results.')
            return redirect('enter_results', session_id=session.pk)

        # Keyed off team_<n>_wins, which the form renders for every team.
        # An earlier version gated on a team_<n>_record field that the template
        # never emitted, so every submission silently saved nothing.
        team_numbers = set()
        for key in request.POST:
            if not key.startswith('team_') or not key.endswith('_wins'):
                continue
            try:
                team_numbers.add(int(key[len('team_'):-len('_wins')]))
            except ValueError:
                continue

        updated = 0
        for team_number in sorted(team_numbers):
            wins = _to_int(request.POST.get(f'team_{team_number}_wins'))
            losses = _to_int(request.POST.get(f'team_{team_number}_losses'))
            ties = _to_int(request.POST.get(f'team_{team_number}_ties'))
            TeamResult.objects.update_or_create(
                session=session,
                team_number=team_number,
                defaults={'wins': wins, 'losses': losses, 'ties': ties})
            updated += 1

        if updated == 0:
            messages.error(request, 'No results were submitted. Please try again.')
        else:
            messages.success(request, f'Saved results for {updated} teams.')
        return redirect('enter_results', session_id=session.pk)

    results = {r.team_number: r for r in TeamResult.objects.filter(session=session)}
    rows = []
    for team in Team.objects.filter(session=session).order_by('team_number'):
        result = results.get(team.team_number)
        rows.append({
            'team': team,
            'result': result,
            'players': [getattr(team, position.lower()) for position in POSITIONS],
        })

    return render(request, 'rosterizer_v2/enter_results.html', {
        'session': session,
        'rows': rows,
        'positions': POSITIONS,
    })


def _to_int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def lock_summary(session):
    """
    Existing teams and remaining unassigned players for the generation screen.

    Existing teams are locked: generation covers only the players not already
    placed, so the convenor sees what is fixed before starting.
    """
    locked_player_ids = set()
    locked_team_count = 0
    for row in Team.objects.filter(session=session).values_list(
            'skip_id', 'vice_id', 'second_id', 'lead_id'):
        locked_team_count += 1
        locked_player_ids.update(pid for pid in row if pid is not None)

    registered = set(
        PlayerSession.objects.filter(session=session).values_list('player_id', flat=True))
    return {
        'locked_team_count': locked_team_count,
        'unassigned_count': len(registered - locked_player_ids),
    }


def generate_rosters_form(request, session_id):
    """Configuration form for generating candidate rosters."""
    session = get_object_or_404(Session, pk=session_id)
    problems = _validation_problems(session)
    return render(request, 'rosterizer_v2/generate_rosters.html', {
        'session': session,
        'problems': problems,
        'coverage': results_coverage(session),
        'default_candidates': DEFAULT_CANDIDATES,
        'max_candidates': MAX_CANDIDATES,
        **lock_summary(session),
    })


def _validation_problems(session):
    try:
        validate_session(session.pk)
    except ValidationProblem as exc:
        return str(exc)
    return None


def generate_rosters(request, session_id):
    """
    Generate candidates and return the card partial.

    Responds to an HTMX post so the convenor sees a loading state while the
    genetic algorithm runs rather than a blank page.
    """
    session = get_object_or_404(Session, pk=session_id)

    if request.method != 'POST':
        return redirect('generate_rosters_form', session_id=session.pk)

    try:
        candidates_wanted = int(request.POST.get('candidates', DEFAULT_CANDIDATES))
    except (TypeError, ValueError):
        candidates_wanted = DEFAULT_CANDIDATES
    candidates_wanted = max(1, min(MAX_CANDIDATES, candidates_wanted))

    problems = _validation_problems(session)
    if problems:
        return render(request, 'rosterizer_v2/_roster_cards.html', {
            'session': session,
            'error': problems,
            'candidates': [],
        })

    summary = lock_summary(session)
    if summary['unassigned_count'] == 0:
        return render(request, 'rosterizer_v2/_roster_cards.html', {
            'session': session,
            'candidates': [],
            'error': None,
            'no_players': True,
        })

    seed = request.POST.get('seed') or None
    result = generate_rosters_v2(session.pk, num_candidates=candidates_wanted, seed=seed)

    stored = []
    for candidate in result['candidates']:
        teams = []
        for team in candidate['roster']:
            teams.append({position: team.get(position) for position in POSITIONS})
        stored.append(teams)
    request.session['v2_rosters'] = stored

    return render(request, 'rosterizer_v2/_roster_cards.html', {
        'session': session,
        'candidates': result['candidates'],
        'shortfall': result['shortfall'],
        'error': None,
    })


def roster_review(request, session_id):
    """Landing page for the review step."""
    session = get_object_or_404(Session, pk=session_id)
    stored = request.session.get('v2_rosters', [])
    if not stored:
        return redirect('generate_rosters_form', session_id=session.pk)

    # Stored candidates are already a list of {position: value} team dicts.
    context = build_context(session.pk)
    candidates = [evaluate_roster(roster, context) | {'roster': roster}
                  for roster in stored]
    candidates.sort(key=lambda c: c['composite'], reverse=True)

    return render(request, 'rosterizer_v2/roster_review.html', {
        'session': session,
        'candidates': candidates,
    })


def select_roster(request, session_id):
    """Persist the chosen roster as Team records."""
    session = get_object_or_404(Session, pk=session_id)
    if request.method != 'POST':
        return redirect('roster_review', session_id=session.pk)

    stored = request.session.get('v2_rosters', [])
    if not stored:
        return redirect('generate_rosters_form', session_id=session.pk)

    try:
        index = int(request.POST.get('selected_roster'))
    except (TypeError, ValueError):
        messages.error(request, 'No roster was selected.')
        return redirect('roster_review', session_id=session.pk)

    if not 0 <= index < len(stored):
        messages.error(request, 'That roster is no longer available.')
        return redirect('roster_review', session_id=session.pk)

    roster = stored[index]
    created = apply_roster(session, roster)
    request.session.pop('v2_rosters', None)
    messages.success(request, f'Applied {created} new teams.')
    return redirect('team_list', session_id=session.pk)


def apply_roster(session, roster):
    """
    Save a roster as Team rows, preserving teams already on the session.

    Mirrors the v1 behaviour: existing teams are left alone and new ones are
    appended with the next available team number.
    """
    existing = Team.objects.filter(session=session)
    taken = set(existing.values_list('team_number', flat=True))
    next_number = 1
    while next_number in taken:
        next_number += 1

    players = {ps.pk: ps.player for ps in
               PlayerSession.objects.filter(session=session).select_related('player')}

    # Compare in *player* id space. Roster values are PlayerSession ids, while
    # Team.get_players() yields Players; mixing the two makes unrelated rosters
    # look identical whenever the id sequences happen to line up.
    existing_compositions = {
        frozenset(p.pk for p in team.get_players()) for team in existing}

    created = 0
    for team in roster:
        members = [players.get(value) for value in team.values() if value is not None]
        member_ids = frozenset(p.pk for p in members if p is not None)
        if member_ids in existing_compositions:
            continue
        new_team = Team(session=session, team_number=next_number)
        for position in POSITIONS:
            value = team.get(position)
            if value is not None:
                setattr(new_team, position.lower(), players.get(value))
        new_team.save()
        existing_compositions.add(member_ids)
        taken.add(next_number)
        next_number += 1
        created += 1
    return created


def team_detail(request, session_id, index):
    """HTMX fragment: the team grid for one candidate roster."""
    session = get_object_or_404(Session, pk=session_id)
    stored = request.session.get('v2_rosters', [])
    if not stored or not 0 <= index < len(stored):
        return HttpResponse('', status=404)

    roster = stored[index]
    players = {ps.pk: ps.player for ps in
               PlayerSession.objects.filter(session=session).select_related('player')}

    rows = []
    for team in roster:
        rows.append([players.get(team.get(position)) for position in POSITIONS])

    return render(request, 'rosterizer_v2/_team_detail.html', {
        'teams': rows,
        'positions': POSITIONS,
    })
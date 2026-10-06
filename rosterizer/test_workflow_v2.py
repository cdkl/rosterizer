"""URL routing and v2 workflow coverage."""

import pytest
from django.urls import resolve, reverse

from .models import Player, PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS
from .roster_evaluation_v2 import build_context, evaluate_team_continuity


def build_league(n=12, year=2025):
    session = Session.objects.create(year=year, session_number=1)
    pss = []
    for i in range(n):
        player = Player.objects.create(first_name=f'P{i}', last_name='X')
        pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=(i * 3) % 40,
            preferred_position1=POSITIONS[i % 4], preferred_position2='', play_with=''))
    return session, pss


# --------------------------------------------------------------------------
# 8.6 URL routing
# --------------------------------------------------------------------------

@pytest.mark.parametrize('name,args,view_name', [
    ('generate_rosters_form', (1,), 'rosterizer.views_v2.generate_rosters_form'),
    ('generate_rosters_v2', (1,), 'rosterizer.views_v2.generate_rosters'),
    ('roster_review_v2', (1,), 'rosterizer.views_v2.roster_review'),
    ('select_roster_v2', (1,), 'rosterizer.views_v2.select_roster'),
    ('enter_results', (1,), 'rosterizer.views_v2.enter_results'),
    ('commit_roster', (1,), 'rosterizer.views_v2.commit_roster_view'),
    ('roster_team_detail', (1, 0), 'rosterizer.views_v2.team_detail'),
])
def test_v2_urls_resolve(name, args, view_name):
    match = resolve(reverse(name, args=args))
    assert match.func.__module__ + '.' + match.func.__name__ == view_name


@pytest.mark.parametrize('name,args', [
    ('index', ()),
    ('session_list', ()),
    ('create_session', ()),
    ('generate_teams_form', (1,)),
    ('roster_review', (1,)),
    ('team_list', (1,)),
    ('rule_list', ()),
])
def test_v1_urls_still_resolve(name, args):
    """The v1 paths must be untouched by the v2 additions."""
    assert resolve(reverse(name, args=args)) is not None


def test_v2_urls_are_namespaced_away_from_v1():
    assert reverse('generate_rosters_form', args=[1]) != \
        reverse('generate_teams_form', args=[1])


# --------------------------------------------------------------------------
# 8.2 generation view
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generate_form_renders_with_coverage(client):
    session, _ = build_league(12)
    response = client.get(reverse('generate_rosters_form', args=[session.pk]))

    assert response.status_code == 200
    assert b'No results have been recorded' in response.content
    assert b'htmx.min.js' in response.content


@pytest.mark.django_db
def test_generate_form_reports_no_play_with_toggle(client):
    """Play-with preferences are mandatory, so no opt-out is offered."""
    session, _ = build_league(12)
    body = client.get(
        reverse('generate_rosters_form', args=[session.pk])).content.decode().lower()

    assert 'use_play_with' not in body
    assert 'full_play_with_adherence' not in body
    assert 'full_last_session_uniqueness' not in body


@pytest.mark.django_db
def test_generate_post_returns_card_fragment(client):
    session, _ = build_league(12)
    response = client.post(reverse('generate_rosters_v2', args=[session.pk]),
                           {'candidates': '3', 'seed': '1'})

    assert response.status_code == 200
    body = response.content.decode()
    assert 'Roster 1' in body
    assert 'Apply Selected Roster' in body
    assert 'v2_rosters' in client.session


@pytest.mark.django_db
def test_generate_post_is_deterministic_for_a_seed(client):
    """The same seed must produce the same rosters, not just a similar score."""
    session, _ = build_league(12)
    url = reverse('generate_rosters_v2', args=[session.pk])

    client.post(url, {'candidates': '2', 'seed': '5'})
    first = client.session['v2_rosters']
    client.post(url, {'candidates': '2', 'seed': '5'})
    second = client.session['v2_rosters']

    assert first == second


# --------------------------------------------------------------------------
# 8.8 validation surfaced instead of generating
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generate_refuses_when_data_is_invalid(client):
    session, pss = build_league(8)
    pss[0].play_with = 'Ghost Person'
    pss[0].save()

    response = client.post(reverse('generate_rosters_v2', args=[session.pk]),
                           {'candidates': '3'})
    body = response.content.decode()

    assert 'Cannot generate rosters' in body
    assert 'not registered' in body
    assert client.session.get('v2_rosters') is None, 'nothing should be stored'


@pytest.mark.django_db
def test_generate_form_blocks_invalid_session(client):
    session, pss = build_league(8)
    pss[0].play_with = 'Ghost Person'
    pss[0].save()
    body = client.get(
        reverse('generate_rosters_form', args=[session.pk])).content.decode()
    assert 'Cannot generate rosters yet' in body


# --------------------------------------------------------------------------
# 8.4 / 8.5 review and team detail
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_review_renders_stored_rosters(client):
    session, pss = build_league(12)
    client.post(reverse('generate_rosters_v2', args=[session.pk]),
                {'candidates': '3', 'seed': '1'})
    response = client.get(reverse('roster_review_v2', args=[session.pk]))

    assert response.status_code == 200
    assert b'Roster 1' in response.content
    assert len(response.context['candidates']) == 3


@pytest.mark.django_db
def test_review_redirects_without_stored_rosters(client):
    session, _ = build_league(8)
    response = client.get(reverse('roster_review_v2', args=[session.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_review_orders_rosters_best_first(client):
    session, pss = build_league(12)
    client.post(reverse('generate_rosters_v2', args=[session.pk]),
                {'candidates': '4', 'seed': '2'})
    response = client.get(reverse('roster_review_v2', args=[session.pk]))

    scores = [c['composite'] for c in response.context['candidates']]
    assert len(scores) > 1
    assert scores == sorted(scores, reverse=True)


@pytest.mark.django_db
def test_team_detail_fragment_lists_players(client):
    session, pss = build_league(12)
    client.post(reverse('generate_rosters_v2', args=[session.pk]),
                {'candidates': '2', 'seed': '1'})
    response = client.get(reverse('roster_team_detail', args=[session.pk, 0]))
    body = response.content.decode()

    assert response.status_code == 200
    assert 'Skip' in body and 'Vice' in body and 'Second' in body and 'Lead' in body
    assert '<table' in body, 'should be a fragment, not a full page'


@pytest.mark.django_db
def test_team_detail_404_for_bad_index(client):
    session, _ = build_league(12)
    response = client.get(reverse('roster_team_detail', args=[session.pk, 99]))
    assert response.status_code == 404


# --------------------------------------------------------------------------
# 8.3 continuity uses live teams, results use frozen snapshots
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_regenerating_prior_teams_changes_continuity_but_not_abilities():
    """
    The two history sources are deliberately different.

    Results read their own snapshot, so regenerating a prior session's teams
    must not disturb computed ability. Continuity reads live Team rows, so it
    must follow the new lineup.
    """
    prior = Session.objects.create(year=2024, session_number=1)
    current, pss = build_league(8, year=2025)

    players = [ps.player for ps in pss]
    Team.objects.create(session=prior, team_number=1,
                        skip=players[0], vice=players[1], second=players[2], lead=players[3])
    TeamResult.objects.create(session=prior, team_number=1,
                              skip=players[0], vice=players[1],
                              second=players[2], lead=players[3], wins=6, losses=2)

    ctx_before = build_context(current.pk)
    ability_before = ctx_before.abilities.ability(players[0].pk, 'Skip')
    same_teams_roster = [{'Skip': pss[0].pk, 'Vice': pss[1].pk,
                          'Second': pss[2].pk, 'Lead': pss[3].pk}]
    continuity_before = evaluate_team_continuity(same_teams_roster, ctx_before)

    # Regenerate the prior session with a completely different lineup.
    Team.objects.filter(session=prior).delete()
    Team.objects.create(session=prior, team_number=1,
                        skip=players[4], vice=players[5], second=players[6], lead=players[7])

    ctx_after = build_context(current.pk)
    ability_after = ctx_after.abilities.ability(players[0].pk, 'Skip')
    continuity_after = evaluate_team_continuity(same_teams_roster, ctx_after)

    assert ability_after == pytest.approx(ability_before), \
        'frozen results must keep the ability rating stable'
    assert continuity_after == [1.0], \
        'continuity should improve once the prior teams no longer match'
    assert continuity_before == [0.0]


# --------------------------------------------------------------------------
# select_roster
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_select_roster_persists_teams(client):
    session, pss = build_league(12)
    client.post(reverse('generate_rosters_v2', args=[session.pk]),
                {'candidates': '3', 'seed': '1'})
    response = client.post(reverse('select_roster_v2', args=[session.pk]),
                           {'selected_roster': '0'})

    assert response.status_code == 302
    assert Team.objects.filter(session=session).count() == 3
    assert client.session.get('v2_rosters') is None, \
        'stored candidates should be cleared after applying'


@pytest.mark.django_db
def test_select_roster_rejects_out_of_range_index(client):
    session, _ = build_league(12)
    client.post(reverse('select_roster_v2', args=[session.pk]),
                {'selected_roster': '99'})
    assert Team.objects.filter(session=session).count() == 0
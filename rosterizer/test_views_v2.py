import pytest
from django.urls import reverse

from .models import Player, PlayerSession, Session, Team, TeamResult
from .views_v2 import apply_roster, commit_roster, results_coverage


def form_payload(client, session, values):
    """
    Build a POST body using the field names the rendered form actually emits.

    Deriving the names from the HTML rather than hard-coding them means a
    template/view mismatch fails the test instead of passing it. An earlier
    suite hard-coded a field the template never rendered, so a completely dead
    results form still had 100% coverage.
    """
    import re
    body = client.get(reverse('enter_results', args=[session.pk])).content.decode()
    payload = {}
    for name in re.findall(r'name="(team_\d+_(?:wins|losses|ties))"', body):
        _, number, field = name.split('_')[0], name.split('_')[1], name.rsplit('_', 1)[1]
        payload[name] = str(values.get((int(number), field), 0))
    return payload


def build_committed(number_of_teams=2, year=2025):
    session = Session.objects.create(year=year, session_number=1)
    teams = []
    players = []
    for t in range(number_of_teams):
        members = []
        for p in range(4):
            player = Player.objects.create(first_name=f'T{t}P{p}', last_name='X')
            players.append(player)
            members.append(player)
        teams.append(Team.objects.create(
            session=session, team_number=t + 1,
            skip=members[0], vice=members[1], second=members[2], lead=members[3]))
    return session, teams, players


# --------------------------------------------------------------------------
# 7.1 commit_roster
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_commit_snapshots_current_teams():
    session, teams, players = build_committed(2)
    assert session.results_committed is False

    commit_roster(session)

    session.refresh_from_db()
    assert session.results_committed is True
    assert TeamResult.objects.filter(session=session).count() == 2

    result = TeamResult.objects.get(session=session, team_number=1)
    assert result.skip_id == teams[0].skip_id
    assert result.lead_id == teams[0].lead_id


@pytest.mark.django_db
def test_commit_is_idempotent():
    session, teams, players = build_committed(2)
    commit_roster(session)
    commit_roster(session)
    assert TeamResult.objects.filter(session=session).count() == 2


@pytest.mark.django_db
def test_commit_preserves_existing_results():
    session, teams, players = build_committed(1)
    TeamResult.objects.create(session=session, team_number=1,
                              skip=teams[0].skip, wins=5, losses=3)
    commit_roster(session)

    result = TeamResult.objects.get(session=session, team_number=1)
    assert (result.wins, result.losses) == (5, 3), 'commit must not wipe entered results'


# --------------------------------------------------------------------------
# 7.2 results entry view
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_enter_results_get_renders_rows(client):
    session, teams, players = build_committed(2)
    response = client.get(reverse('enter_results', args=[session.pk]))

    assert response.status_code == 200
    assert len(response.context['rows']) == 2
    assert b'T1P0' in response.content


@pytest.mark.django_db
def test_enter_results_prefills_existing_values(client):
    session, teams, players = build_committed(2)
    commit_roster(session)
    TeamResult.objects.filter(session=session, team_number=1).update(wins=6, losses=2)

    body = client.get(reverse('enter_results', args=[session.pk])).content.decode()
    assert 'value="6"' in body


@pytest.mark.django_db
def test_enter_results_post_creates_records(client):
    session, teams, players = build_committed(2)
    commit_roster(session)

    client.post(reverse('enter_results', args=[session.pk]), form_payload(client, session, {
        (1, 'wins'): 5, (1, 'losses'): 3, (1, 'ties'): 1,
        (2, 'wins'): 2, (2, 'losses'): 6, (2, 'ties'): 0,
    }))

    first = TeamResult.objects.get(session=session, team_number=1)
    assert (first.wins, first.losses, first.ties) == (5, 3, 1)
    assert first.win_rate == pytest.approx((5 + 0.5) / 9)


@pytest.mark.django_db
def test_enter_results_post_updates_rather_than_duplicates(client):
    session, teams, players = build_committed(1)
    commit_roster(session)
    url = reverse('enter_results', args=[session.pk])

    client.post(url, form_payload(client, session,
                                  {(1, 'wins'): 1, (1, 'losses'): 1, (1, 'ties'): 0}))
    client.post(url, form_payload(client, session,
                                  {(1, 'wins'): 4, (1, 'losses'): 4, (1, 'ties'): 0}))

    assert TeamResult.objects.filter(session=session).count() == 1
    assert TeamResult.objects.get(session=session, team_number=1).wins == 4


@pytest.mark.django_db
def test_enter_results_rejected_before_commit(client):
    session, teams, players = build_committed(1)
    client.post(reverse('enter_results', args=[session.pk]),
                form_payload(client, session,
                             {(1, 'wins'): 5, (1, 'losses'): 3, (1, 'ties'): 0}))
    assert TeamResult.objects.filter(session=session).count() == 0


@pytest.mark.django_db
def test_commit_view_sets_flag(client):
    session, teams, players = build_committed(1)
    client.post(reverse('commit_roster', args=[session.pk]))
    session.refresh_from_db()
    assert session.results_committed is True


@pytest.mark.django_db
def test_negative_and_blank_values_clamped(client):
    session, teams, players = build_committed(1)
    commit_roster(session)
    client.post(reverse('enter_results', args=[session.pk]), {
        'team_1_wins': 'abc', 'team_1_losses': '-4', 'team_1_ties': ''})
    result = TeamResult.objects.get(session=session, team_number=1)
    assert result.wins == 0 and result.losses == 0 and result.ties == 0


# --------------------------------------------------------------------------
# 7.4 deletion guards
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_delete_session_blocked_when_results_exist(client):
    session, teams, players = build_committed(1)
    commit_roster(session)

    client.post(reverse('delete_session', args=[session.pk]))
    assert Session.objects.filter(pk=session.pk).exists()


@pytest.mark.django_db
def test_delete_session_allowed_without_results(client):
    session = Session.objects.create(year=2025, session_number=9)
    client.post(reverse('delete_session', args=[session.pk]))
    assert not Session.objects.filter(pk=session.pk).exists()


@pytest.mark.django_db
def test_clear_players_blocked_when_results_reference_them(client):
    session, teams, players = build_committed(1)
    commit_roster(session)

    client.post(reverse('clear_player_list'))
    assert Player.objects.filter(pk=teams[0].skip_id).exists()


@pytest.mark.django_db
def test_clear_players_allowed_without_results(client):
    build_committed(1)
    client.post(reverse('clear_player_list'))
    assert not Player.objects.exists()


# --------------------------------------------------------------------------
# 7.5 clear_teams warning
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_clear_teams_warns_when_results_exist(client):
    session, teams, players = build_committed(2)
    commit_roster(session)

    response = client.get(reverse('clear_teams', args=[session.pk]))
    assert response.status_code == 200
    assert b'Recorded results' in response.content
    assert Team.objects.filter(session=session).count() == 2, 'teams must survive the warning'


@pytest.mark.django_db
def test_clear_teams_proceeds_after_confirmation(client):
    session, teams, players = build_committed(2)
    commit_roster(session)

    client.post(reverse('clear_teams', args=[session.pk]), {'confirmed': '1'})
    assert Team.objects.filter(session=session).count() == 0
    assert TeamResult.objects.filter(session=session).count() == 2, 'results must survive'


@pytest.mark.django_db
def test_clear_teams_resets_commit_flag(client):
    session, teams, players = build_committed(1)
    commit_roster(session)
    client.post(reverse('clear_teams', args=[session.pk]), {'confirmed': '1'})
    session.refresh_from_db()
    assert session.results_committed is False


# --------------------------------------------------------------------------
# apply_roster
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_apply_roster_appends_after_existing_teams():
    session = Session.objects.create(year=2025, session_number=1)
    existing = []
    for t in range(2):
        members = [Player.objects.create(first_name=f'E{t}{p}', last_name='X') for p in range(4)]
        existing.append(Team.objects.create(
            session=session, team_number=t + 1,
            skip=members[0], vice=members[1], second=members[2], lead=members[3]))

    new_pss = []
    for i in range(4):
        player = Player.objects.create(first_name=f'N{i}', last_name='X')
        new_pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=5,
            preferred_position1='Skip', preferred_position2='', play_with=''))

    created = apply_roster(session, [{'Skip': new_pss[0].pk, 'Vice': new_pss[1].pk,
                                      'Second': new_pss[2].pk, 'Lead': new_pss[3].pk}])

    assert created == 1
    assert Team.objects.filter(session=session).count() == 3
    assert Team.objects.filter(session=session).order_by('team_number').last().team_number == 3


@pytest.mark.django_db
def test_apply_roster_skips_identical_existing_team():
    session = Session.objects.create(year=2025, session_number=1)
    pss = []
    for i in range(4):
        player = Player.objects.create(first_name=f'X{i}', last_name='X')
        pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=5,
            preferred_position1='Skip', preferred_position2='', play_with=''))
    roster = [{'Skip': pss[0].pk, 'Vice': pss[1].pk,
               'Second': pss[2].pk, 'Lead': pss[3].pk}]
    assert apply_roster(session, roster) == 1
    assert apply_roster(session, roster) == 0, 'reapplying the same roster adds nothing'


# --------------------------------------------------------------------------
# results coverage reporting
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_coverage_reports_no_results():
    session = Session.objects.create(year=2025, session_number=1)
    Session.objects.create(year=2024, session_number=1)
    coverage = results_coverage(session)
    assert coverage['any_results'] is False
    assert coverage['total_sessions'] == 1


@pytest.mark.django_db
def test_coverage_reports_partial_results():
    session = Session.objects.create(year=2025, session_number=1)
    prior = Session.objects.create(year=2024, session_number=1)
    players = [Player.objects.create(first_name=f'C{i}', last_name='X') for i in range(4)]
    TeamResult.objects.create(session=prior, team_number=1, skip=players[0], wins=4, losses=4)
    TeamResult.objects.create(session=prior, team_number=2, skip=players[1], wins=3, losses=5)

    coverage = results_coverage(session)
    assert coverage['any_results'] is True
    assert coverage['sessions_with_results'] == 1
    assert coverage['per_session'][prior.pk] == 2
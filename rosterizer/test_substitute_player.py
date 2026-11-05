"""
Tests for the substitute_player management command.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from .models import Player, PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS


# ── helpers ────────────────────────────────────────────────────────────


def build_session_with_teams(n_players=8, n_teams=2):
    """Create a session with players registered and teams assigned."""
    session = Session.objects.create(year=2025, session_number=1)
    players = []
    for i in range(n_players):
        p = Player.objects.create(first_name=f'P{i}', last_name='Test')
        PlayerSession.objects.create(
            player=p, session=session, years_curled=i,
            preferred_position1=POSITIONS[i % 4],
            preferred_position2='', play_with='',
        )
        players.append(p)
    for t in range(n_teams):
        base = t * 4
        Team.objects.create(
            session=session, team_number=t + 1,
            skip=players[base],
            vice=players[base + 1],
            second=players[base + 2],
            lead=players[base + 3],
        )
    return session, players


def run_command(session_id, remove_id, add_id, apply=False):
    """Run substitute_player and return (stdout, stderr) as strings."""
    out = StringIO()
    err = StringIO()
    args = [
        '--session-id', str(session_id),
        '--remove-player', str(remove_id),
        '--add-player', str(add_id),
    ]
    if apply:
        args.append('--apply')
    call_command('substitute_player', *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


# ── 1.2 validation: missing players ────────────────────────────────────


@pytest.mark.django_db
def test_error_when_remove_player_does_not_exist():
    session, players = build_session_with_teams()
    with pytest.raises(CommandError) as exc:
        run_command(session.pk, 9999, players[0].pk)
    assert '9999' in str(exc.value)
    assert 'does not exist' in str(exc.value)


@pytest.mark.django_db
def test_error_when_add_player_does_not_exist():
    session, players = build_session_with_teams()
    with pytest.raises(CommandError) as exc:
        run_command(session.pk, players[0].pk, 9999)
    assert '9999' in str(exc.value)
    assert 'does not exist' in str(exc.value)


@pytest.mark.django_db
def test_error_when_session_does_not_exist():
    with pytest.raises(CommandError) as exc:
        run_command(9999, 1, 2)
    assert '9999' in str(exc.value)


# ── 1.3 validation: removed player not registered ──────────────────────


@pytest.mark.django_db
def test_error_when_remove_player_not_registered():
    session, players = build_session_with_teams()
    # Create a player who is NOT registered in this session
    outsider = Player.objects.create(first_name='Out', last_name='Sider')
    add_player = Player.objects.create(first_name='New', last_name='Player')
    PlayerSession.objects.create(
        player=add_player, session=session, years_curled=1,
        preferred_position1='Skip', preferred_position2='', play_with='',
    )

    with pytest.raises(CommandError) as exc:
        run_command(session.pk, outsider.pk, add_player.pk)
    assert 'not registered' in str(exc.value)


# ── 2.1 dry-run output ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_dry_run_reports_planned_changes():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    # players[0] is skip on team 1; substitute players[7] (lead on team 2)
    add_player = Player.objects.create(first_name='Sub', last_name='Test')
    out, _ = run_command(session.pk, players[0].pk, add_player.pk, apply=False)

    assert 'Dry-run complete' in out
    assert 'No changes written' in out
    assert '--apply' in out
    assert 'register' in out  # PlayerSession would be created
    assert 'Team 1' in out    # players[0] is skip on team 1
    assert add_player.full_name in out

    # Confirm no writes happened
    assert not PlayerSession.objects.filter(
        player=add_player, session=session,
    ).exists()
    team1 = Team.objects.get(session=session, team_number=1)
    assert team1.skip == players[0]


@pytest.mark.django_db
def test_dry_run_when_sub_already_registered():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    # players[7] is a registered lead on team 2; substitute into team 1 skip
    out, _ = run_command(session.pk, players[0].pk, players[7].pk, apply=False)

    assert 'already registered' in out
    assert 'Team 1' in out
    assert 'Dry-run complete' in out


# ── 2.2 apply path ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_apply_creates_playersession_and_updates_teams():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    add_player = Player.objects.create(first_name='Sub', last_name='Test')
    old_skip = players[0]

    out, _ = run_command(session.pk, old_skip.pk, add_player.pk, apply=True)

    assert 'Substitution complete' in out
    assert 'Registered' in out

    # PlayerSession created
    ps = PlayerSession.objects.get(player=add_player, session=session)
    assert ps is not None

    # Team updated
    team1 = Team.objects.get(session=session, team_number=1)
    assert team1.skip == add_player
    assert team1.vice == players[1]  # unchanged


@pytest.mark.django_db
def test_apply_updates_multiple_teams():
    """When the removed player appears on more than one team."""
    # Create 3 teams; put the same player as skip on teams 1 and 2
    session = Session.objects.create(year=2025, session_number=1)
    ps_list = []
    for i in range(12):
        p = Player.objects.create(first_name=f'P{i}', last_name='Test')
        ps_list.append(PlayerSession.objects.create(
            player=p, session=session, years_curled=i,
            preferred_position1=POSITIONS[i % 4],
            preferred_position2='', play_with='',
        ))
    # Player 0 is skip on team 1 and skip on team 2
    Team.objects.create(
        session=session, team_number=1,
        skip=ps_list[0].player, vice=ps_list[1].player,
        second=ps_list[2].player, lead=ps_list[3].player,
    )
    Team.objects.create(
        session=session, team_number=2,
        skip=ps_list[0].player, vice=ps_list[5].player,
        second=ps_list[6].player, lead=ps_list[7].player,
    )
    Team.objects.create(
        session=session, team_number=3,
        skip=ps_list[8].player, vice=ps_list[9].player,
        second=ps_list[10].player, lead=ps_list[11].player,
    )

    add_player = Player.objects.create(first_name='Sub', last_name='Test')
    run_command(session.pk, ps_list[0].player.pk, add_player.pk, apply=True)

    assert Team.objects.get(session=session, team_number=1).skip == add_player
    assert Team.objects.get(session=session, team_number=2).skip == add_player
    # Team 3 skip unchanged
    assert Team.objects.get(session=session, team_number=3).skip == ps_list[8].player


# ── 2.3 idempotency ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_idempotent_reapply():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    add_player = Player.objects.create(first_name='Sub', last_name='Test')

    # First apply
    run_command(session.pk, players[0].pk, add_player.pk, apply=True)
    assert Team.objects.get(session=session, team_number=1).skip == add_player

    # Second apply — should detect no changes
    out, _ = run_command(session.pk, players[0].pk, add_player.pk, apply=True)
    assert 'already complete' in out


@pytest.mark.django_db
def test_idempotent_dry_run_after_apply():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    add_player = Player.objects.create(first_name='Sub', last_name='Test')

    run_command(session.pk, players[0].pk, add_player.pk, apply=True)
    out, _ = run_command(session.pk, players[0].pk, add_player.pk, apply=False)
    assert 'already complete' in out


# ── 3.1 substitute already registered in session ───────────────────────


@pytest.mark.django_db
def test_apply_when_sub_already_registered():
    session, players = build_session_with_teams(n_players=12, n_teams=2)
    # players[8] is registered (index 8-11 are unassigned). Substitute into
    # players[0]'s skip position.
    add_player = players[8]
    ps_before = PlayerSession.objects.filter(
        player=add_player, session=session,
    ).count()

    run_command(session.pk, players[0].pk, add_player.pk, apply=True)

    # No duplicate PlayerSession
    ps_after = PlayerSession.objects.filter(
        player=add_player, session=session,
    ).count()
    assert ps_after == ps_before

    # Team was still updated
    assert Team.objects.get(session=session, team_number=1).skip == add_player


# ── 3.2 session has no teams ───────────────────────────────────────────


@pytest.mark.django_db
def test_no_teams_still_registers_substitute():
    session = Session.objects.create(year=2025, session_number=1)
    old_p = Player.objects.create(first_name='Old', last_name='Player')
    new_p = Player.objects.create(first_name='New', last_name='Player')
    PlayerSession.objects.create(
        player=old_p, session=session, years_curled=1,
        preferred_position1='Skip', preferred_position2='', play_with='',
    )

    out, _ = run_command(session.pk, old_p.pk, new_p.pk, apply=True)

    assert 'Substitution complete' in out
    assert PlayerSession.objects.filter(player=new_p, session=session).exists()
    # No teams to update — the output should reflect that
    assert 'team' not in out.lower() or '0 team' in out.lower() or (
        'Updated 0 team' in out
    )


@pytest.mark.django_db
def test_no_teams_dry_run():
    session = Session.objects.create(year=2025, session_number=1)
    old_p = Player.objects.create(first_name='Old', last_name='Player')
    new_p = Player.objects.create(first_name='New', last_name='Player')
    PlayerSession.objects.create(
        player=old_p, session=session, years_curled=1,
        preferred_position1='Skip', preferred_position2='', play_with='',
    )

    out, _ = run_command(session.pk, old_p.pk, new_p.pk, apply=False)
    assert 'Dry-run complete' in out


# ── 3.3 results committed — TeamResult swap ────────────────────────────


@pytest.mark.django_db
def test_apply_updates_teamresults_when_committed():
    session, players = build_session_with_teams(n_players=8, n_teams=2)

    # Commit results
    session.results_committed = True
    session.save()
    TeamResult.objects.create(
        session=session, team_number=1,
        skip=players[0], vice=players[1],
        second=players[2], lead=players[3],
    )
    TeamResult.objects.create(
        session=session, team_number=2,
        skip=players[4], vice=players[5],
        second=players[6], lead=players[7],
    )

    add_player = Player.objects.create(first_name='Sub', last_name='Test')
    run_command(session.pk, players[0].pk, add_player.pk, apply=True)

    # TeamResult updated
    tr = TeamResult.objects.get(session=session, team_number=1)
    assert tr.skip == add_player

    # TeamResult team 2 unchanged
    tr2 = TeamResult.objects.get(session=session, team_number=2)
    assert tr2.skip == players[4]


@pytest.mark.django_db
def test_dry_run_reports_teamresult_changes():
    session, players = build_session_with_teams(n_players=8, n_teams=2)
    session.results_committed = True
    session.save()
    TeamResult.objects.create(
        session=session, team_number=1,
        skip=players[0], vice=players[1],
        second=players[2], lead=players[3],
    )

    add_player = Player.objects.create(first_name='Sub', last_name='Test')
    out, _ = run_command(session.pk, players[0].pk, add_player.pk, apply=False)

    assert 'TeamResult' in out
    assert 'Dry-run complete' in out

    # No writes happened
    tr = TeamResult.objects.get(session=session, team_number=1)
    assert tr.skip == players[0]
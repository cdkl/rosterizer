"""
CLI reporting for the locked-team path.

Covers tasks 6.1-6.3.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from .models import Player, PlayerSession, Session, Team
from .position_strength import POSITIONS


def build_locked_league(n, locked_teams=0):
    session = Session.objects.create(year=2025, session_number=1)
    pss = []
    for i in range(n):
        player = Player.objects.create(first_name=f'P{i}', last_name='X')
        pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=(i * 3) % 40,
            preferred_position1=POSITIONS[i % 4], preferred_position2='', play_with=''))
    for t in range(locked_teams):
        members = pss[t * 4:(t + 1) * 4]
        Team.objects.create(
            session=session, team_number=t + 1,
            skip=members[0].player, vice=members[1].player,
            second=members[2].player, lead=members[3].player)
    return session, pss


@pytest.mark.django_db
def test_command_reports_locked_and_unassigned_counts():
    session, pss = build_locked_league(30, locked_teams=2)
    out = StringIO()
    call_command('generate_rosters_v2', '--session-id', str(session.pk),
                 '--candidates', '2', '--seed', '1', stdout=out)

    text = out.getvalue()
    assert '2 locked team(s)' in text
    assert '22 unassigned player(s)' in text


@pytest.mark.django_db
def test_command_reports_spanning_conflict_and_exits_non_zero():
    session, pss = build_locked_league(12, locked_teams=1)
    pss[0].play_with = 'P4 X'
    pss[0].save()

    with pytest.raises(CommandError) as exc:
        call_command('generate_rosters_v2', '--session-id', str(session.pk))

    assert 'existing team' in str(exc.value)


@pytest.mark.django_db
def test_command_reports_nothing_to_assign_and_exits_cleanly():
    session, pss = build_locked_league(8, locked_teams=2)
    out = StringIO()
    call_command('generate_rosters_v2', '--session-id', str(session.pk), stdout=out)
    assert 'No players remain to assign' in out.getvalue()

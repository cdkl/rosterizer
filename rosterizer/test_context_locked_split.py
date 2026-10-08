"""
Context build splits already-placed (locked) players from the available pool.

Covers tasks 1.1-1.4: the locked/available split, its effect on team_count and
mean_contribution, and that query count stays flat as locked teams grow.
"""

import random

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .models import Player, PlayerSession, Session, Team
from .position_strength import POSITIONS
from .roster_evaluation_v2 import build_context


def build_locked_league(n, locked_teams=0, years=lambda i: (i * 3) % 40):
    """A session of n players, with the first `locked_teams` quartets on teams."""
    session = Session.objects.create(year=2025, session_number=1)
    pss = []
    for i in range(n):
        player = Player.objects.create(first_name=f'P{i}', last_name='X')
        pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=years(i),
            preferred_position1=POSITIONS[i % 4], preferred_position2='', play_with=''))
    lock_teams(session, pss, locked_teams)
    return session, pss


def lock_teams(session, pss, count):
    for t in range(count):
        members = pss[t * 4:(t + 1) * 4]
        Team.objects.create(
            session=session, team_number=t + 1,
            skip=members[0].player, vice=members[1].player,
            second=members[2].player, lead=members[3].player)


# --------------------------------------------------------------------------
# 1.1 query count stays flat
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_query_count_flat_as_locked_teams_grow():
    session, pss = build_locked_league(32, locked_teams=0)
    with CaptureQueriesContext(connection) as none_locked:
        build_context(session.pk)

    # Lock every team; adding teams must not add per-team queries.
    lock_teams(session, pss, 8)
    with CaptureQueriesContext(connection) as all_locked:
        build_context(session.pk)

    assert len(none_locked) == len(all_locked), 'query count scaled with team count'


@pytest.mark.django_db
def test_build_context_uses_fixed_query_count(django_assert_num_queries):
    session, pss = build_locked_league(8, locked_teams=2)
    with django_assert_num_queries(6):
        build_context(session.pk)


# --------------------------------------------------------------------------
# 1.2 locked/available split and team_count
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_locked_teams_behaviour_unchanged():
    session, pss = build_locked_league(8, locked_teams=0)
    ctx = build_context(session.pk)
    assert ctx.registered_player_ids == frozenset(ps.player_id for ps in pss)
    assert ctx.locked_player_ids == frozenset()
    assert ctx.locked_team_count == 0
    assert ctx.team_count == 2


@pytest.mark.django_db
def test_some_locked_teams_split_available_pool():
    session, pss = build_locked_league(30, locked_teams=2)
    ctx = build_context(session.pk)

    locked = frozenset(ps.player_id for ps in pss[:8])
    assert ctx.locked_player_ids == locked
    assert ctx.locked_team_count == 2
    assert ctx.registered_player_ids.isdisjoint(locked)
    assert len(ctx.registered_player_ids) == 22
    assert ctx.team_count == 6


@pytest.mark.django_db
def test_all_players_locked_gives_zero_teams():
    session, pss = build_locked_league(8, locked_teams=2)
    ctx = build_context(session.pk)
    assert ctx.registered_player_ids == frozenset()
    assert ctx.locked_player_ids == frozenset(ps.player_id for ps in pss)
    assert ctx.locked_team_count == 2
    assert ctx.team_count == 0


# --------------------------------------------------------------------------
# 1.3 mean_contribution scoped to the available pool
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_mean_contribution_scoped_to_available_pool():
    # Locked players are veterans; the available pool are novices.
    session, pss = build_locked_league(
        30, locked_teams=2, years=lambda i: 40 if i < 8 else 0)
    ctx = build_context(session.pk)

    available = ctx.registered_player_ids
    expected = sum(
        max(ctx.abilities.player_contribution(pid, p) for p in POSITIONS)
        for pid in available) / len(available)
    assert ctx.mean_contribution == pytest.approx(expected)

    # It must not be dragged up by the locked veterans.
    all_ids = {ps.player_id for ps in pss}
    all_mean = sum(
        max(ctx.abilities.player_contribution(pid, p) for p in POSITIONS)
        for pid in all_ids) / len(all_ids)
    assert ctx.mean_contribution < all_mean

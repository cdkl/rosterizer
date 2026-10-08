"""
Locked-team behaviour for validation, generation and scoring.

Covers tasks 2.1-2.3 (validation), 3.1-3.2 (generation) and 4.1-4.2 (scoring).
"""

import random

import pytest

from .models import Player, PlayerRule, PlayerSession, Session, Team
from .position_strength import POSITIONS
from .roster_evaluation_v2 import (
    build_context,
    evaluate_completeness,
    evaluate_roster,
    evaluate_team_balance,
)
from .team_generation_v2 import (
    ValidationProblem,
    generate_rosters_v2,
    initialise_roster,
    validate_session,
)


def build_locked_league(n, locked_teams=0):
    """A session of n players, with the first `locked_teams` quartets on teams."""
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


def placed_player_session_ids(roster):
    return [v for team in roster for v in team.values() if v is not None]


def placed_player_ids(roster, context):
    return {context.player_id(v) for v in placed_player_session_ids(roster)}


# --------------------------------------------------------------------------
# 2.1 reject spanning constraints
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_validate_blocks_play_with_spanning_locked_team():
    """A locked player naming an unassigned partner is unsatisfiable."""
    session, pss = build_locked_league(12, locked_teams=1)
    pss[0].play_with = 'P4 X'          # pss[0] is locked; pss[4] is not
    pss[0].save()

    with pytest.raises(ValidationProblem) as exc:
        validate_session(session.pk)

    message = str(exc.value)
    assert 'existing team' in message
    assert str(pss[0].player_id) in message
    assert str(pss[4].player_id) in message


@pytest.mark.django_db
def test_validate_blocks_group_with_locked_members_on_different_teams():
    session, pss = build_locked_league(16, locked_teams=2)
    PlayerRule.objects.create(
        rule_type='must_be_together',
        player1=pss[0].player, player2=pss[4].player)  # team 1 vs team 2

    with pytest.raises(ValidationProblem) as exc:
        validate_session(session.pk)

    assert 'different teams' in str(exc.value)


# --------------------------------------------------------------------------
# 2.2 benign case: pairing entirely inside one locked team
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_validate_accepts_pair_within_one_locked_team():
    session, pss = build_locked_league(12, locked_teams=1)
    pss[0].play_with = 'P1 X'          # both locked on team 1
    pss[0].save()

    context = validate_session(session.pk)
    pair = frozenset({pss[0].player_id, pss[1].player_id})
    assert pair in context.co_location_groups

    out = generate_rosters_v2(session.pk, num_candidates=3, seed=1)
    locked_ps = {pss[0].pk, pss[1].pk}
    for candidate in out['candidates']:
        assert locked_ps.isdisjoint(placed_player_session_ids(candidate['roster']))


# --------------------------------------------------------------------------
# 2.3 locked teams without spanning constraints generate normally
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generate_with_locked_teams_produces_candidates():
    session, pss = build_locked_league(30, locked_teams=2)
    context = validate_session(session.pk)
    out = generate_rosters_v2(session.pk, num_candidates=3, seed=1, context=context)
    assert len(out['candidates']) == 3
    assert context.team_count == 6


# --------------------------------------------------------------------------
# 3.1 generated rosters never contain a locked player
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generated_candidates_exclude_locked_players():
    session, pss = build_locked_league(30, locked_teams=2)
    out = generate_rosters_v2(session.pk, num_candidates=5, seed=7)

    locked_ps = {ps.pk for ps in pss[:8]}
    assert len(out['candidates']) == 5
    for candidate in out['candidates']:
        placed = placed_player_session_ids(candidate['roster'])
        assert len(placed) == len(set(placed))
        assert locked_ps.isdisjoint(placed)
        assert candidate['criteria']['completeness'] == 1.0


# --------------------------------------------------------------------------
# 3.2 fully-placed session returns no candidates
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_fully_placed_session_returns_no_candidates():
    session, pss = build_locked_league(8, locked_teams=2)
    context = validate_session(session.pk)
    assert context.team_count == 0

    out = generate_rosters_v2(session.pk, num_candidates=5, seed=1, context=context)
    assert out['candidates'] == []
    assert out['shortfall'] == 5
    assert out['requested'] == 5


@pytest.mark.django_db
def test_fully_placed_session_does_not_raise():
    session, pss = build_locked_league(8, locked_teams=2)
    out = generate_rosters_v2(session.pk, num_candidates=3, seed=1)
    assert out['candidates'] == []


# --------------------------------------------------------------------------
# 4.1 completeness counts locked players as satisfied
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_completeness_scores_locked_players_as_satisfied():
    session, pss = build_locked_league(30, locked_teams=2)
    ctx = build_context(session.pk)

    roster = initialise_roster(ctx, random.Random(0))
    assert evaluate_completeness(roster, ctx) == 1.0

    # Drop one available player: the score degrades to the one-missing band.
    damaged = [dict(team) for team in roster]
    for team in damaged:
        for position in POSITIONS:
            if team[position] is not None:
                team[position] = None
                break
        else:
            continue
        break
    assert evaluate_completeness(damaged, ctx) == 0.7


# --------------------------------------------------------------------------
# 4.2 balance is scoped to generated teams
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_balance_scoped_to_generated_teams():
    session, pss = build_locked_league(30, locked_teams=2)
    ctx = build_context(session.pk)

    roster = initialise_roster(ctx, random.Random(0))
    assert len(roster) == ctx.team_count
    assert placed_player_ids(roster, ctx).isdisjoint(
        {ps.player_id for ps in pss[:8]})

    score = evaluate_team_balance(roster, ctx)
    assert 0.0 <= score <= 1.0


# --------------------------------------------------------------------------
# 9. play-with reporting scoped to the generated pool
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_locked_play_with_pair_not_reported_or_penalised():
    session, pss = build_locked_league(16, locked_teams=1)  # pss 0-3 locked
    pss[0].play_with = 'P1 X'          # pair entirely inside the locked team
    pss[0].save()

    context = build_context(session.pk)
    pair = frozenset({pss[0].player_id, pss[1].player_id})
    assert pair in context.play_with_pairs

    out = generate_rosters_v2(session.pk, num_candidates=3, seed=1, context=context)
    for candidate in out['candidates']:
        assert not any('play-with' in v for v in candidate['violations'])
        assert candidate['criteria']['plays_with_adherence'] == pytest.approx(1.0)


@pytest.mark.django_db
def test_split_unassigned_play_with_pair_reported_once():
    session, pss = build_locked_league(8, locked_teams=0)
    pss[0].play_with = 'P1 X'
    pss[0].save()
    context = build_context(session.pk)

    # Partners deliberately on different teams; everyone else placed too.
    roster = [
        {POSITIONS[0]: pss[0].pk, POSITIONS[1]: pss[2].pk,
         POSITIONS[2]: pss[3].pk, POSITIONS[3]: pss[4].pk},
        {POSITIONS[0]: pss[1].pk, POSITIONS[1]: pss[5].pk,
         POSITIONS[2]: pss[6].pk, POSITIONS[3]: pss[7].pk},
    ]
    result = evaluate_roster(roster, context)
    reported = [v for v in result['violations'] if 'play-with' in v]
    assert len(reported) == 1
    assert result['criteria']['plays_with_adherence'] < 1.0


@pytest.mark.django_db
def test_multiple_split_pairs_each_reported_once_not_per_team():
    session, pss = build_locked_league(16, locked_teams=0)
    pss[0].play_with = 'P1 X'
    pss[2].play_with = 'P3 X'
    pss[0].save()
    pss[2].save()
    context = build_context(session.pk)

    # Two declared pairs, each kept apart across the four teams.
    roster = [{POSITIONS[0]: pss[t].pk, POSITIONS[1]: pss[t + 4].pk,
               POSITIONS[2]: pss[t + 8].pk, POSITIONS[3]: pss[t + 12].pk}
              for t in range(4)]
    reported = [v for v in evaluate_roster(roster, context)['violations']
                if 'play-with' in v]
    assert len(reported) == 2


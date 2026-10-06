"""
End-to-end coverage across two sessions.

Exercises the path a convenor actually takes: build and commit a past session's
teams, record results, then generate the next session's roster and confirm the
recorded results actually influence the outcome.
"""

import pytest

from .models import Player, PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS, build_ability_table
from .roster_evaluation_v2 import build_context, evaluate_roster
from .team_generation_v2 import generate_rosters_v2
from .views_v2 import apply_roster, commit_roster


def build_two_sessions(player_count=16):
    prior = Session.objects.create(year=2024, session_number=1)
    current = Session.objects.create(year=2025, session_number=1)
    players = []
    for i in range(player_count):
        player = Player.objects.create(first_name=f'P{i:02d}', last_name='X')
        years = 2 + (i * 2) % 30
        for session in (prior, current):
            PlayerSession.objects.create(
                player=player, session=session, years_curled=years,
                preferred_position1=POSITIONS[i % 4],
                preferred_position2='', play_with='')
        players.append((player, years))
    return prior, current, players


def most_experienced(players):
    """The genuinely most experienced player, not merely the last created."""
    player, years = max(players, key=lambda pair: pair[1])
    return player


def most_experienced_skip(players, team_size=4):
    """
    The most experienced player who actually plays Skip.

    A bad record only bites at the position it was earned, so the test has to
    target someone who really is a Skip in the prior session.
    """
    skips = [pair for index, pair in enumerate(players)
             if index % team_size == 0]
    player, years = max(skips, key=lambda pair: pair[1])
    return player


def commit_prior_session_with_results(prior, players, bad_records_for=()):
    """Lay out teams, commit them, and record a result per team."""
    team_size = 4
    flat = [p for p, _ in players]
    for t in range(len(flat) // team_size):
        Team.objects.create(
            session=prior, team_number=t + 1,
            skip=flat[t * team_size], vice=flat[t * team_size + 1],
            second=flat[t * team_size + 2], lead=flat[t * team_size + 3])
    commit_roster(prior)

    for result in TeamResult.objects.filter(session=prior):
        if result.skip_id in {p.id for p in bad_records_for}:
            result.wins, result.losses = 2, 8
        else:
            result.wins, result.losses = 8, 2
        result.ties = 0
        result.save()


@pytest.mark.django_db
def test_bad_position_record_lowers_ability_at_that_position_only():
    """
    A poor record at one position must lower ability there and nowhere else.

    This is what makes position-specific ratings meaningful: the evidence is
    attributed to the position it was earned at.
    """
    prior, current, players = build_two_sessions(16)
    veteran = most_experienced_skip(players)
    commit_prior_session_with_results(prior, players, bad_records_for=[veteran])

    years = PlayerSession.objects.get(session=current, player=veteran).years_curled
    assert years >= 20, 'the veteran should genuinely be experienced'

    table = build_ability_table(current.pk)
    assert table.ability(veteran.pk, 'Skip') < 0.6, \
        'a 2-8 record should drag Skip ability well down'
    for untouched in ('Vice', 'Second', 'Lead'):
        assert table.ability(veteran.pk, untouched) > 0.9, \
            f'{untouched} has no results and should stay at the experience value'


@pytest.mark.django_db
def test_generated_rosters_are_well_balanced():
    """
    Team balance is a first-class objective, so generated rosters must be even.

    Note this is deliberately *team-level*: demoting a weak Skip to Lead would
    load their value onto an already-strong team and widen the spread, so
    team balance can legitimately keep them at Skip.
    """
    prior, current, players = build_two_sessions(16)
    veteran = most_experienced_skip(players)
    commit_prior_session_with_results(prior, players, bad_records_for=[veteran])

    out = generate_rosters_v2(current.pk, num_candidates=5, seed=42)
    for candidate in out['candidates']:
        assert candidate['criteria']['team_balance'] > 0.9, \
            f"balance {candidate['criteria']['team_balance']:.3f} is too uneven"


@pytest.mark.django_db
def test_engine_prefers_the_more_balanced_arrangement():
    """
    Of two rosters holding identical players, the better-balanced one must win.

    Both arrangements put every player in their preferred position, so
    preference and play-with scores are identical and balance is the only thing
    that separates them. This is the operative meaning of preferring team
    balance: the engine ranks the even split higher.
    """
    prior, current, players = build_two_sessions(16)
    commit_prior_session_with_results(prior, players)

    flat = [p for p, _ in players]
    ids = {ps.player_id: ps.pk
           for ps in PlayerSession.objects.filter(session=current)}
    preferred = {i: POSITIONS[i % 4] for i in range(16)}

    # Rank each position's players by experience, strongest first.
    years = {i: flat[i].pk and players[i][1] for i in range(16)}
    groups = {position: sorted((i for i in range(16) if preferred[i] == position),
                               key=lambda i: -years[i])
              for position in POSITIONS}

    def build(assignment):
        return [{preferred[skip]: ids[flat[skip].pk],
                 preferred[vice]: ids[flat[vice].pk],
                 preferred[second]: ids[flat[second].pk],
                 preferred[lead]: ids[flat[lead].pk]}
                for skip, vice, second, lead in assignment]

    lopsided = [[groups[p][rank] for p in POSITIONS] for rank in range(4)]
    spread = [[groups['Skip'][0], groups['Vice'][2], groups['Second'][1], groups['Lead'][3]],
              [groups['Skip'][1], groups['Vice'][3], groups['Second'][0], groups['Lead'][2]],
              [groups['Skip'][2], groups['Vice'][0], groups['Second'][3], groups['Lead'][1]],
              [groups['Skip'][3], groups['Vice'][1], groups['Second'][2], groups['Lead'][0]]]

    context = build_context(current.pk)
    even = evaluate_roster(build(spread), context)
    uneven = evaluate_roster(build(lopsided), context)

    # Precondition: only balance separates these two.
    assert even['criteria']['position_preference'] == \
        uneven['criteria']['position_preference']

    assert even['criteria']['team_balance'] > uneven['criteria']['team_balance']
    assert even['composite'] > uneven['composite'], \
        'the engine must rank the balanced roster higher'


@pytest.mark.django_db
def test_generation_produces_complete_violation_free_rosters():
    prior, current, players = build_two_sessions(16)
    commit_prior_session_with_results(prior, players)

    out = generate_rosters_v2(current.pk, num_candidates=6, seed=7)

    assert len(out['candidates']) == 6
    for candidate in out['candidates']:
        assert candidate['criteria']['completeness'] == 1.0
        assert candidate['violations'] == []
        placed = [v for team in candidate['roster'] for v in team.values() if v]
        assert len(placed) == len(set(placed))


@pytest.mark.django_db
def test_full_workflow_persists_teams():
    """Generate, review and apply -- the convenor's full path."""
    prior, current, players = build_two_sessions(16)
    commit_prior_session_with_results(prior, players)

    out = generate_rosters_v2(current.pk, num_candidates=4, seed=11)
    assert out['candidates']

    created = apply_roster(current, out['candidates'][0]['roster'])

    assert created == 4
    assert Team.objects.filter(session=current).count() == 4
    numbers = sorted(Team.objects.filter(session=current)
                     .values_list('team_number', flat=True))
    assert numbers == [1, 2, 3, 4]

    for team in Team.objects.filter(session=current):
        assert team.skip and team.vice and team.second

    # Every player appears exactly once across the applied teams.
    seen = []
    for team in Team.objects.filter(session=current):
        seen.extend(p.id for p in team.get_players())
    assert len(seen) == len(set(seen)) == len(players)


@pytest.mark.django_db
def test_applying_twice_does_not_duplicate_teams():
    prior, current, players = build_two_sessions(16)
    commit_prior_session_with_results(prior, players)

    out = generate_rosters_v2(current.pk, num_candidates=3, seed=11)
    roster = out['candidates'][0]['roster']

    assert apply_roster(current, roster) == 4
    assert apply_roster(current, roster) == 0
    assert Team.objects.filter(session=current).count() == 4


@pytest.mark.django_db
def test_results_survive_a_later_roster_change():
    """
    Regenerating a past session must not rewrite what its results mean.

    The result row keeps its own copy of the roster, so clearing and rebuilding
    the live teams leaves both the results and the ratings they imply intact.
    """
    prior, current, players = build_two_sessions(16)
    veteran = most_experienced_skip(players)
    commit_prior_session_with_results(prior, players, bad_records_for=[veteran])

    ability_before = build_ability_table(current.pk).ability(veteran.pk, 'Skip')
    result_before = list(
        TeamResult.objects.filter(session=prior)
        .values_list('team_number', 'skip_id', 'wins', 'losses'))

    Team.objects.filter(session=prior).delete()
    flat = [p for p, _ in players]
    for t in range(4):
        base = ((t + 2) * 4) % 16
        Team.objects.create(
            session=prior, team_number=t + 1,
            skip=flat[base], vice=flat[base + 1],
            second=flat[base + 2], lead=flat[base + 3])

    ability_after = build_ability_table(current.pk).ability(veteran.pk, 'Skip')
    result_after = list(
        TeamResult.objects.filter(session=prior)
        .values_list('team_number', 'skip_id', 'wins', 'losses'))

    assert ability_after == pytest.approx(ability_before)
    assert result_after == result_before


@pytest.mark.django_db
def test_no_results_falls_back_to_experience_cleanly():
    """A league with no recorded results must still generate valid rosters."""
    session = Session.objects.create(year=2025, session_number=1)
    for i in range(12):
        player = Player.objects.create(first_name=f'N{i}', last_name='X')
        PlayerSession.objects.create(
            player=player, session=session, years_curled=i % 12,
            preferred_position1=POSITIONS[i % 4],
            preferred_position2='', play_with='')

    table = build_ability_table(session.pk)
    assert table.prior_games == 0.0

    out = generate_rosters_v2(session.pk, num_candidates=3, seed=3)
    assert len(out['candidates']) == 3
    for candidate in out['candidates']:
        assert candidate['criteria']['completeness'] == 1.0
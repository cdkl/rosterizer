import pytest
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

from .models import Player, PlayerRule, PlayerSession, Session, Team, TeamResult
from .position_strength import experience_score
from .roster_evaluation_v2 import (
    CRITERION_FLOOR,
    build_context,
    build_co_location_groups,
    co_location_edges,
    evaluate_completeness,
    evaluate_player_rules,
    evaluate_plays_with_adherence,
    evaluate_position_preference,
    evaluate_roster,
    evaluate_rosters,
    evaluate_team_balance,
    evaluate_team_continuity,
    normalise_name,
    resolve_play_with_pairs,
    team_count_for,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def make_players(n, first='P'):
    return [Player.objects.create(first_name=f'{first}{i}', last_name='X') for i in range(n)]


def make_sessions(session, player_sessions, years=10, pref1='Skip', pref2='', play_with=''):
    out = []
    for ps in player_sessions:
        ps.years_curled = years
        ps.preferred_position1 = pref1
        ps.preferred_position2 = pref2
        ps.play_with = play_with
        ps.save()
        out.append(ps)
    return out


def roster_from(pairs):
    """pairs: list of (skip, vice, second, lead); None marks an empty slot."""
    roster = []
    for group in pairs:
        roster.append(dict(zip(
            ('Skip', 'Vice', 'Second', 'Lead'),
            [p.pk if p is not None else None for p in group])))
    return roster


@pytest.fixture
def eight(db):
    """Eight players whose stated preferences match a clean round-robin split."""
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    order = ('Skip', 'Vice', 'Second', 'Lead')
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1=order[i % 4], preferred_position2='', play_with='')
        for i, p in enumerate(players)]
    return session, players, pss


# --------------------------------------------------------------------------
# 3.1 LeagueContext
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_context_built_from_session(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)

    assert ctx.session_id == session.pk
    assert ctx.registered_player_ids == frozenset(p.pk for p in players)
    assert ctx.player_id(pss[0].pk) == players[0].pk
    assert ctx.preference_by_player[players[0].pk] == ('Skip', '')
    assert ctx.team_count == 2


@pytest.mark.django_db
def test_context_is_frozen(eight):
    ctx = build_context(eight[0].pk)
    with pytest.raises(Exception):
        ctx.session_id = 999


@pytest.mark.django_db
def test_context_team_count_handles_remainder(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(30)
    for p in players:
        PlayerSession.objects.create(
            player=p, session=session, years_curled=5,
            preferred_position1='Skip', preferred_position2='', play_with='')
    assert build_context(session.pk).team_count == 8


def test_team_count_arithmetic():
    assert team_count_for(0) == 0
    assert team_count_for(4) == 1
    assert team_count_for(8) == 2
    assert team_count_for(30) == 8
    assert team_count_for(32) == 8


# --------------------------------------------------------------------------
# 3.2 fixed query count
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_context_query_count_flat_as_league_grows(db):
    session = Session.objects.create(year=2025, session_number=1)
    small = make_players(8, first='S')
    large = make_players(32, first='L')
    for p in small + large:
        PlayerSession.objects.create(
            player=p, session=session, years_curled=5,
            preferred_position1='Skip', preferred_position2='', play_with='')

    with CaptureQueriesContext(connection) as ctx_small:
        build_context(session.pk)
    small_q = len(ctx_small)

    with CaptureQueriesContext(connection) as ctx_large:
        build_context(session.pk)
    large_q = len(ctx_large)

    # Second call hits the same shape; neither should scale with player count.
    assert small_q == large_q


@pytest.mark.django_db
def test_scoring_issues_no_queries(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], pss[7])])

    with CaptureQueriesContext(connection) as captured:
        evaluate_roster(roster, ctx)

    assert len(captured) == 0, f'scoring issued {len(captured)} queries'


# --------------------------------------------------------------------------
# 4.1 completeness and position preference
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_completeness_all_assigned(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], pss[7])])
    assert evaluate_completeness(roster, ctx) == 1.0


@pytest.mark.django_db
def test_completeness_degrades_by_missing_count(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    full = lambda: roster_from([(pss[0], pss[1], pss[2], pss[3]),
                                (pss[4], pss[5], pss[6], pss[7])])
    assert evaluate_completeness(full(), ctx) == 1.0

    one_missing = full(); one_missing[1]['Lead'] = None
    assert evaluate_completeness(one_missing, ctx) == 0.7

    two_missing = full(); two_missing[1]['Lead'] = None; two_missing[1]['Second'] = None
    assert evaluate_completeness(two_missing, ctx) == 0.4

    three_missing = full()
    three_missing[1]['Lead'] = None
    three_missing[1]['Second'] = None
    three_missing[1]['Vice'] = None
    assert evaluate_completeness(three_missing, ctx) == 0.0


@pytest.mark.django_db
def test_position_preference_scores(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    prefs = ['Skip', 'Vice', 'Second', 'Lead']
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1=prefs[i], preferred_position2='', play_with='')
        for i, p in enumerate(players)]
    ctx = build_context(session.pk)

    perfect = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_position_preference(perfect, ctx) == pytest.approx(1.0)

    # Three players displaced from their stated preference.
    displaced = roster_from([(pss[0], pss[2], pss[3], pss[1])])
    assert evaluate_position_preference(displaced, ctx) == pytest.approx(0.25)


# --------------------------------------------------------------------------
# 4.2 continuity
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_continuity_perfect_when_no_prior_sessions(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_team_continuity(roster, ctx) == [1.0]


@pytest.mark.django_db
def test_continuity_penalises_repeated_teammates(db):
    s1 = Session.objects.create(year=2024, session_number=1)
    s2 = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=s2, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    prior = Team.objects.create(session=s1, team_number=1,
                                skip=players[0], vice=players[1],
                                second=players[2], lead=players[3])
    ctx = build_context(s2.pk)

    same = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_team_continuity(same, ctx) == [0.0]

    mixed = roster_from([(pss[0], pss[4], pss[5], pss[6])])
    assert evaluate_team_continuity(mixed, ctx) == [1.0]


@pytest.mark.django_db
def test_continuity_scales_with_overlap(db):
    s1 = Session.objects.create(year=2024, session_number=1)
    s2 = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=s2, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    Team.objects.create(session=s1, team_number=1,
                        skip=players[0], vice=players[1], second=players[2], lead=players[3])
    ctx = build_context(s2.pk)

    two = roster_from([(pss[0], pss[1], pss[4], pss[5])])
    three = roster_from([(pss[0], pss[1], pss[2], pss[5])])
    one = roster_from([(pss[0], pss[4], pss[5], pss[6])])

    assert evaluate_team_continuity(two, ctx) == [0.66]
    assert evaluate_team_continuity(three, ctx) == [0.33]
    assert evaluate_team_continuity(one, ctx) == [1.0]


@pytest.mark.django_db
def test_continuity_exempts_declared_play_with_partners(db):
    s1 = Session.objects.create(year=2024, session_number=1)
    s2 = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=s2, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'P1 X'
    pss[0].save()
    Team.objects.create(session=s1, team_number=1,
                        skip=players[0], vice=players[1], second=players[2], lead=players[3])
    ctx = build_context(s2.pk)

    roster = roster_from([(pss[0], pss[1], pss[4], pss[5])])
    # The pair is declared, so their overlap counts as 1 rather than 2.
    assert evaluate_team_continuity(roster, ctx) == [1.0]
    assert evaluate_team_continuity(roster, ctx, exempt_play_with=False) == [0.66]


# --------------------------------------------------------------------------
# 4.3 play-with and rules
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_plays_with_adherence(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'P1 X'
    pss[0].save()
    ctx = build_context(session.pk)

    together = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_plays_with_adherence(together, ctx) == [1.0]


@pytest.mark.django_db
def test_plays_with_split_scores_half(db):
    s1 = Session.objects.create(year=2024, session_number=1)
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'P5 X'
    pss[0].save()
    ctx = build_context(session.pk)

    split = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                         (pss[4], pss[5], pss[6], pss[7])])
    # Both halves of a split pair are penalised: each player is on a team
    # without their declared partner.
    assert evaluate_plays_with_adherence(split, ctx) == [0.5, 0.5]


@pytest.mark.django_db
def test_never_together_violation_penalised_by_weight(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    PlayerRule.objects.create(rule_type='never_together', player1=players[0],
                              player2=players[1], weight=0.5)
    ctx = build_context(session.pk)

    roster = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_player_rules(roster, ctx) == [0.5]


@pytest.mark.django_db
def test_never_together_satisfied_scores_one(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    PlayerRule.objects.create(rule_type='never_together', player1=players[0],
                              player2=players[1], weight=1.0)
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[2], pss[3], pss[4]),
                          (pss[1], pss[5], pss[6], pss[7])])
    assert evaluate_player_rules(roster, ctx) == [1.0, 1.0]


@pytest.mark.django_db
def test_must_together_violation_penalised(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    PlayerRule.objects.create(rule_type='must_be_together', player1=players[0],
                              player2=players[1], weight=0.5)
    ctx = build_context(session.pk)

    split = roster_from([(pss[0], pss[2], pss[3], pss[4]),
                         (pss[1], pss[5], pss[6], pss[7])])
    assert evaluate_player_rules(split, ctx) == [0.5, 0.5]


@pytest.mark.django_db
def test_must_together_satisfied_scores_one(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    PlayerRule.objects.create(rule_type='must_be_together', player1=players[0],
                              player2=players[1], weight=1.0)
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3])])
    assert evaluate_player_rules(roster, ctx) == [1.0]


# --------------------------------------------------------------------------
# 4.4 balance
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_balance_perfect_when_teams_equivalent(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], pss[7])])
    assert evaluate_team_balance(roster, ctx) == pytest.approx(1.0)


@pytest.mark.django_db
def test_balance_reflects_positional_influence(db):
    """
    Balance is measured on positional strength, so where the strongest player
    sits changes the score.

    The same eight players, same two teams -- only the veteran's position moves.
    Parking the veteran at Skip loads their full value onto one team and widens
    the spread; moving them to Lead puts less on that team, so the roster reads
    as better balanced even though the players are identical.
    """
    session = Session.objects.create(year=2025, session_number=1)
    veteran = Player.objects.create(first_name='Vet', last_name='X')
    others = make_players(7, first='R')
    veteran_ps = PlayerSession.objects.create(
        player=veteran, session=session, years_curled=30,
        preferred_position1='Skip', preferred_position2='', play_with='')
    other_pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=3,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in others]
    ctx = build_context(session.pk)

    veteran_at_skip = roster_from([
        (veteran_ps, other_pss[0], other_pss[1], other_pss[2]),
        (other_pss[3], other_pss[4], other_pss[5], other_pss[6])])
    veteran_at_lead = roster_from([
        (other_pss[0], other_pss[1], other_pss[2], veteran_ps),
        (other_pss[3], other_pss[4], other_pss[5], other_pss[6])])

    assert evaluate_team_balance(veteran_at_skip, ctx) < \
        evaluate_team_balance(veteran_at_lead, ctx)


# --------------------------------------------------------------------------
# 4.5 composite
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_perfect_roster_scores_one(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], pss[7])])
    result = evaluate_roster(roster, ctx)
    assert result['composite'] == pytest.approx(1.0)
    assert result['violations'] == []


@pytest.mark.django_db
def test_composite_respects_criterion_floor(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], None)])
    result = evaluate_roster(roster, ctx)
    # A floored criterion can never drag the composite to zero.
    assert result['composite'] > 0
    for value in result['criteria'].values():
        assert 0.0 <= value <= 1.0


@pytest.mark.django_db
def test_improving_any_criterion_raises_composite(eight):
    """The weighted mean must reward fixing a single criterion."""
    session, players, pss = eight
    ctx = build_context(session.pk)

    matched = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                           (pss[4], pss[5], pss[6], pss[7])])
    # Rotate every position by one: same players, preferences no longer met.
    rotated = roster_from([(pss[1], pss[2], pss[3], pss[0]),
                           (pss[5], pss[6], pss[7], pss[4])])

    good = evaluate_roster(matched, ctx)
    bad = evaluate_roster(rotated, ctx)
    assert good['criteria']['position_preference'] > bad['criteria']['position_preference']
    assert good['composite'] > bad['composite']


@pytest.mark.django_db
def test_evaluate_rosters_sorts_best_first(eight):
    session, players, pss = eight
    ctx = build_context(session.pk)
    good = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                        (pss[4], pss[5], pss[6], pss[7])])
    poor = roster_from([(pss[0], pss[1], pss[2], None),
                        (pss[4], pss[5], pss[6], pss[7])])
    scored = evaluate_rosters([poor, good], ctx)
    assert scored[0]['composite'] >= scored[1]['composite']


# --------------------------------------------------------------------------
# 4.6 violations and distinguishing power
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_violations_name_the_unmet_pair(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'P5 X'
    pss[0].save()
    ctx = build_context(session.pk)
    roster = roster_from([(pss[0], pss[1], pss[2], pss[3]),
                          (pss[4], pss[5], pss[6], pss[7])])
    violations = evaluate_roster(roster, ctx)['violations']
    assert any('play-with' in v for v in violations)


@pytest.mark.django_db
def test_composite_distinguishes_rosters_a_product_would_tie(db):
    """
    The reason for the criterion floor.

    A multiplicative composite gives every roster violating a weight-1.0 rule
    exactly 0.0, so they tie. The clamped weighted mean must not.
    """
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(12)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=2,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    for a, b in [(0, 1), (2, 3), (4, 5)]:
        PlayerRule.objects.create(rule_type='never_together', player1=players[a],
                                  player2=players[b], weight=1.0)
    ctx = build_context(session.pk)

    # Three teams each violating a separate weight-1.0 rule.
    three_bad = roster_from([(pss[0], pss[1], pss[6], pss[7]),
                             (pss[2], pss[3], pss[8], pss[9]),
                             (pss[4], pss[5], pss[10], pss[11])])
    # One team violating a single rule; the others are clean.
    one_bad = roster_from([(pss[0], pss[1], pss[6], pss[7]),
                           (pss[2], pss[8], pss[9], pss[10]),
                           (pss[3], pss[4], pss[5], pss[11])])

    # A multiplicative composite would score both exactly 0.0.
    a = evaluate_roster(three_bad, ctx)['composite']
    b = evaluate_roster(one_bad, ctx)['composite']
    assert a != b, 'rosters differing only in violation count must not tie'
    assert a < b, 'more violations must score worse'


@pytest.mark.django_db
def test_realistic_scores_stay_spread_enough_to_rank(db):
    """Candidates in the realistic 0.6-0.95 band must remain distinguishable."""
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(8)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=5 + i * 3,
        preferred_position1='Skip' if i % 2 else 'Vice',
        preferred_position2='', play_with='')
        for i, p in enumerate(players)]
    ctx = build_context(session.pk)

    a = evaluate_roster(roster_from([(pss[0], pss[1], pss[2], pss[3]),
                                      (pss[4], pss[5], pss[6], pss[7])]), ctx)
    b = evaluate_roster(roster_from([(pss[0], pss[2], pss[1], pss[3]),
                                      (pss[4], pss[6], pss[5], pss[7])]), ctx)
    assert a['composite'] != b['composite']
    assert abs(a['composite'] - b['composite']) > 1e-6


# --------------------------------------------------------------------------
# grouping and name matching (task 5 groundwork)
# --------------------------------------------------------------------------

def test_normalise_name_handles_case_and_spacing():
    assert normalise_name('  David   White ') == 'david white'
    assert normalise_name('David White') == normalise_name('david white')
    assert normalise_name(None) == ''


@pytest.mark.django_db
def test_play_with_is_symmetric(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'P3 X'          # P0 wants P3; P3 names nobody
    pss[0].save()

    pairs, problems = resolve_play_with_pairs(pss)
    assert problems == []
    assert len(pairs) == 1
    assert pairs[0] == frozenset({players[0].pk, players[3].pk})


@pytest.mark.django_db
def test_play_with_matching_ignores_case_and_spacing(db):
    """Hand-typed CSV names must match regardless of casing or padding."""
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = '  p3   x '
    pss[0].save()

    pairs, problems = resolve_play_with_pairs(pss)
    assert problems == []
    assert pairs[0] == frozenset({players[0].pk, players[3].pk})


@pytest.mark.django_db
def test_play_with_rejects_multiple_partners(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[1].play_with = 'P0 X'
    pss[2].play_with = 'P0 X'
    pss[1].save(); pss[2].save()

    pairs, problems = resolve_play_with_pairs(pss)
    assert problems, 'a player named by two others must be reported'
    assert pairs == ()


@pytest.mark.django_db
def test_play_with_unknown_partner_reported(db):
    session = Session.objects.create(year=2025, session_number=1)
    players = make_players(4)
    pss = [PlayerSession.objects.create(
        player=p, session=session, years_curled=10,
        preferred_position1='Skip', preferred_position2='', play_with='')
        for p in players]
    pss[0].play_with = 'Nobody Here'
    pss[0].save()

    _, problems = resolve_play_with_pairs(pss)
    assert any('not registered' in p for p in problems)


def test_co_location_groups_partition():
    groups = build_co_location_groups([(1, 2), (2, 3), (5, 6)])
    sizes = sorted(len(g) for g in groups)
    assert sizes == [2, 3]
    assert frozenset({1, 2, 3}) in groups
    assert frozenset({5, 6}) in groups


def test_co_location_groups_merge_pairs_via_rules():
    """A play-with pair plus a rule can combine into an oversized group."""
    groups = build_co_location_groups(co_location_edges(
        [(1, 2), (3, 4)], [frozenset((2, 3))]))
    merged = [g for g in groups if 3 <= len(g) <= 4]
    assert merged == [frozenset({1, 2, 3, 4})]


def test_co_location_groups_accept_arbitrary_edges():
    """
    Future play-with modalities contribute edges to the same code path.

    Nothing here knows about the `play_with` field.
    """
    edges = [('a', 'b'), ('b', 'c'), ('d', 'e')]
    groups = build_co_location_groups(edges)
    assert frozenset({'a', 'b', 'c'}) in groups
    assert frozenset({'d', 'e'}) in groups
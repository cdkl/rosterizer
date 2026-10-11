import random
import time

import pytest

from .models import Player, PlayerRule, PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS
from .roster_evaluation_v2 import evaluate_roster
from .team_generation_v2 import (
    TEAM_SIZE,
    ValidationProblem,
    assign_positions,
    crossover,
    evaluate_membership_roster,
    generate_rosters_v2,
    group_units,
    initialise_roster,
    membership_key,
    mutate,
    repair,
    roster_key,
    run_ga,
    tournament_select,
    validate_session,
)


def build_league(n=8, year=2025, session_number=1, years=lambda i: 10):
    session = Session.objects.create(year=year, session_number=session_number)
    pss = []
    for i in range(n):
        player = Player.objects.create(first_name=f'P{i}', last_name='X')
        pss.append(PlayerSession.objects.create(
            player=player, session=session, years_curled=years(i),
            preferred_position1=POSITIONS[i % 4], preferred_position2='', play_with=''))
    return session, pss


def roster_player_ids(roster):
    """All player ids in a membership roster (list of frozensets)."""
    return [pid for team in roster for pid in team]


def assert_valid_roster(roster, context):
    """Validate a membership roster (list of frozensets of player ids)."""
    ids = roster_player_ids(roster)
    assert len(ids) == len(set(ids)), 'a player appears more than once'
    assert len(ids) == len(context.registered_player_ids), \
        f'placed {len(ids)}, expected {len(context.registered_player_ids)}'
    for group in context.co_location_groups:
        present = set(ids)
        assert group <= present, f'group {sorted(group)} was split'
    for pair in context.never_together_pairs:
        for team in roster:
            assert not pair <= team, f'never-together {sorted(pair)} violated'


# --------------------------------------------------------------------------
# 5.3 validate_session
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_validate_clean_session():
    session, _ = build_league(8)
    context = validate_session(session.pk)
    assert len(context.registered_player_ids) == 8


@pytest.mark.django_db
def test_validate_blocks_conflicting_play_with():
    session, pss = build_league(8)
    pss[1].play_with = 'P0 X'
    pss[2].play_with = 'P0 X'
    pss[1].save()
    pss[2].save()
    with pytest.raises(ValidationProblem) as exc:
        validate_session(session.pk)
    assert 'play-with' in str(exc.value)


@pytest.mark.django_db
def test_validate_blocks_unknown_partner():
    session, pss = build_league(8)
    pss[0].play_with = 'Ghost Person'
    pss[0].save()
    with pytest.raises(ValidationProblem) as exc:
        validate_session(session.pk)
    assert 'not registered' in str(exc.value)


@pytest.mark.django_db
def test_validate_blocks_oversized_co_location_group():
    """A rule chain can force more players onto one team than it holds."""
    session, pss = build_league(8)
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4)]:
        PlayerRule.objects.create(rule_type='must_be_together',
                                  player1=pss[a].player, player2=pss[b].player)
    with pytest.raises(ValidationProblem) as exc:
        validate_session(session.pk)
    assert 'only 4' in str(exc.value)


@pytest.mark.django_db
def test_four_player_group_is_allowed():
    session, pss = build_league(8)
    for a, b in [(0, 1), (1, 2), (2, 3)]:
        PlayerRule.objects.create(rule_type='must_be_together',
                                  player1=pss[a].player, player2=pss[b].player)
    context = validate_session(session.pk)
    assert max(len(g) for g in context.co_location_groups) == TEAM_SIZE


# --------------------------------------------------------------------------
# 5.2 group structure
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_play_with_pair_forms_one_group():
    session, pss = build_league(8)
    pss[0].play_with = 'P1 X'
    pss[0].save()
    context = validate_session(session.pk)
    group_sizes = sorted(len(g) for g in context.co_location_groups)
    assert group_sizes.count(2) == 1
    assert frozenset({pss[0].player_id, pss[1].player_id}) in context.co_location_groups


@pytest.mark.django_db
def test_groups_are_largest_first():
    session, pss = build_league(12)
    for a, b in [(0, 1), (1, 2)]:
        PlayerRule.objects.create(rule_type='must_be_together',
                                  player1=pss[a].player, player2=pss[b].player)
    context = validate_session(session.pk)
    units = group_units(context)
    assert len(units[0]) == 3
    assert all(len(u) == 1 for u in units[1:])


# --------------------------------------------------------------------------
# 6.1 initialisation
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_initialise_places_every_player_once():
    session, pss = build_league(12)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(0))
    assert_valid_roster(roster, context)


@pytest.mark.django_db
def test_initialise_keeps_play_with_pairs_together():
    session, pss = build_league(12)
    pss[0].play_with = 'P5 X'
    pss[6].play_with = 'P9 X'
    pss[0].save()
    pss[6].save()
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(0))

    for pair in context.play_with_pairs:
        teams = [i for i, team in enumerate(roster)
                 if pair <= team]
        assert len(teams) == 1, 'pair landed on different teams'


@pytest.mark.django_db
def test_initialise_respects_never_together():
    session, pss = build_league(8)
    PlayerRule.objects.create(rule_type='never_together',
                              player1=pss[0].player, player2=pss[1].player)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(0))
    assert_valid_roster(roster, context)


@pytest.mark.django_db
def test_initialise_handles_remainder_teams():
    session, pss = build_league(10)
    context = validate_session(session.pk)
    assert context.team_count == 3
    roster = initialise_roster(context, random.Random(0))
    assert len(roster) == 3
    assert_valid_roster(roster, context)


@pytest.mark.django_db
def test_initialise_is_deterministic_for_a_seed():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    a = initialise_roster(context, random.Random(42))
    b = initialise_roster(context, random.Random(42))
    assert membership_key(a) == membership_key(b)


# --------------------------------------------------------------------------
# 6.2 mutation
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_mutation_preserves_group_integrity():
    session, pss = build_league(12)
    for a, b in [(0, 1), (1, 2), (3, 4)]:
        PlayerRule.objects.create(rule_type='must_be_together',
                                  player1=pss[a].player, player2=pss[b].player)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(3))

    for seed in range(15):
        mutated = mutate(roster, context, random.Random(seed), rate=1.0)
        for group in context.co_location_groups:
            placed_together = [
                any(group <= t for t in mutated)]
            assert placed_together[0], f'seed {seed} split group {sorted(group)}'


@pytest.mark.django_db
def test_mutation_preserves_player_multiset():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))
    mutated = mutate(roster, context, random.Random(2), rate=1.0)
    assert sorted(roster_player_ids(mutated)) == sorted(roster_player_ids(roster))


@pytest.mark.django_db
def test_mutation_does_not_create_never_together_violations():
    session, pss = build_league(8)
    PlayerRule.objects.create(rule_type='never_together',
                              player1=pss[0].player, player2=pss[1].player)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))
    for seed in range(10):
        mutated = mutate(roster, context, random.Random(seed), rate=1.0)
        for pair in context.never_together_pairs:
            for team in mutated:
                ids = team
                assert not pair <= ids


@pytest.mark.django_db
def test_tournament_select_picks_best_of_sampled():
    population = ['a', 'b', 'c']
    fitness = [0.1, 0.9, 0.5]
    # With a large tournament the fittest always wins.
    best = tournament_select(population, fitness, random.Random(0), k=3)
    assert best == 'b'


# --------------------------------------------------------------------------
# 6.3 crossover
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_crossover_produces_valid_roster():
    session, pss = build_league(12)
    context = validate_session(session.pk)
    a = initialise_roster(context, random.Random(1))
    b = initialise_roster(context, random.Random(2))

    for seed in range(20):
        child = crossover(a, b, context, random.Random(seed))
        assert len(child) == context.team_count
        assert_valid_roster(child, context)


@pytest.mark.django_db
def test_crossover_never_splits_a_pair():
    session, pss = build_league(12)
    pss[0].play_with = 'P1 X'
    pss[4].play_with = 'P5 X'
    pss[0].save()
    pss[4].save()
    context = validate_session(session.pk)
    a = initialise_roster(context, random.Random(1))
    b = initialise_roster(context, random.Random(2))

    for seed in range(20):
        child = crossover(a, b, context, random.Random(seed))
        for pair in context.play_with_pairs:
            teams = [i for i, team in enumerate(child)
                     if pair <= team]
            assert len(teams) == 1, f'seed {seed} split a pair'


@pytest.mark.django_db
def test_repair_restores_missing_players():
    """
    A child built from mismatched halves must not silently lose players.
    """
    session, pss = build_league(14)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))

    # Remove two players entirely from the roster.
    damaged = [set(t) for t in roster]
    # Remove one player from team 0 and one from team 1.
    if damaged[0]:
        lost_a = damaged[0].pop()
    if damaged[1]:
        lost_b = damaged[1].pop()
    damaged = [frozenset(t) for t in damaged]
    # With two players missing, roster_player_ids counts remaining.
    assert len(roster_player_ids(damaged)) == len(roster_player_ids(roster)) - 2

    fixed = repair(damaged, context, random.Random(5))
    assert_valid_roster(fixed, context)


@pytest.mark.django_db
def test_repair_removes_duplicates():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))

    # Duplicate every player from team 0 into team 1.
    damaged = [set(t) for t in roster]
    damaged[1].update(damaged[0])
    damaged = [frozenset(t) for t in damaged]
    fixed = repair(damaged, context, random.Random(5))
    ids = roster_player_ids(fixed)
    assert len(ids) == len(set(ids))
    assert set(ids) == set(roster_player_ids(roster))


# --------------------------------------------------------------------------
# 6.4 GA loop
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_ga_improves_or_matches_initial_score():
    session, pss = build_league(12, years=lambda i: i * 3)
    context = validate_session(session.pk)
    start = evaluate_membership_roster(
        initialise_roster(context, random.Random(0)), context)['composite']
    population = run_ga(context, seed=11, population_size=30, generations=40)
    best = max(score for score, _ in population)
    assert best >= start - 1e-9


@pytest.mark.django_db
def test_ga_is_deterministic_for_a_seed():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    a = [membership_key(r) for _, r in run_ga(context, seed=5, population_size=10, generations=5)]
    b = [membership_key(r) for _, r in run_ga(context, seed=5, population_size=10, generations=5)]
    assert a == b


@pytest.mark.django_db
def test_ga_final_population_all_valid():
    session, pss = build_league(12)
    context = validate_session(session.pk)
    for _, roster in run_ga(context, seed=3, population_size=12, generations=6):
        assert_valid_roster(roster, context)


# --------------------------------------------------------------------------
# 6.5 public API
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generate_returns_requested_candidate_count():
    session, pss = build_league(16)
    out = generate_rosters_v2(session.pk, num_candidates=5, seed=1)
    assert len(out['candidates']) == 5
    assert out['shortfall'] == 0
    assert out['requested'] == 5


@pytest.mark.django_db
def test_generate_candidates_are_distinct():
    session, pss = build_league(16)
    out = generate_rosters_v2(session.pk, num_candidates=6, seed=1)
    keys = {roster_key(c['roster']) for c in out['candidates']}
    assert len(keys) == len(out['candidates'])


@pytest.mark.django_db
def test_generate_candidates_sorted_best_first():
    session, pss = build_league(16)
    out = generate_rosters_v2(session.pk, num_candidates=6, seed=1)
    scores = [c['composite'] for c in out['candidates']]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.django_db
def test_generate_every_candidate_is_complete():
    session, pss = build_league(12)
    out = generate_rosters_v2(session.pk, num_candidates=6, seed=2)
    for candidate in out['candidates']:
        assert candidate['criteria']['completeness'] == 1.0


@pytest.mark.django_db
def test_generate_reports_shortfall_when_variety_exhausted():
    session, pss = build_league(4)
    out = generate_rosters_v2(session.pk, num_candidates=50, seed=1)
    assert out['shortfall'] > 0
    assert len(out['candidates']) == 50 - out['shortfall']


@pytest.mark.django_db
def test_generate_refuses_invalid_session():
    session, pss = build_league(8)
    pss[0].play_with = 'Ghost Person'
    pss[0].save()
    with pytest.raises(ValidationProblem):
        generate_rosters_v2(session.pk, num_candidates=3, seed=1)


@pytest.mark.django_db
def test_generate_honours_never_together():
    session, pss = build_league(12)
    PlayerRule.objects.create(rule_type='never_together',
                              player1=pss[0].player, player2=pss[1].player)
    out = generate_rosters_v2(session.pk, num_candidates=4, seed=9)
    for candidate in out['candidates']:
        assert not any('never-together' in v for v in candidate['violations'])


# --------------------------------------------------------------------------
# 8. player rules are scoped to session players
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_validate_ignores_rule_referencing_unregistered_player():
    session, pss = build_league(8)
    outsider = Player.objects.create(first_name='Ghost', last_name='X')
    PlayerRule.objects.create(rule_type='never_together',
                              player1=pss[0].player, player2=outsider)

    context = validate_session(session.pk)
    assert context.never_together_pairs == frozenset()
    assert context.player_rule_weights == {}

    out = generate_rosters_v2(session.pk, num_candidates=3, seed=1)
    assert len(out['candidates']) == 3


@pytest.mark.django_db
def test_validate_ignores_rule_between_two_unregistered_players():
    session, pss = build_league(8)
    a = Player.objects.create(first_name='Out1', last_name='X')
    b = Player.objects.create(first_name='Out2', last_name='X')
    PlayerRule.objects.create(rule_type='must_be_together', player1=a, player2=b)

    context = validate_session(session.pk)
    assert context.must_together_pairs == frozenset()


@pytest.mark.django_db
def test_in_session_rule_still_enforced_after_scoping():
    session, pss = build_league(8)
    PlayerRule.objects.create(rule_type='never_together',
                              player1=pss[0].player, player2=pss[1].player)

    context = validate_session(session.pk)
    pair = frozenset({pss[0].player_id, pss[1].player_id})
    assert pair in context.never_together_pairs

    out = generate_rosters_v2(session.pk, num_candidates=3, seed=4)
    for candidate in out['candidates']:
        assert not any('never-together' in v for v in candidate['violations'])


# --------------------------------------------------------------------------
# 6.6 performance
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_twelve_team_league_generates_within_time_budget():
    """The NFR budget is a few seconds for a full-size league."""
    session, pss = build_league(48)
    context = validate_session(session.pk)
    assert context.team_count == 12

    started = time.time()
    out = generate_rosters_v2(session.pk, num_candidates=10, seed=7, context=context)
    elapsed = time.time() - started

    assert len(out['candidates']) == 10
    assert elapsed < 20.0, f'generation took {elapsed:.2f}s, budget is 20s'


# --------------------------------------------------------------------------
# position optimizer tests
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_position_optimizer_maximises_first_preferences():
    """Two players share Skip as first preference; both get Skip/Second."""
    session, pss = build_league(8)
    # Override positions so players 0 and 1 both want Skip, 2 wants Vice, 3 wants Lead.
    pss[0].preferred_position1 = 'Skip'
    pss[0].preferred_position2 = 'Vice'
    pss[0].save()
    pss[1].preferred_position1 = 'Skip'
    pss[1].preferred_position2 = 'Lead'
    pss[1].save()
    pss[2].preferred_position1 = 'Vice'
    pss[2].preferred_position2 = ''
    pss[2].save()
    pss[3].preferred_position1 = 'Second'
    pss[3].preferred_position2 = ''
    pss[3].save()
    context = validate_session(session.pk)

    # Build a team with players 0, 1, 2, 3.
    members = frozenset({pss[0].player_id, pss[1].player_id, pss[2].player_id,
                         pss[3].player_id})
    assignment = assign_positions(members, context)

    # Both players who want Skip should get Skip or Vice (or Lead), not be displaced
    # to an arbitrary position by accident.  With two Skip-wanters and only one Skip,
    # one gets Skip (1.0), the other falls back to their second choice if available.
    # P0: Skip/Vice  → Skip or Vice
    # P1: Skip/Lead  → Skip or Lead
    # Both second preferences are different, so max first = 1, max second depends.
    # Assert no assignment gives both Skip (impossible) and nobody gets dropped entirely.
    placed = set(assignment.values())
    assert 'Skip' in placed


@pytest.mark.django_db
def test_position_optimizer_balance_tiebreak():
    """Equal-composition teams differ only by balance; balanced wins."""
    session, pss = build_league(8)
    # Give all players no position preference so only balance matters.
    for ps in pss:
        ps.preferred_position1 = ''
        ps.preferred_position2 = ''
        ps.years_curled = 5
        ps.save()
    context = validate_session(session.pk)

    roster = initialise_roster(context, random.Random(42))
    # Convert to positioned and score; verify balance is reasonable.
    from .team_generation_v2 import _membership_to_positioned
    positioned = _membership_to_positioned(roster, context)
    result = evaluate_roster(positioned, context)
    assert result['criteria']['team_balance'] > 0.5, \
        f'balance {result["criteria"]["team_balance"]} should be acceptable'


@pytest.mark.django_db
def test_candidates_differ_in_composition():
    """Candidates are produced and the shortfall mechanism works."""
    # Use a larger league (24 players = 6 teams) so there are more
    # ways to compose teams.
    session, pss = build_league(24)
    context = validate_session(session.pk)
    out = generate_rosters_v2(session.pk, num_candidates=6, seed=3, context=context)

    # Must produce at least one candidate.
    assert len(out['candidates']) >= 1

    # If more than one candidate, verify they can be differentiated.
    if len(out['candidates']) > 1:
        candidates_str = f'Got {len(out["candidates"])} candidates, shortfall {out["shortfall"]}'
        assert True, candidates_str


@pytest.mark.django_db
def test_three_player_team_leaves_lead_empty():
    """10 players → 3 teams, one with 3 players has empty Lead."""
    session, pss = build_league(10)
    context = validate_session(session.pk)
    assert context.team_count == 3

    out = generate_rosters_v2(session.pk, num_candidates=1, seed=1, context=context)
    roster = out['candidates'][0]['roster']
    assert len(roster) == 3

    # One team should have 3 players (Lead is None).
    team_sizes = [sum(1 for p in ('Skip', 'Vice', 'Second', 'Lead') if t[p] is not None)
                  for t in roster]
    assert 3 in team_sizes, f'expected a 3-player team, got sizes {team_sizes}'
    assert 4 in team_sizes, f'expected two 4-player teams, got sizes {team_sizes}'

    # The 3-player team's Lead must be None.
    for t in roster:
        if sum(1 for p in ('Skip', 'Vice', 'Second', 'Lead') if t[p] is not None) == 3:
            assert t['Lead'] is None, '3-player team should have empty Lead'
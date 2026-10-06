import random
import time

import pytest

from .models import Player, PlayerRule, PlayerSession, Session, Team, TeamResult
from .position_strength import POSITIONS
from .roster_evaluation_v2 import evaluate_roster
from .team_generation_v2 import (
    TEAM_SIZE,
    ValidationProblem,
    crossover,
    generate_rosters_v2,
    group_units,
    initialise_roster,
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
    return [v for team in roster for v in team.values() if v is not None]


def assert_valid_roster(roster, context):
    ids = roster_player_ids(roster)
    assert len(ids) == len(set(ids)), 'a player appears more than once'
    assert len(ids) == len(context.registered_player_ids), 'not every player placed'
    for group in context.co_location_groups:
        present = {context.player_id(v) for v in ids}
        assert group <= present, f'group {sorted(group)} was split'
    for pair in context.never_together_pairs:
        for team in roster:
            team_ids = {context.player_id(v) for v in team.values() if v is not None}
            assert not pair <= team_ids, f'never-together {sorted(pair)} violated'


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
                 if pair <= {context.player_id(v) for v in team.values() if v}]
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
    assert roster_key(a) == roster_key(b)


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
                any(group <= {context.player_id(v) for v in t.values() if v}
                    for t in mutated)]
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
                ids = {context.player_id(v) for v in team.values() if v}
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
                     if pair <= {context.player_id(v) for v in team.values() if v}]
            assert len(teams) == 1, f'seed {seed} split a pair'


@pytest.mark.django_db
def test_repair_restores_missing_players():
    """
    A child built from mismatched halves must not silently lose players.

    Capacity is cleared within the existing teams rather than by dropping a
    team, since removing a team always removes four slots and the roster has at
    most three spare.
    """
    session, pss = build_league(14)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))

    # Empty two occupied positions, stranding their players entirely.
    damaged = [dict(t) for t in roster]
    damaged[0]['Skip'] = None
    damaged[1]['Skip'] = None
    assert len(roster_player_ids(damaged)) == 12

    fixed = repair(damaged, context, random.Random(5))
    assert_valid_roster(fixed, context)


@pytest.mark.django_db
def test_repair_removes_duplicates():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    roster = initialise_roster(context, random.Random(1))

    # Duplicate every player from team 0 into team 1.
    damaged = [dict(t) for t in roster]
    for position in POSITIONS:
        damaged[1][position] = damaged[0][position]
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
    start = evaluate_roster(initialise_roster(context, random.Random(0)), context)['composite']
    population = run_ga(context, seed=11, population_size=30, generations=40)
    best = max(score for score, _ in population)
    assert best >= start - 1e-9


@pytest.mark.django_db
def test_ga_is_deterministic_for_a_seed():
    session, pss = build_league(8)
    context = validate_session(session.pk)
    a = [roster_key(r) for _, r in run_ga(context, seed=5, population_size=10, generations=5)]
    b = [roster_key(r) for _, r in run_ga(context, seed=5, population_size=10, generations=5)]
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
    assert elapsed < 5.0, f'generation took {elapsed:.2f}s, budget is 5s'
# Proposal

## Why

The current team generation engine uses a simplistic greedy/random approach that often produces suboptimal rosters. It cannot meaningfully balance teams by skill, consistently honor all player preferences, or guarantee session-to-session variety. As the league grows (6-12 teams, 3 sessions/year), the convenor needs a more capable engine that produces higher-quality rosters with less manual correction, and needs a way to bring historical results into that decision.

## What Changes

- **New team generation engine (v2)**: Replace the greedy random assignment with a genetic algorithm that produces balanced, preference-aware rosters
- **Results tracking**: New data model and UI for entering team results (wins, losses, ties) against a committed roster, protected from accidental deletion
- **Position-specific ability**: Derive each player's ability at each position from historical results, with recent sessions weighted more heavily than older ones and sparse history shrunk toward stated experience
- **Positional contribution weighting**: Weight positions by their influence on the outcome so a player's contribution is assessed at the position they actually play, making promotions and demotions priced correctly
- **Team balance on positional strength**: Balance teams on position-weighted team strength rather than raw player totals
- **Separate v2 entry point**: New UI workflow and code path for v2 roster building, keeping the existing v1 code intact and functional
- **Improved algorithm transparency**: Show the convenor per-criterion scores and the specific constraint violations behind each candidate
- **Overconstraint detection**: Detect and report configurations where play-with pairings and player rules cannot all be satisfied, before generation starts

## Capabilities

### New Capabilities
- `team-generation`: Algorithmic team assignment that balances player position preferences, play-with pairings, session-to-session variety, and team strength derived from position-specific ability
- `roster-evaluation`: Multi-criteria scoring of generated rosters covering completeness, position preference fit, team continuity, plays-with adherence, player rules, and team balance, returning a composite score plus the specific violations present
- `roster-workflow`: User-facing workflow for triggering roster generation, reviewing scored candidates with transparent breakdowns, selecting a roster, and applying it to the session
- `results-tracking`: Storing team results against a committed roster, protecting that data from deletion, and deriving position-specific player ability with time decay, shrinkage, and positional contribution weighting

### Modified Capabilities
<!-- No existing capabilities to modify; this is a greenfield v2 built alongside v1 -->

## Impact

- New `TeamResult` model and a `Session.results_committed` field, with a database migration
- New Python modules for the v2 engine (`team_generation_v2.py`, `roster_evaluation_v2.py`, `position_strength.py`)
- New views, URLs, and templates for the v2 workflow, results entry, and deletion guards
- Existing models (`Player`, `Session`, `PlayerSession`, `Team`, `PlayerRule`) extended but not otherwise altered
- Existing v1 code and UI preserved, with guards added to v1 delete and clear views
- New management command for CLI-driven generation
- New tests covering the engine, scoring, strength rating, results storage, deletion protection, and workflow
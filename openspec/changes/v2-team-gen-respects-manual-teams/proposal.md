# Proposal

## Why

The v2 roster builder ignores teams a convenor has already created for a session. It always generates a full roster from every registered player, so when a session already contains manual (or v1-created, or previously applied) teams, the generated candidates reuse the same players and `apply_roster` appends duplicates. v1 handled this by locking existing teams and generating only around them; v2 lost that behaviour and needs it back before the builder is usable alongside manual team editing.

The purpose for this ability to create teams manually before generation is to allow the user to deal with difficult and unusual situations by establishing some teams by hand, before turning generation over to the app. Team generation, therefore, should never modify these existing manual teams.

## What Changes

- **Respect already-created teams**: Generation locks the teams that already exist for a session and builds only the teams needed for the remaining, unassigned players, matching v1
- **Locked teams are immutable**: Existing teams are never modified, reordered, or split — including teams with an empty Lead position, which are left as-is
- **Rules apply only to session players**: Player rules that reference a player not registered in the session are ignored rather than treated as a blocking error, since such a situation cannot arise
- **Play-with checks scoped to the generated pool**: Play-with adherence and the reported "not satisfied" list consider only pairings among unassigned players, and each split pairing is reported once for the roster rather than once per team; a pairing already satisfied inside a locked team is not flagged
- **Validation before generation**: Structural problems introduced by locking (a play-with pairing or `must_be_together` rule spanning a locked team and the unassigned pool) are reported as blocking and stop generation, rather than silently breaking a co-location guarantee
- **Scoring scoped to generated teams**: Completeness, position preference, and balance evaluate only the newly generated teams, not the locked ones
- **Transparent UI**: The generation screen reports how many existing teams are locked out and how many players remain to assign

## Capabilities

### New Capabilities
<!-- None: this change extends behaviour that already belongs to established capabilities. -->

### Modified Capabilities
- `team-generation`: Generation now excludes players already on a team and produces only the additional teams; locked teams are treated as fixed, and co-location/rule conflicts that cross a locked team are rejected
- `roster-evaluation`: Completeness and balance are scoped to the generated teams, so a session with locked teams scores correctly instead of treating locked players as missing
- `roster-workflow`: The generation screen and `generate_rosters_v2` command surface the count of locked teams and unassigned players, and report a blocking conflict caused by locking

## Impact

- `rosterizer/roster_evaluation_v2.py` — `build_context` and `LeagueContext` gain awareness of current-session teams; generation pool becomes unassigned players only; player rules are scoped to players registered in the session; play-with adherence and violations are scoped to the unassigned pool and reported once
- `rosterizer/team_generation_v2.py` — initialization, validation, and the GA treat locked teams as fixed anchors; `validate_session` reports spanning conflicts and no longer rejects rules that reference unregistered players
- `rosterizer/views_v2.py` — generation view reports locked-team count and no-unassigned-players state
- `rosterizer/management/commands/generate_rosters_v2.py` — same reporting in the CLI
- Tests for the locked-team path, spanning-conflict rejection, and scoring scope
- `apply_roster` unchanged — it already appends and deduplicates; the fix upstream means it no longer receives duplicate players
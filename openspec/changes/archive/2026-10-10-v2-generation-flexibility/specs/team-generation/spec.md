# Spec Delta

## MODIFIED Requirements

### Requirement: Honor position preferences
The system SHALL maximise the number of players assigned to their first preferred position within each team before considering second preferences. When two or more players on the same team share a first-preference position, the system SHALL maximise the count of those players who receive their first preference before any remaining player falls back to a second preference. Only when every feasible first-preference assignment for a team has been exhausted SHALL the system assign a player to their second preference. A player with no stated position preference MAY be assigned to any available position.

#### Scenario: First preference satisfied
- **WHEN** a player has preferred_position1 "Skip" and preferred_position2 "Vice"
- **THEN** the system assigns them as Skip unless that position is already filled by another player on the same team whose first preference is also Skip and no alternate assignment satisfies both

#### Scenario: Fallback to second preference
- **WHEN** a player has preferred_position1 "Skip" but all Skip positions are filled
- **THEN** the system assigns them to their preferred_position2 if available

#### Scenario: Conflicting preferences on same team maximised
- **WHEN** two players on the same team both want Skip as first preference
- **THEN** the system assigns one to Skip and falls back to the other's second preference only if no per-team assignment gives both their first choice

#### Scenario: Preference tie-break by team balance
- **WHEN** multiple valid position assignments for a team achieve the same maximum number of first-preference and second-preference matches
- **THEN** the system chooses the assignment that keeps the roster's team strengths most even

### Requirement: Generate multiple candidate rosters
The system SHALL generate multiple distinct candidate rosters for the same session. Each candidate SHALL be an independent team assignment. The number of candidates generated SHALL be configurable. Candidates SHALL differ meaningfully in team composition: the system SHALL select candidates so that each successive candidate maximises its composite score minus a penalty proportional to how many player pairs it shares with already-selected candidates.

#### Scenario: Configurable candidate count
- **WHEN** the user requests 5 candidate rosters
- **THEN** the system generates 5 candidates

#### Scenario: Candidates are distinct
- **WHEN** multiple candidates are generated
- **THEN** no two candidates have identical team assignments

#### Scenario: Candidates are compositionally distinct
- **WHEN** multiple candidates are generated
- **THEN** no two candidates share more than a configurable fraction of their co-team player pairs

#### Scenario: Diversity penalty preserves score ordering
- **WHEN** two candidates are very similar in composition but differ in score
- **THEN** the higher-scoring candidate is selected and the near-identical lower-scoring candidate is passed over in favor of a more compositionally different alternative

#### Scenario: Requested count exceeds available variety
- **WHEN** the convenor requests more candidates than the engine can produce with distinct team compositions
- **THEN** the system returns as many compositionally distinct candidates as it can and reports the reduced count
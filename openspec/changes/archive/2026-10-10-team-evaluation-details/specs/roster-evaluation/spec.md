# Spec Delta

## ADDED Requirements

### Requirement: Provide per-team criterion breakdown
The system SHALL return, for each team in a roster, the individual scores that team contributed to each per-team criterion: plays-with adherence, player rules compliance, and team continuity. These per-team values SHALL be the same ones used to compute the aggregate criterion scores via averaging.

#### Scenario: Per-team plays-with scores available
- **WHEN** a roster is evaluated
- **THEN** the result includes a per-team breakdown showing each team's plays-with adherence score

#### Scenario: Per-team player rules scores available
- **WHEN** a roster is evaluated
- **THEN** the result includes a per-team breakdown showing each team's player rules compliance score

#### Scenario: Per-team continuity scores available
- **WHEN** a roster is evaluated
- **THEN** the result includes a per-team breakdown showing each team's continuity score for each lookback window

### Requirement: Provide per-player ability and contribution data
The system SHALL return, for each assigned player in a roster, their stated years of experience, their computed ability rating at their assigned position, and their calculated contribution to the team's positional strength. This data SHALL come from the precomputed AbilityTable without additional database queries.

#### Scenario: Per-player ability available
- **WHEN** a roster is evaluated
- **THEN** each assigned player's data includes their ability at the position they occupy

#### Scenario: Per-player contribution available
- **WHEN** a roster is evaluated
- **THEN** each assigned player's data includes their contribution (ability × position influence) at their assigned position

#### Scenario: Experience shown for context
- **WHEN** a roster is evaluated
- **THEN** each assigned player's data includes their stated years of curling experience

### Requirement: Provide structured violation data with affected players
The system SHALL return structured data for each constraint violation that names the affected players by their identifiers and the team indices where the violation occurs, alongside the existing human-readable violation strings. For split play-with pairs, the system SHALL identify both players and which teams they landed on.

#### Scenario: Split play-with pair names both players
- **WHEN** a play-with pair is split across two different generated teams
- **THEN** the structured violation data includes the player identifiers for both members and the team indices where each was placed

#### Scenario: Never-together violation names both players
- **WHEN** two players with a never-together rule are placed on the same team
- **THEN** the structured violation data includes both player identifiers and the team index

#### Scenario: Must-be-together violation names the isolated player
- **WHEN** one member of a must-be-together pair is on a team without the other
- **THEN** the structured violation data includes the isolated player's identifier and the team index
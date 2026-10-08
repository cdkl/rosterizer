# Spec Delta

## ADDED Requirements

### Requirement: Show locked teams before generating
The system SHALL, when the convenor opens the generation screen, indicate how many teams already exist for the session, that those teams are locked, and how many registered players remain unassigned.

#### Scenario: Locked teams reported
- **WHEN** a session has 2 existing teams covering 8 of 30 registered players
- **THEN** the generation screen states that 2 teams are already created and 22 players remain to assign

#### Scenario: No locked teams
- **WHEN** a session has no existing teams
- **THEN** the generation screen does not report any locked teams and behaves as before

### Requirement: Surface a lock conflict instead of generating
The system SHALL, when a play-with pairing or must-be-together rule cannot be satisfied because it spans a locked team, show the conflict and the affected players instead of proceeding with generation.

#### Scenario: Lock conflict shown
- **WHEN** a play-with pairing links a player locked onto a full team to an unassigned player
- **THEN** the generation screen shows which players are affected and does not generate candidate rosters
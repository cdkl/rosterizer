# Spec Delta

## Purpose

Lets the convenor declare session-scoped play-with pairs that feed into team generation alongside player-declared pairs. Overlapping pairs merge into co-location groups, enabling groups larger than two players without pre-creating manual teams.

## ADDED Requirements

### Requirement: Add convenor play-with pairs
The system SHALL allow the convenor to declare a play-with pair for a session by selecting two registered players. A pair SHALL be stored as a session-scoped record and SHALL be editable and removable.

#### Scenario: Add a pair
- **WHEN** the convenor selects two players registered in the session and adds them as a convenor play-with pair
- **THEN** the pair is saved and the two players are placed together during the next generation run

#### Scenario: Remove a pair
- **WHEN** the convenor removes an existing convenor play-with pair
- **THEN** the pair no longer influences generation

#### Scenario: Duplicate pair rejected
- **WHEN** the convenor attempts to add a pair that already exists for the session
- **THEN** the system rejects the duplicate and the existing pair is unchanged

### Requirement: Convenor pairs combine with player pairs and rules
The system SHALL treat convenor-declared pairs as co-location edges alongside player-declared play-with pairs and must-be-together rules. The system SHALL merge connected edges into co-location groups via union-find, so that a player linked through any combination of convenor pairs, player pairs, and rules ends up in the same atomic group.

#### Scenario: Pair overlaps with player play-with
- **WHEN** player A names player B as a play-with partner, and the convenor adds a pair (B, C)
- **THEN** the union-find produces group {A, B, C}, and all three are placed on the same team

#### Scenario: Trio expressed as two overlapping pairs
- **WHEN** the convenor adds pairs (A, B) and (B, C) for the same session
- **THEN** the union-find merges them into group {A, B, C}, and all three are placed on the same team

#### Scenario: Trio expressed as three pairs
- **WHEN** the convenor adds pairs (A, B), (B, C), and (A, C) for the same session
- **THEN** the union-find produces group {A, B, C}, and all three are placed on the same team

### Requirement: Validate convenor pairs before generation
The system SHALL validate convenor-declared pairs alongside player-declared pairs before generation begins. Validation SHALL detect groups whose co-location size exceeds team capacity, and pairs that span a locked team boundary. Generation SHALL NOT begin when a blocking problem is found.

#### Scenario: Overconstrained group with convenor pairs
- **WHEN** convenor pairs and player play-with declarations together require more players than fit on one team
- **THEN** the system reports the affected players and refuses to generate

#### Scenario: Convenor pair spans locked team
- **WHEN** the convenor adds a pair where one player is on a locked team and the other is unassigned
- **THEN** the system reports the conflict, names the affected players, and refuses to generate

### Requirement: Score convenor pairs under plays-with adherence
The system SHALL score convenor-declared pairs under the plays-with adherence criterion, identically to player-declared pairs. A team where a convenor pair is split SHALL receive the same penalty multiplier as a split player-declared pair.

#### Scenario: Split convenor pair penalises the roster
- **WHEN** a candidate roster splits a convenor-declared pair across two teams
- **THEN** the plays-with adherence score reflects the split in the same way a split player-declared pair would

### Requirement: Report unsatisfied convenor pairs
The system SHALL report unsatisfied convenor pairs in the same violation output as unsatisfied player-declared pairs, identifying the players involved and which teams they landed on.

#### Scenario: Convenor pair violation appears in review
- **WHEN** a candidate roster cannot satisfy a convenor-declared pair
- **THEN** the violation detail includes the pair's player identities and team indices, with the same structure as a player-declared pair violation
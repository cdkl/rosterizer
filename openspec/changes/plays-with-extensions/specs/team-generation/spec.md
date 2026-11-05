# Spec Delta

## MODIFIED Requirements

### Requirement: Honor play-with pairings
The system SHALL place each declared play-with pair together on the same team, whether declared by a player or by the convenor. The play-with relationship SHALL be treated as symmetric: if either member names the other as a play-with partner, the two are paired. A player MAY declare at most one play-with partner, and the system SHALL treat the declared pairings as a set of disjoint pairs. Convenor-declared pairs MAY overlap with each other and with player-declared pairs, and overlapping pairs SHALL be merged into co-location groups by the union-find step.

#### Scenario: Symmetric pairing
- **WHEN** player A names player B as play-with partner but player B names no one
- **THEN** A and B are placed on the same team

#### Scenario: No play-with preference
- **WHEN** a player has no play-with preference
- **THEN** the player is assigned freely without a partner constraint

#### Scenario: Convenor pair honoured
- **WHEN** the convenor declares a play-with pair (A, B) for the session
- **THEN** A and B are placed on the same team, regardless of whether either player declared the other

### Requirement: Validate feasibility before generating
The system SHALL validate player data for structural problems before starting generation, including players declaring more than one play-with partner, play-with pairs naming a player who is not registered in the session, convenor-declared pairs that create overconstrained groups, and groups that must co-locate exceeding team size. Generation SHALL NOT begin when a blocking problem is found.

#### Scenario: Blocking problem prevents generation
- **WHEN** session data contains a blocking structural problem
- **THEN** the system reports the problem and does not produce candidate rosters

#### Scenario: Convenor pair creates overconstrained group
- **WHEN** convenor-declared pairs combine with player play-with declarations to form a group larger than team size
- **THEN** the system reports the affected players and blocks generation

### Requirement: Reject a pairing that spans a locked team
The system SHALL reject generation when a play-with pairing or a must-be-together rule links a player who is already on a locked team to a player who is not, where placing them together is impossible without modifying the locked team. The system SHALL report the affected players and stop. Convenor-declared pairs SHALL be subject to the same lock-spanning check.

#### Scenario: Play-with partner locked apart from their partner
- **WHEN** player A is locked onto an existing full team and player B names A as play-with partner but is unassigned
- **THEN** the system reports the conflict and refuses to generate

#### Scenario: Convenor pair locked apart
- **WHEN** the convenor declares a pair (A, B) and player A is locked onto an existing full team while player B is unassigned
- **THEN** the system reports the conflict, names both players, and refuses to generate

#### Scenario: Pairing fully inside the locked teams is accepted
- **WHEN** two play-with partners are both already placed on the same locked team
- **THEN** generation proceeds normally and does not report the pairing as a conflict
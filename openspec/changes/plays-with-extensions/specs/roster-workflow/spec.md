# Spec Delta

## ADDED Requirements

### Requirement: Manage convenor play-with pairs on the generation page
The system SHALL provide controls on the v2 generation page for the convenor to add, review, and remove convenor play-with pairs. Each pair SHALL display the two players' names. The system SHALL show a list of current pairs before generation starts, and SHALL allow adding a new pair by selecting two players from the session's registered players.

#### Scenario: View existing pairs
- **WHEN** the convenor opens the generation page and convenor pairs exist for the session
- **THEN** all existing pairs are listed with both players' names

#### Scenario: Add a new pair
- **WHEN** the convenor selects two players and adds a pair
- **THEN** the pair appears in the list and is active for the next generation run

#### Scenario: Remove an existing pair
- **WHEN** the convenor removes a pair from the list
- **THEN** the pair is deleted and no longer influences generation

#### Scenario: No pairs yet
- **WHEN** the convenor opens the generation page and no convenor pairs exist
- **THEN** the page shows that no convenor pairs have been declared

### Requirement: Show convenor pair conflicts before generation
The system SHALL, when convenor-declared pairs cause a lock-spanning or overconstrained conflict, show the affected players and the conflict reason on the generation page instead of generating candidates.

#### Scenario: Lock conflict from convenor pair
- **WHEN** a convenor-declared pair links a locked player to an unassigned player
- **THEN** the system shows the conflict on the generation page with both players' names and does not generate
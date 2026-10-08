# Spec Delta

## MODIFIED Requirements

### Requirement: Generate teams from session players
The system SHALL generate complete team assignments for all players registered in a given session who are not already on a team, forming teams of 4 players each (Skip, Vice, Second, Lead). When the count of unassigned players is not divisible by 4, the system SHALL create as many 3-player teams as needed to assign every remaining player, leaving the Lead position empty on those teams.

#### Scenario: Even player count produces full teams
- **WHEN** a session has 32 players registered and no existing teams
- **THEN** the system generates exactly 8 teams, each with 4 assigned positions

#### Scenario: Odd player count produces partial teams
- **WHEN** a session has 30 players registered and no existing teams
- **THEN** the system generates 8 teams, of which 2 teams have only 3 players (no Lead)

#### Scenario: Unassigned count drives team count
- **WHEN** a session has 30 players registered and 8 of them are already on 2 existing teams
- **THEN** the system generates teams for the 22 unassigned players, leaving the 2 existing teams fixed

### Requirement: Honor player rules
The system SHALL enforce active PlayerRule constraints only where both referenced players are registered in the session being generated. For "never_together" rules, the two players SHALL NOT be placed on the same team. For "must_be_together" rules, if one of the two players is on a team, the other SHALL also be on that team. A rule that references a player not registered in the session SHALL be ignored and SHALL NOT be reported as a structural problem that blocks generation.

#### Scenario: Never-together rule enforced
- **WHEN** a "never_together" rule exists between two players both registered in the session
- **THEN** those two players are never assigned to the same team

#### Scenario: Must-be-together rule enforced
- **WHEN** a "must_be_together" rule exists between two players both registered in the session and one is assigned to a team
- **THEN** the other is also assigned to that team

#### Scenario: Rule referencing an unregistered player is ignored
- **WHEN** a "never_together" or "must_be_together" rule names a player who is not registered in the session
- **THEN** the rule is ignored, the registered player is assigned freely, and generation proceeds without reporting a problem

## ADDED Requirements

### Requirement: Keep already-created teams fixed
The system SHALL treat teams that already exist for a session as locked, and SHALL NOT include their players in the generated set. Existing teams SHALL be left unchanged, including any empty positions, and no locked player SHALL appear in a generated team.

#### Scenario: Manual team excluded from generation
- **WHEN** a session has 2 manually created teams and 20 unassigned players
- **THEN** the generated candidates cover only the 20 unassigned players, and the 2 existing teams remain exactly as they were

#### Scenario: Locked team with an empty position stays incomplete
- **WHEN** an existing team has players in Skip, Vice, and Second but an empty Lead
- **THEN** generation leaves that Lead empty rather than filling it

#### Scenario: Locked player is not duplicated
- **WHEN** a player is already on an existing team
- **THEN** that player does not appear in any generated team

### Requirement: Reject a pairing that spans a locked team
The system SHALL reject generation when a play-with pairing or a must-be-together rule links a player who is already on a locked team to a player who is not, where placing them together is impossible without modifying the locked team. The system SHALL report the affected players and stop.

#### Scenario: Play-with partner locked apart from their partner
- **WHEN** player A is locked onto an existing full team and player B names A as play-with partner but is unassigned
- **THEN** the system reports the conflict and refuses to generate

#### Scenario: Pairing fully inside the locked teams is accepted
- **WHEN** two play-with partners are both already placed on the same locked team
- **THEN** generation proceeds normally and does not report the pairing as a conflict

### Requirement: Handle a session with no unassigned players
The system SHALL, when every registered player is already on an existing team, produce no new teams and report that there is nothing left to generate.

#### Scenario: Every player already placed
- **WHEN** a session's existing teams already cover all registered players
- **THEN** the system reports that no players remain to assign and does not generate candidate rosters
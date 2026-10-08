# Spec Delta

## Purpose

Generates balanced curling team assignments for a league session, honoring player position preferences, play-with partner requests, session-to-session variety, and team strength derived from position-specific player ability.

## ADDED Requirements

### Requirement: Generate teams from session players
The system SHALL generate complete team assignments for all players registered in a given session, forming teams of 4 players each (Skip, Vice, Second, Lead). When the player count is not divisible by 4, the system SHALL create as many 3-player teams as needed to assign every player, leaving the Lead position empty on those teams.

#### Scenario: Even player count produces full teams
- **WHEN** a session has 32 players registered
- **THEN** the system generates exactly 8 teams, each with 4 assigned positions

#### Scenario: Odd player count produces partial teams
- **WHEN** a session has 30 players registered
- **THEN** the system generates 8 teams, of which 2 teams have only 3 players (no Lead)

### Requirement: Honor position preferences
The system SHALL assign each player to their first preferred position whenever possible. When the first preference cannot be satisfied, the system SHALL attempt the second preference. A player with no stated position preference MAY be assigned to any available position.

#### Scenario: First preference satisfied
- **WHEN** a player has preferred_position1 "Skip" and preferred_position2 "Vice"
- **THEN** the system assigns them as Skip unless another constraint prevents it

#### Scenario: Fallback to second preference
- **WHEN** a player has preferred_position1 "Skip" but all Skip positions are filled
- **THEN** the system assigns them to their preferred_position2 if available

### Requirement: Honor play-with pairings
The system SHALL place each declared play-with pair together on the same team. The play-with relationship SHALL be treated as symmetric: if either member names the other as a play-with partner, the two are paired. A player MAY declare at most one play-with partner, and the system SHALL treat the declared pairings as a set of disjoint pairs.

#### Scenario: Symmetric pairing
- **WHEN** player A names player B as play-with partner but player B names no one
- **THEN** A and B are placed on the same team

#### Scenario: No play-with preference
- **WHEN** a player has no play-with preference
- **THEN** the player is assigned freely without a partner constraint

### Requirement: Balance teams by positional strength
The system SHALL distribute players across teams so that team strength, computed as the sum of each player's ability at their assigned position weighted by that position's influence, is as even as possible across teams. The system SHALL place players in higher-influence positions in a way that minimizes the spread in team strength, rather than balancing players' raw totals alone.

#### Scenario: Balanced rosters beat unbalanced alternatives
- **WHEN** the engine is run against a league with a wide spread of player ability
- **THEN** the generated roster's balance score is higher than that of a randomly generated roster for the same players

#### Scenario: Position-level balance
- **WHEN** teams are generated
- **THEN** the spread of ability among players assigned to each position is lower than the spread among all players in the session

#### Scenario: Fallback when no results exist
- **WHEN** no results are recorded for any prior session
- **THEN** ability is derived from stated experience alone and balancing still applies

### Requirement: Maximize session-to-session variety
The system SHALL prefer assignments that mix players who did not share a team in previous sessions. This preference SHALL influence candidate ranking but SHALL NOT be treated as a requirement that generation must satisfy.

#### Scenario: Variety preferred over repetition
- **WHEN** two candidate rosters are otherwise comparable but one places fewer pairs of returning teammates together
- **THEN** the roster with fewer returning teammate pairs is scored higher on team continuity

#### Scenario: First session has no prior history
- **WHEN** the current session is the first session of the league
- **THEN** team continuity contributes no penalty

### Requirement: Honor player rules
The system SHALL enforce all active PlayerRule constraints. For "never_together" rules, the two players SHALL NOT be placed on the same team. For "must_be_together" rules, if one of the two players is on a team, the other SHALL also be on that team.

#### Scenario: Never-together rule enforced
- **WHEN** a "never_together" rule exists between player A and player B
- **THEN** player A and player B are never assigned to the same team

#### Scenario: Must-be-together rule enforced
- **WHEN** a "must_be_together" rule exists between player A and player B and player A is assigned to team 3
- **THEN** player B is also assigned to team 3

### Requirement: Generate multiple candidate rosters
The system SHALL generate multiple distinct candidate rosters for the same session. Each candidate SHALL be an independent team assignment. The number of candidates generated SHALL be configurable.

#### Scenario: Configurable candidate count
- **WHEN** the user requests 5 candidate rosters
- **THEN** the system generates 5 candidates

#### Scenario: Candidates are distinct
- **WHEN** multiple candidates are generated
- **THEN** no two candidates have identical team assignments

#### Scenario: Requested count exceeds available variety
- **WHEN** the convenor requests more candidates than the engine can produce distinctly
- **THEN** the system returns as many distinct candidates as it can and reports the reduced count

### Requirement: Validate feasibility before generating
The system SHALL validate player data for structural problems before starting generation, including players declaring more than one play-with partner, play-with pairs naming a player who is not registered in the session, and groups that must co-locate exceeding team size. Generation SHALL NOT begin when a blocking problem is found.

#### Scenario: Blocking problem prevents generation
- **WHEN** session data contains a blocking structural problem
- **THEN** the system reports the problem and does not produce candidate rosters
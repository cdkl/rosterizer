# team-generation Specification

## Purpose

Generates balanced curling team assignments for a league session, honoring player position preferences, play-with partner requests, session-to-session variety, and team strength derived from position-specific player ability.

## Requirements

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

### Requirement: Honor play-with pairings
The system SHALL place each declared play-with pair together on the same team. The play-with relationship SHALL be treated as symmetric: if either member names the other as a play-with partner, the two are paired. A player MAY declare at most one play-with partner, and the system SHALL treat the declared pairings as a set of disjoint pairs.

#### Scenario: Symmetric pairing
- **WHEN** player A names player B as play-with partner but player B names no one
- **THEN** A and B are placed on the same team

#### Scenario: No play-with preference
- **WHEN** a player has no play-with preference
- **THEN** the player is assigned freely without a partner constraint

### Requirement: Balance teams by positional strength
The system SHALL distribute players across teams so that team strength, computed as the sum of each player's ability at their assigned position multiplied by that position's influence, is as even as possible across teams. Positional influence SHALL be weighted as follows: Skip 38%, Vice 27%, Second 20%, Lead 15%. The system SHALL place players in higher-influence positions in a way that minimizes the spread in team strength, rather than balancing players' raw totals alone. For 3-player teams with no Lead, the system SHALL rescale the Skip, Vice, and Second weights proportionally so they sum to 1.0 while preserving their relative ratios.

#### Scenario: Balanced rosters beat unbalanced alternatives
- **WHEN** the engine is run against a league with a wide spread of player ability
- **THEN** the generated roster's balance score is higher than that of a randomly generated roster for the same players

#### Scenario: Position-level balance
- **WHEN** teams are generated
- **THEN** the spread of ability among players assigned to each position is lower than the spread among all players in the session

#### Scenario: Fallback when no results exist
- **WHEN** no results are recorded for any prior session
- **THEN** ability is derived from stated experience alone and balancing still applies

#### Scenario: Three-player teams rescale proportions
- **WHEN** a team has only Skip, Vice, and Second with no Lead
- **THEN** the Skip, Vice, and Second influence weights are rescaled proportionally to sum to 1.0, preserving their relative ratios

### Requirement: Maximize session-to-session variety
The system SHALL prefer assignments that mix players who did not share a team in previous sessions. This preference SHALL influence candidate ranking but SHALL NOT be treated as a requirement that generation must satisfy.

#### Scenario: Variety preferred over repetition
- **WHEN** two candidate rosters are otherwise comparable but one places fewer pairs of returning teammates together
- **THEN** the roster with fewer returning teammate pairs is scored higher on team continuity

#### Scenario: First session has no prior history
- **WHEN** the current session is the first session of the league
- **THEN** team continuity contributes no penalty

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

### Requirement: Validate feasibility before generating
The system SHALL validate player data for structural problems before starting generation, including players declaring more than one play-with partner, play-with pairs naming a player who is not registered in the session, and groups that must co-locate exceeding team size. Generation SHALL NOT begin when a blocking problem is found.

#### Scenario: Blocking problem prevents generation
- **WHEN** session data contains a blocking structural problem
- **THEN** the system reports the problem and does not produce candidate rosters

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
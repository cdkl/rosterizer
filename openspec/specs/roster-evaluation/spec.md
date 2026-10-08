# roster-evaluation Specification

## Purpose

Scores generated curling team rosters across multiple quality dimensions so the convenor can compare candidates and select the best one.

## Requirements

### Requirement: Evaluate roster completeness
The system SHALL score a roster on how many unassigned players it places, where locked players already on an existing team are counted as satisfied and not treated as missing. A roster placing every unassigned player SHALL score 1.0. A roster missing 1 unassigned player SHALL score 0.7, missing 2 unassigned players SHALL score 0.4, and missing 3 or more unassigned players SHALL score 0.0.

#### Scenario: All players assigned
- **WHEN** a roster assigns all 32 registered players
- **THEN** the completeness score is 1.0

#### Scenario: One player unassigned
- **WHEN** a roster assigns 31 of 32 registered players
- **THEN** the completeness score is 0.7

#### Scenario: All unassigned players placed
- **WHEN** a roster places all 22 unassigned players while 8 are locked onto existing teams
- **THEN** the completeness score is 1.0

#### Scenario: Locked players are not counted missing
- **WHEN** a roster places every unassigned player and locked players remain on their existing teams
- **THEN** the completeness score is 1.0 rather than penalising for the locked players

#### Scenario: One unassigned player missing
- **WHEN** a roster places 21 of 22 unassigned players
- **THEN** the completeness score is 0.7

### Requirement: Evaluate position preference fit
The system SHALL score a roster on how well player position preferences are met. Each player assigned to their first preference contributes 1.0, second preference contributes 0.5, and any other position contributes 0.0. The overall score SHALL be the average across all assigned players.

#### Scenario: All first preferences met
- **WHEN** every player in a roster is assigned to their preferred_position1
- **THEN** the position preference score is 1.0

#### Scenario: Mixed preferences
- **WHEN** half of players get their first preference and half get their second
- **THEN** the position preference score is 0.75

### Requirement: Evaluate team continuity
The system SHALL score each team on how many of its players were on the same team in prior sessions. Teams with 0 or 1 returning player together SHALL score 1.0. Teams with 2 returning players together SHALL score 0.66. Teams with 3 returning players together SHALL score 0.33. Teams with all 4 returning players together SHALL score 0.0. The system SHALL evaluate continuity against the last 3 sessions with decreasing weight for older sessions.

#### Scenario: No repeated pairings from prior session
- **WHEN** a team shares at most 1 player with any team from the prior session
- **THEN** the team continuity score is 1.0

#### Scenario: Play-with partners exempt from penalty
- **WHEN** two players are paired together from a prior session and they have each other as play-with partners
- **THEN** they count as 1 player for continuity scoring rather than 2

### Requirement: Evaluate plays-with adherence
The system SHALL score each team on whether declared play-with partners are placed together. A team where all players with play-with preferences have their partner on the same team SHALL score 1.0. Each player whose play-with partner is missing from the team SHALL multiply the team score by 0.5.

#### Scenario: All partners together
- **WHEN** every player with a play-with preference has their partner on the same team
- **THEN** the plays-with adherence score is 1.0

#### Scenario: Partner missing
- **WHEN** a player has a play-with partner who is not on the same team
- **THEN** that team's plays-with adherence score is 0.5 or lower

### Requirement: Evaluate player rules compliance
The system SHALL score each team on compliance with PlayerRule constraints. Each violation of a "never_together" rule SHALL multiply the team score by (1.0 - rule weight). Each violation of a "must_be_together" rule SHALL also multiply the team score by (1.0 - rule weight). Teams with no rule violations SHALL score 1.0.

#### Scenario: Never-together violation penalized
- **WHEN** two players with a "never_together" rule (weight 1.0) are on the same team
- **THEN** that team's player rules score is 0.0

#### Scenario: Must-be-together violation penalized
- **WHEN** one player from a "must_be_together" rule (weight 0.5) is on a team without the other
- **THEN** that team's player rules score is 0.5

### Requirement: Evaluate team balance by positional strength
The system SHALL score a roster on how evenly team strength is distributed across teams, where team strength is the sum of each player's ability at their assigned position multiplied by that position's influence weight. The score SHALL be derived from the coefficient of variation (standard deviation divided by mean) of team strength across teams. The score SHALL range from 0.0 for extremely unbalanced rosters to 1.0 for perfectly balanced rosters.

#### Scenario: Perfectly balanced teams
- **WHEN** all teams have the same total strength
- **THEN** the team balance score is 1.0

#### Scenario: Unbalanced teams
- **WHEN** one team's total strength is far above the mean and another's is far below
- **THEN** the team balance score is substantially below 1.0

#### Scenario: Balance reflects positional influence
- **WHEN** two rosters have identical player assignments but differ only in which players occupy the higher-influence positions
- **THEN** the roster placing stronger players in higher-influence positions has a better balance score

#### Scenario: Fallback when no results exist
- **WHEN** no results are recorded for any player in the session
- **THEN** ability is derived entirely from stated experience, and balance is still computed on positional strength

### Requirement: Compute a composite roster score as a weighted mean
The system SHALL compute a single composite score for each roster as a weighted arithmetic mean of its individual criterion scores. Each criterion score SHALL be clamped to a floor of 0.05 before averaging, so that candidates violating a constraint remain distinguishable from one another rather than collapsing to an identical value. The composite score SHALL determine the default sort order when presenting rosters.

#### Scenario: Perfect roster
- **WHEN** a roster scores at or above the floor on every criterion
- **THEN** the composite score is 1.0

#### Scenario: Constrained roster remains distinguishable
- **WHEN** two rosters both violate a weight-1.0 constraint on one team, but one violates fewer other criteria
- **THEN** the two rosters receive different composite scores

#### Scenario: Scores stay in a readable range
- **WHEN** rosters are evaluated with realistic criterion values between 0.6 and 0.95
- **THEN** the composite scores remain spread apart enough to rank the rosters in a consistent order

### Requirement: Provide per-criterion score breakdown
The system SHALL return individual scores for each evaluation criterion alongside the composite score, so the convenor can understand WHY a roster scored the way it did.

#### Scenario: Score breakdown available
- **WHEN** a roster is evaluated
- **THEN** the result includes separate scores for completeness, position preference, team continuity, plays-with adherence, player rules, and team balance

### Requirement: Return violations alongside scores
The system SHALL return the specific constraint violations present in a roster, including unsatisfied play-with pairings and violated player rules, so the convenor can see what a low score represents.

#### Scenario: Violations listed for a roster
- **WHEN** a roster contains an unsatisfied play-with pairing
- **THEN** the evaluation result names the affected players

### Requirement: Exclude locked teams from the balance score
The system SHALL compute team balance from the newly generated teams only, comparing their strengths against each other, and SHALL NOT include locked teams in the balanced set.

#### Scenario: Balance covers generated teams only
- **WHEN** a session has locked teams plus newly generated teams
- **THEN** the balance score reflects the spread among the generated teams, ignoring the strengths of the locked teams

#### Scenario: Generation with locked teams still balances
- **WHEN** generation runs with locked teams present
- **THEN** the generated teams are balanced among themselves and the balance criterion still yields a meaningful score in the 0.0 to 1.0 range

### Requirement: Scope play-with checks to the generated pool
The system SHALL evaluate play-with adherence and report unsatisfied play-with pairings considering only players in the unassigned pool. A pairing whose members are both on a locked team SHALL be treated as satisfied and SHALL NOT be reported. Each unsatisfied pairing SHALL be reported once for the roster, not once per team.

#### Scenario: Pair satisfied inside a locked team
- **WHEN** two play-with partners are both already placed on the same locked team
- **THEN** generation does not report the pairing and it does not lower the play-with adherence score

#### Scenario: Split pairing reported once
- **WHEN** a play-with pairing between two unassigned players lands on different generated teams
- **THEN** the roster reports that pairing exactly once

#### Scenario: Locked pairings do not penalise generated teams
- **WHEN** locked teams contain satisfied play-with pairings and new teams are generated
- **THEN** the play-with adherence score of the generated teams reflects only the unassigned pairings
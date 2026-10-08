# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
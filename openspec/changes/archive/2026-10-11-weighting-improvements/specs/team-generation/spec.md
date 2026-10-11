# Spec Delta

## MODIFIED Requirements

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
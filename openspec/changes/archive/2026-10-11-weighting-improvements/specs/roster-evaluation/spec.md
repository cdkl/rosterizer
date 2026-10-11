# Spec Delta

## MODIFIED Requirements

### Requirement: Evaluate team balance by positional strength
The system SHALL score a roster on how evenly team strength is distributed across teams, where team strength is the sum of each player's ability at their assigned position multiplied by that position's influence weight. Positional influence SHALL be weighted as follows: Skip 38%, Vice 27%, Second 20%, Lead 15%. For 3-player teams with no Lead, the system SHALL rescale the Skip, Vice, and Second weights proportionally so they sum to 1.0. The score SHALL be derived from the coefficient of variation (standard deviation divided by mean) of team strength across teams. The score SHALL range from 0.0 for extremely unbalanced rosters to 1.0 for perfectly balanced rosters.

#### Scenario: Perfectly balanced teams
- **WHEN** all teams have the same total strength
- **THEN** the team balance score is 1.0

#### Scenario: Unbalanced teams
- **WHEN** one team's total strength is far above the mean and another's is far below
- **THEN** the team balance score is substantially below 1.0

#### Scenario: Balance reflects positional influence
- **WHEN** two rosters have identical player assignments but differ only in which players occupy the higher-influence positions
- **THEN** the roster placing stronger players in higher-influence positions has a better balance score

#### Scenario: Three-player teams rescale for balance
- **WHEN** a roster includes a 3-player team with no Lead
- **THEN** that team's strength uses rescaled Skip, Vice, and Second weights for the balance calculation

#### Scenario: Fallback when no results exist
- **WHEN** no results are recorded for any player in the session
- **THEN** ability is computed from stated experience combined with a .500 default per the sparse-data backfill rule, and balance is still computed on positional strength

## ADDED Requirements

### Requirement: Backfill sparse ability data with .500 default
The system SHALL, when computing a player's ability at a position where weighted observed games fall below the shrinkage prior, replace the missing games with a .500 win-rate default. The ability SHALL be computed as the standard shrinkage formula with missing games added at .500. When weighted observed games meet or exceed the prior, the formula SHALL be unchanged.

#### Scenario: No observed games defaults to .500 blend
- **WHEN** a player has zero observed games at a position
- **THEN** their ability at that position is `(0.5 + experience_score) / 2`, not pure experience

#### Scenario: Sparse old data gets proportional backfill
- **WHEN** a player has observed games below the shrinkage prior at a position
- **THEN** the missing portion is filled with .500 performance rather than experience, producing a lower ability than the pure-experience fallback would

#### Scenario: Established players are unchanged
- **WHEN** a player has weighted observed games at or above the shrinkage prior at a position
- **THEN** their ability is computed by the existing shrinkage formula with no .500 backfill term

#### Scenario: Novice rates at floor
- **WHEN** a player has zero years of stated experience and zero observed games at a position
- **THEN** their ability at that position is 0.25
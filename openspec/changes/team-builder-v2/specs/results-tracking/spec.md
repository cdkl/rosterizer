# Spec Delta

## Purpose

Stores team game results from past sessions, protects that data from accidental deletion, and derives position-specific player strength ratings with time decay and shrinkage so the roster builder can assess how much each player contributes at each position.

## ADDED Requirements

### Requirement: Record team game results
The system SHALL allow the convenor to record game results for a committed roster in a session, including wins, losses, ties, and optional points scored and points against. Each result SHALL snapshot the roster's team composition so it remains valid even if the session's teams are later modified.

#### Scenario: Enter results for a session
- **WHEN** the convenor enters 5 wins, 3 losses, and 0 ties for Team 1 in Session 2
- **THEN** a TeamResult is stored with those values, linked to Session 2, Team 1, and the four players who occupied that roster

#### Scenario: Results already exist for a team number in a session
- **WHEN** the convenor submits results for a session and team number that already has a result
- **THEN** the existing result is updated rather than duplicated

### Requirement: Commit a roster before entering results
The system SHALL require the convenor to explicitly commit a session's teams before results can be entered for that session. Committing SHALL record the current team composition as the historical record for that session.

#### Scenario: Commit before entering results
- **WHEN** the convenor commits Session 2's teams and then enters results
- **THEN** the results are recorded against the committed composition

#### Scenario: Attempt to enter results before committing
- **WHEN** the convenor opens the results entry page for an uncommitted session
- **THEN** the system requires committing the roster first and does not accept result input

### Requirement: Protect results data from deletion
The system SHALL block deletion of a session that has results recorded. The system SHALL block bulk deletion of players who appear in any recorded result. The system SHALL warn before clearing the teams of a session that has recorded results.

#### Scenario: Deleting a session with results
- **WHEN** the convenor attempts to delete a session that has recorded results
- **THEN** the deletion is blocked and the system explains that results must be removed first

#### Scenario: Clearing all players when results reference them
- **WHEN** the convenor attempts to clear the player list and recorded results reference those players
- **THEN** the deletion is blocked

#### Scenario: Clearing teams for a session with results
- **WHEN** the convenor confirms clearing teams for a session that has recorded results
- **THEN** the system warns that historical results reference the previous composition, then proceeds if confirmed

### Requirement: Rate player experience on a saturating curve
The system SHALL convert stated years curled into an experience score between 0.0 and 1.0 using a saturating curve, so that early-year gains are large and later gains are small. A player with 0 years SHALL score 0.0. The curve SHALL be parameterized so it can be refined later without changing how it is consumed.

#### Scenario: Novice curler
- **WHEN** a player has 0 years curled
- **THEN** their experience score is 0.0

#### Scenario: Early years show the largest gains
- **WHEN** comparing a player with 1 year to a player with 3 years
- **THEN** the 3-year player's experience score is more than twice the 1-year player's score

#### Scenario: Diminishing returns at higher experience
- **WHEN** comparing the score difference between 5 and 10 years against the difference between 15 and 20 years
- **THEN** the 15-to-20 year difference is smaller than the 5-to-10 year difference

### Requirement: Calculate position-specific ability from results
The system SHALL calculate an ability rating for each player at each position they have played, based on the win rate of the teams they played on at that position. Ties SHALL count as half a win. Ability SHALL be time-weighted so results from more recent sessions count more, and the most recent prior session SHALL carry full weight.

#### Scenario: Consistent winning record at a position
- **WHEN** a player played Skip in prior sessions with win rates of 0.8, 0.7, and 0.9
- **THEN** their Skip ability is a time-weighted average of those rates, weighted toward the most recent

#### Scenario: Ties count as half a win
- **WHEN** a player's team recorded 4 wins, 2 losses, and 2 ties
- **THEN** the win rate used for that session is 0.5

### Requirement: Weight older results less than recent results
The system SHALL apply exponential decay when weighting historical results, using a decay factor of 0.7 by default. Sessions SHALL be ordered by year then session number when determining result age, so that results spanning different years are weighted by their true distance apart.

#### Scenario: Recent results count more
- **WHEN** a player had a 0.9 win rate in the most recent prior session and a 0.9 win rate three sessions earlier
- **THEN** the most recent result contributes more weight than the earlier one

#### Scenario: Cross-year weighting
- **WHEN** comparing a result from Session 3 of one year to Session 3 of the previous year
- **THEN** the earlier result is weighted as older, not treated as equally recent

### Requirement: Shrink sparse results toward the experience expectation
The system SHALL blend a player's observed win rate at a position with their experience-derived expectation, weighted by how much result history exists. A player with no result history SHALL receive exactly their experience-derived expectation. A player with substantial history SHALL be dominated by their observed win rate.

#### Scenario: No history falls back to experience
- **WHEN** a player has no recorded results at a position
- **THEN** their ability at that position equals their experience score

#### Scenario: Limited history is shrunk toward experience
- **WHEN** a player has only a small amount of result history that differs sharply from their experience score
- **THEN** their resulting ability sits between the experience score and the observed win rate, closer to the experience score

#### Scenario: Substantial history dominates experience
- **WHEN** a player has extensive result history at a position
- **THEN** their resulting ability is close to their observed time-weighted win rate

### Requirement: Value a player's contribution at each position
The system SHALL weight each position by its influence on the team's outcome, with Skip having the highest influence and Lead the lowest. The system SHALL compute a player's contribution at a position as their ability at that position multiplied by that position's influence weight. Team strength SHALL be the sum of the four players' contributions at their assigned positions.

#### Scenario: A player is worth more at a higher-influence position
- **WHEN** a player has the same ability of 0.8 at both Skip and Lead
- **THEN** their contribution as Skip is higher than their contribution as Lead

#### Scenario: Promotion to a higher-influence position is priced
- **WHEN** a player has ability 0.8 at Vice and 0.6 at Skip
- **THEN** their contribution at Vice exceeds their contribution at Skip, reflecting the difference in ability despite Skip's higher influence weight

#### Scenario: Team strength sums member contributions
- **WHEN** a team has four players assigned to positions
- **THEN** the team's strength equals the sum of each player's contribution at their assigned position

### Requirement: Detect overconstrained play-with and rule groupings
The system SHALL validate that no group of players who must be placed together exceeds the size of a team. This includes players linked by play-with preferences and by must-be-together rules. When such a group is too large, the system SHALL refuse to generate and SHALL identify the players involved.

#### Scenario: Overconstrained group detected
- **WHEN** play-with pairings and must-be-together rules combine to require 5 players on one team
- **THEN** the system refuses to generate and names the players in the oversized group

#### Scenario: Player with conflicting play-with declarations
- **WHEN** a player is declared as the play-with partner of two different players
- **THEN** the system reports the conflicting declarations as invalid input

### Requirement: Report unmet play-with preferences after generation
The system SHALL report any play-with pairing that could not be satisfied in a generated roster, so the convenor knows which preferences were not met.

#### Scenario: Unsatisfied pairing reported
- **WHEN** a generated roster places two players declared as play-with partners on different teams
- **THEN** the system reports that pairing as unsatisfied for that roster
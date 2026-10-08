# roster-workflow Specification

## Purpose

Provides the convenor with a workflow to trigger roster generation, review scored candidates with transparent criteria breakdowns, select the best roster, and apply it to the session.

## Requirements

### Requirement: Access v2 roster builder from session
The system SHALL provide a distinct entry point for the v2 roster builder, accessible from the session management interface, that is separate from the existing v1 team generation workflow.

#### Scenario: V2 entry point exists alongside v1
- **WHEN** viewing a session's details
- **THEN** both the v1 "Generate Teams" and v2 "Roster Builder" options are available

### Requirement: Configure generation options
The system SHALL allow the convenor to set how many candidate rosters to generate before starting. Play-with preferences SHALL always be used during generation and SHALL NOT be presented as an optional setting. The system SHALL NOT present options for full play-with adherence or full uniqueness from the previous session.

#### Scenario: Set candidate count and generate
- **WHEN** the convenor sets a candidate count and starts generation
- **THEN** the system generates that many candidates using position preferences, play-with preferences, player rules, and positional strength balancing

#### Scenario: No play-with toggle offered
- **WHEN** the convenor views the generation options
- **THEN** no option is presented to disable play-with preferences

### Requirement: Show available results history before generating
The system SHALL show the convenor how much result history exists before generation starts, so that thin ratings can be explained rather than appearing arbitrary. The system SHALL indicate how many teams have results recorded across how many prior sessions, and SHALL state when no results are available and that ability will be derived from stated experience alone.

#### Scenario: Partial results coverage
- **WHEN** results exist for 5 of 8 teams in the most recent prior session and for no earlier sessions
- **THEN** the generation page indicates that results are recorded for 5 of 8 teams in 1 prior session

#### Scenario: No results available
- **WHEN** no results are recorded for any session
- **THEN** the generation page states that no results are available and that ability will be derived from stated experience

### Requirement: Report data problems before generation
The system SHALL check session data for structural problems before generating and SHALL present any problems found to the convenor instead of generating candidates. When overconstrained play-with and rule groupings are detected, the system SHALL name the players involved.

#### Scenario: Overconstrained grouping reported
- **WHEN** play-with pairings and must-be-together rules require more players than fit on one team
- **THEN** the system shows which players are involved and does not generate

### Requirement: Review candidate rosters with score breakdown
The system SHALL present all generated candidate rosters as a list of cards sorted by composite score descending. Each card SHALL display a prominent composite score, color-coded indicators for each evaluation criterion, and an expandable section showing team assignments in a readable grid layout. The system SHALL use green, yellow, and red color coding on score indicators so the convenor can assess quality at a glance.

#### Scenario: Rosters displayed with visual scores
- **WHEN** 10 candidate rosters are generated
- **THEN** all 10 are displayed as cards sorted by composite score descending, each with color-coded indicators for every criterion

#### Scenario: View team assignments
- **WHEN** the convenor expands a candidate roster card
- **THEN** the system shows each team with player names and positions in a readable grid layout

#### Scenario: View constraint violations
- **WHEN** a candidate roster contains unsatisfied play-with pairings or violated player rules
- **THEN** the convenor can see which constraints that roster does not satisfy

### Requirement: Select and apply a roster
The system SHALL allow the convenor to select one candidate roster and apply it to the session, creating Team records in the database. Existing teams for the session SHALL be preserved and not overwritten; new teams SHALL be appended with incremented team numbers.

#### Scenario: Apply selected roster
- **WHEN** the convenor selects a roster and applies it
- **THEN** all team assignments from that roster are saved as Team records for the session

#### Scenario: Existing teams preserved
- **WHEN** a session already has 4 manually created teams and a roster is applied
- **THEN** the existing 4 teams remain unchanged and the new teams start at the next available team number

### Requirement: Enter results for a committed roster
The system SHALL provide a page for entering wins, losses, and ties for each team in a session, after the session's teams have been committed. The system SHALL pre-fill values when results already exist.

#### Scenario: Enter results for a committed session
- **WHEN** the convenor opens results entry for a committed session
- **THEN** the page shows each team with its players and inputs for wins, losses, and ties

#### Scenario: Edit existing results
- **WHEN** results already exist for a team and the convenor submits new values
- **THEN** the stored result is updated with the new values

### Requirement: CLI-driven generation
The system SHALL provide a management command that generates rosters from the command line. The command SHALL accept the session identifier and the number of candidates, and SHALL output scores and team assignments for each candidate.

#### Scenario: CLI generation
- **WHEN** running `python manage.py generate_rosters_v2 --session-id 3 --candidates 5`
- **THEN** the system outputs 5 candidate rosters with scores and team assignments to stdout

#### Scenario: CLI reports validation problems
- **WHEN** the session data contains a blocking structural problem
- **THEN** the command reports the problem and exits without generating candidates

### Requirement: Show locked teams before generating
The system SHALL, when the convenor opens the generation screen, indicate how many teams already exist for the session, that those teams are locked, and how many registered players remain unassigned.

#### Scenario: Locked teams reported
- **WHEN** a session has 2 existing teams covering 8 of 30 registered players
- **THEN** the generation screen states that 2 teams are already created and 22 players remain to assign

#### Scenario: No locked teams
- **WHEN** a session has no existing teams
- **THEN** the generation screen does not report any locked teams and behaves as before

### Requirement: Surface a lock conflict instead of generating
The system SHALL, when a play-with pairing or must-be-together rule cannot be satisfied because it spans a locked team, show the conflict and the affected players instead of proceeding with generation.

#### Scenario: Lock conflict shown
- **WHEN** a play-with pairing links a player locked onto a full team to an unassigned player
- **THEN** the generation screen shows which players are affected and does not generate candidate rosters
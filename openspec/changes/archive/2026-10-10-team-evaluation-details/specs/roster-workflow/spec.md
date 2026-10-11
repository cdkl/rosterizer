# Spec Delta

## MODIFIED Requirements

### Requirement: Review candidate rosters with score breakdown
The system SHALL present all generated candidate rosters as a list of cards sorted by composite score descending. Each card SHALL display a prominent composite score, color-coded indicators for each evaluation criterion, and an expandable section showing team assignments with per-team scoring detail. When the convenor expands a candidate card, the system SHALL show each team with its individual criterion scores, per-player ability and experience information, and any specific constraint violations affecting that team. The system SHALL use green, yellow, and red color coding on score indicators so the convenor can assess quality at a glance.

#### Scenario: Rosters displayed with visual scores
- **WHEN** 10 candidate rosters are generated
- **THEN** all 10 are displayed as cards sorted by composite score descending, each with color-coded indicators for every criterion

#### Scenario: View team assignments
- **WHEN** the convenor expands a candidate roster card
- **THEN** the system shows each team with player names and positions in a readable grid layout

#### Scenario: View per-team scoring
- **WHEN** the convenor expands a candidate roster card
- **THEN** the system shows each team's individual score on plays-with adherence, player rules, and continuity, so the convenor can see which teams drag down the roster's aggregate scores

#### Scenario: View per-player ability information
- **WHEN** the convenor expands a candidate roster card
- **THEN** the system shows each player's stated years of experience, their ability rating at their assigned position, and their contribution to the team's positional strength

#### Scenario: View constraint violations
- **WHEN** a candidate roster contains unsatisfied play-with pairings or violated player rules
- **THEN** the convenor can see which specific players are affected and which teams they ended up on

#### Scenario: View continuity detail
- **WHEN** a team's continuity score is below 1.0 due to returning teammates from prior sessions
- **THEN** the system identifies which players previously shared a team and in which session
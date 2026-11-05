# Spec Delta

## Purpose

Enables a convenor to replace one registered player with another in a session, propagating the swap to all existing team assignments and committed results.

## ADDED Requirements

### Requirement: Substitute one player for another in a session

The system SHALL provide a management command that replaces a registered player (the player being removed) with a different player (the substitute) in a specified session. The command SHALL register the substitute in the session by creating a PlayerSession if one does not already exist. The command SHALL swap the substitute into every Team row where the removed player occupies any position. When the session's results are committed, the command SHALL apply the same swap to every TeamResult row. The command SHALL operate in a dry-run mode by default and SHALL apply changes only when an explicit apply flag is provided.

#### Scenario: Dry-run shows planned changes without modifying data

- **WHEN** the command is run without the apply flag for a session where the removed player is registered and occupies positions in existing teams
- **THEN** the command prints which PlayerSession, Team, and TeamResult rows would be created or updated, but SHALL NOT write any changes to the database

#### Scenario: Apply performs the substitution

- **WHEN** the command is run with the apply flag for a session where the removed player is registered and occupies positions in existing teams
- **THEN** the command registers the substitute player in the session, swaps the substitute into every team position previously held by the removed player, and swaps the substitute into TeamResult rows if results are committed

#### Scenario: Substitute is already registered in the session

- **WHEN** the substitute player already has a PlayerSession for the session
- **THEN** the command SHALL NOT create a duplicate PlayerSession and SHALL proceed with the team and result swaps

#### Scenario: Session has no teams

- **WHEN** the session has no Team rows involving the removed player
- **THEN** the command SHALL still register the substitute (if not already registered) and SHALL report that zero teams were updated

### Requirement: Validate inputs before applying changes

The system SHALL validate that both players exist in the database and that the removed player is registered in the specified session before making any changes. The command SHALL reject the operation with a clear error message when these preconditions are not met.

#### Scenario: Removed player is not registered in the session

- **WHEN** the removed player exists in the database but has no PlayerSession for the specified session
- **THEN** the command SHALL exit with an error stating that the player is not registered in the session and SHALL NOT modify any data

#### Scenario: A player does not exist in the database

- **WHEN** either the removed player or the substitute player ID does not correspond to an existing Player
- **THEN** the command SHALL exit with an error naming the missing player and SHALL NOT modify any data

### Requirement: Idempotent substitution

The system SHALL make the substitution idempotent: running the same substitution a second time after successful apply SHALL report that no changes are needed and SHALL NOT create duplicate data or errors.

#### Scenario: Re-running the same substitution after apply

- **WHEN** the command is run a second time with the apply flag after a successful substitution, and the substitute already occupies all the removed player's former positions
- **THEN** the command SHALL report that the substitution is already complete and SHALL exit without modifying any data
"""
CLI entry point for the v2 roster generator.

Useful for scripting and for inspecting a session's data problems without
opening the browser.
"""

from django.core.management.base import BaseCommand, CommandError

from rosterizer.models import PlayerSession, Session
from rosterizer.position_strength import POSITIONS
from rosterizer.team_generation_v2 import (
    DEFAULT_CANDIDATES,
    ValidationProblem,
    generate_rosters_v2,
    validate_session,
)

CRITERION_LABELS = {
    'completeness': 'complete ',
    'position_preference': 'position',
    'team_continuity': 'variety ',
    'plays_with_adherence': 'play-with',
    'player_rules': 'rules   ',
    'team_balance': 'balance ',
}


class Command(BaseCommand):
    help = 'Generate candidate rosters for a session using the v2 engine.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-id', type=int, required=True,
            help='Session to generate rosters for.')
        parser.add_argument(
            '--candidates', type=int, default=DEFAULT_CANDIDATES,
            help=f'Number of candidate rosters to return (default {DEFAULT_CANDIDATES}).')
        parser.add_argument(
            '--seed', type=str, default=None,
            help='Seed for reproducible output. Omit for a random run.')

    def handle(self, *args, **options):
        session_id = options['session_id']
        candidates_wanted = max(1, options['candidates'])

        if not Session.objects.filter(pk=session_id).exists():
            raise CommandError(f'No session with id {session_id}.')

        # Validate once and reuse the context, so the lock/remainder counts and
        # the generation run all describe the same snapshot.
        try:
            context = validate_session(session_id)
        except ValidationProblem as exc:
            # Non-zero exit so scripts can detect a session needing attention.
            raise CommandError(f'Cannot generate rosters: {exc}') from exc

        self.stdout.write(
            f'{context.locked_team_count} locked team(s), '
            f'{len(context.registered_player_ids)} unassigned player(s).')

        if context.team_count == 0:
            self.stdout.write('No players remain to assign.')
            return

        result = generate_rosters_v2(
            session_id, num_candidates=candidates_wanted, seed=options['seed'],
            context=context)

        players = {
            ps.pk: ps.player
            for ps in PlayerSession.objects.filter(session_id=session_id).select_related('player')
        }

        self.stdout.write(f'Generated {len(result["candidates"])} candidate roster(s).')
        if result['shortfall']:
            self.stdout.write(self.style.WARNING(
                f'  {result["shortfall"]} fewer than requested: the search space was exhausted.'))

        for index, candidate in enumerate(result['candidates'], start=1):
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'Roster {index}  score {candidate["composite"]:.3f}'))
            for key, label in CRITERION_LABELS.items():
                self.stdout.write(f'  {label} {candidate["criteria"][key]:.3f}')

            for violation in candidate['violations']:
                self.stdout.write(self.style.WARNING(f'  ! {violation}'))

            self.stdout.write('')
            for team_index, team in enumerate(candidate['roster'], start=1):
                names = []
                for position in POSITIONS:
                    value = team.get(position)
                    player = players.get(value)
                    names.append(f'{position}: {player.full_name}' if player
                                 else f'{position}: -')
                self.stdout.write(f'  Team {team_index}  ' + '  '.join(names))
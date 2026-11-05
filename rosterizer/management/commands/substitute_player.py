"""
Substitute one registered player for another in a session.

Swaps the substitute into every team position and (if results are committed)
every TeamResult row held by the outgoing player. Designed for emergency
replacements after teams are already set — no need to clear and regenerate.
"""

from django.core.management.base import BaseCommand, CommandError

from rosterizer.models import Player, PlayerSession, Session, Team, TeamResult

# Model field names for the four curling positions, in order.
POSITION_FIELDS = ('skip', 'vice', 'second', 'lead')


class Command(BaseCommand):
    help = (
        'Replace one registered player with another in a session. '
        'Run without --apply to preview changes first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-id', type=int, required=True,
            help='Session to perform the substitution in.',
        )
        parser.add_argument(
            '--remove-player', type=int, required=True,
            help='Player ID to swap out.',
        )
        parser.add_argument(
            '--add-player', type=int, required=True,
            help='Player ID to swap in (must already exist in the database).',
        )
        parser.add_argument(
            '--apply', action='store_true', default=False,
            help='Commit the changes. Omit to preview only.',
        )

    def handle(self, *args, **options):
        session_id = options['session_id']
        remove_id = options['remove_player']
        add_id = options['add_player']
        apply_changes = options['apply']

        # ── validate inputs ────────────────────────────────────────────
        try:
            session = Session.objects.get(pk=session_id)
        except Session.DoesNotExist:
            raise CommandError(f'No session with id {session_id}.')

        try:
            remove_player = Player.objects.get(pk=remove_id)
        except Player.DoesNotExist:
            raise CommandError(f'Player with id {remove_id} does not exist.')

        try:
            add_player = Player.objects.get(pk=add_id)
        except Player.DoesNotExist:
            raise CommandError(f'Player with id {add_id} does not exist.')

        remove_ps = PlayerSession.objects.filter(
            player=remove_player, session=session,
        ).first()
        if remove_ps is None:
            raise CommandError(
                f'{remove_player.full_name} is not registered in {session}.'
            )

        # ── compute what would change ──────────────────────────────────

        # PlayerSession for the substitute
        add_ps = PlayerSession.objects.filter(
            player=add_player, session=session,
        ).first()
        needs_ps = add_ps is None

        # Team rows that reference the removed player
        teams_to_update = []
        for team in Team.objects.filter(session=session):
            for field in POSITION_FIELDS:
                if getattr(team, f'{field}_id') == remove_id:
                    teams_to_update.append((team.pk, team.team_number, field))
                    break  # count each team once even if player appears twice

        # TeamResult rows (only when results are committed)
        results_to_update = []
        if session.results_committed:
            for result in TeamResult.objects.filter(session=session):
                for field in POSITION_FIELDS:
                    if getattr(result, f'{field}_id') == remove_id:
                        results_to_update.append(
                            (result.pk, result.team_number, field),
                        )
                        break

        has_changes = needs_ps or teams_to_update or results_to_update

        # ── idempotency: nothing to do ─────────────────────────────────
        if not has_changes:
            verb = 'Would exit' if not apply_changes else 'Exiting'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{verb}: substitution is already complete — '
                    f'{add_player.full_name} already occupies all positions '
                    f'formerly held by {remove_player.full_name} in {session}.',
                )
            )
            return

        # ── dry-run output ─────────────────────────────────────────────
        action = 'Applying' if apply_changes else 'Would apply'
        self.stdout.write(f'Session: {session}')
        self.stdout.write(f'Remove:  {remove_player.full_name} (id={remove_id})')
        self.stdout.write(f'Add:     {add_player.full_name} (id={add_id})')
        self.stdout.write('')

        if needs_ps:
            self.stdout.write(
                f'{action} PlayerSession: '
                f'register {add_player.full_name} in {session}'
            )
        else:
            self.stdout.write(
                f'PlayerSession: {add_player.full_name} already registered '
                f'in {session}'
            )

        for _, team_number, field in teams_to_update:
            self.stdout.write(
                f'{action} Team {team_number}: '
                f'replace {remove_player.full_name} '
                f'({field} → {add_player.full_name})'
            )

        for _, team_number, field in results_to_update:
            self.stdout.write(
                f'{action} TeamResult {team_number}: '
                f'replace {remove_player.full_name} '
                f'({field} → {add_player.full_name})'
            )

        if not apply_changes:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Dry-run complete. No changes written. '
                    'Run with --apply to commit.'
                )
            )
            return

        # ── apply ──────────────────────────────────────────────────────
        self.stdout.write('')

        if needs_ps:
            PlayerSession.objects.create(
                player=add_player,
                session=session,
                years_curled=remove_ps.years_curled,
                preferred_position1=remove_ps.preferred_position1,
                preferred_position2=remove_ps.preferred_position2,
                play_with=remove_ps.play_with,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Registered {add_player.full_name} in {session}.'
                )
            )

        # Update Team rows
        team_ids = {t[0] for t in teams_to_update}
        if team_ids:
            teams = Team.objects.in_bulk(team_ids)
            for team in teams.values():
                for field in POSITION_FIELDS:
                    if getattr(team, f'{field}_id') == remove_id:
                        setattr(team, field, add_player)
                team.save(update_fields=POSITION_FIELDS)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {len(team_ids)} team(s).'
                )
            )

        # Update TeamResult rows
        result_ids = {r[0] for r in results_to_update}
        if result_ids:
            results = TeamResult.objects.in_bulk(result_ids)
            for result in results.values():
                for field in POSITION_FIELDS:
                    if getattr(result, f'{field}_id') == remove_id:
                        setattr(result, field, add_player)
                result.save(update_fields=POSITION_FIELDS)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {len(result_ids)} TeamResult row(s).'
                )
            )

        self.stdout.write(
            self.style.SUCCESS('Substitution complete.')
        )
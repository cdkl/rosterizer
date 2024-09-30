import os
import csv
from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
from rosterizer.models import Player, Session, PlayerSession, Team
from rosterizer import utilities


class ImportRosterCsvCommand(BaseCommand):
    help = 'Import players and optionally teams from a specified CSV file'

    def add_arguments(self, parser):
        parser.add_argument('roster_file', type=str, help='The path to the roster CSV file')
        parser.add_argument('session_id', type=int, help='The ID of the session')
        parser.add_argument('create_teams', type=bool, help='Whether to create teams from the roster')

    def handle(self, *args, **kwargs):
        roster_file = kwargs['roster_file']
        session_id = kwargs['session_id']
        
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Session with ID {session_id} does not exist'))
            return

        if not os.path.exists(roster_file):
            self.stdout.write(self.style.ERROR(f'File {roster_file} does not exist'))
            return

        # Load the HTML file
        with open(roster_file, encoding='utf-8') as csvfile:
            next(csvfile)  # Skip the extra header row
            reader = csv.DictReader(csvfile)

            # Iterate over the rows and create Player instances
            for row in reader:
                if 'Member Name' not in row:
                    continue

                first_name, last_name = utilities.parse_name(row['Member Name'])
                    
                # Get or create Player
                player, created = Player.objects.update_or_create(
                    last_name=last_name.strip(),
                    first_name=first_name.strip(),
                    defaults={
                        'home_phone': row['Home Phone'],
                        'work_phone': row['Work Phone'],
                        'cell_phone': row['Cell Phone'],
                        'email': row['Email'],
                        'gender': row['Gender'][0].upper() if row['Gender'] else None
                    }
                )

                # Create PlayerSession
                PlayerSession.objects.create(
                    player=player,
                    session_id=session_id,
                    preferred_position1=row['Preferred Position 1'],
                    preferred_position2=row['Preferred Position 2'],
                    play_with=row['Play With'],
                    years_curled=int(row['Years Curled'] or 0)
                )

                if kwargs['create_teams']:
                    # Create or update Team
                    team_number = int(row['Team']) if row['Team'] else None
                    if team_number:
                        team, _ = Team.objects.get_or_create(
                            session_id=session_id, 
                            team_number=team_number
                        )

                        # Assign players to team roles
                        if team.skip is None:
                            team.skip = player
                        elif team.vice is None:
                            team.vice = player
                        elif team.second is None:
                            team.second = player
                        elif team.lead is None:
                            team.lead = player

                        team.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully imported roster from {roster_file} for session {session_id}'))

import os
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from rosterizer import utilities
from rosterizer.models import Player, Session, PlayerSession

class ImportPlayersCommand(BaseCommand):
	help = 'Import players from an HTML file and populate PlayerSession'

	def add_arguments(self, parser):
		parser.add_argument('player_file', type=str, help='The path to the HTML or CSV file to be imported')
		parser.add_argument('session_id', type=int, help='The ID of the session to associate players with')

	def handle(self, *args, **kwargs):
		if kwargs['player_file'].endswith('.html'):
			self.handle_html_file(**kwargs)
		else:
			raise NotImplementedError('Unsupported file format. Please use an HTML file')

	def handle_html_file(self, **kwargs):	
		html_file = kwargs['player_file']
		session_id = kwargs['session_id']

		try:
			session = Session.objects.get(id=session_id)
		except Session.DoesNotExist:
			self.stdout.write(self.style.ERROR(f'Session with ID {session_id} does not exist'))
			return

		if not os.path.exists(html_file):
			self.stdout.write(self.style.ERROR(f'File {html_file} does not exist'))
			return

		with open(html_file, 'r', encoding='utf-8') as file:
			soup = BeautifulSoup(file, 'lxml')
			table = soup.find('table')
			rows = table.find('tbody').find_all('tr')

			for row in rows:
				columns = row.find_all('td')
				if len(columns) < 18:
					continue

				member_name = columns[1].get_text(strip=True)
				home_phone = columns[2].get_text(strip=True)
				work_phone = columns[3].get_text(strip=True)
				cell_phone = columns[4].get_text(strip=True)
				email = columns[5].get_text(strip=True)
				gender = columns[6].text.strip()[0] # assuming the first character is M or F
				years_curled = int(columns[7].get_text(strip=True) or 0)
				preferred_position1 = columns[13].get_text(strip=True)
				preferred_position2 = columns[14].get_text(strip=True)
				play_with = columns[15].get_text(strip=True)

				first_name, last_name = utilities.parse_name(member_name)

				player, created = Player.objects.update_or_create(
					first_name=first_name.strip(),
					last_name=last_name.strip(),
					defaults={
						'home_phone': home_phone,
						'work_phone': work_phone,
						'cell_phone': cell_phone,
						'email': email,
						'gender': gender[0].upper() if gender else None
					}
				)

				PlayerSession.objects.create(
					player=player,
					session=session,
					years_curled=years_curled,
					preferred_position1=preferred_position1,
					preferred_position2=preferred_position2,
					play_with=play_with
				)

				self.stdout.write(self.style.SUCCESS(f'Processed player {first_name} {last_name}'))

		self.stdout.write(self.style.SUCCESS('Import completed successfully'))
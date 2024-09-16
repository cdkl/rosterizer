import json
from django.db import models

# Create your models here.
class Player(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    def __str__(self):
        return self.get_full_name()
    home_phone = models.CharField(max_length=20, blank=True, null=True)
    work_phone = models.CharField(max_length=20, blank=True, null=True)
    cell_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    gender = models.CharField(max_length=1, blank=True, null=True)

class Session(models.Model):
    year = models.IntegerField()
    session_number = models.IntegerField()
    players = models.ManyToManyField(Player)
    def __str__(self):
        return f'{self.year} - {self.session_number}'
    
class PlayerSession(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    years_curled = models.IntegerField()
    preferred_position1 = models.CharField(max_length=10)
    preferred_position2 = models.CharField(max_length=10)
    play_with = models.CharField(max_length=100)
    def __str__(self):
        return f'{self.player} - {self.session}'
    def to_dict(self):
        return {
            'player': {
                'id': self.player.id,
                'first_name': self.player.first_name,
                'last_name': self.player.last_name,
                'full_name': self.player.get_full_name(),
            },
            'session': {
                'id': self.session.id,
                'year': self.session.year,
                'session_number': self.session.session_number,
            },
            'years_curled': self.years_curled,
            'preferred_position1': self.preferred_position1,
            'preferred_position2': self.preferred_position2,
            'play_with': self.play_with,
        }

class PlayerSessionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PlayerSession):
            print(">>>>>" + str(obj.to_dict()) + "<<<<<")
            return obj.to_dict()
        return json.JSONEncoder.default(self, obj)

class PlayerSessionDecoder(json.JSONDecoder):
    def decode(self, s):
        player_session = super().decode(s)
        print(">>>>>" + str(player_session) + "<<<<<")
        return PlayerSession(**player_session)

class Team(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    team_number = models.IntegerField()
    skip = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='skip')
    vice = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='vice')
    second = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='second')
    lead = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='lead')
    def set_players_from_player_sessions(self, skip, vice, second, lead):
        self.skip = skip.player if skip else None
        self.vice = vice.player if vice else None
        self.second = second.player if second else None
        self.lead = lead.player if lead else None
    def to_dict(self):
        return {
            'team_number': self.team_number,
            'skip': self.skip.to_dict() if self.skip else None,
            'vice': self.vice.to_dict() if self.vice else None,
            'second': self.second.to_dict() if self.second else None,
            'lead': self.lead.to_dict() if self.lead else None,
        }


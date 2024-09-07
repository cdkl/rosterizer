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


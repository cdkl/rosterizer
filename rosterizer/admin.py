from django.contrib import admin

from .models import ConvenorPlayWith, Player, PlayerRule, PlayerSession, Session, Team, TeamResult


@admin.register(TeamResult)
class TeamResultAdmin(admin.ModelAdmin):
    list_display = ['session', 'team_number', 'record', 'points_for', 'points_against']
    list_filter = ['session__year']
    search_fields = ['skip__first_name', 'skip__last_name',
                     'vice__first_name', 'vice__last_name',
                     'second__first_name', 'second__last_name',
                     'lead__first_name', 'lead__last_name']
    ordering = ['session__year', 'session__session_number', 'team_number']

    @admin.display(description='Record')
    def record(self, obj):
        return f'{obj.wins}-{obj.losses}-{obj.ties}'


@admin.register(ConvenorPlayWith)
class ConvenorPlayWithAdmin(admin.ModelAdmin):
    list_display = ['session', 'player1', 'player2', 'created_at']
    list_filter = ['session']
    search_fields = ['player1__first_name', 'player1__last_name',
                     'player2__first_name', 'player2__last_name']
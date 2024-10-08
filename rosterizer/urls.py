from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('create_session/', views.create_session, name='create_session'),
    path('sessions/', views.session_list, name='session_list'),
    path('delete_session/<int:session_id>/', views.delete_session, name='delete_session'),
    path('import_players/<int:session_id>/', views.import_players, name='import_players'),
    path('players/', views.player_list, name='player_list'),
    path('clear_player_list/', views.clear_player_list, name='clear_player_list'),
    path('import_roster/<int:session_id>/', views.import_roster, name='import_roster'),
    path('session/<int:session_id>/teams/', views.team_list, name='team_list'),
    path('session/<int:session_id>/clear_teams/', views.clear_teams, name='clear_teams'),
    path('session/<int:session_id>/players/', views.players_in_session, name='players_in_session'),
    path('sessions/<int:session_id>/generate_teams_form/', views.generate_teams_form, name='generate_teams_form'),
    path('sessions/<int:session_id>/generate_teams/', views.generate_teams, name='generate_teams'),
    path('session/<int:session_id>/generate_multiple_rosters/', views.generate_multiple_rosters, name='generate_multiple_rosters'),
    path('session/<int:session_id>/roster_review/', views.roster_review, name='roster_review'),
    path('session/<int:session_id>/select_roster/', views.select_roster, name='select_roster'),
]

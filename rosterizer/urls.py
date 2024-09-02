from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('create_session/', views.create_session, name='create_session'),
    path('sessions/', views.session_list, name='session_list'),
    path('delete_session/<int:session_id>/', views.delete_session, name='delete_session'),
    path('import_players/<int:session_id>/', views.import_players, name='import_players'),
    path('players/', views.player_list, name='player_list'),
]

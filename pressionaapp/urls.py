from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('deputados/', views.deputados_list_view, name='deputados_list'),
    path('deputado/<int:deputado_id>/', views.deputado_detail_view, name='deputado_detail'),
    path('senadores/', views.senadores_list_view, name='senadores_list'),
    path('senador/<int:senador_id>/', views.senador_detail_view, name='senador_detail'),
    
    # Twitter Messages
    path('mensagens/', views.twitter_messages_list_view, name='twitter_messages_list'),
    path('twitter-message/<int:message_id>/preview/', views.twitter_message_preview, name='twitter_message_preview'),
    path('twitter-link/<int:message_id>/mark-used/', views.mark_message_used, name='mark_message_used'),
    
    # Turnstile bot protection
    path('verify-turnstile/', views.verify_turnstile_view, name='verify_turnstile'),
    path('turnstile-challenge/', views.turnstile_challenge_view, name='turnstile_challenge'),
]
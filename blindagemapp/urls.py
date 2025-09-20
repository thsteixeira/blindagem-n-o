from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('deputados/', views.deputados_list_view, name='deputados_list'),
    path('deputado/<int:deputado_id>/', views.deputado_detail_view, name='deputado_detail'),
    path('senadores/', views.senadores_list_view, name='senadores_list'),
    path('senador/<int:senador_id>/', views.senador_detail_view, name='senador_detail'),
]
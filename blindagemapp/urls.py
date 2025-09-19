from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('deputados/', views.deputados_list_view, name='deputados_list'),
    path('deputado/<int:deputado_id>/', views.deputado_detail_view, name='deputado_detail'),
]
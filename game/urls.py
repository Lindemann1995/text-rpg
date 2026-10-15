from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    path('start/', views.start_scene, name='start_scene'),
    path('scene/<slug:slug>/', views.get_scene, name='get_scene'),
]
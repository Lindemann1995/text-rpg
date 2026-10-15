from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

app_name = 'game'

urlpatterns = [
    # Сцены
    path('start/', views.start_scene, name='start_scene'),
    path('scene/current/', views.current_scene, name='current_scene'),    # ← ДО slug!
    path('scene/choose/', views.choose_in_scene, name='choose_in_scene'), # ← ДО slug!
    path('scene/<slug:slug>/', views.get_scene, name='get_scene'),        # ← В САМОМ КОНЦЕ
    
    # Аутентификация
    path('auth/register/', views.register, name='register'),
    path('auth/verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    
    # Игрок
    path('player/me/', views.me, name='me'),
    path('player/classes/', views.list_classes, name='list_classes'),
    path('player/choose-class/', views.choose_class, name='choose_class'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('friends/', views.get_friends_data, name='get_friends_data'),
    path('friends/request/', views.send_friend_request, name='send_friend_request'),
    path('friends/accept/', views.accept_friend_request, name='accept_friend_request'),
    path('friends/decline/', views.decline_friend_request, name='decline_friend_request'),
    path('messages/<str:username>/', views.get_private_messages, name='get_private_messages'),
    path('friends/remove/', views.remove_friend, name='remove_friend'),
]
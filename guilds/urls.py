from django.urls import path

from . import views

app_name = 'guilds'

urlpatterns = [
    path('my/', views.my_guild, name='my_guild'),
    path('create/', views.create_guild, name='create_guild'),
    path('list/', views.guild_list, name='guild_list'),
    path('<int:guild_id>/', views.guild_detail, name='guild_detail'),
    path('members/', views.guild_members, name='guild_members'),
    path('apply/', views.apply, name='apply'),
    path('invite/', views.invite, name='invite'),
    path('applications/', views.applications, name='applications'),
    path('applications/accept/', views.accept_application, name='accept_application'),
    path('applications/decline/', views.decline_application, name='decline_application'),
    path('kick/', views.kick, name='kick'),
    path('leave/', views.leave, name='leave'),
    path('promote/', views.promote, name='promote'),
    path('transfer-leader/', views.transfer_leader, name='transfer_leader'),
    path('treasury/deposit/', views.treasury_deposit, name='treasury_deposit'),
    path('treasury/withdraw/', views.treasury_withdraw, name='treasury_withdraw'),
    path('logs/', views.guild_logs, name='guild_logs'),
    path('chat/history/', views.chat_history, name='chat_history'),
    path('bank/items/', views.bank_items, name='bank_items'),
    path('bank/deposit/', views.bank_deposit, name='bank_deposit'),
    path('bank/withdraw/', views.bank_withdraw, name='bank_withdraw'),
    path('upgrades/', views.get_upgrades, name='get_upgrades'),
    path('upgrades/upgrade/', views.upgrade_building, name='upgrade_building'),
]
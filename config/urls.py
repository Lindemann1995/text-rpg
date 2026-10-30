from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.generic import TemplateView
from game.views import manage_roles, admin_dashboard, beautiful_dashboard, chat_moderation
from game.admin import custom_admin_site

def health(request):
    return JsonResponse({
        'status': 'ok',
        'project': 'Тень Древних',
        'env': 'prod'
    })


urlpatterns = [
     path('privacy/', TemplateView.as_view(template_name='privacy.html'), name='privacy_policy'),
    path('admin/manage-roles/', manage_roles, name='manage_roles'),
    path('dashboard/', beautiful_dashboard, name='beautiful_dashboard'),
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/chat-moderation/', chat_moderation, name='chat_moderation'),
    path('admin/', custom_admin_site.urls),
    path('api/health/', health),
    path('api/game/', include('game.urls')),
    path('api/guilds/', include('guilds.urls')),
    path('api/social/', include('social.urls')),
]
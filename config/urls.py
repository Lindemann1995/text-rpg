from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse



def health(request):
    return JsonResponse({
        'status': 'ok',
        'project': 'Тень Древних',
        'env': 'prod'
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health),
    path('api/game/', include('game.urls')),
    path('api/guilds/', include('guilds.urls')),
    path('api/social/', include('social.urls')),
]
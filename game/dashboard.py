from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from game.models import Player
from guilds.models import Guild

def dashboard_callback(request, context):
    now = timezone.now()
    yesterday = now - timedelta(days=1)
    
    # Собираем статистику
    total_players = Player.objects.count()
    new_players = Player.objects.filter(created_at__gte=yesterday).count()
    total_gold = Player.objects.aggregate(total=Sum('gold'))['total'] or 0
    total_guilds = Guild.objects.count()

    # Формируем список карточек для Unfold
    context.update({
        "cards": [
            {
                "title": "Всего игроков",
                "metric": total_players,
                "footer": f"+{new_players} за сутки",
            },
            {
                "title": "Золото в мире",
                "metric": f"{total_gold:,}",
                "footer": "Общая экономика",
            },
            {
                "title": "Гильдии",
                "metric": total_guilds,
                "footer": "Активные союзы",
            },
        ],
    })
    return context
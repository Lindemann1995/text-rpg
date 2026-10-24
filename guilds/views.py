from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from . import services
from django.utils import timezone
from .models import (
    Guild, GuildMember, GuildApplication, GuildLog,
    GuildChatMessage, GuildUpgrade, GuildUpgradeTemplate,
    GuildUpgradeLevelCost, GuildUISettings, Duel,
    GuildDailyQuest, GuildDailyQuestTemplate, GuildDailyQuestContribution, Castle, CastleSiege, GuildBankItem, GuildBankLog,
)
from .services import get_guild, generate_daily_quests_for_guild, claim_daily_quest_reward
from .serializers import (
    GuildSerializer, GuildMemberSerializer, GuildApplicationSerializer,
    GuildLogSerializer, GuildChatMessageSerializer, GuildBankItemSerializer, GuildBankLogSerializer, 
)


def _err(msg, code=400):
    return Response({'error': msg}, status=code)


@api_view(['GET'])
def my_guild(request):
    """Инфо о моей гильдии + права."""
    player = request.user.player
    info = services.get_player_guild_info(player)
    return Response(info)


@api_view(['POST'])
def create_guild(request):
    name = (request.data.get('name') or '').strip()
    tag = (request.data.get('tag') or '').strip().upper()
    if not name or not tag:
        return _err('Укажи название и тег.')
    if len(name) > 20:
        return _err('Название до 20 символов.')
    if len(tag) > 5:
        return _err('Тег до 5 символов.')
    try:
        guild = services.create_guild(request.user.player, name, tag)
    except ValueError as e:
        return _err(str(e))
    return Response(GuildSerializer(guild).data)


@api_view(['GET'])
def guild_list(request):
    """Список гильдий (для вступления)."""
    guilds = Guild.objects.all().order_by('-level', '-created_at')
    return Response(GuildSerializer(guilds, many=True).data)


@api_view(['GET'])
def guild_detail(request, guild_id):
    g = Guild.objects.filter(id=guild_id).first()
    if not g:
        return _err('Гильдия не найдена.', 404)
    return Response(GuildSerializer(g).data)


@api_view(['GET'])
def guild_members(request):
    player = request.user.player
    guild = services.get_guild(player)
    if not guild:
        return _err('Ты не в гильдии.')
    members = guild.members.select_related('player__user').all()
    return Response(GuildMemberSerializer(members, many=True).data)


@api_view(['POST'])
def apply(request):
    guild_id = request.data.get('guild_id')
    if not guild_id:
        return _err('Не указан guild_id.')
    try:
        services.apply_to_guild(request.user.player, int(guild_id))
    except ValueError as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def invite(request):
    from game.models import Player
    username = (request.data.get('username') or '').strip()
    if not username:
        return _err('Укажи username.')
    target = Player.objects.filter(user__username=username).first()
    if not target:
        return _err('Игрок не найден.', 404)
    try:
        services.invite_player(request.user.player, target)
    except ValueError as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['GET'])
def applications(request):
    player = request.user.player
    guild = services.get_guild(player)
    if not guild:
        return _err('Ты не в гильдии.')
    if not services.can(player, 'accept_members'):
        return _err('Недостаточно прав.', 403)
    apps = guild.applications.filter(status='pending').select_related('player__user')
    return Response(GuildApplicationSerializer(apps, many=True).data)


@api_view(['POST'])
def accept_application(request):
    app_id = request.data.get('application_id')
    try:
        services.accept_application(request.user.player, int(app_id))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def decline_application(request):
    app_id = request.data.get('application_id')
    try:
        services.decline_application(request.user.player, int(app_id))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def kick(request):
    pid = request.data.get('player_id')
    try:
        services.kick_member(request.user.player, int(pid))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def leave(request):
    try:
        services.leave_guild(request.user.player)
    except ValueError as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def promote(request):
    pid = request.data.get('player_id')
    rank = request.data.get('rank')
    try:
        services.promote(request.user.player, int(pid), rank)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def transfer_leader(request):
    pid = request.data.get('player_id')
    try:
        services.transfer_leadership(request.user.player, int(pid))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def treasury_deposit(request):
    amount = request.data.get('amount')
    try:
        services.deposit_gold(request.user.player, int(amount))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['POST'])
def treasury_withdraw(request):
    amount = request.data.get('amount')
    try:
        services.withdraw_gold(request.user.player, int(amount))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['GET'])
def guild_logs(request):
    player = request.user.player
    guild = services.get_guild(player)
    if not guild:
        return _err('Ты не в гильдии.')
    logs = guild.logs.select_related('actor__user').all()[:50]
    return Response(GuildLogSerializer(logs, many=True).data)


@api_view(['GET'])
def chat_history(request):
    player = request.user.player
    guild = services.get_guild(player)
    if not guild:
        return _err('Ты не в гильдии.')
    msgs = guild.chat_messages.select_related('player__user').all()[:50]
    return Response(GuildChatMessageSerializer(msgs, many=True).data)

@api_view(['GET'])
def bank_items(request):
    """Список ресурсов в банке."""
    player = request.user.player
    guild = services.get_guild(player)
    if not guild:
        return _err('Ты не в гильдии.')
    
    items = GuildBankItem.objects.filter(guild=guild).select_related('item')
    return Response(GuildBankItemSerializer(items, many=True).data)

@api_view(['POST'])
def bank_deposit(request):
    """Положить ресурс в банк."""
    item_slug = request.data.get('item_slug')
    amount = request.data.get('amount')
    try:
        services.deposit_resource(request.user.player, item_slug, int(amount))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})

@api_view(['POST'])
def bank_withdraw(request):
    """Забрать ресурс из банка (только лидер/зам)."""
    item_slug = request.data.get('item_slug')
    amount = request.data.get('amount')
    try:
        services.withdraw_resource(request.user.player, item_slug, int(amount))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})


@api_view(['GET'])
def get_upgrades(request):
    player = request.user.player
    return Response(services.get_guild_upgrades(player))

@api_view(['POST'])
def upgrade_building(request):
    upgrade_type = request.data.get('upgrade_type')
    try:
        services.upgrade_guild_upgrade(request.user.player, upgrade_type)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})

@api_view(['POST'])
def siege_action_view(request):
    siege_id = request.data.get('siege_id')
    action = request.data.get('action')  # 'attack', 'defend', 'flee'
    try:
        result = services.siege_action(request.user.player, int(siege_id), action)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response(result)

@api_view(['GET'])
def castle_list(request):
    """Список всех замков (для карты)."""
    castles = Castle.objects.all().select_related('owner')
    result = []
    for c in castles:
        result.append({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'image_path': c.image_path,
            'map_x': c.map_x,
            'map_y': c.map_y,
            'owner': c.owner.tag if c.owner else None,
            'owner_id': c.owner.id if c.owner else None,
            'defense_level': c.defense_level,
            'buff_xp_percent': c.buff_xp_percent,
            'buff_gold_percent': c.buff_gold_percent,
            'siege_cooldown_until': c.siege_cooldown_until.isoformat() if c.siege_cooldown_until else None,
        })
    return Response(result)

@api_view(['GET'])
def castle_detail(request, castle_id):
    castle = Castle.objects.filter(id=castle_id).first()
    if not castle:
        return _err('Замок не найден.', 404)
    
    return Response({
        'id': castle.id,
        'name': castle.name,
        'slug': castle.slug,
        'description': castle.description,
        'image_path': castle.image_path,
        'map_x': castle.map_x,
        'map_y': castle.map_y,
        'owner': castle.owner.tag if castle.owner else None,
        'owner_id': castle.owner.id if castle.owner else None,
        'daily_tax': castle.daily_tax,
        'passive_income': castle.passive_income,
        'defense_level': castle.defense_level,
        'buff_xp_percent': castle.buff_xp_percent,
        'buff_gold_percent': castle.buff_gold_percent,
        'is_under_siege': CastleSiege.objects.filter(castle=castle, status='active').exists(),
        'siege_cooldown_until': castle.siege_cooldown_until.isoformat() if castle.siege_cooldown_until else None,
    })

@api_view(['POST'])
def siege_start(request):
    castle_id = request.data.get('castle_id')
    try:
        siege = services.start_castle_siege(request.user.player, int(castle_id))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True, 'siege_id': siege.id})

@api_view(['POST'])
def siege_action_view(request):
    siege_id = request.data.get('siege_id')
    action = request.data.get('action')
    try:
        result = services.siege_action(request.user.player, int(siege_id), action)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response(result)

@api_view(['POST'])
def collect_taxes(request):
    try:
        result = services.collect_castle_taxes(request.user.player)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response(result)

@api_view(['GET'])
def get_ui_settings(request):
    settings = GuildUISettings.objects.first()
    if not settings:
        # Если настроек нет — создаем дефолтные
        settings = GuildUISettings.objects.create()
    return Response({
        'icon_taxes': settings.icon_taxes,
        'icon_bank': settings.icon_bank,
        'icon_war': settings.icon_war,
        'icon_members': settings.icon_members,
        'icon_chat': settings.icon_chat,
        'icon_castle': settings.icon_castle,
        'icon_applications': settings.icon_applications,
    })


@api_view(['POST'])
def challenge_duel_view(request):
    username = request.data.get('username')
    try:
        duel = services.challenge_duel(request.user.player, username)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True, 'duel_id': duel.id})

@api_view(['POST'])
def accept_duel_view(request):
    duel_id = request.data.get('duel_id')
    try:
        services.accept_duel(request.user.player, int(duel_id))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})

@api_view(['POST'])
def decline_duel_view(request):
    duel_id = request.data.get('duel_id')
    try:
        services.decline_duel(request.user.player, int(duel_id))
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response({'ok': True})

@api_view(['POST'])
def duel_action_view(request):
    duel_id = request.data.get('duel_id')
    action = request.data.get('action')
    try:
        result = services.duel_action(request.user.player, int(duel_id), action)
    except (ValueError, TypeError) as e:
        return _err(str(e))
    return Response(result)

@api_view(['GET'])
def active_duels_view(request):
    return Response(services.get_active_duels(request.user.player))


@api_view(['GET'])
def duel_status(request, duel_id):
    duel = Duel.objects.select_related('challenger__user', 'opponent__user', 'winner__user').filter(id=duel_id).first()
    if not duel:
        return _err('Дуэль не найдена.', 404)
    
    return Response({
        'id': duel.id,
        'status': duel.status,
        'challenger_hp': duel.challenger_hp,
        'opponent_hp': duel.opponent_hp,
        'current_turn': duel.current_turn,
        'winner': duel.winner.user.username if duel.winner else None,
        'log': duel.log[-5:],
    })

@api_view(['GET'])
def get_daily_quests(request):
    player = request.user.player
    guild = get_guild(player)
    if not guild:
        return Response({'error': 'Ты не в гильдии'}, status=400)

    today = timezone.now().date()
    # На всякий случай генерируем, если вдруг крон не сработал
    from .services import generate_daily_quests_for_guild
    generate_daily_quests_for_guild(guild, today)

    quests = GuildDailyQuest.objects.filter(guild=guild, date=today).select_related('template')
    
    data = []
    for q in quests:
        contrib = GuildDailyQuestContribution.objects.filter(daily_quest=q, player=player).first()
        data.append({
            'id': q.id,
            'title': q.template.title,
            'description': q.template.description,
            'image_path': q.template.image_path,
            'required_count': q.template.required_count,
            'progress': q.progress,
            'is_completed': q.is_completed,
            'my_kills': contrib.kills if contrib else 0,
            'is_claimed': contrib.is_claimed if contrib else False,
            'reward_gold': q.template.reward_gold_player,
            'reward_exp': q.template.reward_exp,
        })

    return Response({
        'streak': guild.daily_streak,
        'quests': data
    })

@api_view(['POST'])
def claim_daily_quest(request, quest_id):
    try:
        from .services import claim_daily_quest_reward
        tmpl = claim_daily_quest_reward(request.user.player, quest_id)
        return Response({
            'message': f'Награда за "{tmpl.title}" получена!',
            'gold': tmpl.reward_gold_player,
            'exp': tmpl.reward_exp
        })
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
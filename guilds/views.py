from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import (
    Guild, GuildMember, GuildApplication, GuildLog, GuildChatMessage, GuildBankItem, GuildBankLog,
)

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
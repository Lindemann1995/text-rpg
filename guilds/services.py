"""
Бизнес-логика гильдий.
"""
from django.db import transaction

from game.models import Player, Item, Inventory

from .models import (
    Guild, GuildMember, GuildRank, GuildApplication, GuildLog,
    GuildUpgrade, GuildUpgradeTemplate, GuildUpgradeLevelCost,
    GuildBankItem, GuildBankLog,
)

# Константы
GUILD_SCROLL_SLUG = 'guild_foundation_scroll'
GUILD_CREATE_LEVEL = 8
GUILD_CREATE_COST = 20000
GUILD_MAX_MEMBERS = 30

RANK_PERMISSIONS = {
    'manage_guild':      {GuildRank.LEADER},
    'accept_members':    {GuildRank.LEADER, GuildRank.DEPUTY},
    'kick_members':      {GuildRank.LEADER, GuildRank.DEPUTY},
    'manage_upgrades':   {GuildRank.LEADER, GuildRank.DEPUTY},
    'manage_treasury':   {GuildRank.LEADER, GuildRank.DEPUTY},
    'deposit_treasury':  {GuildRank.LEADER, GuildRank.DEPUTY, GuildRank.VETERAN, GuildRank.NOVICE},
    'invite_players':    {GuildRank.LEADER, GuildRank.DEPUTY, GuildRank.VETERAN},
    'promote_members':   {GuildRank.LEADER, GuildRank.DEPUTY},
    'manage_ranks':      {GuildRank.LEADER},
    'use_sparring':      {GuildRank.LEADER, GuildRank.DEPUTY, GuildRank.VETERAN, GuildRank.NOVICE},
}


def _log(guild, actor, action, details=''):
    GuildLog.objects.create(guild=guild, actor=actor, action=action, details=details)


def get_membership(player: Player):
    return GuildMember.objects.select_related('guild').filter(player=player).first()


def get_guild(player: Player):
    m = get_membership(player)
    return m.guild if m else None


def can(player: Player, action: str) -> bool:
    m = get_membership(player)
    if not m:
        return False
    allowed = RANK_PERMISSIONS.get(action, set())
    return m.rank in allowed


def get_player_guild_info(player: Player) -> dict:
    m = get_membership(player)
    if not m:
        return {'in_guild': False}

    g = m.guild
    return {
        'in_guild': True,
        'guild_id': g.id,
        'name': g.name,
        'tag': g.tag,
        'rank': m.rank,
        'rank_display': m.get_rank_display(),
        'rank_color': m.rank_color,
        'treasury_gold': g.treasury_gold,
        'members_count': g.members.count(),
        'is_leader': m.rank == GuildRank.LEADER,
        'username': player.user.username,
        'permissions': {
            action: m.rank in ranks
            for action, ranks in RANK_PERMISSIONS.items()
        },
    }


@transaction.atomic
def create_guild(player: Player, name: str, tag: str) -> Guild:
    if get_membership(player):
        raise ValueError('Ты уже состоишь в гильдии.')
    if player.level < GUILD_CREATE_LEVEL:
        raise ValueError(f'Нужен {GUILD_CREATE_LEVEL}+ уровень.')
    if player.gold < GUILD_CREATE_COST:
        raise ValueError(f'Нужно {GUILD_CREATE_COST} золота.')
    if Guild.objects.filter(tag=tag).exists():
        raise ValueError('Такой тег уже занят.')
    if Guild.objects.filter(name=name).exists():
        raise ValueError('Гильдия с таким названием уже существует.')

    scroll = Item.objects.filter(slug=GUILD_SCROLL_SLUG).first()
    if not scroll:
        raise ValueError('Свиток основания не настроен.')
    inv = Inventory.objects.filter(player=player, item=scroll).first()
    if not inv or inv.quantity < 1:
        raise ValueError('Нет «Свитка основания гильдии» в инвентаре.')

    player.gold -= GUILD_CREATE_COST
    player.save(update_fields=['gold'])

    inv.quantity -= 1
    if inv.quantity <= 0:
        inv.delete()
    else:
        inv.save(update_fields=['quantity'])

    guild = Guild.objects.create(
        name=name, tag=tag, leader=player, treasury_gold=GUILD_CREATE_COST,
    )
    GuildMember.objects.create(guild=guild, player=player, rank=GuildRank.LEADER)

    player.role = 'guild_leader'
    player.save(update_fields=['role'])

    _log(guild, player, 'create', f'Гильдия «{name}» [{tag}] основана')

    # Создаем прогресс для всех существующих шаблонов
    for tmpl in GuildUpgradeTemplate.objects.all():
        GuildUpgrade.objects.get_or_create(guild=guild, template=tmpl, defaults={'level': 0})

    return guild


def invite_player(actor: Player, target: Player):
    if not can(actor, 'invite_players'):
        raise ValueError('Недостаточно прав для приглашения.')
    if get_membership(target):
        raise ValueError('Игрок уже в гильдии.')

    guild = get_guild(actor)
    if guild.members.count() >= GUILD_MAX_MEMBERS:
        raise ValueError('Гильдия заполнена.')

    app, created = GuildApplication.objects.get_or_create(
        guild=guild, player=target, status='pending',
    )
    if not created:
        raise ValueError('Заявка уже существует.')

    _log(guild, actor, 'invite', f'Приглашён {target.user.username}')
    return app


def apply_to_guild(player: Player, guild_id: int):
    if get_membership(player):
        raise ValueError('Ты уже в гильдии.')
    guild = Guild.objects.filter(id=guild_id).first()
    if not guild:
        raise ValueError('Гильдия не найдена.')
    if not guild.is_open:
        raise ValueError('Гильдия закрыта для заявок.')
    if guild.members.count() >= GUILD_MAX_MEMBERS:
        raise ValueError('Гильдия заполнена.')

    app, created = GuildApplication.objects.get_or_create(
        guild=guild, player=player, status='pending',
    )
    if not created:
        raise ValueError('Заявка уже подана.')
    return app


@transaction.atomic
def accept_application(actor: Player, application_id: int):
    if not can(actor, 'accept_members'):
        raise ValueError('Недостаточно прав.')
    app = GuildApplication.objects.select_related('guild', 'player').filter(
        id=application_id, status='pending',
    ).first()
    if not app:
        raise ValueError('Заявка не найдена.')
    if app.guild != get_guild(actor):
        raise ValueError('Это заявка в другую гильдию.')
    if app.guild.members.count() >= GUILD_MAX_MEMBERS:
        raise ValueError('Гильдия заполнена.')
    if get_membership(app.player):
        raise ValueError('Игрок уже в другой гильдии.')

    GuildMember.objects.create(guild=app.guild, player=app.player, rank=GuildRank.NOVICE)
    app.status = 'accepted'
    app.save(update_fields=['status'])
    _log(app.guild, actor, 'accept', f'Принят {app.player.user.username}')
    return app


def decline_application(actor: Player, application_id: int):
    if not can(actor, 'accept_members'):
        raise ValueError('Недостаточно прав.')
    app = GuildApplication.objects.filter(
        id=application_id, status='pending', guild=get_guild(actor),
    ).first()
    if not app:
        raise ValueError('Заявка не найдена.')
    app.status = 'declined'
    app.save(update_fields=['status'])
    _log(app.guild, actor, 'decline', f'Отклонён {app.player.user.username}')
    return app


@transaction.atomic
def kick_member(actor: Player, target_player_id: int):
    if not can(actor, 'kick_members'):
        raise ValueError('Недостаточно прав.')
    guild = get_guild(actor)
    target_m = GuildMember.objects.select_related('player', 'guild').filter(
        guild=guild, player_id=target_player_id,
    ).first()
    if not target_m:
        raise ValueError('Участник не найден.')
    if target_m.rank == GuildRank.LEADER:
        raise ValueError('Нельзя исключить лидера.')
    target_m.delete()
    _log(guild, actor, 'kick', f'Исключён {target_m.player.user.username}')
    return target_m.player


@transaction.atomic
def leave_guild(player: Player):
    m = get_membership(player)
    if not m:
        raise ValueError('Ты не в гильдии.')
    if m.rank == GuildRank.LEADER:
        raise ValueError('Лидер не может выйти.')
    guild = m.guild
    m.delete()
    if player.role == 'guild_leader':
        player.role = 'player'
        player.save(update_fields=['role'])
    _log(guild, player, 'leave', f'Вышел {player.user.username}')


@transaction.atomic
def promote(actor: Player, target_player_id: int, new_rank: str):
    if not can(actor, 'promote_members'):
        raise ValueError('Недостаточно прав.')
    if new_rank not in GuildRank.values:
        raise ValueError('Неверный ранг.')
    if new_rank == GuildRank.LEADER:
        raise ValueError('Для передачи лидерства используй отдельный метод.')

    guild = get_guild(actor)
    target_m = GuildMember.objects.filter(guild=guild, player_id=target_player_id).first()
    if not target_m:
        raise ValueError('Участник не найден.')
    if target_m.rank == GuildRank.LEADER:
        raise ValueError('Нельзя изменить ранг лидера.')
    if new_rank == GuildRank.DEPUTY and actor != guild.leader:
        raise ValueError('Назначать заместителей может только лидер.')
    if new_rank == GuildRank.DEPUTY:
        deputies = GuildMember.objects.filter(guild=guild, rank=GuildRank.DEPUTY).count()
        if deputies >= 3:
            raise ValueError('Заместителей уже 3.')

    old = target_m.rank
    target_m.rank = new_rank
    target_m.save(update_fields=['rank'])
    _log(guild, actor, 'promote', f'{target_m.player.user.username}: {old} → {new_rank}')
    return target_m


@transaction.atomic
def transfer_leadership(actor: Player, target_player_id: int):
    if not can(actor, 'manage_guild'):
        raise ValueError('Только лидер может передать лидерство.')
    guild = get_guild(actor)
    target_m = GuildMember.objects.filter(guild=guild, player_id=target_player_id).first()
    if not target_m:
        raise ValueError('Участник не найден.')
    if target_m.player_id == actor.id:
        raise ValueError('Ты уже лидер.')

    actor_m = get_membership(actor)
    actor_m.rank = GuildRank.DEPUTY
    actor_m.save(update_fields=['rank'])

    target_m.rank = GuildRank.LEADER
    target_m.save(update_fields=['rank'])

    guild.leader = target_m.player
    guild.save(update_fields=['leader'])

    actor.role = 'player'
    actor.save(update_fields=['role'])
    target_m.player.role = 'guild_leader'
    target_m.player.save(update_fields=['role'])

    _log(guild, actor, 'transfer', f'Лидерство передано {target_m.player.user.username}')


@transaction.atomic
def deposit_gold(player: Player, amount: int):
    if amount <= 0:
        raise ValueError('Сумма должна быть больше 0.')
    if not can(player, 'deposit_treasury'):
        raise ValueError('Недостаточно прав.')
    m = get_membership(player)
    if player.gold < amount:
        raise ValueError('Недостаточно золота.')

    player.gold -= amount
    player.save(update_fields=['gold'])

    guild = m.guild
    guild.treasury_gold += amount
    guild.save(update_fields=['treasury_gold'])

    m.contributed_gold += amount
    m.save(update_fields=['contributed_gold'])

    _log(guild, player, 'deposit', f'+{amount} золота в казну')


@transaction.atomic
def withdraw_gold(player: Player, amount: int):
    if amount <= 0:
        raise ValueError('Сумма должна быть больше 0.')
    if not can(player, 'manage_treasury'):
        raise ValueError('Выводить золото могут только лидер и замы.')
    guild = get_guild(player)
    if guild.treasury_gold < amount:
        raise ValueError('В казне недостаточно золота.')

    guild.treasury_gold -= amount
    guild.save(update_fields=['treasury_gold'])

    player.gold += amount
    player.save(update_fields=['gold'])

    _log(guild, player, 'withdraw', f'-{amount} золота из казны')


@transaction.atomic
def deposit_resource(player: Player, item_slug: str, amount: int):
    if amount <= 0:
        raise ValueError('Количество должно быть больше 0.')
    m = get_membership(player)
    if not m:
        raise ValueError('Ты не в гильдии.')
    guild = m.guild
    try:
        item = Item.objects.get(slug=item_slug)
    except Item.DoesNotExist:
        raise ValueError('Предмет не найден.')

    inv = Inventory.objects.filter(player=player, item=item).first()
    if not inv or inv.quantity < amount:
        raise ValueError('Недостаточно этого предмета в инвентаре.')

    inv.quantity -= amount
    if inv.quantity <= 0:
        inv.delete()
    else:
        inv.save(update_fields=['quantity'])

    bank_item, _ = GuildBankItem.objects.get_or_create(guild=guild, item=item, defaults={'quantity': 0})
    bank_item.quantity += amount
    bank_item.save(update_fields=['quantity'])

    GuildBankLog.objects.create(guild=guild, player=player, item=item, quantity=amount, action='deposit')
    _log(guild, player, 'bank_deposit', f'Положил {item.name} x{amount} в банк')
    return bank_item


@transaction.atomic
def withdraw_resource(player: Player, item_slug: str, amount: int):
    if amount <= 0:
        raise ValueError('Количество должно быть больше 0.')
    m = get_membership(player)
    if not m:
        raise ValueError('Ты не в гильдии.')
    if m.rank not in [GuildRank.LEADER, GuildRank.DEPUTY]:
        raise ValueError('Только лидер и замы могут забирать ресурсы из банка.')
    guild = m.guild
    try:
        item = Item.objects.get(slug=item_slug)
    except Item.DoesNotExist:
        raise ValueError('Предмет не найден.')

    bank_item = GuildBankItem.objects.filter(guild=guild, item=item).first()
    if not bank_item or bank_item.quantity < amount:
        raise ValueError('В банке недостаточно этого ресурса.')

    bank_item.quantity -= amount
    if bank_item.quantity <= 0:
        bank_item.delete()
    else:
        bank_item.save(update_fields=['quantity'])

    inv, _ = Inventory.objects.get_or_create(player=player, item=item, defaults={'quantity': 0})
    inv.quantity += amount
    inv.save(update_fields=['quantity'])

    GuildBankLog.objects.create(guild=guild, player=player, item=item, quantity=amount, action='withdraw')
    _log(guild, player, 'bank_withdraw', f'Забрал {item.name} x{amount} из банка')
    return inv


# --- УЛУЧШЕНИЯ ---

@transaction.atomic
def upgrade_guild_upgrade(player: Player, upgrade_type: str):
    if not can(player, 'manage_upgrades'):
        raise ValueError('Только лидер и замы могут улучшать гильдию.')

    guild = get_guild(player)
    template = GuildUpgradeTemplate.objects.filter(upgrade_type=upgrade_type).first()
    if not template:
        raise ValueError('Шаблон улучшения не найден.')

    upgrade, _ = GuildUpgrade.objects.get_or_create(guild=guild, template=template, defaults={'level': 0})
    if upgrade.level >= 3:
        raise ValueError('Максимальный уровень уже достигнут.')

    cost = GuildUpgradeLevelCost.objects.filter(template=template, target_level=upgrade.level + 1).first()
    if not cost:
        raise ValueError('Стоимость для этого уровня еще не настроена админом.')

    if guild.treasury_gold < cost.gold_cost:
        raise ValueError(f'Недостаточно золота в казне. Нужно {cost.gold_cost}.')

    bank_item = None
    if cost.item:
        bank_item = GuildBankItem.objects.filter(guild=guild, item=cost.item).first()
        if not bank_item or bank_item.quantity < cost.quantity:
            current = bank_item.quantity if bank_item else 0
            raise ValueError(f'Недостаточно ресурса «{cost.item.name}» в банке. Нужно {cost.quantity}, у тебя {current}.')

    guild.treasury_gold -= cost.gold_cost
    guild.save(update_fields=['treasury_gold'])

    if bank_item:
        bank_item.quantity -= cost.quantity
        if bank_item.quantity <= 0:
            bank_item.delete()
        else:
            bank_item.save(update_fields=['quantity'])

    upgrade.level += 1
    upgrade.save(update_fields=['level'])

    _log(guild, player, 'upgrade', f'{template.name} улучшено до ур.{upgrade.level}')
    return upgrade


def get_guild_upgrades(player: Player):
    guild = get_guild(player)
    if not guild:
        return []

    templates = GuildUpgradeTemplate.objects.all().order_by('upgrade_type')
    result = []

    for tmpl in templates:
        upgrade, _ = GuildUpgrade.objects.get_or_create(guild=guild, template=tmpl, defaults={'level': 0})
        cost = GuildUpgradeLevelCost.objects.filter(template=tmpl, target_level=upgrade.level + 1).first()

        next_cost = None
        if cost:
            next_cost = {
                'gold': cost.gold_cost,
                'item_name': cost.item.name if cost.item else None,
                'item_image': cost.item.image_path if cost.item else None,
                'item_slug': cost.item.slug if cost.item else None,
                'quantity': cost.quantity,
                'quantity': cost.quantity if cost.item else 0,
                'item_description': cost.item.description if cost.item else '',
            }

        result.append({
            'type': tmpl.upgrade_type,
            'name': tmpl.name,
            'description': tmpl.description,
            'icon': tmpl.icon,
            'level': upgrade.level,
            'next_level_cost': next_cost,
        })
    return result

def get_guild_bonuses(player: Player) -> dict:
    """
    Вычисляет баффы от улучшений гильдии для конкретного игрока.
    Возвращает множители (например, 1.05 = +5%).
    """
    # Базовые значения (без гильдии)
    bonuses = {
        'xp_multiplier': 1.0,
        'gold_multiplier': 1.0,
        'loot_multiplier': 1.0,
        'strength_multiplier': 1.0,
        'hp_multiplier': 1.0,
        'mp_multiplier': 1.0,
    }

    guild = get_guild(player)
    if not guild:
        return bonuses

    # Получаем все прокачанные улучшения гильдии
    upgrades = GuildUpgrade.objects.filter(guild=guild).select_related('template')
    levels = {up.template.upgrade_type: up.level for up in upgrades}

    # 1. Зал воинов (опыт)
    war_hall_lvl = levels.get('war_hall', 0)
    if war_hall_lvl > 0:
        bonuses['xp_multiplier'] += 0.05 * war_hall_lvl

    # 2. Сокровищница (золото)
    treasury_lvl = levels.get('treasury', 0)
    if treasury_lvl > 0:
        bonuses['gold_multiplier'] += 0.05 * treasury_lvl

    # 3. Алтарь силы (урон)
    altar_lvl = levels.get('altar', 0)
    if altar_lvl > 0:
        bonuses['strength_multiplier'] += 0.02 * altar_lvl

    # 4. Библиотека (опыт навыков) - пока не используется в combat.py, но пусть будет
    # library_lvl = levels.get('library', 0)
    # if library_lvl > 0:
    #     bonuses['skill_xp_multiplier'] = 1.0 + (0.05 * library_lvl)

    # 5. Казарма (макс HP)
    barracks_lvl = levels.get('barracks', 0)
    if barracks_lvl > 0:
        bonuses['hp_multiplier'] += 0.05 * barracks_lvl

    # 6. Магический круг (макс MP)
    magic_circle_lvl = levels.get('magic_circle', 0)
    if magic_circle_lvl > 0:
        bonuses['mp_multiplier'] += 0.05 * magic_circle_lvl

    # 7. Кузница (шанс лута)
    forge_lvl = levels.get('forge', 0)
    if forge_lvl > 0:
        bonuses['loot_multiplier'] += 0.02 * forge_lvl

    return bonuses
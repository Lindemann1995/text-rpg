"""
Бизнес-логика гильдий.
"""
from django.db import transaction
import random
import zlib
from datetime import timedelta
from django.db.models import Q
from game.models import Player, Item, Inventory, Location
from django.utils import timezone
from .models import (
    Guild, GuildMember, GuildRank, GuildApplication, GuildLog,
    GuildUpgrade, GuildUpgradeTemplate, GuildUpgradeLevelCost,
    GuildBankItem, GuildBankLog, Castle, CastleSiege, SiegeEnemy, Duel,
    GuildDailyQuest, GuildDailyQuestTemplate, GuildDailyQuestContribution,
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
        'castles_count': g.castles.count(),
        'castle_buff_xp': g.castles.first().buff_xp_percent if g.castles.exists() else 0,
        'castle_buff_gold': g.castles.first().buff_gold_percent if g.castles.exists() else 0,
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

        # 🆕 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ГИЛЬДЕЙСКОЙ ЛОКАЦИИ (безопасно)
    try:
        from game.models import Location
        Location.objects.create(
            name=f"Земли гильдии [{tag}]",
            slug=f"guild_land_{guild.id}",
            description=f"Личная территория гильдии {name}. Здесь вы можете охотиться и развиваться.",
            location_type="farm",
            min_level=1,
            is_available=True,
            is_guild_only=True,
            guild=guild,
        )
    except Exception as e:

            # Если локация не создалась, мы просто пишем в консоль, но гильдию не откатываем
            print(f"!!! ОШИБКА СОЗДАНИЯ ЛОКАЦИИ ДЛЯ ГИЛЬДИИ: {e}")

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

    # 🆕 ИЩЕМ СУЩЕСТВУЮЩУЮ ЗАЯВКУ (любую, даже принятую или отклоненную)
    app = GuildApplication.objects.filter(guild=guild, player=player).first()
    
    if app:
        # Если заявка уже висит в ожидании — ругаемся
        if app.status == 'pending':
            raise ValueError('Заявка уже подана.')
        
        # Если заявка была принята или отклонена — просто обновляем её статус обратно на "ожидает"
        app.status = 'pending'
        app.save(update_fields=['status'])
        return app
    else:
        # Если заявки вообще не было — создаем новую
        app = GuildApplication.objects.create(
            guild=guild, player=player, status='pending',
        )
        return app


@transaction.atomic
def accept_application(actor: Player, application_id: int):
    if not can(actor, 'accept_members'):
        raise ValueError('Недостаточно прав.')
    
    app = GuildApplication.objects.select_related('guild', 'player').filter(
        id=application_id, 
        guild=get_guild(actor)
    ).first()
    
    if not app:
        raise ValueError('Заявка не найдена.')
        
    # 🆕 ПРОВЕРКА: Если заявка уже принята или отклонена
    if app.status != 'pending':
        raise ValueError('Эта заявка уже обработана (принята или отклонена).')
        
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
        # 7. Кузница (шанс лута)
    forge_lvl = levels.get('forge', 0)
    if forge_lvl > 0:
        bonuses['loot_multiplier'] += 0.02 * forge_lvl

    # 8. Замок гильдии (уникальные баффы владельца)
    castle = Castle.objects.filter(owner=guild).first()
    if castle:
        if castle.buff_xp_percent > 0:
            bonuses['xp_multiplier'] += (castle.buff_xp_percent / 100.0)
        if castle.buff_gold_percent > 0:
            bonuses['gold_multiplier'] += (castle.buff_gold_percent / 100.0)

    return bonuses

@transaction.atomic
def start_castle_siege(player: Player, castle_id: int):
    """Начинает PvE-осаду свободного замка (создает врагов)."""
    if not can(player, 'manage_guild'):
        raise ValueError('Только лидер гильдии может объявить осаду.')
    
    guild = get_guild(player)
    if not guild:
        raise ValueError('Ты не в гильдии.')
    
    castle = Castle.objects.filter(id=castle_id).first()
    if not castle:
        raise ValueError('Замок не найден.')
    
    if castle.owner:
        raise ValueError('Этот замок уже занят другой гильдией.')
    
    if CastleSiege.objects.filter(castle=castle, status='active').exists():
        raise ValueError('Этот замок уже осаждают.')
    
        # Проверка КД
    if castle.siege_cooldown_until and castle.siege_cooldown_until > timezone.now():
        remaining = castle.siege_cooldown_until - timezone.now()
        minutes = int(remaining.total_seconds() // 60)
        raise ValueError(f'Этот замок под защитой ещё {minutes} мин.')
    # Создаем осаду
    siege = CastleSiege.objects.create(
        castle=castle,
        attacker_guild=guild,
        status='active',
        player_hp=player.health,
    )
    
        # Создаем НПС-защитников (сложность растет экспоненциально)
    num_enemies = castle.defense_level + 3  # минимум 4 врага
    for i in range(num_enemies):
        # HP растет квадратично (100, 225, 400...)
        base_hp = 100 + (castle.defense_level * 50) + (i * 20)
        # Атака растет сильнее
        base_attack = 10 + (castle.defense_level * 8)
        # Защита тоже растет
        base_defense = castle.defense_level * 3
        
        SiegeEnemy.objects.create(
            siege=siege,
            name=f'Стражник {i+1}',
            health=base_hp,
            max_health=base_hp,
            attack=base_attack,
            defense=base_defense,
        )
    
    _log(guild, player, 'siege', f'Начата осада замка «{castle.name}»')
    # Ставим КД на 3 часа после начала осады (или после ее окончания)
    castle.siege_cooldown_until = timezone.now() + timedelta(hours=3)
    castle.save(update_fields=['siege_cooldown_until'])
    return siege


@transaction.atomic
def siege_action(player: Player, siege_id: int, action: str):
    """Действие игрока в осаде: attack, defend, flee."""
    siege = CastleSiege.objects.select_related('castle', 'attacker_guild').filter(id=siege_id).first()
    if not siege:
        raise ValueError('Осада не найдена.')
    
    if siege.status != 'active':
        raise ValueError('Эта осада уже завершена.')
    
    if siege.attacker_guild != get_guild(player):
        raise ValueError('Ты не участвуешь в этой осаде.')
    
    # Получаем текущего врага
    enemies = siege.enemies.filter(is_dead=False).order_by('id')
    if not enemies.exists():
        # Победа!
        siege.status = 'won'
        siege.finished_at = timezone.now()
        siege.castle.owner = siege.attacker_guild
        siege.castle.save(update_fields=['owner'])
        siege.save()
        _log(siege.attacker_guild, player, 'siege_won', f'Замок «{siege.castle.name}» захвачен!')
        return {'status': 'won', 'castle': siege.castle.name}
    
    current_enemy = enemies.first()
    
    # Действие игрока
    if action == 'attack':
        damage = max(1, player.strength - current_enemy.defense)
        is_crit = random.random() < 0.15
        if is_crit:
            damage = int(damage * 1.5)
        
        current_enemy.health -= damage
        if is_crit:
            _add_siege_log(siege, 'player', f'💥 КРИТ! Ты нанёс {damage} урона стражнику.')
        else:
            _add_siege_log(siege, 'player', f'🗡 Ты нанёс {damage} урона стражнику.')
        
        if current_enemy.health <= 0:
            current_enemy.is_dead = True
            current_enemy.health = 0
            _add_siege_log(siege, 'system', f'🏆 Стражник {current_enemy.name} повержен!')
        current_enemy.save()
    
    elif action == 'defend':
        _add_siege_log(siege, 'player', '🛡 Ты встал в защиту.')
    
    elif action == 'flee':
        siege.status = 'lost'
        siege.finished_at = timezone.now()
        siege.save()
        _log(siege.attacker_guild, player, 'siege_fled', f'Побег из осады «{siege.castle.name}»')
        return {'status': 'lost', 'message': 'Ты сбежал из осады.'}
    
    # Ответ врага (если он еще жив)
    if not current_enemy.is_dead:
        enemy_damage = max(1, current_enemy.attack - player.endurance // 2)
        
        # Шанс 20% на ярость (двойной урон)
        is_rage = random.random() < 0.2
        if is_rage:
            enemy_damage = int(enemy_damage * 2)
            _add_siege_log(siege, 'enemy', f'🔥 ЯРОСТЬ! {current_enemy.name} нанёс {enemy_damage} урона!')
        elif action == 'defend':
            enemy_damage = enemy_damage // 2
            _add_siege_log(siege, 'enemy', f'⚔️ {current_enemy.name} нанёс {enemy_damage} урона (заблокировано).')
        else:
            _add_siege_log(siege, 'enemy', f'⚔️ {current_enemy.name} нанёс {enemy_damage} урона.')
        
        siege.player_hp -= enemy_damage
        
        # ПРОВЕРКА НА ПОРАЖЕНИЕ
        if siege.player_hp <= 0:
            siege.player_hp = 0
            siege.status = 'lost'
            siege.finished_at = timezone.now()
            siege.save()
            _log(siege.attacker_guild, player, 'siege_lost', f'Поражение в осаде «{siege.castle.name}»')
            return {'status': 'lost', 'message': 'Ты пал в бою.'}
    
    siege.save()
    
    return {
        'status': 'active',
        'player_hp': siege.player_hp,
        'enemies_left': siege.enemies.filter(is_dead=False).count(),
        'current_enemy': {
            'name': current_enemy.name,
            'hp': current_enemy.health,
            'max_hp': current_enemy.max_health,
        } if not current_enemy.is_dead else None,
        'log': siege.log[-5:],
    }


def _add_siege_log(siege, actor, message):
    siege.log.append({'actor': actor, 'message': message})
    siege.save(update_fields=['log'])

@transaction.atomic
def collect_castle_taxes(player: Player):
    """Собирает налоги со всех замков гильдии."""
    guild = get_guild(player)
    if not guild:
        raise ValueError('Ты не в гильдии.')
    
    if not can(player, 'manage_treasury'):
        raise ValueError('Только лидер и замы могут собирать налоги.')
    
    castles = Castle.objects.filter(owner=guild)
    if not castles.exists():
        raise ValueError('У твоей гильдии нет замков.')
    
    now = timezone.now()
    total_income = 0
    total_tax = 0
    messages = []
    
    for castle in castles:
        # Проверяем, прошло ли 24 часа с последнего сбора
        if castle.last_tax_collected and (now - castle.last_tax_collected) < timedelta(hours=24):
            continue
        
        # Начисляем доход
        guild.treasury_gold += castle.passive_income
        total_income += castle.passive_income
        
        # Списываем налог
        if guild.treasury_gold >= castle.daily_tax:
            guild.treasury_gold -= castle.daily_tax
            total_tax += castle.daily_tax
            castle.debt_deadline = None  # Долг сброшен
            messages.append(f'Замок «{castle.name}»: +{castle.passive_income}💰, -{castle.daily_tax}💰')
        else:
            # Не хватает золота — ставим дедлайн (2 дня)
            if not castle.debt_deadline:
                castle.debt_deadline = now + timedelta(days=2)
            messages.append(f'Замок «{castle.name}»: НЕ ХВАТАЕТ ЗОЛОТА НА НАЛОГ! Дедлайн: {castle.debt_deadline.strftime("%d.%m.%Y")}')
        
        castle.last_tax_collected = now
        castle.save(update_fields=['last_tax_collected', 'debt_deadline'])
    
    guild.save(update_fields=['treasury_gold'])
    
    if total_income == 0:
        raise ValueError('Налоги уже собраны. Попробуй позже (через 24 часа).')
    
    _log(guild, player, 'tax_collect', f'Собрано налогов: +{total_income}, уплачено: -{total_tax}')
    
    return {
        'total_income': total_income,
        'total_tax': total_tax,
        'messages': messages,
        'treasury_gold': guild.treasury_gold,
    }


@transaction.atomic
def check_castle_debts():
    """Проверяет долги по замкам и отбирает их (вызывать раз в день)."""
    now = timezone.now()
    castles = Castle.objects.filter(owner__isnull=False, debt_deadline__lt=now)
    
    for castle in castles:
        guild = castle.owner
        castle.owner = None
        castle.debt_deadline = None
        castle.save(update_fields=['owner', 'debt_deadline'])
        
        _log(guild, None, 'castle_lost', f'Замок «{castle.name}» отобран из-за неуплаты налогов')

@transaction.atomic
def challenge_duel(challenger: Player, opponent_username: str):
    """Вызывает игрока на дуэль."""
    if challenger.user.username == opponent_username:
        raise ValueError('Нельзя вызвать самого себя.')
    
    opponent = Player.objects.filter(user__username=opponent_username).first()
    if not opponent:
        raise ValueError('Игрок не найден.')
    
    # Проверяем, нет ли уже активной дуэли
    if Duel.objects.filter(
        Q(challenger=challenger, status__in=['pending', 'active']) |
        Q(opponent=challenger, status__in=['pending', 'active'])
    ).exists():
        raise ValueError('У тебя уже есть активная дуэль.')
    
    if Duel.objects.filter(
        Q(challenger=opponent, status__in=['pending', 'active']) |
        Q(opponent=opponent, status__in=['pending', 'active'])
    ).exists():
        raise ValueError('У этого игрока уже есть активная дуэль.')
    
    duel = Duel.objects.create(
        challenger=challenger,
        opponent=opponent,
        status='pending',
        challenger_hp=challenger.health,
        opponent_hp=opponent.health,
    )
    return duel


@transaction.atomic
def accept_duel(player: Player, duel_id: int):
    """Принимает вызов на дуэль."""
    duel = Duel.objects.select_related('challenger', 'opponent').filter(id=duel_id).first()
    if not duel:
        raise ValueError('Дуэль не найдена.')
    if duel.opponent != player:
        raise ValueError('Это не твой вызов.')
    if duel.status != 'pending':
        raise ValueError('Дуэль уже неактивна.')
    
    duel.status = 'active'
    duel.challenger_hp = duel.challenger.health
    duel.opponent_hp = duel.opponent.health
    duel.save()
    return duel


@transaction.atomic
def decline_duel(player: Player, duel_id: int):
    """Отклоняет вызов."""
    duel = Duel.objects.filter(id=duel_id).first()
    if not duel or duel.opponent != player:
        raise ValueError('Дуэль не найдена.')
    
    duel.status = 'declined'
    duel.finished_at = timezone.now()
    duel.save()
    return duel


@transaction.atomic
def duel_action(player: Player, duel_id: int, action: str):
    """Действие в дуэли: attack."""
    # Блокируем строку, чтобы два одновременных запроса не прошли
    duel = Duel.objects.select_for_update().select_related('challenger', 'opponent').filter(id=duel_id).first()
    
    if not duel or duel.status != 'active':
        raise ValueError('Дуэль неактивна.')
    
    if player not in [duel.challenger, duel.opponent]:
        raise ValueError('Ты не участник этой дуэли.')
    
    # ПРОВЕРКА ОЧЕРЕДИ
    if player == duel.challenger and duel.current_turn != 'challenger':
        raise ValueError('Сейчас не твой ход. Дождись противника.')
    if player == duel.opponent and duel.current_turn != 'opponent':
        raise ValueError('Сейчас не твой ход. Дождись противника.')
    
    # Определяем, кто атакует
    if player == duel.challenger:
        attacker, defender = duel.challenger, duel.opponent
        defender_hp = duel.opponent_hp
        is_challenger_turn = True
    else:
        attacker, defender = duel.opponent, duel.challenger
        defender_hp = duel.challenger_hp
        is_challenger_turn = False
    
    # Расчет урона
    base_damage = max(1, attacker.strength - (defender.endurance // 4))
    variance = random.uniform(0.9, 1.1)
    damage = int(base_damage * variance)
    is_crit = random.random() < 0.15
    if is_crit:
        damage = int(damage * 1.5)
    damage = max(1, damage)
    
    defender_hp -= damage
    
    crit_text = "💥 КРИТ! " if is_crit else ""
    _add_duel_log(duel, attacker, f'{crit_text}⚔️ {attacker.user.username} нанёс {damage} урона!')
    
    # Обновляем HP
    if is_challenger_turn:
        duel.opponent_hp = defender_hp
    else:
        duel.challenger_hp = defender_hp
    
    # Проверка победы
    if defender_hp <= 0:
        duel.status = 'finished'
        duel.winner = attacker
        duel.finished_at = timezone.now()
        duel.save()
        return {'status': 'finished', 'winner': attacker.user.username, 'log': duel.log[-5:]}
    
    # ПЕРЕДАЕМ ХОД
    duel.current_turn = 'opponent' if is_challenger_turn else 'challenger'
    duel.turn += 1
    duel.save()
    
    return {
        'status': 'active',
        'current_turn': duel.current_turn,
        'challenger_hp': duel.challenger_hp,
        'opponent_hp': duel.opponent_hp,
        'log': duel.log[-5:],
    }


def _add_duel_log(duel, actor, message):
    duel.log.append({'actor': actor.user.username, 'message': message})
    duel.save(update_fields=['log'])


def get_active_duels(player: Player):
    """Возвращает список активных и ожидающих дуэлей игрока."""
    duels = Duel.objects.filter(
        Q(challenger=player) | Q(opponent=player),
        status__in=['pending', 'active']
    ).select_related('challenger__user', 'opponent__user')
    
    result = []
    for d in duels:
        result.append({
            'id': d.id,
            'challenger': d.challenger.user.username,
            'opponent': d.opponent.user.username,
            'status': d.status,
            'is_my_challenge': d.challenger == player,
            'challenger_hp': d.challenger_hp,
            'opponent_hp': d.opponent_hp,
            'log': d.log[-5:],
            'current_turn': d.current_turn,
            'my_username': player.user.username,
        })
    return result

def generate_daily_quests_for_guild(guild: Guild, target_date=None):
    """Генерирует 3 случайных квеста на день."""
    if not target_date:
        target_date = timezone.now().date()
    
    # Если уже есть квесты на этот день — не генерируем
    if GuildDailyQuest.objects.filter(guild=guild, date=target_date).exists():
        return

    # Берем все активные шаблоны
    templates = list(GuildDailyQuestTemplate.objects.filter(is_active=True))
    if len(templates) < 3:
        return # Недостаточно шаблонов

    # Чтобы у каждой гильдии был свой набор, используем seed
    random.seed(guild.id + zlib.crc32(str(target_date).encode()))
    selected_templates = random.sample(templates, 3)

    for tmpl in selected_templates:
        GuildDailyQuest.objects.create(
            guild=guild,
            template=tmpl,
            date=target_date,
        )

def check_daily_quest_progress(player: Player, enemy):
    """Вызывается из combat.py при убийстве моба."""
    guild = get_guild(player)
    if not guild:
        return

    today = timezone.now().date()
    quests = GuildDailyQuest.objects.filter(
        guild=guild, 
        date=today, 
        is_completed=False,
        template__target_enemy=enemy
    )

    for quest in quests:
        quest.progress += 1
        if quest.progress >= quest.template.required_count:
            quest.is_completed = True
            quest.completed_at = timezone.now()
            _log(guild, None, 'daily_quest_done', f'Квест "{quest.template.title}" выполнен!')
        quest.save()

        contrib, _ = GuildDailyQuestContribution.objects.get_or_create(
            daily_quest=quest, player=player
        )
        contrib.kills += 1
        contrib.save()

@transaction.atomic
def claim_daily_quest_reward(player: Player, quest_id: int):
    """Сдача награды за ежедневку."""
    quest = GuildDailyQuest.objects.select_related('guild', 'template').filter(id=quest_id).first()
    if not quest or quest.guild != get_guild(player):
        raise ValueError('Квест не найден.')
    
    if not quest.is_completed:
        raise ValueError('Квест еще не выполнен гильдией.')

    contrib = GuildDailyQuestContribution.objects.filter(daily_quest=quest, player=player).first()
    if not contrib:
        raise ValueError('Ты не участвовал в этом квесте.')
    if contrib.is_claimed:
        raise ValueError('Ты уже получил награду.')

    # Выдаем награды
    player.gold += quest.template.reward_gold_player
    player.experience += quest.template.reward_exp
    player.save()

    guild = quest.guild
    guild.treasury_gold += quest.template.reward_gold_treasury
    guild.save()

    contrib.is_claimed = True
    contrib.save()

    return quest.template

@transaction.atomic
def process_daily_quests_reset():
    """Вызывается в 23:59. Проверяет выполнение, начисляет серию, генерирует новые."""
    today = timezone.now().date()
    
    for guild in Guild.objects.all():
        quests = GuildDailyQuest.objects.filter(guild=guild, date=today)
        if not quests.exists():
            continue

        all_completed = all(q.is_completed for q in quests)
        
        if all_completed:
            guild.daily_streak += 1
            guild.last_daily_completed_date = today
            
            # Бонус за 7 дней подряд
            if guild.daily_streak >= 7:
                guild.treasury_gold += 3500
                _log(guild, None, 'daily_streak_reward', 'Серия 7 дней! +3500 золота в казну.')
                guild.daily_streak = 0 # Сбрасываем после награды
        else:
            if guild.daily_streak > 0:
                _log(guild, None, 'daily_streak_lost', 'Серия ежедневок прервана.')
            guild.daily_streak = 0
            
        guild.save()
        
        # Генерируем на завтра
        tomorrow = today + timedelta(days=1)
        generate_daily_quests_for_guild(guild, tomorrow)
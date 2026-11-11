"""
Сервис VIP-статуса «Тень Платинум».
Единая точка: выдача предмета, активация, получение бонусов, истечение.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from game.models import (
    Player, PlayerVip, PlayerVipItem, VipBonus, VipItemTemplate,
    PlayerNotification, Combat,
)


# ---------- Чтение ----------

def get_active_vip(player: Player):
    """Возвращает активный PlayerVip (самый поздний expires_at) или None."""
    now = timezone.now()
    return (
        PlayerVip.objects
        .filter(player=player, expires_at__gt=now)
        .select_related('vip_status')
        .order_by('-expires_at')
        .first()
    )


def get_active_vip_bonuses(player: Player) -> dict:
    """
    Возвращает словарь бонусов активного VIP:
    {'experience_multiplier': 2.0, 'gold_multiplier': 1.5, 'chat_color': '#B9A7FF', ...}
    """
    vip = get_active_vip(player)
    if not vip:
        return {}

    result = {}
    bonuses = VipBonus.objects.filter(vip_status=vip.vip_status, is_active=True)
    for b in bonuses:
        if b.bonus_type == 'chat_color':
            result['chat_color'] = vip.vip_status.color_hex
        else:
            result[b.bonus_type] = b.value
    # Гарантируем цвет, даже если бонус chat_color не создан
    result.setdefault('chat_color', vip.vip_status.color_hex)
    return result


def get_vip_color(player: Player) -> str:
    """Цвет автора в чате или пустая строка."""
    return get_active_vip_bonuses(player).get('chat_color', '')


def is_in_combat(player: Player) -> bool:
    return Combat.objects.filter(player=player, status='active').exists()


# ---------- Выдача ----------

def grant_vip_item(
    player: Player,
    template: VipItemTemplate,
    quantity: int = 1,
    source: str = 'other',
    source_ref: str = '',
) -> PlayerVipItem:
    """
    Выдаёт VIP-активатор в инвентарь (не занимает слот).
    Если такой шаблон уже есть — увеличивает quantity.
    """
    if quantity <= 0:
        return None

    with transaction.atomic():
        item, created = PlayerVipItem.objects.get_or_create(
            player=player,
            template=template,
            defaults={'quantity': 0, 'source': source, 'source_ref': source_ref},
        )
        item.quantity += quantity
        item.save(update_fields=['quantity'])
        return item


# ---------- Активация ----------

class VipActivationError(Exception):
    """Ошибка активации с человекочитаемым сообщением."""
    pass


def activate_vip_item(player: Player, player_vip_item_id: int) -> PlayerVip:
    """
    Активирует VIP-предмет. Время складывается с текущим активным VIP того же статуса.
    В бою — запрещено. После активации предмет удаляется (необратимо).
    """
    if is_in_combat(player):
        raise VipActivationError('Нельзя активировать VIP во время боя.')

    try:
        pvi = PlayerVipItem.objects.select_related('template', 'template__vip_status').get(
            id=player_vip_item_id, player=player,
        )
    except PlayerVipItem.DoesNotExist:
        raise VipActivationError('VIP-предмет не найден.')

    template = pvi.template
    if not template.is_active:
        raise VipActivationError('Этот VIP-предмет больше не активен.')

    status = template.vip_status
    days = template.days

    with transaction.atomic():
        now = timezone.now()

        # Ищем активный VIP того же статуса
        current = (
            PlayerVip.objects
            .select_for_update()
            .filter(player=player, vip_status=status, expires_at__gt=now)
            .order_by('-expires_at')
            .first()
        )

        if current:
            current.expires_at = current.expires_at + timedelta(days=days)
            current.save(update_fields=['expires_at'])
            vip = current
        else:
            vip = PlayerVip.objects.create(
                player=player,
                vip_status=status,
                activated_at=now,
                expires_at=now + timedelta(days=days),
                source=pvi.source,
                source_ref=pvi.source_ref,
            )

        # Удаляем/уменьшаем предмет
        if pvi.quantity > 1:
            pvi.quantity -= 1
            pvi.save(update_fields=['quantity'])
        else:
            pvi.delete()

        # Уведомление
        PlayerNotification.objects.create(
            player=player,
            title=f'{status.name} активирован',
            message=f'Статус «{status.name}» активен до {vip.expires_at:%d.%m.%Y %H:%M} (МСК).',
        )

    return vip
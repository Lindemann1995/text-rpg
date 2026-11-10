from django.db import transaction
from django.db.models import F
from game.models import Inventory, InventoryInstance, Item, Player, EquipmentSlot

BONUS_FIELDS = [
    'bonus_strength', 'bonus_agility', 'bonus_intelligence',
    'bonus_endurance', 'bonus_sanity', 'bonus_health', 'bonus_mana',
]

def add_item(player: Player, item: Item, quantity: int = 1) -> list:
    """
    Выдает предмет игроку.
    Если предмет стакуемый (и не является экипировкой) — обновляет Inventory (возвращает [Inventory]).
    Если не стакуемый — создает InventoryInstance (возвращает список экземпляров).
    """
    if quantity <= 0:
        return []

    # 🆕 Защита от дурака: если у предмета есть слот экипировки, он ОБЯЗАТЕЛЬНО уникальный,
    # даже если в админке случайно поставили галочку "стакуется"
    is_actually_stackable = item.is_stackable and not item.equip_slot

    if is_actually_stackable:
        with transaction.atomic():
            inv, created = Inventory.objects.get_or_create(
                player_id=player.id,
                item_id=item.id,
                defaults={'quantity': 0}
            )
            inv.quantity += quantity
            inv.save(update_fields=['quantity'])
        return [inv]
    else:
        instances = []
        with transaction.atomic():
            for _ in range(quantity):
                inst = InventoryInstance.objects.create(
                    player_id=player.id,
                    item_id=item.id,
                )
                instances.append(inst)
        return instances

def remove_item(player: Player, item: Item, quantity: int = 1) -> bool:
    """
    Забирает стакуемый предмет из Inventory.
    Возвращает True, если успешно, False если не хватает количества.
    """
    if quantity <= 0:
        return True

    try:
        with transaction.atomic():
            inv = Inventory.objects.select_for_update().get(player=player, item=item)
            if inv.quantity < quantity:
                return False
            
            inv.quantity -= quantity
            if inv.quantity <= 0:
                inv.delete()
            else:
                inv.save(update_fields=['quantity'])
            return True
    except Inventory.DoesNotExist:
        return False

def remove_instance(instance: InventoryInstance) -> bool:
    """
    Удаляет конкретный экземпляр. Если он был надет, сначала снимает.
    """
    with transaction.atomic():
        # Если вещь надета, нужно снять её и пересчитать статы
        if instance.is_equipped:
            from .inventory import unequip_instance
            unequip_instance(instance)
        
        instance.delete()
        return True

def sync_player_bonuses(player: Player):
    """
    Пересчитывает все бонусы игрока от надетой экипировки.
    Использует базовые статы из класса (если есть) + бонусы от вещей.
    """
    # 1. Сбрасываем текущие статы к базовым значениям
    if player.character_class:
        player.strength = player.character_class.base_strength
        player.agility = player.character_class.base_agility
        player.intelligence = player.character_class.base_intelligence
        player.endurance = player.character_class.base_endurance
        player.sanity = player.character_class.base_sanity
    else:
        player.strength = 10
        player.agility = 10
        player.intelligence = 10
        player.endurance = 10
        player.sanity = 10

    # Сбрасываем бонусные HP/MP (базовые оставляем)
    base_max_health = 100 + (player.level - 1) * 10
    base_max_mana = 50 + (player.level - 1) * 5
    
    player.max_health = base_max_health
    player.max_mana = base_max_mana

    # 2. Прибавляем бонусы от всех надетых вещей
    equipped_slots = EquipmentSlot.objects.filter(player=player).select_related('item', 'inventory_instance')
    
    for slot in equipped_slots:
        if not slot.item:
            continue
            
        source = slot.inventory_instance if slot.inventory_instance else slot.item
        
        for field in BONUS_FIELDS:
            val = getattr(source, field, 0)
            if val:
                current_val = getattr(player, field)
                setattr(player, field, current_val + val)

    # Корректируем текущие HP/MP, чтобы они не превышали новые максимумы
    if player.health > player.max_health:
        player.health = player.max_health
    if player.mana > player.max_mana:
        player.mana = player.max_mana

    player.save()

def equip_instance(player: Player, instance: InventoryInstance) -> bool:
    """
    Надевает экземпляр на игрока.
    Жестко удаляет все старые вещи из этого слота, чтобы не было дублей.
    """
    item = instance.item
    if not item.equip_slot:
        return False

    with transaction.atomic():
        # 1. Находим ВСЕ старые слоты для этого типа
        old_slots = EquipmentSlot.objects.filter(player=player, slot=item.equip_slot)
        
        for old_slot in old_slots:
            # Снимаем старые экземпляры
            if old_slot.inventory_instance:
                old_slot.inventory_instance.is_equipped = False
                old_slot.inventory_instance.save(update_fields=['is_equipped'])
            old_slot.delete()

        # 2. Помечаем новый экземпляр как надетый
        instance.is_equipped = True
        instance.save(update_fields=['is_equipped'])

        # 3. Создаем ровно один новый слот
        EquipmentSlot.objects.create(
            player=player,
            slot=item.equip_slot,
            item=item,
            inventory_instance=instance
        )

        # 4. Пересчитываем статы
        sync_player_bonuses(player)
        return True

def unequip_instance(instance: InventoryInstance) -> bool:
    """
    Снимает экземпляр (слот ищется по игроку).
    """
    player = instance.player
    item = instance.item

    with transaction.atomic():
        slot = EquipmentSlot.objects.filter(player=player, inventory_instance=instance).first()
        if not slot:
            return False

        slot.delete()

        instance.is_equipped = False
        instance.save(update_fields=['is_equipped'])

        sync_player_bonuses(player)
        return True
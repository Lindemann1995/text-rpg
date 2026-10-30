"""
Логика боевой системы.
"""
import random
from django.utils import timezone
from .models import (Combat, Enemy, Player, Flag, Item, Inventory, EnemyLoot, PlayerQuest, CombatSettings
)


def start_combat(player: Player, enemy: Enemy) -> Combat:
    """Начинает новый бой"""
    # Баффы гильдии больше не умножают базовые статы в БД, мы считаем их на лету
    
    combat = Combat.objects.create(
        player=player,
        enemy=enemy,
        player_hp=player.health,
        enemy_hp=enemy.health,
        turn=1,
        status='active',
        log=[],
    )
    _add_log(combat, 'system', f'⚔️ Бой начался: {player.user.username} vs {enemy.name}')
    combat.save()
    return combat


def player_attack(combat: Combat) -> dict:
    """Игрок атакует врага"""
    if combat.status != 'active':
        return {'error': 'Бой уже завершён'}
    
    player = combat.player
    enemy = combat.enemy
    
    # Применяем бафф Алтаря силы
    from guilds.services import get_guild_bonuses
    bonuses = get_guild_bonuses(player)
    
    # 🆕 СЧИТАЕМ БАЗОВЫЙ УРОН В ЗАВИСИМОСТИ ОТ КЛАССА
    cls = player.character_class.name.lower() if player.character_class else 'воин'
    primary_stat = player.strength
    
    if 'лучник' in cls:
        primary_stat = player.agility
    elif 'жнец' in cls:
        primary_stat = player.intelligence # или player.sanity

    effective_stat = int(primary_stat * bonuses['strength_multiplier'])
    base_damage = max(1, effective_stat - enemy.defense)
    
    settings = get_combat_settings()
    is_crit = random.random() < settings.crit_chance
    damage = int(base_damage * settings.crit_multiplier) if is_crit else base_damage
    
    combat.enemy_hp -= damage
    combat.turn += 1
    
    if is_crit:
        _add_log(combat, 'player', f'💥 КРИТ! Ты нанёс {damage} урона!')
    else:
        _add_log(combat, 'player', f'🗡 Ты нанёс {damage} урона.')
    
    # Проверка победы
    if combat.enemy_hp <= 0:
        combat.enemy_hp = 0
        combat.status = 'won'
        combat.finished_at = timezone.now()
        
        # ВЫДАЕМ НАГРАДЫ И ПОЛУЧАЕМ СПИСОК (а также реальные цифры)
        dropped_items, real_xp, real_gold = _apply_rewards(player, enemy)
        
        # 🆕 ТЕПЕРЬ ЗАПИСЫВАЕМ В ЛОГ РЕАЛЬНЫЕ ЦИФРЫ
        _add_log(combat, 'system', f'🏆 Победа! +{real_xp} XP, +{real_gold} золота')
        
        print(f"=== ЛОГ: ВРАГ {enemy.name} ПОБЕЖДЕН. ВЫДАНО {real_xp} XP, {real_gold} золота ===")
        
        # 🆕 ОБНОВЛЯЕМ ПРОГРЕСС КВЕСТОВ
        _update_kill_quests(player, enemy)
        
        # 🆕 ОБНОВЛЯЕМ ПРОГРЕСС ЕЖЕДНЕВОК ГИЛЬДИИ
        try:
            from guilds.services import check_daily_quest_progress
            check_daily_quest_progress(player, enemy)
        except Exception as e:
            print(f"Ошибка при обновлении ежедневок: {e}")
            
        # Сохраняем лут в бой (чтобы Flutter мог его прочитать)
        combat.boss_state = {'dropped_items': dropped_items}
        combat.save()
        
        # Возвращаем словарь с лутом
        result = _combat_to_dict(combat)
        result['dropped_items'] = dropped_items
        return result
    else:
        enemy_damage = max(1, enemy.attack - player.endurance // 2)
        combat.player_hp -= enemy_damage
        _add_log(combat, 'enemy', f'⚔️ {enemy.name} нанёс {enemy_damage} урона.')
        
        if combat.player_hp <= 0:
            combat.player_hp = 0
            combat.status = 'lost'
            combat.finished_at = timezone.now()
            _add_log(combat, 'system', '💀 Поражение... Ты потерял сознание.')
    
    combat.save()
    _sync_player_hp(player, combat.player_hp)
    return _combat_to_dict(combat)


def player_defend(combat: Combat) -> dict:
    """Игрок защищается — уменьшает урон следующего удара на 50%"""
    if combat.status != 'active':
        return {'error': 'Бой уже завершён'}
    
    player = combat.player
    enemy = combat.enemy
    
    combat.turn += 1
    _add_log(combat, 'player', '🛡 Ты встал в защиту.')
    
    enemy_damage = max(1, enemy.attack - player.endurance // 2)
    enemy_damage = enemy_damage // 2
    combat.player_hp -= enemy_damage
    _add_log(combat, 'enemy', f'⚔️ {enemy.name} нанёс {enemy_damage} урона (заблокировано).')
    
    if combat.player_hp <= 0:
        combat.player_hp = 0
        combat.status = 'lost'
        combat.finished_at = timezone.now()
        _add_log(combat, 'system', '💀 Поражение...')
    
    combat.save()
    _sync_player_hp(player, combat.player_hp)
    return _combat_to_dict(combat)


def player_flee(combat: Combat) -> dict:
    """Побег — 50% шанс успеха"""
    if combat.status != 'active':
        return {'error': 'Бой уже завершён'}
    
    if random.random() < 0.5:
        combat.status = 'fled'
        combat.finished_at = timezone.now()
        _add_log(combat, 'system', '🏃 Ты сбежал с поля боя.')
    else:
        combat.turn += 1
        _add_log(combat, 'system', '❌ Побег не удался!')
        enemy = combat.enemy
        player = combat.player
        enemy_damage = max(1, enemy.attack - player.endurance // 2)
        combat.player_hp -= enemy_damage
        _add_log(combat, 'enemy', f'⚔️ {enemy.name} нанёс {enemy_damage} урона.')
        
        if combat.player_hp <= 0:
            combat.player_hp = 0
            combat.status = 'lost'
            combat.finished_at = timezone.now()
            _add_log(combat, 'system', '💀 Поражение...')
    
    combat.save()
    _sync_player_hp(combat.player, combat.player_hp)
    return _combat_to_dict(combat)


def _apply_rewards(player: Player, enemy: Enemy) -> tuple:
    """Выдает награды и возвращает (список_лута, реальный_опыт, реальное_золото)"""
    dropped_items = []
    real_xp = 0
    real_gold = 0
    
    try:
        # Применяем баффы гильдии (опыт и золото)
        from guilds.services import get_guild_bonuses
        bonuses = get_guild_bonuses(player)

        # 1. Награды за уровень
        level_diff = player.level - enemy.level
        xp_reward = enemy.xp_reward
        gold_reward = enemy.gold_reward
        
        settings = get_combat_settings()
        if level_diff >= settings.level_diff_penalty_threshold:
            xp_reward = max(1, xp_reward // settings.level_diff_penalty_divider)
            gold_reward = max(0, gold_reward // settings.level_diff_penalty_divider)
        elif level_diff <= settings.level_diff_bonus_threshold:
            xp_reward = int(xp_reward * settings.level_diff_bonus_multiplier)
            gold_reward = int(gold_reward * settings.level_diff_bonus_multiplier)

        # ПРИМЕНЯЕМ БАФФЫ
        xp_reward = int(xp_reward * bonuses['xp_multiplier'])
        gold_reward = int(gold_reward * bonuses['gold_multiplier'])

        # Сохраняем для возврата
        real_xp = xp_reward
        real_gold = gold_reward

        # 🆕 Начисляем золото (опыт начислим через метод)
        player.gold += gold_reward
        
        # 2. СЧЕТЧИК УБИЙСТВ
        player.enemies_killed += 1
        print(f"=== СТАТИСТИКА: {player.user.username} убил {enemy.name}. Всего убийств: {player.enemies_killed} ===")

        # 3. Лут
        location = enemy.location 
        possible_loots = enemy.loot_table.all()
        
        for loot in possible_loots:
            if not (loot.min_enemy_level <= enemy.level <= loot.max_enemy_level):
                continue
                
            drop_chance = loot.chance
            if location:
                loc_level_diff = player.level - location.min_level
                if loc_level_diff > 5:
                    penalty = (loc_level_diff - 5) * 10
                    drop_chance = max(0, drop_chance - penalty)

            # ПРИМЕНЯЕМ БАФФ ЛУТА (Кузница)
            drop_chance = int(drop_chance * bonuses['loot_multiplier'])

            roll = random.randint(1, 100)
            if roll <= drop_chance:
                qty = random.randint(loot.quantity_min, loot.quantity_max)
                
                inv, created = Inventory.objects.get_or_create(
                    player=player, 
                    item=loot.item,
                    defaults={'quantity': 0}
                )
                inv.quantity += qty
                inv.save()
                
                dropped_items.append({
                    'slug': loot.item.slug,
                    'name': loot.item.name,
                    'quantity': qty,
                    'rarity': loot.item.rarity,
                    'item_type': loot.item.item_type, 
                    'image_path': loot.item.image_path,
                    'bonus_strength': loot.item.bonus_strength,
                    'bonus_agility': loot.item.bonus_agility,
                    'bonus_intelligence': loot.item.bonus_intelligence,
                    'bonus_endurance': loot.item.bonus_endurance,
                    'bonus_health': loot.item.bonus_health,
                })
        
        # 4. 🆕 Начисление опыта и проверка повышения уровня
        leveled_up = player.add_experience(xp_reward)
        if leveled_up:
            print(f"=== УРОВЕНЬ ПОВЫШЕН: {player.user.username} теперь {player.level} уровня ===")
            
        # ВАЖНО: Сохраняем игрока в конце
        player.save()
        
    except Exception as e:
        print(f"!!! ОШИБКА ПРИ ВЫДАЧЕ НАГРАДЫ: {e}")
        player.save()
        
    return dropped_items, real_xp, real_gold

def _update_kill_quests(player: Player, enemy: Enemy):
    """Обновляет прогресс квестов, где нужно убить этого моба"""
    try:
        active_quests = PlayerQuest.objects.filter(player=player, status='active')
        
        for pq in active_quests:
            # Ищем шаги этого квеста, где нужно убить именно этого моба
            objectives = pq.quest.objectives.filter(objective_type='kill', target_enemy=enemy)
            
            updated = False
            for obj in objectives:
                obj_id_str = str(obj.id)
                current = pq.progress_data.get(obj_id_str, 0)
                
                if current < obj.required_count:
                    current += 1
                    pq.progress_data[obj_id_str] = current
                    updated = True
                    
            if updated:
                # Проверяем, выполнены ли ВСЕ шаги этого квеста
                all_done = True
                for obj in pq.quest.objectives.all():
                    current = pq.progress_data.get(str(obj.id), 0)
                    if current < obj.required_count:
                        all_done = False
                        break
                
                if all_done:
                    pq.status = 'ready'
                    print(f"=== КВЕСТ ГОТОВ К СДАЧЕ: {pq.quest.title} (Игрок: {player.user.username}) ===")
                else:
                    print(f"=== ПРОГРЕСС КВЕСТА: {pq.quest.title} обновлен ===")
                
                pq.save()
                
    except Exception as e:
        print(f"!!! ОШИБКА ПРИ ОБНОВЛЕНИИ КВЕСТОВ: {e}")


def _sync_player_hp(player: Player, new_hp: int):
    """Синхронизирует HP игрока после боя"""
    max_hp = player.effective_max_health
    player.health = max(1, new_hp) if new_hp > 0 else max_hp // 2
    player.save()


def _add_log(combat: Combat, actor: str, message: str):
    """Добавляет запись в лог боя"""
    combat.log.append({
        'turn': combat.turn,
        'actor': actor,
        'message': message,
    })


def _combat_to_dict(combat: Combat) -> dict:
    """Превращает бой в словарь для JSON"""
    return {
        'id': combat.id,
        'status': combat.status,
        'turn': combat.turn,
        'player': {
            'hp': combat.player_hp,
            'max_hp': combat.player.effective_max_health,
            'username': combat.player.user.username,
        },
        'enemy': {
            'id': combat.enemy.id,
            'name': combat.enemy.name,
            'hp': combat.enemy_hp,
            'max_hp': combat.enemy.health,
            'level': combat.enemy.level,
        },
        'log': combat.log[-10:],
    }

def get_combat_settings():
    """Возвращает настройки боя или дефолтные, если их нет в БД"""
    settings = CombatSettings.objects.first()
    if not settings:
        # Если настроек нет (например, в тестах), создаем временные
        return CombatSettings()
    return settings
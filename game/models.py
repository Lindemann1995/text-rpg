from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CharacterClass(models.Model):
    """Класс персонажа (Воин, Маг, Лучник и т.д.)"""
    
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Иконка'
    )
    
    # Базовые статы (с какими значениями игрок начинает)
    base_strength = models.IntegerField(default=10, verbose_name='Сила')
    base_agility = models.IntegerField(default=10, verbose_name='Ловкость')
    base_intelligence = models.IntegerField(default=10, verbose_name='Интеллект')
    base_endurance = models.IntegerField(default=10, verbose_name='Выносливость')
    base_sanity = models.IntegerField(default=10, verbose_name='Рассудок')
    
    class Meta:
        verbose_name = 'Класс персонажа'
        verbose_name_plural = 'Классы персонажей'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    

class Player(models.Model):
    """Игровой профиль игрока"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    character_class = models.ForeignKey(
        CharacterClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Класс'
    )

    # Прогресс.
    level = models.IntegerField(default=1, verbose_name='Уровень')
    experience = models.IntegerField(default=0, verbose_name='Опыт')
    experience_to_next = models.IntegerField(default=100, verbose_name='Опыт до след. уровня')
    last_offline_claim = models.DateTimeField(default=timezone.now, verbose_name='Время последнего сбора оффлайн-награды')
    offline_gold_rate = models.IntegerField(default=10, verbose_name='Золота в час (оффлайн)')
    privacy_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата принятия политики')
    privacy_version = models.CharField(max_length=10, default='1.0', verbose_name='Версия политики')
    # Статы
    strength = models.IntegerField(default=10, verbose_name='Сила')
    agility = models.IntegerField(default=10, verbose_name='Ловкость')
    intelligence = models.IntegerField(default=10, verbose_name='Интеллект')
    endurance = models.IntegerField(default=10, verbose_name='Выносливость')
    sanity = models.IntegerField(default=10, verbose_name='Рассудок')
    
    # 🆕 Модерация
    is_banned = models.BooleanField(default=False, verbose_name='Забанен')
    ban_until = models.DateTimeField(null=True, blank=True, verbose_name='Бан до')
    mute_until = models.DateTimeField(null=True, blank=True, verbose_name='Мут до')
    ban_reason = models.CharField(max_length=255, blank=True, verbose_name='Причина бана/мута')
    
    stat_points = models.IntegerField(
        default=0, 
        verbose_name="Очки характеристик",
        help_text="Свободные очки, которые игрок может распределить"
    )

    # Ресурсы
    health = models.IntegerField(default=100, verbose_name='Здоровье')
    max_health = models.IntegerField(default=100, verbose_name='Макс. здоровье')
    mana = models.IntegerField(default=50, verbose_name='Мана')
    max_mana = models.IntegerField(default=50, verbose_name='Макс. мана')
    gold = models.IntegerField(default=0, verbose_name='Золото')

    # Текущая позиция в сюжете.
    current_scene = models.ForeignKey(
        'Scene',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='players_here',
        verbose_name='Текущая сцена'
    )

    ROLE_CHOICES = [
        ('player', 'Игрок'),
        ('vip', 'VIP'),
        ('moderator', 'Модератор'),
        ('guild_leader', 'Лидер гильдии'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='player', 
        verbose_name='Роль в чате'
    )
    # Фракция.
    faction = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Орден Света'),
            ('shadow', 'Культ Тени'),
            ('free', 'Свободные'),
            ('none', 'Без фракции'),
        ],
        default='none',
        verbose_name='Фракция'
    )
    current_location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='players_here',
        verbose_name='Текущая локация'
    )

    # Подтверждение email
    email_verified = models.BooleanField(
        default=False,
        verbose_name='Email подтверждён'
    )
    email_verification_token = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Токен подтверждения email'
    )

    # Обучение.
    is_in_tutorial = models.BooleanField(default=True, verbose_name='В обучении')

    # Метаданные.
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')
    
    # 🆕 ДОБАВЛЕНО ДЛЯ РЕГЕНЕРАЦИИ:
    last_regen_at = models.DateTimeField(default=timezone.now, verbose_name='Последняя регенерация')
    
    enemies_killed = models.IntegerField(default=0, verbose_name='Убито врагов')
    last_seen = models.DateTimeField(auto_now=True, verbose_name='Последняя активность')

    # Внутри класса Player
    @property
    def effective_max_health(self):
        """Возвращает максимальное HP с учетом баффов гильдии."""
        try:
            from guilds.services import get_guild_bonuses
            bonuses = get_guild_bonuses(self)
            return int(self.max_health * bonuses['hp_multiplier'])
        except Exception:
            return self.max_health

    @property
    def effective_max_mana(self):
        """Возвращает максимальное MP с учетом баффов гильдии."""
        try:
            from guilds.services import get_guild_bonuses
            bonuses = get_guild_bonuses(self)
            return int(self.max_mana * bonuses['mp_multiplier'])
        except Exception:
            return self.max_mana
    
    class Meta:
        verbose_name = 'Игрок'
        verbose_name_plural = 'Игроки'
        ordering = ['-level']

    def __str__(self):
        return f'{self.user.username} [{self.level} ур.]'


class Scene(models.Model):
    """Сцена - один текстовый фрагмент игры с выбором"""

    SCENE_TYPES = [
        ('story', 'Сюжетная'),
        ('combat', 'Бой'),
        ('tutorial', 'Обучение'),
        ('dungeon', 'Подземелье'),
        ('shop', 'Магазин'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='Название сцены'
    )
    slug = models.TextField(
        max_length=100,
        unique=True,
        verbose_name='Индентификатор (slug)',
        help_text='Латиницей, без пробелов. Например: start_temple'
    )
    text = models.TextField(
        verbose_name='Текст сцены'
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Локация',
        help_text='Например: Мир Древних, Деревня Кайроса'
    )
    scene_type = models.CharField(
        max_length=20,
        choices=SCENE_TYPES,
        default='story',
        verbose_name='Тип сцены'    
    )
    is_tutorial = models.BooleanField(
        default=False,
        verbose_name='Сцена обучения'
    )
    is_start = models.BooleanField(
        default=False,
        verbose_name='Стартовая сцена',
        help_text='С нее начинает новый игрок'
    )

    # Метаданные.
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')

    class Meta:
        verbose_name = 'Сцена'
        verbose_name_plural = 'Сцены'
        ordering = ['id']
        
    def __str__(self):
        return f'{self.title} ({self.slug})'


class Choice(models.Model):
    """Вариант выбора в сцене."""

    scene = models.ForeignKey(
        Scene,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Сцена'
    )
    text = models.CharField(
        max_length=300,
        verbose_name='Текст кнопки',
        help_text='Например: взять осколок'
    )
    next_scene = models.ForeignKey(
        Scene,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='came_from',
        verbose_name='Следующая сцена'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок',
        help_text='Чем меньше число, тем выше кнопка'
    )
    
    required_flag = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Требуемый флаг'
    )

    set_flag = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Установить флаг',
        help_text='Например: has_shard'
    )

    class Meta:
        verbose_name = 'Выбор'
        verbose_name_plural = 'Выборы'
        ordering = ['scene', 'order']

    def __str__(self):
        return f'{self.text} → {self.next_scene.slug if self.next_scene else "конец"}'


class Flag(models.Model):
    """Флаг — отметка о действии игрока в сюжете"""
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='flags',
        verbose_name='Игрок'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название флага',
        help_text='Например: has_shard, saved_kultist'
    )
    value = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Значение',
        help_text='Обычно "1", но может быть любым'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Установлен')
    
    class Meta:
        verbose_name = 'Флаг'
        verbose_name_plural = 'Флаги'
        unique_together = [['player', 'name']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.player.user.username}: {self.name}={self.value}'


class Item(models.Model):
    """Предмет — оружие, броня, зелье, ресурс"""
    
    ITEM_TYPES = [
        ('weapon', 'Оружие'),
        ('armor', 'Броня'),
        ('potion', 'Зелье'),
        ('resource', 'Ресурс'),
        ('recipe', 'Свиток (Рецепт)'),
        ('quest', 'Квестовый'),
        ('misc', 'Разное'),
    ]
    
    RARITIES = [
        ('common', 'Обычный'),
        ('uncommon', 'Необычный'),
        ('rare', 'Редкий'),
        ('epic', 'Эпический'),
        ('legendary', 'Легендарный'),
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название'
    )

    effect_type = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Тип эффекта',
        help_text='heal_hp, heal_mp и т.д.'
    )
    effect_value = models.IntegerField(
        default=0,
        verbose_name='Значение эффекта'
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name='Идентификатор (slug)'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Иконка'
    )
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPES,
        default='misc',
        verbose_name='Тип'
    )
    rarity = models.CharField(
        max_length=20,
        choices=RARITIES,
        default='common',
        verbose_name='Редкость'
    )
    price = models.IntegerField(
        default=0,
        verbose_name='Цена',
        help_text='В золоте'
    )

    required_classes = models.ManyToManyField(
        CharacterClass,
        blank=True,
        related_name='equipment_items',
        verbose_name='Требуемые классы',
        help_text='Пусто = любой класс'
    )
    required_level = models.IntegerField(
        default=1,
        verbose_name='Требуемый уровень'
    )
    equip_slot = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('weapon', 'Оружие'),
            ('armor', 'Броня'),
            ('helmet', 'Шлем'),
            ('ring', 'Кольцо'),
            ('amulet', 'Амулет'),
        ],
        verbose_name='Слот'
    )
    image_path = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='Путь к картинке',
        help_text='Например: items/rusty_sword.png (без assets/images/)'
    )
    # --- ПОЛЯ ДЛЯ РЕСУРСОВ (добавлено) ---
    max_stack = models.IntegerField(
        default=999, 
        verbose_name='Макс. в стаке',
        help_text='Сколько ресурсов может лежать в одной ячейке'
    )
    scroll_unlock = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='unlocked_by_scroll',
        verbose_name='Привязан к свитку',
        help_text='Выбери свиток крафта. Если пусто — ресурс падает просто так.'
    )
    bonus_strength = models.IntegerField(default=0, verbose_name='+ Сила')
    bonus_agility = models.IntegerField(default=0, verbose_name='+ Ловкость')
    bonus_intelligence = models.IntegerField(default=0, verbose_name='+ Интеллект')
    bonus_endurance = models.IntegerField(default=0, verbose_name='+ Выносливость')
    bonus_sanity = models.IntegerField(default=0, verbose_name='+ Рассудок')
    bonus_health = models.IntegerField(default=0, verbose_name='+ Здоровье (HP)')
    bonus_mana = models.IntegerField(default=0, verbose_name='+ Мана (MP)')
    
    class Meta:
        verbose_name = 'Предмет'
        verbose_name_plural = 'Предметы'
        ordering = ['item_type', 'name']
    
    def __str__(self):
        return f'{self.name} ({self.get_rarity_display()})'


class Inventory(models.Model):
    """Предмет в инвентаре игрока"""
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='inventory',
        verbose_name='Игрок'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        verbose_name='Предмет'
    )
    quantity = models.IntegerField(
        default=1,
        verbose_name='Количество'
    )
    is_equipped = models.BooleanField(
        default=False,
        verbose_name='Экипирован'
    )
    
    acquired_at = models.DateTimeField(auto_now_add=True, verbose_name='Получен')
    
    class Meta:
        verbose_name = 'Предмет в инвентаре'
        verbose_name_plural = 'Инвентари'
        unique_together = [['player', 'item']]
        ordering = ['-acquired_at']
    
    def __str__(self):
        return f'{self.player.user.username}: {self.item.name} x{self.quantity}'


class Location(models.Model):
    """Локация — регион на карте мира"""
    
    LOCATION_TYPES = [
        ('farm', 'Фарм (Охота)'),
        ('trade', 'Торговая'),
        ('story', 'Сюжетная'),
        ('dungeon', 'Подземелье'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(max_length=100, blank=True, verbose_name='Иконка')
    
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPES,
        default='farm',
        verbose_name='Тип локации',
        help_text='Определяет, что откроется при входе в локацию'
    )
    
    min_level = models.IntegerField(default=1, verbose_name='Мин. уровень')
    is_available = models.BooleanField(default=True, verbose_name='Доступна')
    
    # Исправлены дубликаты map_x и map_y
    map_x = models.IntegerField(default=0, verbose_name='X на карте')
    map_y = models.IntegerField(default=0, verbose_name='Y на карте')
    
    # 🆕 ДОБАВЬ ЭТИ ДВЕ СТРОЧКИ В КОНЕЦ КЛАССА:
    is_guild_only = models.BooleanField(default=False, verbose_name='Только для гильдии')
    guild = models.ForeignKey(
        'guilds.Guild', on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='locations', verbose_name='Гильдия (если закрытая)'
    )
    class Meta:
        verbose_name = 'Локация'
        verbose_name_plural = 'Локации'
        ordering = ['min_level']
    
    def __str__(self):
        return f'{self.name} (ур. {self.min_level}+) [{self.get_location_type_display()}]'


class Enemy(models.Model):
    """Враг — монстр в локации"""
    
    ENEMY_TYPES = [
        ('normal', 'Обычный'),
        ('elite', 'Элитный'),
        ('boss', 'Босс'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Имя')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(max_length=100, blank=True, verbose_name='Иконка')
    
    enemy_type = models.CharField(
        max_length=20,
        choices=ENEMY_TYPES,
        default='normal',
        verbose_name='Тип'
    )
    scale = models.FloatField(
        default=1.0, 
        verbose_name="Масштаб",
        help_text="1.0 = стандартный размер. 1.5 = больше на 50%. 0.5 = меньше на 50%."
    )
    
    location = models.ForeignKey(
        'Location',
        on_delete=models.CASCADE,
        related_name='enemies',
        verbose_name='Локация',
        null=True,
        blank=True
    )
    flip_image = models.BooleanField(
        default=False, 
        verbose_name='Отразить картинку (смотрит влево)',
        help_text='Включи, если враг смотрит не в ту сторону'
    )
    
    level = models.IntegerField(default=1, verbose_name='Уровень')
    health = models.IntegerField(default=50, verbose_name='HP')
    attack = models.IntegerField(default=5, verbose_name='Атака')
    defense = models.IntegerField(default=0, verbose_name='Защита')
    
    xp_reward = models.IntegerField(default=10, verbose_name='Опыт')
    gold_reward = models.IntegerField(default=5, verbose_name='Золото')
    
    abilities = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Способности',
        help_text='Например: {"poison": true, "summon_wolves": 3}'
    )
    image_path = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='Путь к картинке',
        help_text='Например: characters/enemies/dragon.png (без assets/images/)'
    )
    bg_image_path = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='Фон арены',
        help_text='Например: ui/battle_forest.png'
    )
    
    class Meta:
        verbose_name = 'Враг'
        verbose_name_plural = 'Враги'
        ordering = ['location', 'level']
    
    def __str__(self):
        return f'{self.name} (ур. {self.level})'


class Combat(models.Model):
    """Активный бой игрока"""
    
    STATUSES = [
        ('active', 'Активен'),
        ('won', 'Победа'),
        ('lost', 'Поражение'),
        ('fled', 'Побег'),
    ]
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='combats',
        verbose_name='Игрок'
    )
    enemy = models.ForeignKey(
        Enemy,
        on_delete=models.CASCADE,
        verbose_name='Враг'
    )
    
    player_hp = models.IntegerField(verbose_name='HP игрока')
    enemy_hp = models.IntegerField(verbose_name='HP врага')
    
    turn = models.IntegerField(default=1, verbose_name='Ход')
    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default='active',
        verbose_name='Статус'
    )
    
    log = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Лог боя',
        help_text='История ходов'
    )
    
    boss_state = models.JSONField(default=dict, blank=True, verbose_name='Состояние босса')
    
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Бой'
        verbose_name_plural = 'Бои'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.player.user.username} vs {self.enemy.name} ({self.status})'


class Trader(models.Model):
    """Торговец в Мире Торговли"""
    
    name = models.CharField(max_length=100, verbose_name='Имя')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(max_length=100, blank=True, verbose_name='Иконка')
    
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='traders',
        verbose_name='Локация'
    )
    
    items = models.ManyToManyField(
        Item,
        blank=True,
        related_name='traders',
        verbose_name='Товары'
    )
    
    markup = models.FloatField(default=1.0, verbose_name='Наценка')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    class Meta:
        verbose_name = 'Торговец'
        verbose_name_plural = 'Торговцы'
    
    def __str__(self):
        return f'{self.name} ({self.location.name})'


class EquipmentSlot(models.Model):
    """Экипировка игрока — что надето"""
    
    SLOTS = [
        ('weapon', 'Оружие'),
        ('armor', 'Броня'),
        ('helmet', 'Шлем'),
        ('ring', 'Кольцо'),
        ('amulet', 'Амулет'),
    ]
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='equipment',
        verbose_name='Игрок'
    )
    slot = models.CharField(
        max_length=20,
        choices=SLOTS,
        verbose_name='Слот'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Предмет'
    )
    equipped_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Экипировка'
        verbose_name_plural = 'Экипировка'
        unique_together = [['player', 'slot']]
    
    def __str__(self):
        return f'{self.player.user.username} — {self.slot}: {self.item.name if self.item else "пусто"}'
    

class EnemyLoot(models.Model):
    """Настройка выпадения предметов с конкретного врага"""
    
    enemy = models.ForeignKey(
        Enemy, 
        on_delete=models.CASCADE, 
        related_name='loot_table',
        verbose_name='Враг'
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        verbose_name='Выпадающий предмет'
    )
    
    min_enemy_level = models.IntegerField(
        default=1, 
        verbose_name='Мин. уровень моба'
    )
    max_enemy_level = models.IntegerField(
        default=100, 
        verbose_name='Макс. уровень моба'
    )
    
    chance = models.IntegerField(
        default=10, 
        verbose_name='Шанс выпадения (%)',
        help_text='От 1 до 100. 100 = падает всегда.'
    )
    quantity_min = models.IntegerField(default=1, verbose_name='Мин. количество')
    quantity_max = models.IntegerField(default=1, verbose_name='Макс. количество')

    class Meta:
        verbose_name = 'Лут с врага'
        verbose_name_plural = 'Таблицы лута'
        unique_together = [['enemy', 'item', 'min_enemy_level', 'max_enemy_level']]
        ordering = ['enemy', 'min_enemy_level']

    def __str__(self):
        return f'{self.enemy.name} (Ур. {self.min_enemy_level}-{self.max_enemy_level}) -> {self.item.name} ({self.chance}%)'


# ==========================================
# 🧙‍♂️ СИСТЕМА NPC И ДИАЛОГОВ
# ==========================================

class NPC(models.Model):
    name = models.CharField(max_length=100, verbose_name='Имя NPC')
    slug = models.SlugField(unique=True, verbose_name='Slug (для кода)')
    description = models.TextField(blank=True, verbose_name='Описание (для админки)')
    image_path = models.CharField(max_length=200, blank=True, verbose_name='Путь к аватарке', help_text='Например: npc/blacksmith.png')
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Локация')
    
    greeting_text = models.TextField(verbose_name='Приветствие', help_text='Текст, который NPC говорит при встрече')
    post_quest_dialogue = models.TextField(
        blank=True,
        verbose_name='Диалог после сдачи квеста',
        help_text='Что NPC скажет после того, как вы сдадите ему квест.'
    )

    class Meta:
        verbose_name = 'NPC'
        verbose_name_plural = 'NPC (Персонажи)'
        ordering = ['name']

    def __str__(self):
        return self.name


class DialogueOption(models.Model):
    """Варианты ответов в диалоге с NPC (включая выдачу квестов)"""
    npc = models.ForeignKey(NPC, on_delete=models.CASCADE, related_name='dialogue_options', verbose_name='NPC')
    text = models.CharField(max_length=200, verbose_name='Текст кнопки', help_text='Например: "Дай мне работу"')
    response_text = models.TextField(verbose_name='Ответ NPC', help_text='Что NPC скажет после нажатия')
    order = models.IntegerField(default=0, verbose_name='Порядок кнопок')
    
    gives_quest = models.ForeignKey('Quest', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Выдает квест')

    class Meta:
        verbose_name = 'Вариант диалога'
        verbose_name_plural = 'Варианты диалогов'
        ordering = ['order']


# ==========================================
# 📜 СИСТЕМА КВЕСТОВ (ВЕТКИ)
# ==========================================

class QuestLine(models.Model):
    """Квестовая линия (ветка), объединяющая квесты в цепочку"""
    title = models.CharField(max_length=200, verbose_name='Название линии', help_text='Например: Спасти деревню')
    slug = models.SlugField(unique=True, verbose_name='Slug линии')
    description = models.TextField(blank=True, verbose_name='Описание для себя')

    class Meta:
        verbose_name = 'Квестовая линия (Ветка)'
        verbose_name_plural = 'Квестовые линии (Ветки)'

    def __str__(self):
        return self.title


class Quest(models.Model):
    title = models.CharField(max_length=200, verbose_name='Название квеста')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    description = models.TextField(verbose_name='Описание задачи', help_text='Что нужно сделать игроку')
    
    # Привязка к NPC
    giver_npc = models.ForeignKey(NPC, on_delete=models.SET_NULL, null=True, blank=True, related_name='quests_given', verbose_name='Кто выдает квест')
    turn_in_npc = models.ForeignKey(NPC, on_delete=models.SET_NULL, null=True, blank=True, related_name='quests_turned_in', verbose_name='Кому сдавать', help_text='Оставь пустым, если сдает тому же, кто выдал')
    
    required_level = models.IntegerField(default=1, verbose_name='Мин. уровень')
    is_repeatable = models.BooleanField(default=False, verbose_name='Можно повторять')
    
    # 🆕 ПРИВЯЗКА К ЛИНИИ (ВЕТКЕ)
    quest_line = models.ForeignKey(
        QuestLine, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='quests', 
        verbose_name='Квестовая линия',
        help_text='Если это часть сюжетной ветки, выбери её здесь.'
    )
    order_in_line = models.IntegerField(
        default=1, 
        verbose_name='Порядок в линии',
        help_text='Шаг 1, Шаг 2 и т.д. Игра будет выдавать их по порядку.'
    )
    
    # --- НАГРАДЫ ---
    reward_exp = models.IntegerField(default=0, verbose_name='Награда: Опыт')
    reward_gold = models.IntegerField(default=0, verbose_name='Награда: Золото')
    reward_item = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True, blank=True, related_name='quest_reward_items', verbose_name='Награда: Предмет')
    reward_item_qty = models.IntegerField(default=1, verbose_name='Количество предметов')
    reward_resource = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True, blank=True, related_name='quest_reward_resources', verbose_name='Награда: Ресурс')
    reward_resource_qty = models.IntegerField(default=1, verbose_name='Количество ресурсов')
    reward_vip_days = models.IntegerField(default=0, verbose_name='Награда: VIP (дней)', help_text='0 = без VIP. 1 = на 1 день и т.д.')
    
    class Meta:
        verbose_name = 'Квест'
        verbose_name_plural = 'Квесты'
        ordering = ['required_level']

    def __str__(self):
        if self.quest_line:
            return f"[{self.quest_line.title}] Шаг {self.order_in_line}: {self.title}"
        return self.title


class QuestObjective(models.Model):
    """Шаги квеста (убить X мобов, собрать Y предметов)"""
    OBJECTIVE_TYPES = [
        ('kill', 'Убить моба'),
        ('collect', 'Собрать предмет'),
    ]
    
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name='objectives', verbose_name='Квест')
    order = models.IntegerField(default=1, verbose_name='Порядок шага')
    objective_type = models.CharField(max_length=20, choices=OBJECTIVE_TYPES, verbose_name='Тип задачи')
    
    target_enemy = models.ForeignKey('Enemy', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Цель (Моб)')
    target_item = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Цель (Предмет)')
    
    required_count = models.IntegerField(default=1, verbose_name='Сколько нужно')

    class Meta:
        verbose_name = 'Шаг квеста'
        verbose_name_plural = 'Шаги квестов'
        ordering = ['quest', 'order']

    def __str__(self):
        return f'{self.quest.title} - Шаг {self.order}'


class PlayerQuest(models.Model):
    """Прогресс игрока по квесту"""
    STATUSES = [
        ('active', 'В процессе'),
        ('ready', 'Готов к сдаче'),
        ('completed', 'Завершен'),
    ]
    
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='quests', verbose_name='Игрок')
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, verbose_name='Квест')
    status = models.CharField(max_length=20, choices=STATUSES, default='active', verbose_name='Статус')
    
    progress_data = models.JSONField(default=dict, verbose_name='Прогресс выполнения')
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Квест игрока'
        verbose_name_plural = 'Квесты игроков'
        unique_together = [['player', 'quest']]
    

# ==========================================
# 🛠 СИСТЕМА КРАФТА
# ==========================================

class Recipe(models.Model):
    """Рецепт крафта предмета"""
    name = models.CharField(max_length=200, verbose_name='Название рецепта')
    description = models.TextField(blank=True, verbose_name='Описание (что крафтим)')
    
    # Привязка к НПС (Коваль, Зельевар и т.д.)
    npc = models.ForeignKey(
        NPC, 
        on_delete=models.CASCADE, 
        related_name='recipes',
        verbose_name='НПС (кто учит)',
        null=True, blank=True
    )
    
    # Что получится в итоге
    result_item = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        related_name='crafted_by_recipes',
        verbose_name='Результат крафта (Предмет)'
    )
    result_quantity = models.IntegerField(default=1, verbose_name='Количество на выходе')
    
    # Свиток, который нужен для изучения
    scroll_item = models.ForeignKey(
        Item, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='learns_recipes',
        verbose_name='Свиток для изучения',
        help_text='Выбери предмет-свиток (тип: Свиток), который откроет этот рецепт.'
    )
    
    required_level = models.IntegerField(default=1, verbose_name='Требуемый уровень игрока')
    gold_cost = models.IntegerField(default=0, verbose_name='Стоимость изучения (золото)')
    
    class Meta:
        verbose_name = 'Рецепт (Крафт)'
        verbose_name_plural = 'Рецепты (Крафт)'
        ordering = ['required_level', 'name']

    def __str__(self):
        return f'{self.name} -> {self.result_item.name}'


class RecipeIngredient(models.Model):
    """Ингредиент для рецепта"""
    recipe = models.ForeignKey(
        Recipe, 
        on_delete=models.CASCADE, 
        related_name='ingredients',
        verbose_name='Рецепт'
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        verbose_name='Необходимый предмет (Ресурс)'
    )
    quantity = models.IntegerField(default=1, verbose_name='Количество')

    class Meta:
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'
        unique_together = [['recipe', 'item']]

    def __str__(self):
        return f'{self.recipe.name}: {self.item.name} x{self.quantity}'


class PlayerRecipe(models.Model):
    """Изученные рецепты игрока"""
    player = models.ForeignKey(
        Player, 
        on_delete=models.CASCADE, 
        related_name='learned_recipes',
        verbose_name='Игрок'
    )
    recipe = models.ForeignKey(
        Recipe, 
        on_delete=models.CASCADE, 
        verbose_name='Рецепт'
    )
    learned_at = models.DateTimeField(auto_now_add=True, verbose_name='Изучен')

    class Meta:
        verbose_name = 'Изученный рецепт'
        verbose_name_plural = 'Изученные рецепты'
        unique_together = [['player', 'recipe']]

    def __str__(self):
        return f'{self.player.user.username} изучил {self.recipe.name}'


class CombatSettings(models.Model):
    """Настройки боевой системы (для гибкого баланса из админки)"""
    crit_chance = models.FloatField(
        default=0.15, 
        verbose_name="Шанс крита (0.0 - 1.0)",
        help_text="0.15 = 15%"
    )
    crit_multiplier = models.FloatField(
        default=1.5, 
        verbose_name="Множитель крита",
        help_text="Во сколько раз увеличивается урон при крите"
    )
    level_diff_penalty_threshold = models.IntegerField(
        default=10,
        verbose_name="Порог разницы уровней (штраф)",
        help_text="Если игрок выше моба на столько уровней, награда режется"
    )
    level_diff_penalty_divider = models.IntegerField(
        default=10,
        verbose_name="Делитель штрафа",
        help_text="Во сколько раз режется награда при большом разрыве"
    )
    level_diff_bonus_threshold = models.IntegerField(
        default=-5,
        verbose_name="Порог разницы уровней (бонус)",
        help_text="Если игрок ниже моба на столько уровней, награда растет"
    )
    level_diff_bonus_multiplier = models.FloatField(
        default=1.5,
        verbose_name="Множитель бонуса",
        help_text="Во сколько раз растет награда при низком уровне"
    )

    class Meta:
        verbose_name = "Настройки боя"
        verbose_name_plural = "Настройки боя"

    def __str__(self):
        return "Настройки боевой системы"


class OnlineHistory(models.Model):
    """История онлайна для графика"""
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")
    online = models.IntegerField(default=0, verbose_name="Онлайн")
    
    class Meta:
        verbose_name = "История онлайна"
        verbose_name_plural = "История онлайна"
        ordering = ['-timestamp']


class PlayerReport(models.Model):
    """Жалоба на игрока"""
    REPORT_REASONS = [
        ('toxic', 'Оскорбления / Токсичность'),
        ('spam', 'Спам / Реклама'),
        ('cheat', 'Читерство / Взлом'),
        ('other', 'Другое'),
    ]
    
    reporter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='reports_sent', verbose_name='Кто пожаловался')
    target = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='reports_received', verbose_name='На кого жалуются')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS, verbose_name='Причина')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    is_resolved = models.BooleanField(default=False, verbose_name='Обработана')
    moderator_comment = models.TextField(blank=True, verbose_name='Ответ модератора')
    
    class Meta:
        verbose_name = 'Жалоба'
        verbose_name_plural = 'Жалобы'
        ordering = ['-created_at']

class PlayerNotification(models.Model):
    """Уведомления для игроков (ответы модераторов, системные сообщения)"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='notifications', verbose_name='Игрок')
    title = models.CharField(max_length=100, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Текст уведомления')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.player.user.username} - {self.title}'
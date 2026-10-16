from django.db import models
from django.contrib.auth.models import User


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

    # Статы
    strength = models.IntegerField(default=10, verbose_name='Сила')
    agility = models.IntegerField(default=10, verbose_name='Ловкость')
    intelligence = models.IntegerField(default=10, verbose_name='Интеллект')
    endurance = models.IntegerField(default=10, verbose_name='Выносливость')
    sanity = models.IntegerField(default=10, verbose_name='Рассудок')

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
    
    # Условие для показа (временно не используется.).
    required_flag = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Требуемый флаг'
    )

    # Что устанавливает этот выбор.
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

        # Эффект предмета
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
    # В модель Item добавь:

    # Для экипировки
    required_class = models.ForeignKey(
        CharacterClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment',
        verbose_name='Требуемый класс',
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
    # Бонусы к статам
    bonus_strength = models.IntegerField(default=0, verbose_name='+ Сила')
    bonus_agility = models.IntegerField(default=0, verbose_name='+ Ловкость')
    bonus_intelligence = models.IntegerField(default=0, verbose_name='+ Интеллект')
    bonus_endurance = models.IntegerField(default=0, verbose_name='+ Выносливость')
    bonus_sanity = models.IntegerField(default=0, verbose_name='+ Рассудок')
    
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
        verbose_name='Экипирован',
        help_text='Только для оружия и брони'
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
    
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(max_length=100, blank=True, verbose_name='Иконка')
    
    min_level = models.IntegerField(default=1, verbose_name='Мин. уровень')
    is_available = models.BooleanField(default=True, verbose_name='Доступна')
    
    # Позиция на карте (для визуала в будущем)
    map_x = models.IntegerField(default=0, verbose_name='X на карте')
    map_y = models.IntegerField(default=0, verbose_name='Y на карте')
    
    class Meta:
        verbose_name = 'Локация'
        verbose_name_plural = 'Локации'
        ordering = ['min_level']
    
    def __str__(self):
        return f'{self.name} (ур. {self.min_level}+)'


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
    
    location = models.ForeignKey(
        'Location',
        on_delete=models.CASCADE,
        related_name='enemies',
        verbose_name='Локация',
        null=True,
        blank=True
    )
    
    level = models.IntegerField(default=1, verbose_name='Уровень')
    health = models.IntegerField(default=50, verbose_name='HP')
    attack = models.IntegerField(default=5, verbose_name='Атака')
    defense = models.IntegerField(default=0, verbose_name='Защита')
    
    # Награды
    xp_reward = models.IntegerField(default=10, verbose_name='Опыт')
    gold_reward = models.IntegerField(default=5, verbose_name='Золото')
    
    # Способности (для боссов)
    abilities = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Способности',
        help_text='Например: {"poison": true, "summon_wolves": 3}'
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
    
    # Для боссов — сколько раз уже призывал, отравлял и т.д.
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
    
    # Какие товары продаёт (ссылки на Item)
    items = models.ManyToManyField(
        Item,
        blank=True,
        related_name='traders',
        verbose_name='Товары'
    )
    
    # Наценка (1.5 = +50%)
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
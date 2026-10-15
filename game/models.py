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
    strenght = models.IntegerField(default=10, verbose_name='Сила')
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
    
    acquired_at = models.DateTimeField(auto_now_add=True, verbose_name='Получен')
    
    class Meta:
        verbose_name = 'Предмет в инвентаре'
        verbose_name_plural = 'Инвентари'
        unique_together = [['player', 'item']]
        ordering = ['-acquired_at']
    
    def __str__(self):
        return f'{self.player.user.username}: {self.item.name} x{self.quantity}'
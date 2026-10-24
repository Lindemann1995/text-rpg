from django.db import models
from django.utils import timezone

from game.models import Player


class GuildRank(models.TextChoices):
    """Ранги внутри гильдии."""
    LEADER = 'leader', 'Лидер'
    DEPUTY = 'deputy', 'Заместитель'
    VETERAN = 'veteran', 'Ветеран'
    NOVICE = 'novice', 'Новичок'


RANK_COLORS = {
    GuildRank.LEADER: '#FFD700',
    GuildRank.DEPUTY: '#C0C0C0',
    GuildRank.VETERAN: '#CD7F32',
    GuildRank.NOVICE: '#FFFFFF',
}


class Guild(models.Model):
    name = models.CharField(max_length=20, unique=True, verbose_name='Название')
    tag = models.CharField(max_length=5, unique=True, verbose_name='Тег')
    leader = models.OneToOneField(Player, on_delete=models.PROTECT, related_name='led_guild', verbose_name='Лидер')
    treasury_gold = models.IntegerField(default=0, verbose_name='Золото в казне')
    level = models.IntegerField(default=1, verbose_name='Уровень гильдии')
    is_open = models.BooleanField(default=True, verbose_name='Открытая')
    banner_preset = models.CharField(max_length=50, blank=True, verbose_name='Штандарт')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    daily_streak = models.IntegerField(default=0, verbose_name='Серия ежедневок')
    last_daily_completed_date = models.DateField(null=True, blank=True, verbose_name='Дата последней серии')
    class Meta:
        verbose_name = 'Гильдия'
        verbose_name_plural = 'Гильдии'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.tag}] {self.name}'


class GuildMember(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='members', verbose_name='Гильдия')
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='guild_membership', verbose_name='Игрок')
    rank = models.CharField(max_length=20, choices=GuildRank.choices, default=GuildRank.NOVICE, verbose_name='Ранг')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='Вступил')
    contributed_gold = models.IntegerField(default=0, verbose_name='Внёс золота')

    class Meta:
        verbose_name = 'Участник гильдии'
        verbose_name_plural = 'Участники гильдий'
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.player.user.username} [{self.get_rank_display()}] в {self.guild.tag}'

    @property
    def rank_color(self):
        return RANK_COLORS.get(self.rank, '#FFFFFF')


class GuildApplication(models.Model):
    STATUSES = [
        ('pending', 'На рассмотрении'),
        ('accepted', 'Принята'),
        ('declined', 'Отклонена'),
    ]
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='applications', verbose_name='Гильдия')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='guild_applications', verbose_name='Игрок')
    status = models.CharField(max_length=20, choices=STATUSES, default='pending', verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Подана')

    class Meta:
        verbose_name = 'Заявка в гильдию'
        verbose_name_plural = 'Заявки в гильдии'
        ordering = ['-created_at']
        unique_together = [['guild', 'player', 'status']]

    def __str__(self):
        return f'{self.player.user.username} → {self.guild.tag} ({self.status})'


class GuildLog(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='logs', verbose_name='Гильдия')
    actor = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Кто сделал')
    action = models.CharField(max_length=50, verbose_name='Действие')
    details = models.TextField(blank=True, verbose_name='Детали')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Когда')

    class Meta:
        verbose_name = 'Лог гильдии'
        verbose_name_plural = 'Логи гильдий'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.guild.tag}] {self.action} — {self.created_at:%d.%m.%Y %H:%M}'


class GuildChatMessage(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='chat_messages', verbose_name='Гильдия')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name='Автор')
    message = models.TextField(verbose_name='Сообщение')
    rank_color = models.CharField(max_length=20, default='#FFFFFF', verbose_name='Цвет ранга')
    tag = models.CharField(max_length=10, default='', verbose_name='Тег гильдии')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')

    class Meta:
        verbose_name = 'Сообщение гильд-чата'
        verbose_name_plural = 'Сообщения гильд-чата'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.guild.tag}] {self.player.user.username}: {self.message[:30]}'


class GuildBankItem(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='bank_items', verbose_name='Гильдия')
    item = models.ForeignKey('game.Item', on_delete=models.CASCADE, verbose_name='Предмет')
    quantity = models.IntegerField(default=0, verbose_name='Количество')

    class Meta:
        verbose_name = 'Ресурс в банке'
        verbose_name_plural = 'Ресурсы в банке'
        unique_together = [['guild', 'item']]
        ordering = ['item__name']

    def __str__(self):
        return f'[{self.guild.tag}] {self.item.name} x{self.quantity}'


class GuildBankLog(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='bank_logs', verbose_name='Гильдия')
    player = models.ForeignKey('game.Player', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Игрок')
    item = models.ForeignKey('game.Item', on_delete=models.SET_NULL, null=True, verbose_name='Предмет')
    quantity = models.IntegerField(verbose_name='Количество')
    action = models.CharField(max_length=20, choices=[('deposit', 'Положил'), ('withdraw', 'Забрал')], verbose_name='Действие')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Когда')

    class Meta:
        verbose_name = 'Лог банка'
        verbose_name_plural = 'Логи банка'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.guild.tag}] {self.player.user.username} {self.action} {self.item.name} x{self.quantity}'


# --- НОВАЯ АРХИТЕКТУРА УЛУЧШЕНИЙ ---

class GuildUpgradeTemplate(models.Model):
    """Глобальный шаблон улучшения."""
    UPGRADE_TYPES = [
        ('war_hall', 'Зал воинов'),
        ('treasury', 'Сокровищница'),
        ('altar', 'Алтарь силы'),
        ('library', 'Библиотека'),
        ('barracks', 'Казарма'),
        ('magic_circle', 'Магический круг'),
        ('forge', 'Кузница'),
        ('hall_of_fame', 'Зал славы'),
        ('warehouse', 'Склад'),
        ('training_yard', 'Тренировочный двор'),
    ]

    upgrade_type = models.CharField(max_length=30, choices=UPGRADE_TYPES, unique=True, verbose_name='Тип улучшения')
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    icon = models.CharField(max_length=10, default='🏰', verbose_name='Иконка (эмодзи)')

    class Meta:
        verbose_name = 'Шаблон улучшения'
        verbose_name_plural = 'Шаблоны улучшений'

    def __str__(self):
        return self.name


class GuildUpgradeLevelCost(models.Model):
    """Стоимость прокачки для конкретного уровня (глобальная)."""
    template = models.ForeignKey(GuildUpgradeTemplate, on_delete=models.CASCADE, related_name='costs', verbose_name='Шаблон')
    target_level = models.IntegerField(verbose_name='Для уровня')
    gold_cost = models.IntegerField(default=0, verbose_name='Золото из казны')
    item = models.ForeignKey('game.Item', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Ресурс из банка')
    quantity = models.IntegerField(default=0, verbose_name='Количество ресурса')

    class Meta:
        verbose_name = 'Стоимость уровня улучшения'
        verbose_name_plural = 'Стоимости уровней'
        unique_together = [['template', 'target_level']]

    def __str__(self):
        res = self.item.name if self.item else 'Без ресурса'
        return f'{self.template.name} ур.{self.target_level}: {self.gold_cost}💰 + {self.quantity} {res}'


class GuildUpgrade(models.Model):
    """Прогресс конкретной гильдии в улучшении."""
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='upgrades', verbose_name='Гильдия')
    template = models.ForeignKey(GuildUpgradeTemplate, on_delete=models.CASCADE, verbose_name='Шаблон улучшения')
    level = models.IntegerField(default=0, verbose_name='Уровень')

    class Meta:
        verbose_name = 'Улучшение гильдии'
        verbose_name_plural = 'Улучшения гильдий'
        unique_together = [['guild', 'template']]

    def __str__(self):
        return f'{self.guild.tag}: {self.template.name} ур.{self.level}'


class Castle(models.Model):
    """Замок на карте мира."""
    name = models.CharField(max_length=100, verbose_name='Название замка')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Слаг (для кода)')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Визуал
    image_path = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='Путь к картинке',
        help_text='Например: map/castle_dark.png (без assets/images/)'
    )
    
    # Координаты для карты (в процентах от 0.0 до 1.0)
    map_x = models.FloatField(default=0.5, verbose_name='X на карте (0.0 - 1.0)')
    map_y = models.FloatField(default=0.5, verbose_name='Y на карте (0.0 - 1.0)')
    
    # Владелец
    owner = models.ForeignKey(
        Guild, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='castles',
        verbose_name='Владелец'
    )
    
    # Экономика
    daily_tax = models.IntegerField(default=2000, verbose_name='Ежедневный налог (золото)')
    passive_income = models.IntegerField(default=1500, verbose_name='Пассивный доход (золото/день)')
    defense_level = models.IntegerField(default=1, verbose_name='Уровень защиты (гарнизон НПС)')
    
    # Баффы владельцу
    buff_xp_percent = models.IntegerField(default=10, verbose_name='Бафф: % к опыту')
    buff_gold_percent = models.IntegerField(default=10, verbose_name='Бафф: % к золоту')

    last_tax_collected = models.DateTimeField(null=True, blank=True, verbose_name='Последний сбор налогов')
    debt_deadline = models.DateTimeField(null=True, blank=True, verbose_name='Дедлайн по долгу')
    siege_cooldown_until = models.DateTimeField(null=True, blank=True, verbose_name='КД на осаду до')

    class Meta:
        verbose_name = 'Замок'
        verbose_name_plural = 'Замки'
        ordering = ['name']

    def __str__(self):
        status = f'[{self.owner.tag}]' if self.owner else '[Свободен]'
        return f'{status} {self.name}'


class CastleSiege(models.Model):
    """Активная осада замка (инстанс)."""
    STATUSES = [
        ('active', 'Активна'),
        ('won', 'Победа атакующих'),
        ('lost', 'Победа защитников'),
    ]
    
    castle = models.ForeignKey(Castle, on_delete=models.CASCADE, related_name='sieges', verbose_name='Замок')
    attacker_guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='attacks', verbose_name='Атакующая гильдия')
    defender_guild = models.ForeignKey(Guild, on_delete=models.SET_NULL, null=True, blank=True, related_name='defenses', verbose_name='Защищающаяся гильдия')
    
    status = models.CharField(max_length=20, choices=STATUSES, default='active', verbose_name='Статус')
    
    # Состояние боя
    current_enemy_index = models.IntegerField(default=0, verbose_name='Индекс текущего врага')
    player_hp = models.IntegerField(default=0, verbose_name='HP игрока в осаде')
    log = models.JSONField(default=list, blank=True, verbose_name='Лог боя')
    
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Начало')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Конец')

    class Meta:
        verbose_name = 'Осада замка'
        verbose_name_plural = 'Осады замков'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.attacker_guild.tag} → {self.castle.name} ({self.status})'


class SiegeEnemy(models.Model):
    """НПС-защитник в осаде."""
    siege = models.ForeignKey(CastleSiege, on_delete=models.CASCADE, related_name='enemies', verbose_name='Осада')
    name = models.CharField(max_length=100, verbose_name='Имя')
    health = models.IntegerField(verbose_name='HP')
    max_health = models.IntegerField(verbose_name='Макс. HP')
    attack = models.IntegerField(verbose_name='Атака')
    defense = models.IntegerField(verbose_name='Защита')
    is_dead = models.BooleanField(default=False, verbose_name='Убит')

    class Meta:
        verbose_name = 'Защитник осады'
        verbose_name_plural = 'Защитники осады'
        ordering = ['id']

    def __str__(self):
        return f'{self.name} (HP: {self.health}/{self.max_health})'

class GuildUISettings(models.Model):
    """Настройки визуала гильдии (иконки для кнопок)."""
    name = models.CharField(max_length=50, default='Настройки UI', verbose_name='Название')
    
    # Иконки для кнопок (пути к картинкам)
    icon_taxes = models.CharField(
        max_length=200, 
        default='ui/icons/taxes.png', 
        verbose_name='Иконка "Налоги"',
        help_text='Например: ui/icons/taxes.png'
    )
    icon_bank = models.CharField(
        max_length=200, 
        default='ui/icons/bank.png', 
        verbose_name='Иконка "Банк"',
        help_text='Например: ui/icons/bank.png'
    )
    icon_war = models.CharField(
        max_length=200, 
        default='ui/icons/war.png', 
        verbose_name='Иконка "Кузня"',
        help_text='Например: ui/icons/war.png'
    )
    icon_members = models.CharField(
        max_length=200, 
        default='ui/icons/members.png', 
        verbose_name='Иконка "Состав"',
        help_text='Например: ui/icons/members.png'
    )
    icon_chat = models.CharField(
        max_length=200, 
        default='ui/icons/chat.png', 
        verbose_name='Иконка "Чат"',
        help_text='Например: ui/icons/chat.png'
    )
    icon_castle = models.CharField(
        max_length=200, 
        default='ui/icons/castle.png', 
        verbose_name='Иконка "Замки"',
        help_text='Например: ui/icons/castle.png'
    )
    icon_applications = models.CharField(
        max_length=200, 
        default='ui/icons/applications.png', 
        verbose_name='Иконка "Заявки"',
        help_text='Например: ui/icons/applications.png'
    )

    class Meta:
        verbose_name = 'Настройки UI гильдии'
        verbose_name_plural = 'Настройки UI гильдий'

    def __str__(self):
        return self.name
    
class Duel(models.Model):
    """PvP-дуэль между двумя игроками."""
    STATUSES = [
        ('pending', 'Ожидание'),
        ('active', 'Активна'),
        ('finished', 'Завершена'),
        ('declined', 'Отклонена'),
    ]
    
    challenger = models.ForeignKey(
        Player, 
        on_delete=models.CASCADE, 
        related_name='duels_challenged',
        verbose_name='Вызывающий'
    )
    opponent = models.ForeignKey(
        Player, 
        on_delete=models.CASCADE, 
        related_name='duels_received',
        verbose_name='Противник'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUSES, 
        default='pending',
        verbose_name='Статус'
    )
    
    # Состояние боя
    challenger_hp = models.IntegerField(default=100, verbose_name='HP вызывающего')
    opponent_hp = models.IntegerField(default=100, verbose_name='HP противника')
    turn = models.IntegerField(default=1, verbose_name='Ход')
    current_turn = models.CharField(
        max_length=20, 
        choices=[('challenger', 'Вызывающий'), ('opponent', 'Противник')],
        default='challenger',
        verbose_name='Чей ход'
    )
    log = models.JSONField(default=list, blank=True, verbose_name='Лог боя')
    
    winner = models.ForeignKey(
        Player, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='duels_won',
        verbose_name='Победитель'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершена')

    class Meta:
        verbose_name = 'PvP Дуэль'
        verbose_name_plural = 'PvP Дуэли'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.challenger.user.username} vs {self.opponent.user.username} ({self.status})'

class GuildDailyQuestTemplate(models.Model):
    """Шаблон ежедневного гильдейского квеста (создается в админке)"""
    title = models.CharField(max_length=200, verbose_name='Название квеста')
    description = models.TextField(verbose_name='Описание')
    image_path = models.CharField(
        max_length=200, blank=True, verbose_name='Путь к картинке',
        help_text='Например: quests/daily_wolves.png'
    )
    target_enemy = models.ForeignKey(
        'game.Enemy', on_delete=models.CASCADE, 
        verbose_name='Какого моба бить'
    )
    required_count = models.IntegerField(default=50, verbose_name='Сколько нужно убить')
    
    # Награды
    reward_gold_player = models.IntegerField(default=100, verbose_name='Золото каждому сдавшему')
    reward_gold_treasury = models.IntegerField(default=500, verbose_name='Золото в казну гильдии')
    reward_exp = models.IntegerField(default=100, verbose_name='Опыт игроку')
    
    difficulty = models.IntegerField(default=1, verbose_name='Сложность (1-10)')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Шаблон ежедневки гильдии'
        verbose_name_plural = 'Шаблоны ежедневок гильдии'
        ordering = ['-difficulty']

    def __str__(self):
        return f'{self.title} ({self.target_enemy.name} x{self.required_count})'


class GuildDailyQuest(models.Model):
    """Конкретный квест на сегодня для конкретной гильдии"""
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name='daily_quests', verbose_name='Гильдия')
    template = models.ForeignKey(GuildDailyQuestTemplate, on_delete=models.CASCADE, verbose_name='Шаблон')
    date = models.DateField(verbose_name='Дата')
    
    progress = models.IntegerField(default=0, verbose_name='Общий прогресс')
    is_completed = models.BooleanField(default=False, verbose_name='Выполнен')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Когда выполнен')

    class Meta:
        verbose_name = 'Ежедневка гильдии'
        verbose_name_plural = 'Ежедневки гильдий'
        unique_together = [['guild', 'template', 'date']]
        ordering = ['date', 'template']

    def __str__(self):
        return f'[{self.guild.tag}] {self.template.title} ({self.progress}/{self.template.required_count})'


class GuildDailyQuestContribution(models.Model):
    """Личный вклад игрока в ежедневку"""
    daily_quest = models.ForeignKey(GuildDailyQuest, on_delete=models.CASCADE, related_name='contributions', verbose_name='Ежедневка')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name='Игрок')
    kills = models.IntegerField(default=0, verbose_name='Убийств')
    is_claimed = models.BooleanField(default=False, verbose_name='Награда получена')

    class Meta:
        verbose_name = 'Вклад в ежедневку'
        verbose_name_plural = 'Вклады в ежедневки'
        unique_together = [['daily_quest', 'player']]
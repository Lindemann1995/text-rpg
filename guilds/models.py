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
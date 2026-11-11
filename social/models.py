from django.db import models
from game.models import Player

class Friendship(models.Model):
    """Заявки в друзья и дружба."""
    STATUSES = [
        ('pending', 'Ожидает подтверждения'),
        ('accepted', 'Друзья'),
        ('declined', 'Отклонена'),
    ]
    
    from_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, 
        related_name='sent_friend_requests', verbose_name='От кого'
    )
    to_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, 
        related_name='received_friend_requests', verbose_name='Кому'
    )
    status = models.CharField(
        max_length=20, choices=STATUSES, default='pending', 
        verbose_name='Статус'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Дружба'
        verbose_name_plural = 'Дружбы'
        unique_together = [['from_player', 'to_player']]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.from_player.user.username} -> {self.to_player.user.username} ({self.status})'


class PrivateMessage(models.Model):
    """Личные сообщения между игроками."""
    sender = models.ForeignKey(
        Player, on_delete=models.CASCADE, 
        related_name='sent_messages', verbose_name='Отправитель'
    )
    receiver = models.ForeignKey(
        Player, on_delete=models.CASCADE, 
        related_name='received_messages', verbose_name='Получатель'
    )
    message = models.TextField(verbose_name='Текст сообщения')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')

    class Meta:
        verbose_name = 'Личное сообщение'
        verbose_name_plural = 'Личные сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.user.username} -> {self.receiver.user.username}: {self.message[:20]}'

class GlobalChatMessage(models.Model):
    """Сообщения глобального чата."""
    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, 
        related_name='global_messages', verbose_name='Игрок'
    )
    message = models.TextField(verbose_name='Сообщение')
    
    # 🆕 ДОБАВЛЯЕМ ЭТУ СТРОКУ:
    author_color = models.CharField(
        max_length=7, blank=True, default='',
        verbose_name='Цвет автора (денормализовано)',
        help_text='HEX из VIP-статуса на момент отправки. Пусто = дефолт.'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')

    class Meta:
        verbose_name = 'Сообщение глобального чата'
        verbose_name_plural = 'Сообщения глобального чата'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.player.user.username}: {self.message[:20]}'
from django.core.management.base import BaseCommand
from game.services.vip import check_expiry_warning, expire_vips

class Command(BaseCommand):
    help = 'Проверяет истечение VIP-статусов и шлёт уведомления.'

    def handle(self, *args, **options):
        warned = check_expiry_warning()
        self.stdout.write(self.style.SUCCESS(f'Предупреждений за 24ч: {warned}'))
        expired = expire_vips()
        self.stdout.write(self.style.SUCCESS(f'Обработано истёкших: {expired}'))
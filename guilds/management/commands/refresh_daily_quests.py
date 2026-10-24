from django.core.management.base import BaseCommand
from guilds.services import process_daily_quests_reset

class Command(BaseCommand):
    help = 'Обновляет ежедневные задания гильдий (в 23:59)'

    def handle(self, *args, **options):
        self.stdout.write("Запуск обновления ежедневок...")
        process_daily_quests_reset()
        self.stdout.write(self.style.SUCCESS("Ежедневки успешно обновлены!"))
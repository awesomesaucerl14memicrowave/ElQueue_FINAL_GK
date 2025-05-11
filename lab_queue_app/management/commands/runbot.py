from django.core.management.base import BaseCommand
from bot import main  # Импортируем функцию из bot.py

class Command(BaseCommand):
    help = 'Запускает Telegram-бота'

    def handle(self, *args, **options):
        main()

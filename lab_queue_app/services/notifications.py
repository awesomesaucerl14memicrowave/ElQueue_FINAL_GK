from django.conf import settings
import telegram
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class NotificationService:
    def __init__(self):
        self.channel_layer = get_channel_layer()
        if hasattr(settings, 'TELEGRAM_BOT_TOKEN'):
            self.bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        else:
            self.bot = None

    def send_browser_notification(self, user, message, notification_type):
        """Отправка браузерного уведомления"""
        profile = user.profile
        
        # Проверяем, включены ли уведомления данного типа
        if not profile.browser_notifications:
            return
            
        if not getattr(profile, f'browser_{notification_type}', True):
            return
            
        async_to_sync(self.channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_notification",
                "message": message
            }
        )

    def send_telegram_notification(self, user, message, notification_type):
        """Отправка уведомления в Telegram"""
        if not self.bot:
            return
            
        profile = user.profile
        
        # Проверяем, включены ли уведомления в Telegram
        if not profile.telegram_notifications or not profile.telegram_id:
            return
            
        if not getattr(profile, f'telegram_{notification_type}', True):
            return
            
        try:
            self.bot.send_message(
                chat_id=profile.telegram_id,
                text=message,
                parse_mode='HTML'
            )
        except telegram.error.TelegramError:
            # Логирование ошибки если нужно
            pass

    def notify_queue_join_leave(self, user, action, queue_name):
        """Уведомление о входе/выходе из очереди"""
        message = f"Вы {'вошли в' if action == 'join' else 'вышли из'} очередь: {queue_name}"
        self.send_browser_notification(user, message, 'queue_join_leave')
        self.send_telegram_notification(user, message, 'queue_join_leave')

    def notify_position_change(self, user, queue_name, new_position, old_position):
        """Уведомление об изменении позиции"""
        message = f"Ваша позиция в очереди {queue_name} изменилась: {old_position} → {new_position}"
        self.send_browser_notification(user, message, 'position_change')
        self.send_telegram_notification(user, message, 'position_change')

    def notify_position_milestone(self, user, queue_name, position):
        """Уведомление о достижении определенной позиции"""
        if position in [2, 3]:
            message = f"Осталось совсем немного! Ваша позиция в очереди {queue_name}: {position}"
            self.send_browser_notification(user, message, 'position_3_2')
            self.send_telegram_notification(user, message, 'position_3_2')
        elif position == 1:
            message = f"Вы следующий! Ваша позиция в очереди {queue_name}: {position}"
            self.send_browser_notification(user, message, 'position_1')
            self.send_telegram_notification(user, message, 'position_1')

notification_service = NotificationService() 
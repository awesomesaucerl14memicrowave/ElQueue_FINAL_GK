import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.user_id = self.scope["user"].id
        self.group_name = f"user_{self.user_id}"

        # Присоединяемся к группе пользователя
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Покидаем группу пользователя
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def send_notification(self, event):
        # Отправляем уведомление в браузер
        await self.send(text_data=json.dumps({
            "type": "notification",
            "message": event["message"]
        })) 
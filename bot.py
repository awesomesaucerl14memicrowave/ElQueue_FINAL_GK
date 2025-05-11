import logging
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from django.core.management import call_command
import django
import os
import sys
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lab_queue.settings')
django.setup()

from lab_queue_app.models import TelegramBindToken, UserProfile, AvatarImage

# Токен бота
TOKEN = '7951386321:AAHxpTDG6yhTRl9ap2uazpy7vX_-9mv1HPw'

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Асинхронные обёртки для ORM
get_bind_token = sync_to_async(TelegramBindToken.objects.get, thread_sensitive=True)
get_user_profile = sync_to_async(lambda user: user.profile, thread_sensitive=True)
save_profile = sync_to_async(UserProfile.save, thread_sensitive=True)
save_bind_token = sync_to_async(TelegramBindToken.save, thread_sensitive=True)
create_avatar_image = sync_to_async(AvatarImage.objects.create, thread_sensitive=True)

async def get_profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        photos = await context.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][0].file_id)
            photo_data = await file.download_as_bytearray()
            return ContentFile(photo_data, name=f"avatar_{user_id}.jpg")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении фото профиля: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args  # Получаем аргументы из /start
    if args:
        token_str = args[0]
        try:
            # Асинхронно получаем токен
            bind_token = await get_bind_token(token=token_str, is_used=False)

            # Асинхронно получаем пользователя и профиль
            user = await sync_to_async(lambda bt: bt.user)(bind_token)
            profile = await get_user_profile(user)
            chat_id = update.effective_chat.id

            # Обновляем и сохраняем профиль
            profile.telegram_id = str(chat_id)
            await save_profile(profile)
            logger.info(f"Профиль сохранён для пользователя {user.username}, telegram_id: {profile.telegram_id}")

            # Получаем и сохраняем аватарку, если она есть
            photo_file = await get_profile_photo(update, context, chat_id)
            if photo_file:
                avatar_image = await create_avatar_image(image=photo_file)
                profile.avatar = avatar_image
                await save_profile(profile)
                logger.info(f"Аватарка сохранена для пользователя {user.username}")

            # Помечаем токен как использованный
            bind_token.is_used = True
            await save_bind_token(bind_token)
            logger.info(f"Токен {token_str} помечен как использованный")

            await update.message.reply_text('Telegram успешно привязан! Теперь ты можешь получать уведомления.')
        except TelegramBindToken.DoesNotExist:
            await update.message.reply_text('Неверный или уже использованный токен.')
        except Exception as e:
            logger.error(f"Ошибка при обработке /start: {e}")
            await update.message.reply_text('Произошла ошибка при привязке.')
    else:
        await update.message.reply_text('Привет! Отправь /start с токеном или используй глубокую ссылку для привязки.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Пожалуйста, используй глубокую ссылку или команду /start с токеном для привязки.')

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
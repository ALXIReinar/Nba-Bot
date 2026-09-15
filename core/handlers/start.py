from aiogram.types import Message
from redis.asyncio import Redis

from core.config_dir.config import bot, env
from core.data.postgres import PgSql
from core.utils.anything import RedisKeys


async def on_startup():
    # log_event('Бот запущен', level='WARNING')
    await bot.send_message(env.admin_tg_id, 'Бот запущен!')


async def start_handler(message: Message, redis: Redis, db: PgSql):
    """Пример хендлера с использованием редис и БД"""
    
    # Автоматическая регистрация/обновление пользователя
    user = message.from_user

    await message.answer(f"Send Hello")

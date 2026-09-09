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

    await redis.set(RedisKeys.important_key(message.from_user.id), 1)

    any_data = await db.cards.get_all_cards()

    await message.answer(f"Start Message! DB Cards: {any_data}")

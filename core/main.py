import asyncio

from aiogram import Dispatcher
from aiogram.filters import Command
from asyncpg import create_pool
from redis.asyncio import Redis

from core.config_dir.config import bot, redis_settings, pool_settings
from core.handlers.middlewares.pg_middleware import PostgresMiddleware
# from core.handlers.callback_center import callback_factory
from core.handlers.start import start_handler, on_startup

dp = Dispatcher()


async def main():
    """"""
    "PostgreSQL"
    db_pool = await create_pool(**pool_settings)
    dp.update.middleware.register(PostgresMiddleware(db_pool))

    "Redis"
    redis_conn = Redis(**redis_settings, decode_responses=True)

    "Команды"
    dp.message.register(start_handler, Command('start'))

    "Коллбэки"
    # dp.callback_query.register(callback_factory) # Не подключаем, т.к. не имеет отношения к коду этого проекта

    dp.startup.register(on_startup)
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            redis=redis_conn,
        )
    finally:
        await db_pool.close()
        await redis_conn.aclose()



if __name__ == '__main__':
    asyncio.run(main())
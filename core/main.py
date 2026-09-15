import asyncio

from aiogram.filters import Command
from asyncpg import create_pool
from redis.asyncio import Redis

from core.config_dir.config import bot, dp, redis_settings, pool_settings
from core.handlers.middlewares.pg_middleware import PostgresMiddleware
from core.handlers.middlewares.online_match_middleware import OnlineMatchMiddleware
from core.handlers.start import start_handler, on_startup
from core.handlers.online_5v5.router import router as online_router
from core.utils.online_timeouts import scheduler


async def main():
    """"""
    "PostgreSQL"
    db_pool = await create_pool(**pool_settings)
    db_mware = PostgresMiddleware(db_pool)
    dp.update.middleware.register(db_mware)
    # await db_mware.cards_init() # Для заполнения глобальных переменных словарей. Нигде не используются, поэтому выключено

    "Redis"
    redis_conn = Redis(**redis_settings, decode_responses=True)
    await redis_conn.flushall()

    "Middlewares"
    online_match_mware = OnlineMatchMiddleware()
    dp.message.middleware.register(online_match_mware)
    dp.callback_query.middleware.register(online_match_mware)

    "Команды"
    dp.message.register(start_handler, Command('start'))

    "Коллбэки"

    "Роутеры"
    dp.include_router(online_router)

    "APScheduler"
    scheduler.start()

    dp.startup.register(on_startup)
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            redis=redis_conn,
        )
    finally:
        scheduler.shutdown()
        await db_pool.close()
        await redis_conn.aclose()



if __name__ == '__main__':
    asyncio.run(main())
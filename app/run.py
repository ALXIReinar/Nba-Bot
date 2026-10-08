import asyncio

import psycopg2
# import app.old_core.schedule as schedule
# from aiogram.types import Update

from app.core.bot import bot, logger
from app.core.bot import dp, Dispatcher

from app.core.middleware.postgres import PostgresMiddleware
from app.db.postgres import PgSql
from app.core.services import Services

# from old.handlers.main import router as router_main
# from old.handlers.getcard import router as router_getcard
# from old.handlers.crosstep.watchcards import router as router_watchcards
# from old.handlers.crosstep.workshop.workshop import router as router_workshop
# from old.handlers.crosstep.workshop.rubbish import router as router_rubbish
# from old.handlers.crosstep.workshop.craft import router as router_craft
# from old.handlers.crosstep.present import router as router_present
# from app.old_core.handlers.crosstep.throw_ball import router as router_throw_ball
# from app.old_core.handlers.crosstep.trade import router as router_trade
# from old.handlers.crosstep.profile import router as router_profile
# from old.handlers.crosstep.tasks import router as router_tasks
# from app.old_core.handlers.admin_functions import router as router_admin
# from app.modules.game_5v5.online.handlers.middlewares.online_match_middleware import OnlineMatchMiddleware
# from app.old_core.handlers.crosstep.rating.rating_game import router as router_game
# from app.old_core.handlers.crosstep.rating.rating_team import router as router_team
# from app.old_core.handlers.crosstep.packs import router as pack_router
# # from old.handlers.promo import router as promo_router
# from app.old_core.handlers.crosstep.album import router as album_router
# from app.old_core.handlers.crosstep.shop import router as router_shop
# from app.handlers.crosstep.new_year import router as router_new_year

# from app.modules.main.handler import router as main_router
# from app.modules.collection.handler import router as collection_router
# from app.old_core.handlers.crosstep.watchcards import router as watchcards_router
# from app.old_core.handlers.crosstep.handlers_crossstep import router as crossstep_router
# from app.old_core.handlers.crosstep.profile import router as profile_router

# from app.old_core.handlers.crosstep.workshop.workshop import router as workshop_router
# from app.old_core.handlers.crosstep.workshop.rubbish import router as rubbish_router
# from app.old_core.handlers.crosstep.workshop.craft import router as craft_router

# from app.modules.game_5v5.online.handlers.game_5v5.online.router import router as online_router
# from app.modules.game_5v5.online.utils.online_timeouts import scheduler as online_scheduler
# from app.modules.tasks.handler import router as task_router


from aiogram import Dispatcher
import logging

import sys
import os

# import app.old_core.handlers.crosstep.rating.season_manager as season_manage
from app.core.middleware.postgres import PostgresMiddleware
from redis.asyncio import Redis
from app.core.config import pool_settings, redis_settings, env

# from app.middlewares.user_middleware import UserInternalIdMiddleware
from app.core.ImageCache import image_cache
from app.modules.tasks.handler import router as tasks_router
from app.modules.main.handler import router as main_handler_router, on_startup

# Добавляем корневую директорию в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg

async def main():
    db_pool = await asyncpg.create_pool(**pool_settings)

    connection = await asyncpg.connect(
        database=env.postgres_db,
        user=env.postgres_user,
        password=env.postgres_password,
        host=env.postgres_host,
        port=env.postgres_port,)

    db = PgSql(db_pool, connection)

    services = Services(db)
    # await services.init()

    redis_conn = Redis(**redis_settings, decode_responses=True)

    # TODO: в проде такого не должно быть. Эта команда очищает весь редис
    await redis_conn.flushall()

    dp.update.middleware.register(
        PostgresMiddleware(db, services, redis_conn),
    )

    dp.include_router(tasks_router)
    dp.include_router(main_handler_router)

    # dp.update.outer_middleware(UserInternalIdMiddleware(services.users))

    # dp.include_router(main_router)
    # dp.include_router(collection_router)
    # dp.include_router(watchcards_router)
    # dp.include_router(crossstep_router)
    # dp.include_router(profile_router)
    # dp.include_router(workshop_router)
    # dp.include_router(rubbish_router)
    # dp.include_router(craft_router)
    # dp.include_router(router_throw_ball)

    # dp.include_router(router_game)
    # dp.include_router(router_team)
    # dp.include_router(task_router)
    # dp.include_router(router_trade)
    # dp.include_router(pack_router)
    # dp.include_router(router_shop)
    # dp.include_router(router_admin)

    # online_match_mware = OnlineMatchMiddleware()
    # dp.message.middleware.register(online_match_mware)
    # dp.callback_query.middleware.register(online_match_mware)

    # "Роутеры"
    # dp.include_router(online_router)

    # "APScheduler"
    # online_scheduler.start()
    # await schedule.schedule()

    # dp.include_router(router_rubbish)

    # dp.include_router(router_shop)
    # dp.include_router(album_router)
    # dp.include_router(router_craft)
    # dp.include_router(router_present)
    # dp.include_router(router_throw_ball)
    # dp.include_router(router_trade)
    # dp.include_router(router_profile)
    # dp.include_router(router_tasks)
    # dp.include_router(pack_router)
    # dp.include_router(router_admin)
    # dp.include_router(promo_router)
    # dp.include_router(router_new_year)
    # setup_logging(dp)

    logger.info("Started")
    # asyncio.create_task(schedule.schedule())

    # await season_manage.season_manager.start_work()
    dp.startup.register(on_startup)


    await bot.delete_webhook(drop_pending_updates=True, request_timeout=120)
    try:
        await dp.start_polling(
            bot, 
            skip_updates=True,
            timeout=120,        # timeout для polling (было по умолчанию 10-30с)
            connection_timeout=60  # timeout для соединения
        )
    finally:
        await db_pool.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
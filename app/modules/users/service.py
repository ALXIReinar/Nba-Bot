from asyncpg import Connection

from app.db.postgres import PgSql
# import old.dataBase as db
import asyncio

from app.core.bot import bot, dp, bot, logger
# import old.handlers.crosstep.tasks as tasks

from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.context import FSMContext

# from old.handlers.crosstep.rating.rating_header import Match

# import app.old_core.database as old_db
# from app.modules.tasks.service import TasksService
from app.modules.pull_cards.service import PullCardsService
# from app.modules.trades.service import TradesService


from app.modules.base_service import BaseService


class UsersService(BaseService):
    # def __init__(self, db: PgSql, tasksService: TasksService, pullCardsService: PullCardsService, tradesService: TradesService):
    def __init__(self, db: PgSql, pullCardsService: PullCardsService):
        self.db = db
        self.trading = {}
        self.user_locks: dict[int, asyncio.Lock] = {}
        # self.tasksService = tasksService
        self.pullCardsService = pullCardsService
        # self.tradesService = tradesService

    async def is_username_in_db(self, user):
        async with self._connection(None) as conn:
            id = await self.resolve_user_id(user)
            return id != None

    async def resolve_user_id(
        self,
        user: str | int,
        conn: Connection | None = None
    ) -> int | None:
        if user is None:
            return

        async with self._connection(conn) as connection:
            if isinstance(user, int):
                if await self.db.users.exists(user, connection):
                    return user

                return None

            if user.isnumeric():
                user_id = int(user)

                if await self.db.users.exists(user_id, connection):
                    return user_id

                return None

            if user[0] != '@':
                user = '@' + user
            
            return await self.db.users.get_id_by_username(user, connection)

    async def is_banned(self, user: int | str) -> bool:
        user_id = await self.resolve_user_id(user)
        return await self.db.users.is_banned(user_id)        
    
    async def ban_user(self, user_id: int):
        await self.db.users.ban(user_id)


        #TODO: ban users
        # clear user data
        # clear FSM
        # etc.

    async def get_username(self, user_id: int):
        return await self.db.users.get_username(user_id)

    async def update_username(self, user_id: int, username: str):
        return await self.db.users.update_username(user_id, username)

    async def get_user_sub_date(self, user_id: int):
        return await self.db.users.get_sub_date(user_id)

    async def add_user(
        self,
        user_id: int,
        username: str | None,
        referrer: int | None,
    ):
        if username == None:
            username = 'null'
        else:
            username = '@' + username

        if not await self.db.users.exists(referrer):
            referrer = None

        # Подсчёт мячиков за подписанные каналы
        # channels_info = old_db.get_channels_info()
        # subbed_channels = []
        throw_count = 0
        # for channel_info in channels_info:
        #     if await self.is_user_subscribed_to_channel(user_id, channel_info[0]):
        #         subbed_channels.append(channel_info[0])
        #         if channel_info[3] == 'b':
        #             throw_count += 1
        
        async with self._connection(None) as conn:
                await self.db.users.create_user(
                    user_id=user_id,
                    username=username,
                    referrer=referrer,
                    throw_count=throw_count,
                    subbed_channels=[],
                    conn=conn,
                )
                # await conn.execute(f"INSERT INTO user_stats (user_id) VALUES ({user_id});")
                # await conn.execute(f"INSERT INTO user_ex_cards (user_id, cards) VALUES ({user_id}, '[]');")
                # await conn.execute(f"INSERT INTO user_team (user_id) VALUES ({user_id});")
                await conn.execute(f"INSERT INTO user_packs (user_id) VALUES ({user_id});")
                # await conn.execute(f"INSERT INTO dusts (user_id, silver_dust, gold_dust, legend_dust)"
                #             f"VALUES ({user_id}, 0, 0, 0);")
                # await conn.execute(f"INSERT INTO user_album (user_id)"
                #             f"VALUES ({user_id});")

                # await self.tasksService.UpdateTasks(user_id, conn)
                # if referrer is not None:
                #     await self.tasksService.PerformAction(self.tasksService.refferers_made_action, int(referrer), conn)
                #     await self.pullCardsService.add_additional_try(int(referrer), 2, conn)


    async def is_user_subscribed_to_channel(self, user_id : int, chat_id: str | int) -> bool:
        try:
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            status = chat_member.status
            return not status.value == 'left' and not status.value == 'kicked'
        except:
            return False
    
    # async def clear_user_data(self,user_id: int):
    #     self.tradesService.remove_from_trading(user_id)
    #     await self.clear_user_state(user_id)

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        return self.user_locks.setdefault(user_id, asyncio.Lock())

    def truncate_username(self, text, max_length=25):
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        else:
            return text

    async def clear_user_state(
        self,
        user_id: int
    ):
        to_user_state: FSMContext = FSMContext(
                storage=dp.storage,
                key=StorageKey(
                chat_id=user_id,
                user_id=user_id,  
                bot_id=bot.id))

        #TODO: reset match
        await to_user_state.clear()
        await to_user_state.set_state(None)

        # unlock_user_actions(user_id)
        # if state not in match_group:
        #         await to_user_state.clear()
        #         await to_user_state.set_state(None)
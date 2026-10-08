
import asyncpg

from app.db.postgres import PgSql, Connection
# from app.modules.collection.service import CollectionService, BaseService
import random

from datetime import datetime, timedelta

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.base_service import BaseService

FOUR_HOURS = 14400
MAX_TICKETS = 6

@dataclass
class PullResult:
    success: bool
    category: str | None = None       # 'clip' | 'card' | ...
    card_id: int | None = None
    remained_hours: int | None = None
    remained_minutes: int | None = None

class PullCardsService(BaseService):
    """
        Сервис бесплатных попыток вытаскивания карточек.
    """
    def __init__(self, db: PgSql):
        self.db = db

    # def __init__(self, db: PgSql, collectionService):
    #     self.db = db
        # self.collectionService = collectionService

    # async def pull_card_for_user(self, user_id: int) -> PullResult:
    #     """
    #         Вытащить карточку для пользователя.
    #     """
    #     async with self._connection(None) as conn:
    #             # 1. Блокируем строку пользователя — все параллельные вызовы
    #             #    для этого user_id выстроятся в очередь.
    #             row = await conn.fetchrow(
    #                 """
    #                 SELECT last_ticket_time, count_get, additional_try
    #                 FROM users
    #                 WHERE user_id = $1
    #                 FOR UPDATE;
    #                 """,
    #                 user_id,
    #             )
    #             if row is None:
    #                 # пользователя нет — считаем, что попыток нет
    #                 return PullResult(success=False, remained_hours=0, remained_minutes=0)
    #             last_time, count_get, additional_try = row
    #             # 2. Пересчитываем накопленные попытки по времени (та же логика,
    #             #    что была в update_count_get, но уже под блокировкой).
    #             now_time = datetime.now().replace(microsecond=0)
    #             diff_in_seconds = (now_time - last_time).total_seconds()
    #             regenerated = int(diff_in_seconds // FOUR_HOURS)
    #             count_get = min(MAX_TICKETS, count_get + regenerated)
    #             # новая "опорная" точка отсчёта
    #             if count_get >= MAX_TICKETS:
    #                 new_time = now_time
    #             else:
    #                 rest = diff_in_seconds % FOUR_HOURS
    #                 new_time = now_time - timedelta(seconds=rest)
    #             # 3. Пытаемся списать попытку атомарно в рамках транзакции.
    #             success = False
    #             if count_get > 0:
    #                 count_get -= 1
    #                 success = True
    #             elif additional_try > 0:
    #                 additional_try -= 1
    #                 success = True
    #             remained_hours = remained_minutes = None
    #             if not success:
    #                 # 4. Попыток нет — считаем, сколько ждать.
    #                 return_seconds = FOUR_HOURS - diff_in_seconds
    #                 if return_seconds < 0:
    #                     return_seconds = 0
    #                 delta = timedelta(seconds=return_seconds)
    #                 remained_hours = delta.seconds // 3600
    #                 remained_minutes = (delta.seconds % 3600) // 60
    #             # 5. Сохраняем состояние пользователя (в любом случае —
    #             #    даже если не списали, надо записать пересчитанный count_get).
    #             await conn.execute(
    #                 """
    #                 UPDATE users
    #                 SET count_get = $1,
    #                     additional_try = $2,
    #                     last_ticket_time = $3
    #                 WHERE user_id = $4;
    #                 """,
    #                 count_get,
    #                 additional_try,
    #                 new_time,
    #                 user_id,
    #             )
    #             if not success:
    #                 return PullResult(
    #                     success=False,
    #                     remained_hours=remained_hours,
    #                     remained_minutes=remained_minutes,
    #                 )
    #             # 6. Выдаём карту — внутри той же транзакции.
    #             category = self.define_pull_category()
    #             if category == 'clip':
    #                 card_id = await self.db.cards.get_random_clip_id(conn)
    #                 await self.collectionService.give_clip(user_id, card_id, conn)
    #             else:
    #                 card_id = await self.db.cards.get_random_card_id(category, conn)
    #                 await self.collectionService.give_card(user_id, card_id, conn=conn)
    #             return PullResult(success=True, category=category, card_id=card_id)

    async def add_additional_try(self, user_id : int, count : int, connection: Connection | None = None):
        """
        Добавление дополнительных попыток.
        """
        async with self._connection(connection) as conn:
            await conn.execute("UPDATE users SET additional_try = additional_try + $1 WHERE user_id = $2", count, user_id)

    def define_pull_category(self) -> str:
        random_number = random.random()
        if random_number < 0.896:
            return 'bronze'
        elif random_number < 0.966:
            return 'silver'
        elif random_number < 0.9968:
            return 'gold'
        elif random_number < 0.9998:
            return 'clip'
        elif random_number < 0.9999:
            return 'diamond'
        else:
            return 'legend'


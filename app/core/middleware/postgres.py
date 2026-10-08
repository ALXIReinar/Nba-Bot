from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.core.services import Services

from app.db.postgres import PgSql
from redis.asyncio import Redis


class PostgresMiddleware(BaseMiddleware):
    def __init__(self, db: PgSql, services : Services, redis: Redis):
        super().__init__()
        self.db = db
        self.services = services
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any]
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db
        data["services"] = self.services
        data["redis"] = self.redis

        return await handler(event, data)
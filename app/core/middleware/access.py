from app.db.postgres import PgSql
from app.core.config import env
import app.core.bot as bt
from aiogram import BaseMiddleware

class UserAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        user = data["event_from_user"]
        db: PgSql = data["db"]

        if user.id != env.admin_tg_id:
            if await db.users.is_banned(user.id):
                return False

            if bt.techincal_work:
                return False

        return await handler(event, data)
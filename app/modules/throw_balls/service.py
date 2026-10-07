from asyncpg import Connection

from app.db.postgres import PgSql
from app.modules.base_service import BaseService

class ThrowBallService(BaseService):
    """
    Сервис кидания мячиков.
    """
    def __init__(self, db: PgSql):
        super().__init__(db)

    async def get_throws_count(self, user_id, conn: Connection | None = None):
        """
        Количество мячиков пользователя.
        """
        async with self._connection(conn) as connection:
            return await connection.fetchval("SELECT throw_count FROM users WHERE user_id = $1", user_id)
    
    async def add_throws(self, user_id: int, count: int, conn: Connection | None = None):
        """
        Добавить мячики пользователю.
        """
        async with self._connection(conn) as connection:
            return await connection.execute("UPDATE users SET throw_count = throw_count + $1::int WHERE user_id=$2", count, user_id)
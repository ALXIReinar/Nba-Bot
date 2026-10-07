from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from asyncpg import Connection
from app.db.postgres import PgSql


class BaseService:
    def __init__(self, db: PgSql):
        self.db = db

    @asynccontextmanager
    async def _connection(
        self,
        conn: Connection | None = None,
    ) -> AsyncGenerator[Connection, None]:
        if conn is not None:
            yield conn
            return

        async with self.db.pool.acquire() as connection:
            async with connection.transaction():
                yield connection
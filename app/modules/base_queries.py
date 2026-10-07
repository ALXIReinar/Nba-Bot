from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import asyncpg
from asyncpg import Pool


class BaseQueries:
    def __init__(self, pool: Pool):
        self.pool = pool

    @asynccontextmanager
    async def _connection(
        self,
        conn: asyncpg.Connection | None = None,
    ) -> AsyncGenerator[asyncpg.Connection, None]:
        if conn is not None:
            yield conn
            return

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield connection
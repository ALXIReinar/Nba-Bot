from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import asyncpg
from asyncpg import Pool
from datetime import datetime

from app.modules.base_queries import BaseQueries

class UsersQueries(BaseQueries):

    async def create_user(
        self,
        user_id: int,
        username: str,
        referrer: int | None,
        throw_count: int,
        subbed_channels: list[int],
        conn: asyncpg.Connection | None = None,
    ):
        async with self._connection(conn) as connection:
            await connection.execute(
                """
                INSERT INTO users
                    (user_id, count_get, username, last_ticket_time, throw_count, reffer, sub_date)
                VALUES
                    ($1, 6, $2, $3, $4, $5, $6);
                """, user_id, username, datetime.now().replace(microsecond=0), throw_count, referrer, datetime.now()
            )

    async def is_banned(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ) -> bool:
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM users_ban
                    WHERE user_id = $1
                )
                """,
                user_id,
            )

    async def exists(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ) -> bool:
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE user_id = $1
                )
                """,
                user_id,
            )

    async def get_id_by_username(
        self,
        username: str,
        conn: asyncpg.Connection | None = None,
    ) -> int | None:
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT user_id
                FROM users
                WHERE username = $1
                """,
                username,
            )

    async def username_exists(
        self,
        username: str,
        conn: asyncpg.Connection | None = None,
    ) -> bool:
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE username = $1
                )
                """,
                username,
            )

    async def get_username(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ) -> str | None:
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT username
                FROM users
                WHERE user_id = $1
                """,
                user_id,
            )

    async def get_sub_date(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ):
        async with self._connection(conn) as connection:
            return await connection.fetchval(
                """
                SELECT sub_date
                FROM users
                WHERE user_id = $1
                """,
                user_id,
            )

    async def update_username(
        self,
        user_id: int,
        username: str,
        conn: asyncpg.Connection | None = None,
    ) -> None:
        async with self._connection(conn) as connection:
            await connection.execute(
                """
                UPDATE users
                SET username = $1
                WHERE user_id = $2
                """,
                username,
                user_id,
            )

    async def ban(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ) -> None:
        async with self._connection(conn) as connection:
            await connection.execute(
                """
                INSERT INTO users_ban (user_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
                """,
                user_id,
            )

    async def unban(
        self,
        user_id: int,
        conn: asyncpg.Connection | None = None,
    ) -> None:
        async with self._connection(conn) as connection:
            await connection.execute(
                """
                DELETE FROM users_ban
                WHERE user_id = $1
                """,
                user_id,
            )
from asyncpg import Connection


class UsersQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_username(self, user_id: int) -> str:
        """Получить username пользователя по ID"""
        result = await self.conn.fetchval(
            "SELECT username FROM users WHERE user_id = $1",
            user_id
        )
        if result is None or result == 'null':
            return "Аноним"
        return result

    async def find_by_username(self, username: str) -> dict | None:
        """Найти пользователя по username (без @)"""
        result = await self.conn.fetchrow(
            "SELECT user_id, username, first_name, last_name FROM users WHERE username = $1",
            username
        )
        return dict(result) if result else None

    async def find_by_id(self, user_id: int) -> dict | None:
        """Найти пользователя по user_id"""
        result = await self.conn.fetchrow(
            "SELECT user_id, username, first_name, last_name FROM users WHERE user_id = $1",
            user_id
        )
        return dict(result) if result else None

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None
    ):
        """
        Создать или обновить пользователя.
        INSERT ... ON CONFLICT UPDATE для синхронизации данных.
        """
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                updated_at = NOW()
            """,
            user_id, username, first_name, last_name
        )



running_users = {}

def lock_user_actions(user_id):
      running_users[user_id] = True

def unlock_user_actions(user_id):
      running_users.pop(user_id, None)

def is_user_actions_locked(user_id):
      return running_users.get(user_id) is not None
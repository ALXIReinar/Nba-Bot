from asyncpg import Connection


class UserTeamsQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_user_teams(self, user_id: int):
        query = "SELECT * FROM user_team WHERE user_id = $1"
        return await self.conn.fetch(query, user_id)
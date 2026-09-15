from asyncpg import Connection

from core.utils.anything import categories


class UserTeamsQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_user_team(self, user_id: int):
        query = "SELECT pg, sf, c, sg, pf FROM user_team WHERE user_id = $1"
        return await self.conn.fetchrow(query, user_id)

    async def get_card_name(self, id):
        # Вставишь своё соединение
        tuple_of_cards = await self.conn.fetchrow(f'SELECT category, name FROM cards WHERE card_id={id};')

        message = f"{categories[tuple_of_cards['category']].emoji}{tuple_of_cards['name']}"
        return message

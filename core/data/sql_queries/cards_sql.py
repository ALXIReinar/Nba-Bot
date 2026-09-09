from asyncpg import Connection


class CardsQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_all_cards(self):
        query = "SELECT * FROM cards"
        return await self.conn.fetch(query)

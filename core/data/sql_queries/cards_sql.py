from asyncpg import Connection

from core.utils.anything import categories


class CardsQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_all_cards(self):
        query = "SELECT * FROM cards"
        return await self.conn.fetch(query)

    async def get_card_name(self, id):
        # Вставишь своё соединение
        tuple_of_cards = await self.conn.fetchrow(f'SELECT category, name FROM cards WHERE card_id={id};')

        message = f"{categories[tuple_of_cards['category']].emoji}{tuple_of_cards['name']}"
        return message

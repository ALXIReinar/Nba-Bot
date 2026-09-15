from asyncpg import Pool
from typing import Any, Callable, Dict, Awaitable

from aiogram.types import TelegramObject
from aiogram import BaseMiddleware

from core.data.postgres import PgSql
from core.utils.anything import categories


class PostgresMiddleware(BaseMiddleware):
    def __init__(self, pool: Pool):
        super().__init__()
        self.pool = pool

    # async def cards_init(self):
    #     async with self.pool.acquire() as conn:
    #         cards = await conn.fetch(
    #             "SELECT card_id, name, position, club, category, mid_range_shot, threepoint_shot, layup, dunk, perimetr_defense, interior_defense, dribbling, passplay, block, pass_perception, hands, steal, active FROM cards;")
    #
    #     for card in cards:
    #         id = int(card['card_id'])
    #         caption = f'{categories[card['category']].emoji}{card['name']}\n📍{card['position']}\n👨‍👩‍👦‍👦{card['club']}\n\n<code>Outside Scoring: 3️⃣ {card['threepoint_shot']} 2️⃣ {card['mid_range_shot']}\nInside Scoring:  ⤴️ {card['layup']} ⤵️ {card['dunk']}\nPlaymaking:      ⛹️‍♂️ {card['dribbling']} 🤝 {card['passplay']}\nDefence:         🎯 {card['perimetr_defense']} 🎨 {card['interior_defense']}\nExtra:           🚫 {card['block']} 🪬 {card['pass_perception']}\n                 👐 {card['hands']} 🥷 {card['steal']}</code>'
    #         active = card['active']
    #         cards_caption[id] = caption
    #         if active:
    #             cards_tuple[card['category']] = cards_tuple.get(card['category'], []) + [id]
    #         else:
    #             cards_tuple['archive'] = cards_tuple.get('archive', []) + [id]


    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> None:
        async with self.pool.acquire() as conn:
            data['db'] = PgSql(conn)
            return await handler(event, data)
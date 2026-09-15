from aiogram.types import Message
from numpy.ma.extras import mr_
from redis.asyncio import Redis

from core.config_dir.config import bot, env
from core.data.postgres import PgSql
from core.handlers.rating_header import positions
from core.utils.anything import RedisKeys


async def on_startup():
    # log_event('Бот запущен', level='WARNING')
    await bot.send_message(env.admin_tg_id, 'Бот запущен!')


async def start_handler(message: Message, redis: Redis, db: PgSql):
    """Пример хендлера с использованием редис и БД"""
    
    # Автоматическая регистрация/обновление пользователя
    user = message.from_user
    await db.users.upsert_user(user.id, user.username, user.first_name, user.last_name)

    team = []
    for pos in positions:
        card = await db.conn.fetchrow('SELECT card_id, name FROM cards WHERE position LIKE $1 ORDER BY RANDOM()', f'%{pos}%')
        team.append(card.values())

    card_ids, names = zip(*team)
    team_init = await db.conn.fetchval('INSERT INTO user_team (user_id, pg, sf, c, sg, pf) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING RETURNING user_id', user.id, *card_ids)
    if team_init:
        text = f"Пользователь добавлен в бд. \nuser_id(tg_id): <b>{user.id}</b>\nКоманда состоит из: [\n- <b>{'</b>\n - <b>'.join(names)}</b>\n]"
        print(text)
        await message.answer(text)
        return

    if len(set(card_ids)) < 5:
        await message.answer('Коллизия при создании случайной команды. Вызови /start снова!')
        return

    await message.answer(f'Пользователь уже есть, команда не изменилась. Для приглашения в пвп введи <code>/invite</code> [username]. \n\nНапример,  <code>/invite mvpALXI</code>')

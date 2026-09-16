import logging
import os
from functools import lru_cache
from pathlib import Path

import orjson
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from asyncpg import Connection
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


env_files = (
    os.getenv('ENV_FILE') or
    '.env.bot'
)
load_dotenv(env_files, override=True)
logging.critical(f'\033[35m{env_files}\033[0m | app_mode: \033[33m{os.getenv('APP_MODE')}\033[0m')

WORKDIR = Path(__file__).resolve().parent.parent.parent

"Создаём директории"
CARDS_PHOTO_PATH = WORKDIR / 'cards_photo'
CARDS_PHOTO_PATH.mkdir(parents=True, exist_ok=True)

LOG_DIR = WORKDIR / 'bot_logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    pg_port: int
    pg_host: str
    pg_user: str
    pg_db: str
    pg_password: str
    pg_max_connections: int

    redis_max_connections: int
    redis_host: str
    redis_port: int

    bot_token: str
    admin_tg_id: int

    cards_path: Path | str = CARDS_PHOTO_PATH

    # Настройки дружеского ПВП режима
    match_ttl: int = os.getenv("MATCH_TTL", 10_800) # 3 часа
    match_request_ttl: int = os.getenv("MATCH_REQUEST_TTL", 300) # 5 минут

    model_config = SettingsConfigDict(extra='allow')

@lru_cache
def get_env_vars():
    return Settings()
env = get_env_vars()


"Bot & Dispatcher"
bot = Bot(token=env.bot_token, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
dp = Dispatcher()


"PostgreSQL"
async def init(conn: Connection):
    await conn.set_type_codec(
        'jsonb',
        encoder=lambda v: orjson.dumps(v).decode('utf-8'),
        decoder=orjson.loads,
        schema='pg_catalog',
    )
    await conn.set_type_codec(
        'json',
        encoder=lambda v: orjson.dumps(v).decode('utf-8'),
        decoder=orjson.loads,
        schema='pg_catalog',
    )

pool_settings = dict(
    user=env.pg_user,
    database=env.pg_db,
    password=env.pg_password,
    host=env.pg_host,
    port=env.pg_port,
    command_timeout=60,
    init=init,
    max_size=env.pg_max_connections # connections on pool
)


"Redis"
redis_settings = dict(
    host=env.redis_host,
    port=env.redis_port,
    max_connections=env.redis_max_connections,
)

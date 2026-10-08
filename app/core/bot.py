from aiogram import Bot, Dispatcher



from app.core.config import env, CARDS_PHOTO_PATH
import logging
from logging.handlers import RotatingFileHandler

from aiogram.client.session.aiohttp import AiohttpSession

import socket
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector



session = AiohttpSession(
    timeout=30.0
)

bot = Bot(token=env.bot_token, session=session, parse_mode='html', disable_web_page_preview=True)
dp = Dispatcher()

techincal_work = False

# TODO: Настаиваю на смене логера. Предлагаю log_event (app.core.logger_config)
# Поддерживает цвета, сообщает вплоть до пути к файлу, функции и конкретной строки
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    "bot.log", maxBytes=5*1024*1024, backupCount=3
)

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)



cards_path = CARDS_PHOTO_PATH / "cards_photo"


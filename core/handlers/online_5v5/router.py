"""
Главный роутер для онлайн-режима 5 на 5.
Объединяет все хендлеры PvP режима.
"""
from aiogram import Router

# Импортируем роутеры из других модулей
from .handlers_request import router as request_router
from .handlers_prepare import router as prepare_router
from .handlers_game import router as game_router

# Главный роутер онлайн-режима
router = Router(name="online_5v5")

# Подключаем суб-роутеры
router.include_router(request_router)
router.include_router(prepare_router)
router.include_router(game_router)

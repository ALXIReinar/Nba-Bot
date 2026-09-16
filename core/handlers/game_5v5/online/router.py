from aiogram import Router

from .handlers_request import router as request_router
from .handlers_prepare import router as prepare_router
from .handlers_game import router as game_router

router = Router(name="online_5v5")

router.include_router(request_router)
router.include_router(prepare_router)
router.include_router(game_router)

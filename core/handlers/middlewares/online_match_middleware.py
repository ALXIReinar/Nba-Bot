from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from core.data.online_matches_manager import OnlineMatchesManager
from core.utils.anything import GAME_CALLBACKS, GAME_CALLBACK_PREFIXES
from core.utils.logger_config import log_event
from core.utils.online_timeouts import finish_match_by_exit



class OnlineMatchMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания выхода из PvP матча.
    
    Если пользователь в активном матче делает НЕ игровое действие -
    завершает матч с сообщением о выходе.
    """

    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет активный матч при каждом действии.
        """
        # Получаем user_id
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
        
        # Проверяем, является ли действие игровым
        if isinstance(event, CallbackQuery):
            callback_data = event.data
            
            # Проверяем точное совпадение
            if callback_data in GAME_CALLBACKS:
                return await handler(event, data)
            
            # Проверяем префиксы
            for prefix in GAME_CALLBACK_PREFIXES:
                if callback_data.startswith(prefix):
                    return await handler(event, data)
        
        # Проверяем игровые команды
        if isinstance(event, Message) and event.text:
            if event.text.startswith('/invite'):
                return await handler(event, data)
        
        # НЕ игровое действие - проверяем активный матч
        redis: Redis = data.get('redis')
        if not redis:
            return await handler(event, data)
        
        matches_manager = OnlineMatchesManager(redis)
        match_id = await matches_manager.get_user_match_id(user_id)
        
        if match_id:
            # Пользователь в игре, но делает НЕ игровое действие
            log_event(f"Не игровое действие. Техническое поражение! | tg_id: \033[31m{user_id}\033[0m; match_id: \033[35m{match_id}\033[0m", level='WARNING')
            
            await finish_match_by_exit(match_id, user_id, redis)
            
            # Уведомляем пользователя
            if isinstance(event, CallbackQuery):
                await event.answer("Ты вышел из игры", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("❌ Ты вышел из игры")
        
        return await handler(event, data)

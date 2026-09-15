import logging
import time
import uuid

import orjson
from redis.asyncio import Redis

from core.utils.anything import RedisKeys


logger = logging.getLogger(__name__)


class OnlineMatchesManager:
    """CRUD операции для PvP матчей в Redis"""
    
    # TTL для ключей (в секундах)
    MATCH_TTL = 10800  # 3 часа
    REQUEST_TTL = 300  # 5 минут
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    # ==================== Match Requests ====================
    
    async def create_match_request(
        self,
        from_user_id: int,
        from_username: str,
        to_user_id: int,
        to_username: str
    ) -> bool:
        """
        Создать запрос на игру.
        
        Returns:
            bool: True если создан успешно, False если запрос уже существует
        """
        key = RedisKeys.match_request(from_user_id, to_user_id)
        
        request_data = {
            "from_user_id": from_user_id,
            "from_username": from_username,
            "to_user_id": to_user_id,
            "to_username": to_username,
            "created_at": time.time()
        }
        
        # Проверяем, существует ли запрос
        exists = await self.redis.exists(key)
        if exists:
            logger.info(f"Match request already exists: {from_user_id} -> {to_user_id}")
            return False
        
        # Сохраняем с TTL
        await self.redis.setex(
            key,
            self.REQUEST_TTL,
            orjson.dumps(request_data)
        )
        
        logger.info(f"Created match request: {from_user_id} -> {to_user_id}")
        return True
    
    async def get_match_request(
        self,
        from_user_id: int,
        to_user_id: int
    ) -> dict | None:
        """Получить запрос на игру"""
        key = RedisKeys.match_request(from_user_id, to_user_id)
        data = await self.redis.get(key)
        
        if not data:
            return None
        
        return orjson.loads(data)
    
    async def delete_match_request(
        self,
        from_user_id: int,
        to_user_id: int
    ):
        """Удалить запрос на игру"""
        key = RedisKeys.match_request(from_user_id, to_user_id)
        await self.redis.delete(key)
        logger.info(f"Deleted match request: {from_user_id} -> {to_user_id}")
    
    # ==================== Matches ====================
    
    async def create_match(
        self,
        player1_id: int,
        player2_id: int,
        player1_username: str,
        player2_username: str,
        player1_team: dict,
        player2_team: dict,
        player1_real_user_id: int = None,
        player2_real_user_id: int = None
    ) -> str:
        """
        Создать новый матч.
        
        Args:
            player1_real_user_id: Реальный user_id игрока 1 (для FSM, может отличаться от player1_id в test_pvp)
            player2_real_user_id: Реальный user_id игрока 2 (для FSM, может отличаться от player2_id в test_pvp)
        
        Returns:
            str: match_id (UUID)
        """
        match_id = uuid.uuid4().hex
        
        match_data = {
            "match_id": match_id,
            "player1_id": player1_id,
            "player2_id": player2_id,
            "player1_real_user_id": player1_real_user_id or player1_id,  # Для FSM StorageKey
            "player2_real_user_id": player2_real_user_id or player2_id,  # Для FSM StorageKey
            "player1_username": player1_username,
            "player2_username": player2_username,
            "state": "waiting_tactic",  # waiting_tactic | coin_toss | playing | finished
            "current_attacker_id": None,
            "turn_number": 0,
            "cycle": 0,  # 1-5
            "pass_count": 0,  # 0-3
            "score": {
                "player1": 0,
                "player2": 0
            },
            "player1_tactic": None,
            "player2_tactic": None,
            "teams": {
                "player1": player1_team,
                "player2": player2_team
            },
            "game_state": {},
            "waiting_message_id": {
                "player1": None,
                "player2": None
            },
            "winner_id": None,
            "finish_reason": None,
            "created_at": time.time()
        }
        
        # Сохраняем матч
        key = RedisKeys.pvp_match(match_id)
        await self.redis.setex(
            key,
            self.MATCH_TTL,
            orjson.dumps(match_data)
        )
        
        # Связываем игроков с матчем
        await self.set_user_in_match(player1_id, match_id)
        await self.set_user_in_match(player2_id, match_id)
        
        logger.info(f"Created match {match_id}: {player1_id} vs {player2_id}")
        return match_id
    
    async def get_match(self, match_id: str) -> dict | None:
        """Получить данные матча"""
        key = RedisKeys.pvp_match(match_id)
        data = await self.redis.get(key)
        
        if not data:
            return None
        
        return orjson.loads(data)
    
    async def update_match(self, match_id: str, data: dict):
        """
        Обновить данные матча.
        
        Args:
            match_id: ID матча
            data: Словарь с обновлёнными полями (будет смержен с существующими)
        """
        key = RedisKeys.pvp_match(match_id)
        
        # Получаем текущие данные
        current_data = await self.get_match(match_id)
        if not current_data:
            logger.warning(f"Attempted to update non-existent match: {match_id}")
            return
        
        # Мержим данные
        current_data.update(data)
        
        # Сохраняем обратно
        await self.redis.setex(
            key,
            self.MATCH_TTL,
            orjson.dumps(current_data)
        )
    
    async def delete_match(self, match_id: str):
        """Удалить матч"""
        match_data = await self.get_match(match_id)
        if not match_data:
            return
        
        # Удаляем связи игроков с матчем
        await self.remove_user_from_match(match_data["player1_id"])
        await self.remove_user_from_match(match_data["player2_id"])
        
        # Удаляем сам матч
        key = RedisKeys.pvp_match(match_id)
        await self.redis.delete(key)
        
        logger.info(f"Deleted match {match_id}")
    
    # ==================== User Lookups ====================
    
    async def get_user_match_id(self, user_id: int) -> str | None:
        """Получить ID матча, в котором находится пользователь"""
        key = RedisKeys.user_in_match(user_id)
        match_id = await self.redis.get(key)
        return match_id
    
    async def set_user_in_match(self, user_id: int, match_id: str):
        """Связать пользователя с матчем"""
        key = RedisKeys.user_in_match(user_id)
        await self.redis.setex(key, self.MATCH_TTL, match_id)
        logger.info(f"User {user_id} linked to match {match_id}")
    
    async def remove_user_from_match(self, user_id: int):
        """Удалить связь пользователя с матчем"""
        key = RedisKeys.user_in_match(user_id)
        await self.redis.delete(key)
        logger.info(f"User {user_id} unlinked from match")
    
    # ==================== Helpers ====================
    
    async def increment_turn_number(self, match_id: str) -> int:
        """
        Инкрементировать номер хода и вернуть новое значение.
        
        Returns:
            int: Новый turn_number
        """
        match_data = await self.get_match(match_id)
        if not match_data:
            logger.warning(f"Cannot increment turn for non-existent match: {match_id}")
            return -1
        
        new_turn_number = match_data["turn_number"] + 1
        await self.update_match(match_id, {"turn_number": new_turn_number})
        
        logger.info(f"Match {match_id}: turn_number incremented to {new_turn_number}")
        return new_turn_number
    
    async def update_waiting_message(
        self,
        match_id: str,
        player_key: str,  # "player1" или "player2"
        message_id: int | None
    ):
        """
        Обновить ID сообщения "Ожидаем хода соперника..." для редактирования.
        
        Args:
            match_id: ID матча
            player_key: "player1" или "player2"
            message_id: ID сообщения или None
        """
        match_data = await self.get_match(match_id)
        if not match_data:
            return
        
        match_data["waiting_message_id"][player_key] = message_id
        await self.update_match(match_id, {"waiting_message_id": match_data["waiting_message_id"]})


def get_matches_manager(redis: Redis) -> OnlineMatchesManager:
    """
    Фабрика для создания менеджера матчей.
    Используется для DI в хендлерах.
    """
    return OnlineMatchesManager(redis)

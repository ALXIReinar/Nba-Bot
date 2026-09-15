"""
Хендлеры подготовки к игре: выбор тактики и "монетка".
"""
import asyncio
import logging
import random

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Dice
from aiogram.types.dice import DiceEmoji
from redis.asyncio import Redis

from core.config_dir.config import bot, env, dp
from core.data.online_matches_manager import OnlineMatchesManager
from core.handlers.online_5v5 import messages as pvp_messages
from core.handlers.online_5v5.keyboards import pvp_choose_tactic_keyboard
from core.handlers.online_5v5.states import OnlineMatch


# logging = logging.getlogging(__name__)
router = Router(name="online_5v5_prepare")


@router.callback_query(
    F.data.in_({"pvp_tactic_defense", "pvp_tactic_attack", "pvp_tactic_balance"}),
    StateFilter(OnlineMatch.ChoosingTactic)
)
async def choose_tactic_pvp(
    callback: CallbackQuery,
    state: FSMContext,
    redis: Redis
):
    """
    Обработчик выбора тактики для PvP матча.
    Когда оба игрока выбрали тактику - запускаем "монетку".
    """
    user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id
    logging.info(f"User ID: {user_id} | 40: handlers_prepare")

    matches_manager = OnlineMatchesManager(redis)
    
    # 1. Получаем match_id пользователя
    match_id = await matches_manager.get_user_match_id(user_id)
    
    if not match_id:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return
    
    # 2. Получаем данные матча
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return
    
    # 3. Определяем тактику из callback_data
    tactic_map = {
        "pvp_tactic_defense": "defense",
        "pvp_tactic_attack": "attack",
        "pvp_tactic_balance": "balance"
    }
    tactic = tactic_map[callback.data]
    
    # 4. Сохраняем тактику игрока
    player_key = "player1" if user_id == match_data["player1_id"] else "player2"
    tactic_field = f"{player_key}_tactic"
    
    await matches_manager.update_match(match_id, {tactic_field: tactic})

    logging.info(f"Match {match_id}: {player_key} chose tactic '{tactic}'")

    # 5. Обновляем клавиатуру с выбранной тактикой
    await callback.message.edit_reply_markup(
        reply_markup=pvp_choose_tactic_keyboard(tactic)
    )
    await callback.answer(f"Тактика выбрана")
    
    # 6. Проверяем, выбрали ли оба игрока тактику
    match_data = await matches_manager.get_match(match_id)

    if match_data["player1_tactic"] and match_data["player2_tactic"]:
        # Оба выбрали - запускаем монетку
        logging.info(f"Match {match_id}: Both players chose tactics, starting coin toss")
        
        # ЗАЩИТА ОТ RACE CONDITION: проверяем, что монетка ещё не запущена
        if match_data["state"] != "waiting_tactic":
            logging.info(f"Match {match_id}: Coin toss already started, skipping")
            return
        
        # Обновляем состояние матча СРАЗУ, чтобы второй callback не запустил монетку повторно
        await matches_manager.update_match(match_id, {"state": "coin_toss"})
        
        # Переводим обоих в состояние просмотра монетки (через storage напрямую)
        player1_id = match_data["player1_id"]
        player2_id = match_data["player2_id"]
        
        # Создаём FSMContext для обоих игроков
        # Используем player_id для обоих параметров (работает для любого режима)
        storage = dp.storage

        key_p1 = StorageKey(bot_id=bot.id, chat_id=player1_id, user_id=player1_id)
        key_p2 = StorageKey(bot_id=bot.id, chat_id=player2_id, user_id=player2_id)
        
        await storage.set_state(key=key_p1, state=OnlineMatch.WatchingCoinToss)
        await storage.set_state(key=key_p2, state=OnlineMatch.WatchingCoinToss)
        
        # Запускаем монетку
        await coin_toss(
            match_id,
            player1_id,
            player2_id,
            redis
        )
    else:
        # Ожидаем второго игрока
        await callback.message.answer(
            pvp_messages.get_waiting_opponent_tactic_message()
        )


async def coin_toss(
    match_id: str,
    player1_id: int,
    player2_id: int,
    redis: Redis
):
    """
    "Монетка" - определяет, кто начинает первым.
    Отправляет 3 эмодзи 🏀 с интервалом 2 сек обоим игрокам.
    
    Args:
        match_id: ID матча
        player1_id: ID первого игрока
        player2_id: ID второго игрока
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    
    # 1. Отправляем начальное сообщение
    await bot.send_message(
        player1_id,
        pvp_messages.get_coin_toss_start_message()
    )
    if not player2_id == 999999999:
        await bot.send_message(
            player2_id,
            pvp_messages.get_coin_toss_start_message()
        )
    
    await asyncio.sleep(1)
    
    # 2. Три броска мяча
    player1_score = 0
    player2_score = 0
    
    for i in range(3):

        "Отправляем стикер 'Бросок в кольцо'"
        dice_p1 = await bot.send_dice(player1_id, emoji=DiceEmoji.BASKETBALL)
        dice_p2 = await bot.send_dice(player2_id, emoji=DiceEmoji.BASKETBALL)

        # От тг узнаём, какая анимация была(промах/попадание)
        # Чем лучше бросок, тем больше очков даётся
        if dice_p1.dice.value >= 4:
            player1_score += dice_p1.dice.value - 2

        if dice_p2.dice.value >= 4:
            player2_score += dice_p2.dice.value - 2

        await asyncio.sleep(2)
    
    # 3. Итоги
    await bot.send_message(
        player1_id,
        pvp_messages.get_coin_toss_result_message(player1_score, player2_score)
    )
    await bot.send_message(
        player2_id,
        pvp_messages.get_coin_toss_result_message(player2_score, player1_score)
    )
    
    await asyncio.sleep(1)
    
    # 4. Определяем первого атакующего
    if player1_score > player2_score:
        first_attacker_id = player1_id
        result_msg_p1 = "⚔️ Ты начинаешь первым!"
        result_msg_p2 = "🛡 Соперник начинает первым!"
    elif player2_score > player1_score:
        first_attacker_id = player2_id
        result_msg_p1 = "🛡 Соперник начинает первым!"
        result_msg_p2 = "⚔️ Ты начинаешь первым!"
    else:
        # Ничья - подбрасываем монетку
        first_attacker_id = random.choice([player1_id, player2_id])
        if first_attacker_id == player1_id:
            result_msg_p1 = "🎲 Ничья! Монетка решила - ты начинаешь первым!"
            result_msg_p2 = "🎲 Ничья! Монетка решила - соперник начинает первым!"
        else:
            result_msg_p1 = "🎲 Ничья! Монетка решила - соперник начинает первым!"
            result_msg_p2 = "🎲 Ничья! Монетка решила - ты начинаешь первым!"
    
    await bot.send_message(player1_id, result_msg_p1)
    await bot.send_message(player2_id, result_msg_p2)
    
    logging.info(
        f"Match {match_id}: Coin toss completed. "
        f"First attacker: {first_attacker_id} "
        f"(scores: P1={player1_score}, P2={player2_score})"
    )
    
    # 5. Обновляем данные матча
    await matches_manager.update_match(match_id, {
        "state": "playing",
        "current_attacker_id": first_attacker_id,
        "cycle": 1,
        "pass_count": 0,
        "turn_number": 1
    })
    
    await asyncio.sleep(2)
    
    # 6. Запускаем игру
    from core.handlers.online_5v5.handlers_game import start_pvp_attack
    from core.config_dir.config import dp
    await start_pvp_attack(match_id, redis, dp.storage)

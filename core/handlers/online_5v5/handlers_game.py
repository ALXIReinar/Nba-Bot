import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from redis.asyncio import Redis

from core.config_dir.config import bot, env
from core.config_dir.img_cache import image_cache
from core.data.online_matches_manager import OnlineMatchesManager
from core.data.sql_queries import users
from core.handlers.online_5v5 import messages as pvp_messages
from core.handlers.online_5v5.game_logic import (
    deserialize_team,
    apply_tactic_to_team,
    set_positions_for_pvp,
    execute_attack_action,
    execute_pass_action
)
from core.handlers.online_5v5.keyboards import (
    pvp_game_keyboard,
    pvp_only_attack_keyboard
)
from core.handlers.online_5v5.states import OnlineMatch
from core.handlers.rating_header import platform_position_emoji
from core.utils.online_timeouts import (
    schedule_turn_timeout,
    finish_match_normal
)


# logging = logging.getlogging(__name__)
router = Router(name="online_5v5_game")


async def start_pvp_attack(match_id: str, redis: Redis, bot_storage=None):
    """
    Начать новую атаку в PvP матче.
    
    Args:
        match_id: ID матча
        redis: Redis connection
        bot_storage: FSM storage для установки состояний (опционально)
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        logging.error(f"Match {match_id} not found")
        return
    
    cycle = match_data["cycle"]
    attacker_id = match_data["current_attacker_id"]
    defender_id = (
        match_data["player2_id"]
        if attacker_id == match_data["player1_id"]
        else match_data["player1_id"]
    )
    
    # Проверяем, не закончилась ли игра (5 циклов)
    if cycle > 5:
        await finish_match(match_id, redis)
        return
    
    # Получаем команды
    attacker_key = "player1" if attacker_id == match_data["player1_id"] else "player2"
    defender_key = "player2" if attacker_key == "player1" else "player1"
    
    att_team = deserialize_team(match_data["teams"][attacker_key])
    def_team = deserialize_team(match_data["teams"][defender_key])
    
    # Применяем тактики
    attacker_tactic = match_data[f"{attacker_key}_tactic"]
    defender_tactic = match_data[f"{defender_key}_tactic"]
    
    apply_tactic_to_team(att_team, attacker_tactic)
    apply_tactic_to_team(def_team, defender_tactic)
    
    # Устанавливаем позиции
    pg_pair, first_pair, second_pair = set_positions_for_pvp(
        att_team,
        def_team,
        pass_state="none",
        def_debuff=0,
        save_pg=False
    )
    
    # Сохраняем игровое состояние
    game_state = {
        "pg_pair": serialize_player_pair(pg_pair),
        "first_pair": serialize_player_pair(first_pair),
        "second_pair": serialize_player_pair(second_pair),
        "pass_state": "none",
        "def_debuff": 0,
        "current_action": 1  # 1 = атака, 2 = пас первому, 3 = пас второму
    }
    
    await matches_manager.update_match(match_id, {
        "game_state": game_state,
        "pass_count": 0
    })
    
    # Отправляем сообщения игрокам
    attacker_score = match_data["score"][attacker_key]
    defender_score = match_data["score"][defender_key]
    
    # Устанавливаем FSM состояния для обоих игроков
    if bot_storage:
        from aiogram.fsm.storage.base import StorageKey
        
        # Используем player_id для обоих параметров (работает для любого режима)
        storage_key_att = StorageKey(bot_id=bot.id, chat_id=attacker_id, user_id=attacker_id)
        storage_key_def = StorageKey(bot_id=bot.id, chat_id=defender_id, user_id=defender_id)
        
        # Атакующий - PlayingTurn, Защищающийся - WaitingOpponent
        await bot_storage.set_state(key=storage_key_att, state=OnlineMatch.PlayingTurn)
        await bot_storage.set_state(key=storage_key_def, state=OnlineMatch.WaitingOpponent)
    
    # Атакующему
    await bot.send_message(
        attacker_id,
        pvp_messages.get_you_attack_first_message(cycle, attacker_score, defender_score)
    )
    
    await send_action_message(attacker_id, match_id, redis)
    
    # Защищающемуся
    await bot.send_message(
        defender_id,
        pvp_messages.get_opponent_attacks_message(cycle, defender_score, attacker_score)
    )
    
    waiting_msg = await bot.send_message(
        defender_id,
        pvp_messages.get_waiting_opponent_move_message()
    )
    
    # Сохраняем ID сообщения ожидания для редактирования
    await matches_manager.update_waiting_message(
        match_id,
        defender_key,
        waiting_msg.message_id
    )
    
    logging.info(f"Match {match_id}: Started attack cycle {cycle}, attacker={attacker_id}")
    


async def send_action_message(user_id: int, match_id: str, redis: Redis):
    """
    Отправить сообщение с выбором действия атакующему.
    
    Args:
        user_id: ID игрока
        match_id: ID матча
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    game_state = match_data["game_state"]
    pass_count = match_data["pass_count"]
    current_action = game_state["current_action"]
    
    pg_pair = deserialize_player_pair(game_state["pg_pair"])
    
    # Формируем сообщение
    pos = pg_pair.position
    player = pg_pair.attacker
    defender = pg_pair.defender
    
    opp_def = (
        defender.get_interior_def()
        if pos == 'interior'
        else defender.get_perimetr_def()
    )
    
    message = get_dribble_message(player, defender, pos, opp_def)
    
    # Выбираем клавиатуру
    if pass_count >= 3:
        keyboard = pvp_only_attack_keyboard()
    else:
        keyboard = pvp_game_keyboard(current_action)
    
    # Отправляем карточку
    await image_cache.send_card(
        user_id,
        player.card_id,
        message,
        reply_markup=keyboard
    )


def get_dribble_message(player, opp, pos: str, opp_def) -> str:
    """Сообщение атаки (аналог из rating_game.py)"""
    message = f"{platform_position_emoji[pos]}Атака\n————————————\n{player.name}\n"
    if pos == 'interior':
        message += f"<code>Inside Scoring:  ⤴️ {player.get_layup()} ⤵️ {player.get_dunk()}"
    else:
        message += f"<code>Outside Scoring: 3️⃣ {player.get_three_point_shot()} 2️⃣ {player.get_mid_point_shot()}"
    message += f"\nPlaymaking:      ⛹️‍♂️ {player.get_dribbling()} 🤝 {player.get_passplay()}</code>\n\nVS\n\n{opp.name}\n<code>Defence:         {platform_position_emoji[pos]} {opp_def} 🚫 {opp.get_block()}</code>"
    message += f"\n————————————\n[{player.get_dribbling()}⛹️‍♂️] vs [{opp_def}{platform_position_emoji[pos]}]"
    message += f"\n[{player.get_hands()}👐] vs [{opp.get_steal()}🥷]"
    return message


def get_pass_message(pg_pair, pass_pair) -> str:
    """Сообщение паса (аналог из rating_game.py)"""
    pass_pos = pass_pair.position
    pass_attacker = pass_pair.attacker
    pass_defender = pass_pair.defender
    pg_pos = pg_pair.position
    pg_attacker = pg_pair.attacker
    pg_defender = pg_pair.defender
    
    message = f"{platform_position_emoji[pass_pos]}Сыграть с\n————————————\n{pass_attacker.name}\n"
    if pass_pair.position == 'interior':
        message += f"<code>Inside Scoring:  ⤴️ {pass_attacker.get_layup()} ⤵️ {pass_attacker.get_dunk()}"
    else:
        message += f"<code>Outside Scoring: 3️⃣ {pass_attacker.get_three_point_shot()} 2️⃣ {pass_attacker.get_mid_point_shot()}"
    
    message += f"\nPlaymaking:      ⛹️‍♂️ {pass_attacker.get_dribbling()} 🤝 {pass_attacker.get_passplay()}</code>\n\nVS\n\n{pass_defender.name}\n<code>Defence:         {platform_position_emoji[pass_pos]} {pass_defender.get_defence(pass_pos)} 🚫 {pass_defender.get_block()}</code>"
    message += f"\n————————————\n[{pg_attacker.get_passplay()}🤝] vs [{pg_defender.get_defence(pg_pos)}🛡]"
    message += f"\n[{pg_attacker.get_hands()}👐] vs [{pg_defender.get_steal()}🥷]"
    message += f"\n[{pg_attacker.get_passplay()}🤝] vs [{pass_defender.get_pass_perception()}🪬]"
    return message


@router.callback_query(
    F.data.in_({'pvp_1', 'pvp_2', 'pvp_3'}),
    StateFilter(OnlineMatch.PlayingTurn)
)
async def pvp_choose_action(callback: CallbackQuery, redis: Redis):
    """
    Переключение между кнопками выбора действия [1|2|3].
    """
    user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id
    matches_manager = OnlineMatchesManager(redis)
    
    # Проверяем блокировку действий
    if users.is_user_actions_locked(user_id):
        await callback.answer("Подожди немного")
        return
    
    match_id = await matches_manager.get_user_match_id(user_id)
    
    if not match_id:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return
    
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return
    
    # Определяем выбранное действие
    action = int(callback.data.split('_')[1])
    
    # Обновляем game_state
    game_state = match_data["game_state"]
    game_state["current_action"] = action
    
    await matches_manager.update_match(match_id, {"game_state": game_state})
    
    # Обновляем сообщение с новой клавиатурой
    pg_pair = deserialize_player_pair(game_state["pg_pair"])
    
    if action == 1:
        # Атака
        pos = pg_pair.position
        player = pg_pair.attacker
        defender = pg_pair.defender
        opp_def = (
            defender.get_interior_def()
            if pos == 'interior'
            else defender.get_perimetr_def()
        )
        message = get_dribble_message(player, defender, pos, opp_def)
        keyboard = pvp_game_keyboard(1)
    else:
        # Пас
        pass_pair_key = "first_pair" if action == 2 else "second_pair"
        pass_pair = deserialize_player_pair(game_state[pass_pair_key])
        message = get_pass_message(pg_pair, pass_pair)
        keyboard = pvp_game_keyboard(action)
    
    await image_cache.edit_card_media(
        callback.message.chat.id,
        callback.message.message_id,
        pg_pair.attacker.card_id,
        message,
        keyboard
    )


@router.callback_query(F.data == 'pvp_run', StateFilter(OnlineMatch.PlayingTurn))
async def pvp_execute_action(callback: CallbackQuery, state: FSMContext, redis: Redis):
    """
    Выполнить выбранное действие (атака или пас).
    """
    user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id

    # Проверяем блокировку
    if users.is_user_actions_locked(user_id):
        await callback.answer("Подожди немного")
        return
    
    users.lock_user_actions(user_id)
    
    try:
        matches_manager = OnlineMatchesManager(redis)
        match_id = await matches_manager.get_user_match_id(user_id)
        
        if not match_id:
            await callback.answer("❌ Матч не найден", show_alert=True)
            return
        
        match_data = await matches_manager.get_match(match_id)
        
        if not match_data:
            await callback.answer("❌ Матч не найден", show_alert=True)
            return
        
        # Инкрементим turn_number и планируем новый таймаут
        new_turn_number = await matches_manager.increment_turn_number(match_id)
        schedule_turn_timeout(match_id, new_turn_number, redis)
        
        game_state = match_data["game_state"]
        current_action = game_state["current_action"]
        
        # Выполняем действие
        if current_action == 1:
            # Атака
            await execute_pvp_attack(match_id, callback, redis)
        else:
            # Пас
            await execute_pvp_pass(match_id, current_action, callback, redis)
    
    finally:
        users.unlock_user_actions(user_id)
        await callback.answer()


async def execute_pvp_attack(match_id: str, callback: CallbackQuery, redis: Redis):
    """Выполнить атаку"""
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    game_state = match_data["game_state"]
    pg_pair = deserialize_player_pair(game_state["pg_pair"])
    
    # Выполняем атаку
    first_msg, action_msg, success_msg, score = execute_attack_action(pg_pair)
    
    # Отправляем результат атакующему
    user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id

    await bot.send_message(user_id, first_msg + "...")
    await asyncio.sleep(1)
    await bot.send_message(user_id, first_msg + action_msg + "...")
    await asyncio.sleep(2)
    await bot.send_message(user_id, first_msg + action_msg + success_msg)
    
    # Определяем ключи игроков
    attacker_id = match_data["current_attacker_id"]
    attacker_key = "player1" if attacker_id == match_data["player1_id"] else "player2"
    defender_key = "player2" if attacker_key == "player1" else "player1"
    defender_id = match_data[f"{defender_key}_id"]
    
    # Отправляем результат с 🆚 защищающемуся
    await bot.send_message(
        defender_id,
        f"🆚 {first_msg}{action_msg}{success_msg}"
    )
    
    if score >= 0:
        # Атака успешна - обновляем счёт
        match_data["score"][attacker_key] += score
        await matches_manager.update_match(match_id, {
            "score": match_data["score"],
            "def_debuff": 0
        })
        
        await asyncio.sleep(1)
        
        # Переходим к следующему циклу
        await switch_attacker(match_id, redis)
    else:
        # Мяч потерян - снижаем защиту на 10%
        await bot.send_message(
            user_id,
            "Защита снижена на 10%"
        )
        await bot.send_message(
            defender_id,
            "🆚 Защита снижена на 10%"
        )
        
        await matches_manager.update_match(match_id, {"def_debuff": 0.1})
        await switch_attacker(match_id, redis)


async def execute_pvp_pass(
    match_id: str,
    action: int,
    callback: CallbackQuery,
    redis: Redis
):
    """Выполнить пас"""
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    game_state = match_data["game_state"]
    pg_pair = deserialize_player_pair(game_state["pg_pair"])
    
    pass_pair_key = "first_pair" if action == 2 else "second_pair"
    pass_pair = deserialize_player_pair(game_state[pass_pair_key])
    
    # Выполняем пас
    first_msg, success_msg, success, pass_state = execute_pass_action(pg_pair, pass_pair)
    
    # Отправляем результат атакующему
    user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id

    await bot.send_message(user_id, first_msg + "...")
    await asyncio.sleep(2)
    await bot.send_message(user_id, first_msg + success_msg)
    
    # Определяем ключи игроков
    attacker_id = match_data["current_attacker_id"]
    attacker_key = "player1" if attacker_id == match_data["player1_id"] else "player2"
    defender_key = "player2" if attacker_key == "player1" else "player1"
    defender_id = match_data[f"{defender_key}_id"]
    
    # Отправляем результат с 🆚 защищающемуся
    await bot.send_message(
        defender_id,
        f"🆚 {first_msg}{success_msg}"
    )
    
    await asyncio.sleep(1)
    
    if success:
        # Пас удался - обновляем позиции
        pass_count = match_data["pass_count"] + 1
        
        # Получаем команды
        att_team = deserialize_team(match_data["teams"][attacker_key])
        def_team = deserialize_team(match_data["teams"][defender_key])
        
        # Применяем тактики
        apply_tactic_to_team(att_team, match_data[f"{attacker_key}_tactic"])
        apply_tactic_to_team(def_team, match_data[f"{defender_key}_tactic"])
        
        # Получаем текущий def_debuff из game_state
        current_def_debuff = match_data["game_state"].get("def_debuff", 0)
        
        # Устанавливаем новые позиции (с сохранением pg = pass_pair.attacker)
        pg_pair_new, first_pair_new, second_pair_new = set_positions_for_pvp(
            att_team,
            def_team,
            pass_state=pass_state,
            def_debuff=current_def_debuff,
            save_pg=True,
            pg_pair=pass_pair  # Мяч теперь у получателя паса
        )
        
        # Сохраняем новое состояние
        new_game_state = {
            "pg_pair": serialize_player_pair(pg_pair_new),
            "first_pair": serialize_player_pair(first_pair_new),
            "second_pair": serialize_player_pair(second_pair_new),
            "pass_state": pass_state,
            "def_debuff": current_def_debuff,
            "current_action": 1
        }
        
        await matches_manager.update_match(match_id, {
            "game_state": new_game_state,
            "pass_count": pass_count
        })
        
        # Продолжаем атаку
        await send_action_message(attacker_id, match_id, redis)
    else:
        # Пас не удался - переход хода
        await bot.send_message(
            user_id,
            "Защита снижена на 10%"
        )
        await bot.send_message(
            defender_id,
            "🆚 Защита снижена на 10%"
        )
        
        await matches_manager.update_match(match_id, {"def_debuff": 0.1})
        await switch_attacker(match_id, redis)


async def switch_attacker(match_id: str, redis: Redis):
    """
    Переключить атакующего (смена ролей).
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    # Переключаем атакующего
    current_attacker = match_data["current_attacker_id"]
    new_attacker = (
        match_data["player2_id"]
        if current_attacker == match_data["player1_id"]
        else match_data["player1_id"]
    )
    
    cycle = match_data["cycle"]
    
    # Проверяем, нужно ли инкрементить цикл
    # Цикл инкрементится после хода второго игрока
    attacker_key = "player1" if current_attacker == match_data["player1_id"] else "player2"
    
    if attacker_key == "player2":
        # Второй игрок закончил атаку - инкрементим цикл
        cycle += 1
    
    await matches_manager.update_match(match_id, {
        "current_attacker_id": new_attacker,
        "cycle": cycle,
        "pass_count": 0
    })
    
    # Запускаем следующую атаку
    from core.config_dir.config import dp
    await start_pvp_attack(match_id, redis, dp.storage)


async def finish_match(match_id: str, redis: Redis):
    """
    Завершить матч после 5 циклов.
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    # Определяем победителя
    player1_score = match_data["score"]["player1"]
    player2_score = match_data["score"]["player2"]
    
    if player1_score > player2_score:
        winner_id = match_data["player1_id"]
    elif player2_score > player1_score:
        winner_id = match_data["player2_id"]
    else:
        winner_id = None  # Ничья
    
    await finish_match_normal(match_id, winner_id, redis)


# Вспомогательные функции сериализации PlayersPair

def serialize_player_pair(pair) -> dict:
    """Сериализация PlayersPair для Redis"""
    from core.handlers.rating_header import PlayerInfo
    
    def serialize_player(p: PlayerInfo) -> dict:
        return {
            "card_id": p.card_id,
            "name": p.name,
            "category": p.category,
            "position": p.position,
            "positions": p.positions,
            "team_name": p.team_name,
            "on_right_position": p.on_right_position,
            "base_stats": {
                "three_point": p.base_stats.three_point,
                "mid_point": p.base_stats.mid_point,
                "layup": p.base_stats.layup,
                "dunk": p.base_stats.dunk,
                "perimetr_def": p.base_stats.perimetr_def,
                "interior_def": p.base_stats.interior_def,
                "passplay": p.base_stats.passplay,
                "dribbling": p.base_stats.dribbling,
                "block": p.base_stats.block,
                "hands": p.base_stats.hands,
                "pass_perception": p.base_stats.pass_perception,
                "steal": p.base_stats.steal
            },
            "current_stats": {
                "three_point": p.current_stats.three_point,
                "mid_point": p.current_stats.mid_point,
                "layup": p.current_stats.layup,
                "dunk": p.current_stats.dunk,
                "perimetr_def": p.current_stats.perimetr_def,
                "interior_def": p.current_stats.interior_def,
                "passplay": p.current_stats.passplay,
                "dribbling": p.current_stats.dribbling,
                "block": p.current_stats.block,
                "hands": p.current_stats.hands,
                "pass_perception": p.current_stats.pass_perception,
                "steal": p.current_stats.steal
            }
        }
    
    return {
        "attacker": serialize_player(pair.attacker),
        "defender": serialize_player(pair.defender),
        "position": pair.position
    }


def deserialize_player_pair(pair_data: dict):
    """Десериализация PlayersPair из Redis"""
    from core.handlers.rating_header import PlayerInfo, PlayerStats, PlayersPair
    
    def deserialize_player(p_data: dict) -> PlayerInfo:
        base_stats = PlayerStats(
            three_point=p_data["base_stats"]["three_point"],
            mid_point=p_data["base_stats"]["mid_point"],
            layup=p_data["base_stats"]["layup"],
            dunk=p_data["base_stats"]["dunk"],
            perimetr_def=p_data["base_stats"]["perimetr_def"],
            interior_def=p_data["base_stats"]["interior_def"],
            passplay=p_data["base_stats"]["passplay"],
            dribbling=p_data["base_stats"]["dribbling"],
            block=p_data["base_stats"]["block"],
            steal=p_data["base_stats"]["steal"],
            hands=p_data["base_stats"]["hands"],
            pass_perception=p_data["base_stats"]["pass_perception"]
        )
        
        player = PlayerInfo(
            card_id=p_data["card_id"],
            position=p_data["position"],
            category=p_data["category"],
            name=p_data["name"],
            stats=base_stats,
            team_name=p_data["team_name"],
            positions=p_data["positions"]
        )
        player.on_right_position = p_data["on_right_position"]
        
        # Восстанавливаем current_stats
        player.current_stats = PlayerStats(
            three_point=p_data["current_stats"]["three_point"],
            mid_point=p_data["current_stats"]["mid_point"],
            layup=p_data["current_stats"]["layup"],
            dunk=p_data["current_stats"]["dunk"],
            perimetr_def=p_data["current_stats"]["perimetr_def"],
            interior_def=p_data["current_stats"]["interior_def"],
            passplay=p_data["current_stats"]["passplay"],
            dribbling=p_data["current_stats"]["dribbling"],
            block=p_data["current_stats"]["block"],
            steal=p_data["current_stats"]["steal"],
            hands=p_data["current_stats"]["hands"],
            pass_perception=p_data["current_stats"]["pass_perception"]
        )
        
        return player
    
    attacker = deserialize_player(pair_data["attacker"])
    defender = deserialize_player(pair_data["defender"])
    
    return PlayersPair(attacker, defender, pair_data["position"])

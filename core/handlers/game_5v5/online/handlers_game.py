import asyncio

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery
from redis.asyncio import Redis

from core.config_dir.config import bot, dp
from core.config_dir.img_cache import image_cache
from core.data.online_matches_manager import OnlineMatchesManager
from core.data.sql_queries import users
from core.handlers.game_5v5.online import messages as pvp_messages
from core.handlers.game_5v5.online.game_logic import (
    apply_tactic_to_team,
    set_positions_for_pvp,
    execute_attack_action,
    execute_pass_action
)
from core.handlers.game_5v5.online.serializers import deserialize_team, serialize_player_pair, deserialize_player_pair
from core.handlers.game_5v5.online.keyboards import (
    pvp_game_keyboard,
    pvp_only_attack_keyboard
)
from core.handlers.game_5v5.online.states import OnlineMatch
from core.utils.anything import GamePvpCalls, platform_position_emoji
from core.utils.logger_config import log_event
from core.utils.online_timeouts import (
    schedule_turn_timeout,
    finish_match_normal
)


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
        log_event(f"Матч не найден. Невозможно начать атаку | match_id: \033[31m{match_id}\033[0m", level='WARNING')
        return
    
    cycle = match_data["cycle"]
    attacker_id = match_data["current_attacker_id"]
    defender_id = (
        match_data["player2_id"]
        if attacker_id == match_data["player1_id"]
        else match_data["player1_id"]
    )


    "Проверяем, не закончилась ли игра (5 циклов)"
    # Можно сделать cycle > match_data["max_cycles"]. А задавать при /invite test_user 10
    # По дефолту - 5 (match_data.get("max_cycles", 5))
    if cycle > 5:
        log_event(f'Матч завершён. Подводим итоги | match_id: \033[33m{match_id}; attacker_tg_id: \033[36m{attacker_id}\033[0m; defender_tg_id: \033[0m{defender_id}\033[0m; cycle: \033[31m{cycle}\033[0m')
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
        
        # Используем player_id для обоих параметров
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
    await matches_manager.update_waiting_message(match_id, defender_key, waiting_msg.message_id)
    log_event(f"Атака инициализирована! Атакующий - выбирает атаку, Защита - ждёт и смотрит | match_id: \033[33m{match_id}; attacker_tg_id: \033[36m{attacker_id}\033[0m; defender_tg_id: \033[0m{defender_id}\033[0m; cycle: \033[31m{cycle}\033[0m")


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
        log_event(f'Матч не найден. Не удалось отправить сообщение для хода | match_id: \033[33m{match_id}\033[0m', level='WARNING')
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
    log_event(f'Отправили выбор действия атакующему | card_id: \033[33m{player.card_id}\033[0m; tg_id: \033[32m{user_id}\033[0m')


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
    F.data.in_({GamePvpCalls.pvp_1, GamePvpCalls.pvp_2, GamePvpCalls.pvp_3}),
    StateFilter(OnlineMatch.PlayingTurn)
)
async def pvp_choose_action(callback: CallbackQuery, redis: Redis):
    """
    Переключение между кнопками выбора действия [1|2|3].
    """
    user_id = callback.from_user.id
    matches_manager = OnlineMatchesManager(redis)

    # Проверяем блокировку действий
    if users.is_user_actions_locked(user_id):
        log_event(f'Пользователь шалит. Спамит кнопки | tg_id: \033[31m{user_id}\033[0m', level='WARNING')
        await callback.answer("Подожди немного")
        return

    # Достаём данные о матче
    match_id = await matches_manager.get_user_match_id(user_id)
    match_data = await matches_manager.get_match(match_id)

    if not match_data:
        log_event(f'Матч не найден. Не удалось сменить действие для атаки | match_id: \033[33m{user_id}\033[0m', level='WARNING')
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    # Определяем выбранное действие
    action = int(callback.data.split('_')[1])

    # Обновляем game_state
    game_state = match_data["game_state"]
    game_state["current_action"] = action

    log_event(f'Пользователь выбирает другое действие для атаки. Применяем статы | user_id: \033[36m{user_id}\033[0m; match_id: \033[33m{match_id}\033[0m')
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
        callback.message.chat.id, callback.message.message_id, pg_pair.attacker.card_id, message, keyboard
    )
    log_event(f'Пользователь выбрал другое действие для атаки. Отобразили на клавиатуре | tg_id: \033[31m{user_id}\033[0m; match_id: \033[33m{match_id}\033[0m; cur_action: \033[34m{action}\033[0m')


@router.callback_query(F.data == GamePvpCalls.pvp_run, StateFilter(OnlineMatch.PlayingTurn))
async def pvp_execute_action(callback: CallbackQuery, state: FSMContext, redis: Redis):
    """
    Выполнить выбранное действие (атака или пас).
    """
    user_id = callback.from_user.id

    # Проверяем блокировку
    if users.is_user_actions_locked(user_id):
        log_event(f'Пользователь шалит. Спамит кнопки | tg_id: \033[31m{user_id}\033[0m', level='WARNING')
        await callback.answer("Подожди немного")
        return
    
    users.lock_user_actions(user_id)

    try:
        "Находим данные матча"
        matches_manager = OnlineMatchesManager(redis)
        match_id = await matches_manager.get_user_match_id(user_id)
        match_data = await matches_manager.get_match(match_id)

        if not match_data:
            log_event(f'Матч не найден. Не удалось сменить действие для атаки(клавиатура) | user_id: \033[33m{user_id}\033[0m', level='WARNING')
            await callback.answer("❌ Матч не найден", show_alert=True)
            return

        "Обрабатываем статы"
        log_event(f'Пользователь подтвердил действие для атаки. Исполняем | user_id: \033[36m{user_id}\033[0m; match_id: \033[33m{match_id}\033[0m')

        # Инкрементим turn_number и планируем новый таймаут
        new_turn_number = await matches_manager.increment_turn_number(match_id)
        schedule_turn_timeout(match_id, new_turn_number, redis)

        game_state = match_data["game_state"]
        current_action = game_state["current_action"]

        # Выполняем действие
        if current_action == 1:
            # Атака
            log_event(f'Атакующий идёт в нападение | user_id: \033[34m{user_id}\033[0m; match_id: \033[32m{match_id}\033[0m')
            await execute_pvp_attack(match_id, callback, redis)
        else:
            log_event(f'Атакующий сделал Пас | user_id: \033[36m{user_id}\033[0m; match_id: \033[33m{match_id}\033[0m')
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
    user_id = callback.from_user.id

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
    log_event(f'Определяем исход атаки | attacker_tg_id: \033[36m{attacker_id}\033[0m; defender_tg_id: \033[34m{defender_id}\033[0m; match_id: \033[33m{match_id}\033[0m')
    await bot.send_message(defender_id, f"🆚 {first_msg}{action_msg}{success_msg}")
    
    if score >= 0:
        # Атака успешна - обновляем счёт
        match_data["score"][attacker_key] += score
        await matches_manager.update_match(match_id, {
            "score": match_data["score"],
            "def_debuff": 0
        })
        
        await asyncio.sleep(1)
        
        # Переходим к следующему циклу
        log_event(f'Атака успешна! Следующий цикл | attacker_tg_id: \033[33m{attacker_id}\033[0m; defender_tg_id: \033[31m{defender_id}\033[0m; match_id: \033[35m{match_id}\033[0m')
        await switch_attacker(match_id, redis)
    else:
        # Мяч потерян - снижаем защиту на 10%
        log_event(f'Мяч потерян! Следующий цикл | attacker_tg_id: \033[31m{attacker_id}\033[0m; defender_tg_id: \033[32m{defender_id}\033[0m; match_id: \033[35m{match_id}\033[0m')

        await bot.send_message(user_id, "Защита снижена на 10%")
        await bot.send_message(defender_id, "🆚 Защита снижена на 10%")
        
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
    log_event(f'Определяем исход паса | match_id: \033[33m{match_id}\033[0m')
    first_msg, success_msg, success, pass_state = execute_pass_action(pg_pair, pass_pair)
    
    # Отправляем результат атакующему
    user_id = callback.from_user.id

    await bot.send_message(user_id, first_msg + "...")
    await asyncio.sleep(2)
    await bot.send_message(user_id, first_msg + success_msg)
    
    # Определяем ключи игроков
    attacker_id = match_data["current_attacker_id"]
    attacker_key = "player1" if attacker_id == match_data["player1_id"] else "player2"
    defender_key = "player2" if attacker_key == "player1" else "player1"
    defender_id = match_data[f"{defender_key}_id"]
    
    # Отправляем результат с 🆚 защищающемуся
    await bot.send_message(defender_id, f"🆚 {first_msg}{success_msg}")
    await asyncio.sleep(1)
    
    if success:
        # Пас удался - обновляем позиции
        log_event(f'Пас успешен, применяем статы | match_id: \033[33m{match_id}\033[0m')
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
        log_event(f'Статы применены, продолжаем цикл | match_id: \033[32m{match_id}\033[0m')
        await send_action_message(attacker_id, match_id, redis)
    else:
        # Пас не удался - переход хода
        log_event(f'Пас провалился. Запускаем новый цикл. Обработка итогов текущего цикла... | match_id: \033[32m{match_id}\033[0m')
        await bot.send_message(user_id, "Защита снижена на 10%")
        await bot.send_message(defender_id, "🆚 Защита снижена на 10%")
        
        await matches_manager.update_match(match_id, {"def_debuff": 0.1})
        await switch_attacker(match_id, redis)


async def switch_attacker(match_id: str, redis: Redis):
    """
    Переключить атакующего (смена ролей).
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        log_event(f'Матч не найден. Не удалось сменить роли(для нового цикла) | match_id: \033[33m{match_id}\033[0m', level='WARNING')
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

    log_event(f'Цикл обработан. Запускаем атаку! | match_id: \033[32m{match_id}\033[0m; new_attacker_tg_id: \033[32m{new_attacker}\033[0m')
    await start_pvp_attack(match_id, redis, dp.storage)


async def finish_match(match_id: str, redis: Redis):
    """
    Завершить матч после 5 циклов.
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        log_event(f'Матч не найден. Не удалось подвести итоги | match_id: \033[33m{match_id}\033[0m', level='WARNING')
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

    log_event(f"Матч завершён (None == ничья)! Запускаем пост-процедуры | match_id: \033[32m{match_id}\033[0m; winner_tg_id: \033[32m{winner_id}\033[0m")
    await finish_match_normal(match_id, winner_id, redis)


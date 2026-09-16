import random
import asyncio
import logging as logger

from aiogram import F, Router
from aiogram.types import CallbackQuery

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from aiogram.types import Message


from core.config_dir.config import bot, env
from core.config_dir.img_cache import image_cache
from core.data.postgres import PgSql
from core.data.sql_queries import users
from core.handlers.game_5v5.core.game_stat_configs import pass_debuff_values, PassSecondState, dribbling_buff_values, PassFirstState, \
    PressureResult, AttackFirstState, shoot_buff_values, ShootType
from core.handlers.game_5v5.core.rating_header import PlayerInfo, Team, PlayersPair, Match
from core.utils.anything import positions, platform_position_emoji, pick_tactic_message, tactic_message
from core.utils import keyboards

router = Router()

import copy



from aiogram.exceptions import TelegramNetworkError
from python_socks import ProxyError


async def safe_send(bot_, *args, user_id: int, **kwargs) -> Message | bool:
    for attempt in range(3):
        try:
            message = await bot_.send_message(*args, **kwargs)
            return message, True

        except (ProxyError, TelegramNetworkError) as e:
            logger.warning(
                f"Ошибка отправки сообщения пользователю {user_id} "
                f"(попытка {attempt + 1}/3): {e}"
            )

            if attempt < 2:
                await asyncio.sleep(1 + attempt)

    logger.error(
        f"Не удалось отправить сообщение пользователю {user_id} "
        f"после 3 попыток"
    )
    return None, False


async def safe_edit(message: Message, text: str, user_id: int) -> bool:
    for attempt in range(3):
        try:
            await message.edit_text(text)
            return True

        except (ProxyError, TelegramNetworkError) as e:
            logger.warning(
                f"Ошибка изменения сообщения пользователю {user_id} "
                f"(попытка {attempt + 1}/3): {e}"
            )

            if attempt < 2:
                await asyncio.sleep(1 + attempt)

    logger.error(
        f"Не удалось изменить сообщение пользователю {user_id} "
        f"после 3 попыток"
    )
    return False

# TODO move help functions to other place

def get_best_interior_def(team: list[PlayerInfo]) -> PlayerInfo:
    chances = []
    all_stats = 0
    for i in range(len(team)):
        add = team[i].get_interior_def() ** 2
        chances.append(all_stats + add)
        all_stats += add

    for i in range(len(chances)):
        chances[i] /= all_stats

    rand = random.random()

    for i in range(len(chances)):
        if rand <= chances[i]:
            return team[i]

def get_best_perimetr_def(team: list[PlayerInfo]) -> PlayerInfo:
    chances = []
    all_stats = 0
    for i in range(len(team)):
        add = team[i].get_perimetr_def() ** 2
        chances.append(all_stats + add)
        all_stats += add

    for i in range(len(chances)):
        chances[i] /= all_stats

    rand = random.random()

    for i in range(len(chances)):
        if rand <= chances[i]:
            return team[i]
        
def get_center_player(team: list[PlayerInfo]) -> PlayerInfo:
    return team[positions.index("C")]

async def get_team_info(user_id, db: PgSql) -> str:
    # team = await db.conn.fetchrow(f"SELECT {positions[0]}, {positions[1]}, {positions[2]}, {positions[3]}, {positions[4]} FROM user_team WHERE user_id={user_id}")
    team = await db.conn.fetchrow(f"SELECT {', '.join(positions)} FROM user_team WHERE user_id = $1", user_id)

    # TODO for loop
    # TODO instead for cycle: result = f"<code>{'\n'.join([f"{role_column.upper()}: {team_card_value}" for role_column, team_card_value in team.values()])}</code>"

    result = "<code>"
    result += "C:  "
    result += await db.cards.get_card_name(team[0]) + "\n"
    result += "PG: "
    result += await db.cards.get_card_name(team[1]) + "\n"
    result += "PF: "
    result += await db.cards.get_card_name(team[2]) + "\n"
    result += "SG: "
    result += await db.cards.get_card_name(team[3]) + "\n"
    result += "SF: "
    result += await db.cards.get_card_name(team[4]) + "</code>"
    return result

def get_pg_player(team : list[PlayerInfo]):
    first : PlayerInfo = team[positions.index("PG")]
    copy_team = copy.copy(team)
    copy_team.remove(first)
    second : PlayerInfo = None
    third : PlayerInfo = None

    max = 0
    for i in range(4):
        player = copy_team[i]
        passplay = player.get_passplay()
        if(passplay > max):
            max = passplay
            second = player

    copy_team.remove(second)

    max = 0
    for i in range(3):
        player = copy_team[i]
        passplay = player.get_passplay()
        if(passplay > max):
            max = passplay
            third = player


    player = None
    rand = random.random()

    if rand <= 0.5:
        player = first
    elif rand <= 0.75:
        player = second
    else:
        player = third
        
    return player

max_cycles = 5
max_passes = 3

async def set_positions(state : FSMContext, switch : bool, save_pg : bool):
        data = await state.get_data()
        att_orig_team : Team = data['att_team'] if not switch else data['def_team']
        def_orig_team : Team = data['def_team'] if not switch else data['att_team']
        pass_state = data["pass_state"]
        def_debuff = data["def_debuff"]

        def_orig_team.reset_stats()
        att_orig_team.reset_stats()

        if(def_debuff != 0):
            def_orig_team.apply_def_debuff(def_debuff)

        att_team : list[PlayerInfo] = [player for player in att_orig_team.players]
        def_team : list[PlayerInfo] = [player for player in def_orig_team.players]
            

        pg : PlayerInfo = None
        pg_opp : PlayerInfo = None
        if(save_pg):
            pg_pair : PlayersPair = data["pg_pair"]
            pg = pg_pair.attacker if not switch else pg_pair.defender
            pg_opp = pg_pair.defender if not switch else pg_pair.attacker
            pg_pos = pg_pair.position
        else:
            pg = get_pg_player(att_team)
            pg_pos = pg.get_shooting_platform_position()
            pg_opp = get_best_interior_def(def_team) if pg_pos == 'interior' else get_best_perimetr_def(def_team)
        
        pg_pair = PlayersPair(pg, pg_opp, pg_pos)
        
        def_team.remove(pg_opp)
        att_team.remove(pg)

        first = random.choice(att_team)
        att_team.remove(first)
        second = random.choice(att_team)
        att_team.remove(second)

        first_pos = first.get_shooting_platform_position()
        second_pos = second.get_shooting_platform_position()

        first_opp : PlayerInfo = None
        first_opp = get_best_interior_def(def_team) if first_pos == 'interior' else get_best_perimetr_def(def_team)
        def_team.remove(first_opp) 
        second_opp = get_best_interior_def(def_team) if second_pos == 'interior' else get_best_perimetr_def(def_team)
        
        first_pair = PlayersPair(first, first_opp, first_pos)
        second_pair = PlayersPair(second, second_opp, second_pos)

        debuff = 0
        if(pass_state == 'good'):
            debuff = pass_debuff_values[PassSecondState.good]
        elif(pass_state == 'normal'):
            debuff = pass_debuff_values[PassSecondState.normal]
        elif(pass_state == 'perfect'):
            debuff = pass_debuff_values[PassSecondState.perfect]
        elif(pass_state == 'bad'):
            pg_pair.attacker.current_stats.dribbling = max(0, int(pg_pair.attacker.current_stats.dribbling * dribbling_buff_values[PassFirstState.bad]))
        
        if debuff != 0:
            pg_pair.defender.apply_def_debuff(debuff)

        await state.update_data(att_team=att_orig_team, def_team=def_orig_team, pg_pair=pg_pair, first_pair=first_pair, second_pair=second_pair)

def get_pass_message(pg_pair : PlayersPair, pass_pair : PlayersPair):
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

def get_pass_message_old(player: PlayerInfo, opp : PlayerInfo, pos : str, passplay, pass_def, first_hands, first_steal, opp_def) -> str:
    message = f"{platform_position_emoji[pos]}Сыграть с\n————————————\n{player.name}\n"
    if pos == 'interior':
        message += f"<code>Inside Scoring:  ⤴️ {player.get_layup()} ⤵️ {player.get_dunk()}"
    else:
        message += f"<code>Outside Scoring: 3️⃣ {player.get_three_point_shot()} 2️⃣ {player.get_mid_point_shot()}"
    message += f"\nPlaymaking:      ⛹️‍♂️ {player.get_dribbling()} 🤝 {player.get_passplay()}</code>\n\nVS\n\n{opp.name}\n<code>Defence:         {platform_position_emoji[pos]} {opp_def} 🚫 {opp.get_block()}</code>"
    message += f"\n————————————\n[{passplay}🤝] vs [{pass_def}🛡]"
    message += f"\n[{first_hands}👐] vs [{first_steal}🥷]"
    message += f"\n[{passplay}🤝] vs [{opp.get_pass_perception()}🪬]"
    return message

async def edit_to_pass_message(message : Message, action : int, pg_pair : PlayersPair, pass_pair : PlayersPair):
    message_str = get_pass_message(pg_pair, pass_pair)
    await image_cache.edit_card_media(message.chat.id, message.message_id, pass_pair.attacker.card_id, message_str, reply_markup=keyboards.craft_keyboard_5v5(action))

def get_dribble_message(player: PlayerInfo, opp : PlayerInfo, pos : str, opp_def) -> str:
    message = f"{platform_position_emoji[pos]}Атака\n————————————\n{player.name}\n"
    if pos == 'interior':
        message += f"<code>Inside Scoring:  ⤴️ {player.get_layup()} ⤵️ {player.get_dunk()}"
    else:
        message += f"<code>Outside Scoring: 3️⃣ {player.get_three_point_shot()} 2️⃣ {player.get_mid_point_shot()}"
    message += f"\nPlaymaking:      ⛹️‍♂️ {player.get_dribbling()} 🤝 {player.get_passplay()}</code>\n\nVS\n\n{opp.name}\n<code>Defence:         {platform_position_emoji[pos]} {opp_def} 🚫 {opp.get_block()}</code>"
    message += f"\n————————————\n[{player.get_dribbling()}⛹️‍♂️] vs [{opp_def}{platform_position_emoji[pos]}]"
    message += f"\n[{player.get_hands()}👐] vs [{opp.get_steal()}🥷]"
    return message

async def edit_to_dribble_message(message : Message, player : PlayerInfo, opp : PlayerInfo, pos : str, opp_def):
    message_str = get_dribble_message(player, opp, pos, opp_def)
    await image_cache.edit_card_media(message.chat.id, message.message_id, player.card_id, message_str, reply_markup=keyboards.craft_keyboard_5v5(1))

async def send_only_dribble_message(user_id, player : PlayerInfo, opp : PlayerInfo, pos : str, opp_def):
    message = get_dribble_message(player, opp, pos, opp_def)
    await image_cache.send_card(user_id, player.card_id, message, reply_markup=keyboards.only_choose_attack)

async def send_dribble_message(user_id, player : PlayerInfo, opp : PlayerInfo, pos : str, opp_def):
    message = get_dribble_message(player, opp, pos, opp_def)
    await image_cache.send_card(user_id, player.card_id, message, reply_markup=keyboards.craft_keyboard_5v5(1))
    
async def send_attack_message(user_id, state : FSMContext):
    await state.set_state(Match.PlayingMatch)
    await state.update_data(action = 1)
    data = await state.get_data()
    pg_pair : PlayersPair = data['pg_pair']
    pass_count = data['pass_count']

    opp_def = pg_pair.defender.get_interior_def() if pg_pair.position == 'interior' else pg_pair.defender.get_perimetr_def()
    if(pass_count == 3):
        await send_only_dribble_message(user_id, pg_pair.attacker, pg_pair.defender, pg_pair.position, opp_def)
    else:
        await send_dribble_message(user_id, pg_pair.attacker, pg_pair.defender, pg_pair.position, opp_def)

async def send_start_player_attack_message(callback : CallbackQuery, state : FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    own_score = data['own_score']
    opp_score = data['opp_score']
    cycle = data['cycle']
    await bot.send_message(user_id, f"Ты атакуешь! {cycle}/{max_cycles}\n\nСчёт: {own_score} - {opp_score}")

@router.callback_query(F.data.in_({'1', '2', '3'}), Match.PlayingMatch)
async def edit_message(callback : CallbackQuery, state : FSMContext):
    user_id = callback.from_user.id

    if(users.is_user_actions_locked(user_id)):
        await callback.answer("Подожди 30 сек")
        return
    
    users.lock_user_actions(user_id)
    
    try:
        data = await state.get_data()
        if(callback.data == '1'):
            data = await state.get_data()
            pg_pair : PlayersPair = data['pg_pair']
            opp_def = pg_pair.defender.get_interior_def() if pg_pair.position == 'interior' else pg_pair.defender.get_perimetr_def()
            await state.update_data(action=1)
            await edit_to_dribble_message(callback.message, pg_pair.attacker, pg_pair.defender, pg_pair.position, opp_def)
        elif(callback.data == '2'):
            data = await state.get_data()
            pg_pair : PlayersPair = data['pg_pair']
            pass_pair : PlayersPair = data['first_pair']
            await state.update_data(action=2)
            await edit_to_pass_message(callback.message, 2, pg_pair, pass_pair)   
        elif(callback.data == '3'):
            data = await state.get_data()
            pg_pair : PlayersPair = data['pg_pair']
            pass_pair : PlayersPair = data['second_pair']
            await state.update_data(action=3)
            await edit_to_pass_message(callback.message, 3, pg_pair, pass_pair)   
    finally:
        users.unlock_user_actions(user_id)

# def calculate_chance_to_dribble(dribble, defence):
#     diff = dribble - defence
#     sign = -1 if diff < 0 else 1
#     chance = 0.5 + sign * 0.4 * min((abs(diff) / 20.0), 1) + sign * max((min(30, abs(diff)) - 20), 0) / 100
#     return chance

def calculate_chance_to_dribble(dribble, defence):
    chance = 0
    if(dribble + 5 > defence):
        diff = dribble + 5 - defence
        chance = diff / 20
    return chance

def calculate_chance_to_open_throw(pair : PlayersPair) -> float:
    opp_def = pair.defender.get_interior_def() if pair.position == 'interior' else pair.defender.get_perimetr_def()
    dribbling = pair.attacker.get_dribbling()
    return calculate_chance_to_dribble(dribbling, opp_def)

def calculate_chance_to_successful_attack(pair : PlayersPair) -> float:
    chance_to_dribble = calculate_chance_to_open_throw(pair)
    multiply_chance = 0
    if(pair.position == 'interior'):
        dunk = pair.attacker.get_dunk()
        layup = pair.attacker.get_layup()
        all = dunk + layup
        multiply_chance = dunk / all * dunk / 100 + layup / all * layup / 100
    else:
        p3 = pair.attacker.get_three_point_shot()
        p2 = pair.attacker.get_mid_point_shot()
        all = p3 + p2
        multiply_chance = p3 / all * p3 / 100 + p2 / all * p2 / 100

    opp_def = pair.defender.get_interior_def() if pair.position == 'interior' else pair.defender.get_perimetr_def()

    return chance_to_dribble * multiply_chance

def calculate_pressure(hands, steal) -> PressureResult:
    diff = hands - steal
    if diff >= -40:
        rand = random.random()
        chance = (diff + 40) / 100
        if rand <= chance:
            return PressureResult.overcome_pressure
        else:
            return PressureResult.lost_to_pressure
    elif(hands > steal):
        return PressureResult.overcome_pressure
    else:
        return PressureResult.lost_to_pressure

def try_shoot(dribbling, defence, hands, steal, attack, block) -> AttackFirstState:
    diff = dribbling - defence
    rand = random.random()
    shoot_Type = None
    if(diff > 30):
        shoot_Type = ShootType.free_throw
    elif (diff > 15):
        chance = (diff - 15) / 15
        if rand <= chance:
            shoot_Type = ShootType.free_throw
        else:
            shoot_Type = ShootType.hard_throw
    elif (diff > 5):
        shoot_Type = ShootType.hard_throw
    elif (diff > -5):
        chance = (diff + 5) / 10
        if(rand < chance):
            shoot_Type = ShootType.hard_throw
        else:
            shoot_Type = ShootType.through_block
    else:
        pressure = calculate_pressure(hands, steal)
        if pressure == PressureResult.overcome_pressure:
            shoot_Type = ShootType.through_block

    if(shoot_Type == None):
        return AttackFirstState.lost
    
    rand = random.random()
    buff = shoot_buff_values[shoot_Type]
    attack = min(100, int(buff * attack)) / 100
    if shoot_Type == ShootType.through_block:
        attack -= block / 100 / 2
    if rand <= attack:
        if(shoot_Type == ShootType.through_block):
            return AttackFirstState.trough_block_success
        elif(shoot_Type == ShootType.hard_throw):
            return AttackFirstState.hard_throw_success
        elif(shoot_Type == ShootType.free_throw):
            return AttackFirstState.free_throw_success
    else:
        if(shoot_Type == ShootType.through_block):
            return AttackFirstState.trough_block_fail
        elif(shoot_Type == ShootType.hard_throw):
            return AttackFirstState.hard_throw_fail
        elif(shoot_Type == ShootType.free_throw):
            return AttackFirstState.free_throw_fail 

def try_to_pass(pg_pair : PlayersPair, pass_pair : PlayersPair) -> PassFirstState | PassSecondState:
    passplay = pg_pair.attacker.get_passplay()
    hands = pg_pair.attacker.get_hands()
    defence = pg_pair.defender.get_defence(pg_pair.position)
    steal = pg_pair.defender.get_steal()
    pass_perception = pass_pair.defender.get_pass_perception()
    firstState = None
    secondState = None
    diff = passplay - defence
    if(diff >= 0):
        firstState = PassFirstState.good
    elif diff < 0:
        rand = random.random()
        chance = (diff + 15) / 10
        if rand <= chance:
            firstState = PassFirstState.good
        else:
            pressure = calculate_pressure(hands, steal)
            firstState = PassFirstState.bad if pressure == PressureResult.overcome_pressure else PassFirstState.lost
    else:
        pressure = calculate_pressure(hands, steal)
        firstState = PassFirstState.bad if pressure == PressureResult.overcome_pressure else PassFirstState.lost

    if firstState in [PassFirstState.bad, PassFirstState.lost]:
        return firstState, None
    
    if secondState != None:
        return firstState, secondState
    diff = passplay - pass_perception + diff
    rand = random.random()
    if(diff > 90):
        secondState = PassSecondState.perfect
    elif(diff > 50):
        chance = (diff - 50) / 40
        if rand <= chance:
            secondState = PassSecondState.perfect
        else:
            secondState = PassSecondState.good
    elif(diff > 35):
        secondState = PassSecondState.good
    elif(diff > 20):
        chance = (diff - 20) / 15
        if rand <= chance:
            secondState = PassSecondState.good
        else:
            secondState = PassSecondState.normal
    else:
        secondState = PassSecondState.normal

    return firstState, secondState

def calculate_chance_to_pass(passplay, steal) -> PassFirstState:
    diff = steal - passplay
    if diff >= 5:
        return max(0, 0.8 + 0.8 * (diff / 40))
    else:
        return min(1, 0.8 + 0.2 * (diff / 10))
    
def calculate_chance_to_pass_pair(pg_pair: PlayersPair) -> PassFirstState:
    passplay = pg_pair.attacker.get_passplay()
    steal = pg_pair.defender.get_steal()
    return calculate_chance_to_pass(passplay, steal)  

def calculate_goodness_pass(pg_pair: PlayersPair, pass_pair: PlayersPair) -> float:
    pass_chanse = calculate_chance_to_pass_pair(pg_pair)
    pair = copy.deepcopy(pass_pair)
    pair.defender.current_stats.perimetr_def *= pass_debuff_values[PassSecondState.normal]
    pair.defender.current_stats.interior_def *= pass_debuff_values[PassSecondState.normal]
    
    chance_to_dribble = calculate_chance_to_successful_attack(pair)

    return pass_chanse * chance_to_dribble

@router.callback_query(F.data == 'run')
async def run(callback : CallbackQuery, state : FSMContext, db: PgSql):
    user_id = callback.from_user.id

    if(users.is_user_actions_locked(user_id)):
        await callback.answer("Подожди 30 сек")
        return


    data = await state.get_data()
    pg_pair : PlayersPair = data['pg_pair']
    
    users.lock_user_actions(user_id)
    try:
        await image_cache.edit_card_media(callback.message.chat.id, callback.message.message_id, pg_pair.attacker.card_id, callback.message.html_text)
    except Exception:
        logger.error("Ошибка смены фотки")

    try:
        # user_id уже определён в начале функции
        if(data['action'] == 1):
            first_msg, action_msg, success_msg, score = await end_attack(pg_pair, False)
            if(score >= 0):
                await state.update_data(def_debuff=0, own_score = data['own_score'] + score)
                msg, suc = await safe_send(
                    bot,
                    user_id,
                    first_msg + "...",
                    user_id=user_id,
                )
                await asyncio.sleep(1)
                if suc:
                    await safe_edit(msg, first_msg + action_msg + "...", user_id)
                else:
                    msg, suc = await safe_send(
                        bot,
                        user_id,
                        first_msg + action_msg + "...",
                        user_id=user_id,
                    )
                await asyncio.sleep(2)
                if suc:
                    await safe_edit(msg, first_msg + action_msg + success_msg, user_id)
                else:
                    msg, suc = await safe_send(
                        bot,
                        user_id,
                        first_msg + action_msg + suc,
                        user_id=user_id,
                    )
                await asyncio.sleep(1)
                await safe_send(
                        bot,
                        user_id, f"Команда соперника нападает!\n\nСчёт: {data['own_score'] + score} - {data['opp_score']}",
                        user_id=user_id,
                    )
                await start_bot_attack(callback, state, False, db)
            else:
                await safe_send(
                        bot,
                        user_id, f"Проход не удался!\nМяч перехвачен, защита снижена на 10%\n\nСчёт: {data['own_score']} - {data['opp_score']}",
                        user_id=user_id,
                    )
                await state.update_data(def_debuff=0.1)
                await start_bot_attack(callback, state, True, db)
        else:
            pass_pair : PlayersPair = None
            if(data['action'] == 2):
                pass_pair = data['first_pair']
            else:
                pass_pair = data['second_pair']
            
            first_msg, success_msg, success = await end_pass(state, pg_pair, pass_pair, False)

            msg, suc = await safe_send(bot, user_id, first_msg + "...", user_id=user_id)
            await asyncio.sleep(2)
            if suc:
                await safe_edit(msg, first_msg + success_msg, user_id)
            else:
                await safe_send(bot, user_id, first_msg + success_msg, user_id=user_id)
            await asyncio.sleep(2)

            if(success):
                await set_positions(state, False, True)
                await send_attack_message(user_id, state)
            else:
                await start_bot_attack(callback, state, True, db)
            
    finally:
        users.unlock_user_actions(user_id)

async def bot_try_pass(callback: CallbackQuery, state: FSMContext, pg_pair : PlayersPair, pass_pair : PlayersPair, db: PgSql):
    user_id = callback.from_user.id
    message = get_pass_message(pg_pair, pass_pair)
    await image_cache.send_card(user_id, pg_pair.attacker.card_id, '🤖' + message)

    await asyncio.sleep(2)

    first_msg, suc_msg, success = await end_pass(state, pg_pair, pass_pair, True)
    await safe_send(bot, user_id, first_msg + suc_msg, user_id=user_id)
    await asyncio.sleep(1)

    if(success):
        await bot_choose_action(callback, state, False, True, db)
    else:
        await start_player_cycle(callback, state, True, True, db)


async def bot_try_dribble(callback: CallbackQuery, state: FSMContext, pair : PlayersPair, db: PgSql):
    user_id = callback.from_user.id
    data = await state.get_data()

    opp_def = pair.defender.get_interior_def() if pair.position == 'interior' else pair.defender.get_perimetr_def()
    message = get_dribble_message(pair.attacker, pair.defender, pair.position, opp_def)
    await image_cache.send_card(user_id, pair.attacker.card_id, '🤖' + message)
    await asyncio.sleep(2)

    first_msg, action_msg, suc_msg, score = await end_attack(pair, True)
    await safe_send(bot, user_id, first_msg + action_msg + suc_msg, user_id=user_id)
    await asyncio.sleep(2)

    if score >= 0:
        await state.update_data(opp_score=data['opp_score'] + score, def_debuff=0)
        await start_player_cycle(callback, state, True, False, db)
    else:
        await bot.send_message(user_id, f'🤖Проход не удался!\n\nМяч перехвачен, защита снижена на 10%')
        await state.update_data(def_debuff=0.1)
        await start_player_cycle(callback, state, True, True, db)

async def start_bot_attack(callback: CallbackQuery, state : FSMContext, save_pg : bool, db: PgSql):
    await asyncio.sleep(1)
    await state.update_data(pass_state='none', pass_count=0)
    await bot_choose_action(callback, state, True, save_pg, db)

async def bot_choose_action(callback: CallbackQuery, state : FSMContext, switch : bool, save_pg : bool, db: PgSql):
    await set_positions(state, switch, save_pg)
    data = await state.get_data()
    pg_pair : PlayersPair = data['pg_pair']
    first_pair : PlayersPair = data['first_pair']
    second_pair : PlayersPair = data['second_pair']
    pass_count = data['pass_count']

    if(pass_count == 3):
        await bot_try_dribble(callback, state, pg_pair, db)
        return

    chance_to_attack = calculate_chance_to_successful_attack(pg_pair)
    
    chance_to_pass_first = calculate_goodness_pass(pg_pair, first_pair)
    chance_to_pass_second = calculate_goodness_pass(pg_pair, second_pair)

    massive = [chance_to_attack, chance_to_pass_first, chance_to_pass_second]

    index = massive.index(max(massive))

    match index:
        case 0:
            await bot_try_dribble(callback, state, pg_pair, db)
        case 1:
            await bot_try_pass(callback, state, pg_pair, first_pair, db)
        case 2:
            await bot_try_pass(callback, state, pg_pair, second_pair, db)
            
async def end_pass(state : FSMContext, pair : PlayersPair, pass_pair : PlayersPair, is_bot : bool = False) -> str | str | bool:
    data = await state.get_data()

    pass_state = 'none'
    pass_count = data['pass_count']

    hands = pair.attacker.get_hands()

    steal = pair.defender.get_steal()

    firstState, secondState = try_to_pass(pair, pass_pair)

    first_message = '🤖' if is_bot else ''
    success_message = ""
    if firstState != PassFirstState.good:
        first_message += f"{pair.attacker.name} под гнётом защиты\n[{hands}👐 vs {steal}🥷]!\n"
        if(firstState == PassFirstState.bad):
            success_message = f"Получается передать к {pass_pair.attacker.name} плохой пас!\n\nДрибблинг у игрока снижен на 15%"
            success_message += f"\nПасов осталось - {max_passes - pass_count - 1}"
            pass_state = 'bad'
        else:
            success_message = "У противника получается выбить мяч!\n\nЗащита снижена на 10%"
    else:
        first_message += f"{pair.attacker.name} пасует к {pass_pair.attacker.name}\n"
        if(secondState == PassSecondState.normal):
            pass_state = 'normal'
            success_message = f"Пасс удался! Защита противника снижена на 10%"
        elif(secondState == PassSecondState.good):
            pass_state = 'good'
            success_message = "Отличный пасс! Защита противника снижена на 25%"
        else:
            pass_state = 'perfect'
            success_message = "ИДЕАЛЬНЫЙ ПАСС! Защита противника разбита"
        success_message += f"\nПасов осталось - {max_passes - pass_count - 1}"

    if(firstState != PassFirstState.lost):
        await state.update_data(pg_pair=pass_pair, pass_state=pass_state, pass_count=data["pass_count"] + 1)
        result = True
    else:
        await state.update_data(def_debuff=0.1)
        result = False
    
    return first_message, success_message, result

async def end_attack(players_pair : PlayersPair, is_bot : bool = False) -> (str | str | str | int):
    player : PlayerInfo = players_pair.attacker
    pos = players_pair.position

    hands = player.get_hands()
    dribbling = player.get_dribbling()

    defence = players_pair.defender.get_interior_def() if players_pair.position == 'interior' else players_pair.defender.get_perimetr_def()
    steal = players_pair.defender.get_steal()
    block = players_pair.defender.get_block()

    throw_message = ""
    attack = 0
    score = 0

    first_message = '🤖' if is_bot else ''
    if(pos == 'interior'):
        dunk = player.get_dunk()
        layup = player.get_layup()
        all = dunk + layup

        rand = random.random()

        if(rand <= dunk / all):
            attack = dunk
            score = 2
            throw_message = f"Попытка заданчить (%s⤵️)"
        else:
            score = 2
            attack = layup
            throw_message = f"Попытка сделать лэй-ап (%s⤴️)"

    else:
        three = player.get_three_point_shot()
        midpoint = player.get_mid_point_shot()
        all = three + midpoint

        rand = random.random()

        attack = 0

        if(rand <= three / all):
            attack = three
            score = 3
            throw_message =  f"Бросает трешку (%s3️⃣)"
        else:
            score = 2
            attack = midpoint
            throw_message =  f"Бросает двухочковый (%s2️⃣)"
    
    attackState = try_shoot(dribbling, defence, hands, steal, attack, block)
    first_message += f"{players_pair.attacker.name} атакует"
    action_message = ""
    success_message = ""
    
    await asyncio.sleep(2)
    if attackState in [AttackFirstState.lost, AttackFirstState.trough_block_fail, AttackFirstState.trough_block_success]:
        buff = shoot_buff_values[ShootType.through_block]
        chance = min(100, int(buff * attack - int(block / 2)))
        if attackState == AttackFirstState.lost:
            action_message = "\nНеудача, противник выбил мяч!"
            score = -1
        elif(attackState == AttackFirstState.trough_block_success):
            action_message = '\n' + throw_message % attack + f"\nчерез блок ({block}🚫)\nШанс {chance}%!"
            success_message = "\n\nУспех!"
        else:
            action_message = '\n' + throw_message % attack + f"\nчерез блок ({block}🚫)\nШанс {chance}%!"
            success_message = "\n\nБЛОК!"
            score = 0
    elif attackState in [AttackFirstState.hard_throw_fail, AttackFirstState.hard_throw_success]:
        buff = shoot_buff_values[ShootType.hard_throw]
        attack = min(100, int(buff * attack))
        action_message = f"\nСложный бросок!\n" + throw_message % attack
        if attackState == AttackFirstState.hard_throw_success:
            success_message = "\n\nУспех!"
        else:
            success_message = "\n\nПромах!"
            score = 0
    elif attackState in [AttackFirstState.free_throw_success, AttackFirstState.free_throw_fail]:
        buff = shoot_buff_values[ShootType.free_throw]
        attack = min(100, int(buff * attack))
        action_message = f"\nОткрытый бросок!\n" + throw_message % attack
        if attackState == AttackFirstState.free_throw_success:
            success_message = "\n\nУспех!"
        else:
            success_message = "\n\nПромах!"
            score = 0

    return first_message, action_message, success_message, score

async def give_reward(reward_dict: dict, user_id: int):
    text = ''
    for key in reward_dict.keys():
        if key == 'try':
            text += f'{reward_dict[key]}🤲 '
            add = reward_dict[key]
            users.add_additional_try(user_id, add)
        elif key == 'balls':
            text += f'{reward_dict[key]}🏀 '
            add = reward_dict[key]
            users.add_throw(user_id, add)
        elif key == 'bronze_pack':
            text += f'{reward_dict[key]}📦🥉 '
            users.add_packs('bronze', 1, user_id)
    
    await bot.send_message(user_id, f"🎗Ты получаешь награду за достижение рейтинга : {text}")

async def check_rewards(max_rating: int, new_rating: int, user_id: int, db: PgSql):
    rewards = await db.conn.fetch('SELECT rating, reward FROM rewards_5v5')

    for reward in rewards:
        if max_rating < reward[0] and new_rating >= reward[0]:
            await give_reward(reward[1], user_id)
            break

async def change_rating(user_id, add_rating, db: PgSql):
    res = await db.conn.fetchrow('SELECT rating, max_rating FROM user_rating WHERE user_id = $1', user_id)
    rating = res['rating']
    max_rating = res['max_rating']
    if rating + add_rating > max_rating:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
        await check_rewards(max_rating, rating + add_rating, user_id, db)
        max_rating = rating + add_rating # лишнее, в sql пересчитывается
    await db.conn.execute(f"UPDATE user_rating SET (rating, played_this_season, max_rating) = (GREATEST(rating + {add_rating}, 0), TRUE, GREATEST(max_rating, rating + {add_rating})) WHERE user_id={user_id};")


async def start_player_cycle(callback : CallbackQuery, state : FSMContext, switch : bool, save_pg : bool, db: PgSql):
    data = await state.get_data()
    user_id = callback.from_user.id
    await asyncio.sleep(1)
    if(data['cycle'] == max_cycles):

        message = f"Конец игры\n\nСчёт: {data['own_score']} - {data['opp_score']}\n"
        add_rating = data['own_score'] - data['opp_score']
        if(data['own_score'] == data['opp_score']):
            message += "Ничья!\n\n"
        elif(data['own_score'] > data['opp_score']):
            add_rating += 10
            message += "Ты победил!\n\n"
            # await tasks.PerformAction(tasks.games_winned, user_id)
        else:
            add_rating += -10
            message += "Ты проиграл!\n\n"
            # await tasks.PerformAction(tasks.games_loosed, user_id)
        # await tasks.PerformAction(tasks.games_played, user_id)

        rating = await db.conn.fetchval("SELECT rating FROM user_rating WHERE user_id = $1", user_id)

        sign = "+"
        if add_rating < 0:
            sign = "-"

        if(rating + add_rating < 0):
            add_rating = 0 - rating
        
        message += f'Изменение рейтинга: {rating} {sign} {abs(add_rating)}🏆'
        logger.info(f"Изменение рейтинга user {user_id} {sign}{add_rating}")
        await bot.send_message(user_id, message, reply_markup=keyboards.main_keyboard)
        await change_rating(user_id, add_rating, db)
        await state.clear()
    else:
        data['pass_state'] = 'none'
        data['pass_count'] = 0
        data['cycle'] += 1
        await state.update_data(data)
        await send_start_player_attack_message(callback, state)
        await set_positions(state, switch, save_pg)
        await send_attack_message(user_id, state)

@router.callback_query(F.data.in_({"defense", "attack", "balance"}), StateFilter(Match.ChoosingTactic))
async def pick_tactic(callback : CallbackQuery, state : FSMContext, db: PgSql):
    data = await state.get_data()
    team : Team = data['att_team']
    team.set_tactic(callback.data)
    team.set_current_stats_as_base()
    await state.update_data(own_score=0, opp_score=0, cycle=0, def_debuff=0)
    await state.set_state(Match.PlayingMatch)
    await callback.message.edit_text(text=f"Ты выбрал {pick_tactic_message[callback.data]} тактику", reply_markup=None)
    await start_player_cycle(callback, state, False, False, db)

@router.callback_query(F.data == "play_ranked", StateFilter(Match.ChoosingToPlay))
async def play_ranked(callback : CallbackQuery, state : FSMContext, db: PgSql):
    """
    Матч Против бота, НЕ требует зависимости для ТЗ(онлайн пвп"игрок против игрока", а не бот vs игрок)
    """
    user_id = callback.from_user.id
    tickets = await db.conn.fetchval("SELECT tickets FROM user_rating WHERE user_id = $1", user_id)

    if(tickets <= 0):
        await callback.answer("Билеты закончились")
        return
    opponents_info = await db.conn.fetch(f'''WITH target_rank AS (
    SELECT rating 
    FROM user_rating 
    WHERE user_id = $1 
),
lower_ranks AS (
    SELECT ur.user_id, ur.rating, ur.defense_tactic
    FROM user_rating ur
	JOIN user_team ut ON ur.user_id = ut.user_id
    WHERE (ut.PG, ut.PF, ut.C, ut.SF, ut.SG) IS NOT null
	AND ur.rating <= (SELECT rating FROM target_rank)
	AND ur.user_id != $1
    ORDER BY ur.rating DESC 
    LIMIT 10
),
higher_ranks AS (
    SELECT ur.user_id, ur.rating, ur.defense_tactic
    FROM user_rating ur
	JOIN user_team ut ON ur.user_id = ut.user_id
    WHERE (ut.PG, ut.PF, ut.C, ut.SF, ut.SG) IS NOT null
	AND ur.rating > (SELECT rating FROM target_rank)
	AND ur.user_id != $1
    ORDER BY ur.rating ASC 
    LIMIT 10
)
SELECT * FROM lower_ranks
UNION ALL
SELECT * FROM higher_ranks''', user_id)
#     cursor.execute(f'''WITH target_rank AS (
#     SELECT rating
#     FROM user_rating
#     WHERE user_id = {user_id}
# ),
# lower_ranks AS (
#     SELECT ur.user_id, ur.rating, ur.defense_tactic
#     FROM user_rating ur
# 	JOIN user_team ut ON ur.user_id = ut.user_id
#     WHERE (ut.PG, ut.PF, ut.C, ut.SF, ut.SG) IS NOT null
# 	AND ur.rating <= (SELECT rating FROM target_rank)
# 	AND ur.user_id != {user_id}
#     ORDER BY ur.rating DESC
#     LIMIT 200
# ),
# higher_ranks AS (
#     SELECT ur.user_id, ur.rating, ur.defense_tactic
#     FROM user_rating ur
# 	JOIN user_team ut ON ur.user_id = ut.user_id
#     WHERE (ut.PG, ut.PF, ut.C, ut.SF, ut.SG) IS NOT null
# 	AND ur.rating > (SELECT rating FROM target_rank)
# 	AND ur.user_id != {user_id}
#     ORDER BY ur.rating ASC
#     LIMIT 200
# )
# SELECT * FROM lower_ranks
# UNION ALL
# SELECT * FROM higher_ranks;''')
    if(len(opponents_info) == 0):
    # if not opponents_info:
        await callback.answer("Недостаточно пользователей")
        return
    await state.set_state(Match.StartedRanked)
    await callback.message.delete()
    message = await bot.send_message(chat_id=user_id, text="Ищем противника...", reply_markup=keyboards.ReplyKeyboardRemove())
    await db.conn.execute(f"UPDATE user_rating SET tickets = tickets - 1 WHERE user_id = $1", user_id)


    index = random.randint(0, len(opponents_info) - 1)
    opponent = opponents_info[index]
    opp_team : Team = await Team.get_team_from_user_id(opponent[0], db)
    opp_team.set_tactic(opponent[2])
    opp_team.set_current_stats_as_base()
    own_team = await Team.get_team_from_user_id(user_id, db)
    await state.update_data(att_team=own_team, def_team=opp_team, opp_id=opponent[0])
    await asyncio.sleep(2)
    await message.delete()

    "Превью оппонента"
    team_info = await get_team_info(opponent[0], db)
    await bot.send_message(chat_id=user_id, text=f"Твой оппонент - {await db.users.get_username(opponent[0])} | {opponent[1]}🏆\n\nКоманда({tactic_message[opponent[2]]}):\n\n{team_info}", parse_mode='html')
    await asyncio.sleep(2)

    "Пользователь играет(должен выбрать тактику)"
    await state.set_state(Match.ChoosingTactic)
    await bot.send_message(chat_id=user_id, text="Выбери тактику", reply_markup=keyboards.keyboard_choose_tactic)
    await callback.answer()

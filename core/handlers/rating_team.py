
import app.keyboards as keyboards

import app.users as users

from app.users import truncate_text
from app.bot import image_cache
from core.config_dir.config import bot

from aiogram.types import LinkPreviewOptions

from aiogram import F, Router
from aiogram.types import CallbackQuery

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from core.data.postgres import PgSql
from core.handlers.rating_header import Match, positions, get_max_rating, get_user_defense_tactic, Team

router = Router()

async def get_rating_text(user_id, db: PgSql) -> str:
    user_info = await db.conn.fetchrow(f"SELECT rating, played_this_season FROM user_rating WHERE user_id = $1", user_id)

    # return f"Межсезонье⏳"
    if not user_info['played_this_season']:
    # if user_info[1] is False:
        return "Ты ещё не играл в этом сезоне"
    else:
        return f"Твой рейтинг - {user_info['rating']}🏆"

@router.callback_query(F.data == "members", StateFilter(Match.Team))
async def choose_members(callback : CallbackQuery, state : FSMContext, db: PgSql):
    data = await state.get_data()
    tactic = data['tactic']
    team : Team = await Team.get_team_from_user_id(callback.from_user.id, db)
    team.set_tactic(tactic)
    await state.update_data(team=team)
    await watch_team(callback, state, 'PG', False)

@router.callback_query(F.data == 'back', StateFilter(Match.WatchingTeam, Match.WatchingTactic))
async def back_to_tactic(callback : CallbackQuery, state : FSMContext):
    await callback.message.delete()
    await state.set_state(Match.Team)
    await bot.send_message(chat_id=callback.from_user.id, text="⛹️5 на 5", reply_markup=keyboards.keyboard_5v5_team)

@router.callback_query(F.data == "my_team", StateFilter(Match.Main))
async def show_team(callback : CallbackQuery, state : FSMContext, db: PgSql):
    await state.set_state(Match.Team)
    tactic = await get_user_defense_tactic(callback.from_user.id, db)
    await state.update_data(tactic=tactic)
    await callback.message.edit_text(text="⛹️5 на 5", reply_markup=keyboards.keyboard_5v5_team)

@router.callback_query(F.data == 'tactic', StateFilter(Match.Team))
async def show_tactics(callback : CallbackQuery, state : FSMContext):
    await state.set_state(Match.WatchingTactic)
    data = await state.get_data()
    await callback.message.edit_text(text="⛹️5 на 5\n\nВыбери тактику для обороны.", reply_markup=keyboards.craft_choose_tactic(data['tactic']))

@router.callback_query(F.data.in_({"defense", "attack", "balance"}), StateFilter(Match.WatchingTactic))
async def choose_tactic(callback : CallbackQuery, state : FSMContext, db: PgSql):
    await db.conn.execute(f"UPDATE user_rating SET defense_tactic = '{callback.data}' WHERE user_id={callback.from_user.id};")
    await state.update_data(tactic=callback.data)
    await callback.message.edit_text(text="⛹️5 на 5\n\nВыбери тактику для обороны.", reply_markup=keyboards.craft_choose_tactic(callback.data))


@router.callback_query(F.data == 'ticket_channel', StateFilter(Match.Main))
async def ticket_channels(callback: CallbackQuery, state: FSMContext, db: PgSql):
    await state.set_state(Match.WatchingChannels)
    text = "⛹️5 на 5\n\nПодпишись на каналы и получай за это билетики.\n"
    channels_info = db.get_channels_info()
    used_id = callback.from_user.id
    not_subbed_info = []
    subbed_info = []
    expired_info = []


    result = await db.conn.fetchrow(f"SELECT subscribed_channels, used_channels FROM users WHERE user_id = $1", used_id)
    used = result['used_channels']
    subbed = result['subscribed_channels']

    for info in channels_info:
        if(info[3] != 't'):
            continue
        if(info[0] in subbed):
            if(info[0] in used):
                expired_info.append(info)
            else:
                subbed_info.append(info)
        else:
            not_subbed_info.append(info)
    
    for info in not_subbed_info:
        text += "\n" + "❌" + f'<a href="{info[2]}">{info[1]}</a>'
    for info in subbed_info:
        text += "\n" + "✅" + f'<a href="{info[2]}">{info[1]}</a>'
    for info in expired_info:
        text += "\n" + "🕜" + f'<a href="{info[2]}">{info[1]}</a>'

    text +='\n\n<a href="https://t.me/STEEEPSERVICES">Добавить канал</a>'

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.back, link_preview_options = LinkPreviewOptions(is_disabled=True))

@router.callback_query(F.data == "rating_table", StateFilter(Match.Main))
async def show_rating_table(callback : CallbackQuery, state : FSMContext, db: PgSql):

    users_info = await db.conn.fetch("SELECT user_id, rating FROM user_rating WHERE played_this_season is TRUE ORDER BY rating DESC LIMIT 10;")
    if(len(users_info) == 0):
        await callback.answer(text="Рейтинг пуст")
        return
    
    await state.set_state(Match.WatchingRating)
    players_count = await db.conn.fetchval("SELECT COUNT(*) FROM user_rating WHERE played_this_season is TRUE;")
    max_rating = users_info[0]['rating']
    own_info = await db.conn.fetch(f"""SELECT * FROM (SELECT rating, user_id, ROW_NUMBER() OVER (ORDER BY rating DESC) AS row_number FROM user_rating WHERE played_this_season is TRUE) AS rating_table WHERE user_id={callback.from_user.id};""")
    text = f"Играют в этом сезоне: <b>{players_count:5d}</b>⛹️‍♂️\n     <b><i>—————————————</i></b>\n"
    len_rating = len(str(max_rating))
    len_pos = 2
    if(own_info is None):
        for i in range(len(users_info)):
            username = users.get_username(users_info[i]['user_id'])
            if(username != 'Аноним'):
                text += f'<code>{i + 1:{len_pos}d}) {users_info[i]['rating']:{len_rating}d}🏆</code> - <a href="https://t.me/{username[1:]}">{truncate_text(username, 12)}</a>\n'
            else:
                text += f"<code>{i + 1:{len_pos}d}) {users_info[i]['rating']:{len_rating}d}🏆</code> - Аноним\n"
            
        text += "       <b><i>—————————————</i></b>\n"
        text += f'Ты еще не играл в этом сезоне!\n'
    else:
        if own_info[2] > 10:
            len_pos = len(str(own_info[2]))
        for i in range(len(users_info)):
            username = users.get_username(users_info[i]['user_id'])
            if(username != 'Аноним'):
                if(i == own_info[2] - 1):
                    text += f'<b><i><code>{i + 1:{len_pos}d}) {users_info[i]['rating']:{len_rating}d}🏆</code> - <a href="https://t.me/{username[1:]}">{truncate_text(username, 12)}</a></i></b>\n'
                else:
                    text += f'<code>{i + 1:{len_pos}d}) {users_info[i]['rating']:{len_rating}d}🏆</code> - <a href="https://t.me/{username[1:]}">{truncate_text(username, 12)}</a>\n'
            else:
                text += f"<code>{i + 1:{len_pos}d}) {users_info[i]['rating']:{len_rating}d}🏆</code> - Аноним\n"
        if own_info[2] > 10:
            username = users.get_username(own_info['user_id'])
            text += "      <b><i>—————————————\n"
            text += f'<code>{own_info[2]:{len_pos}d}) {own_info[0]:{len_rating}d}🏆</code> - <a href="https://t.me/{username[1:]}">{truncate_text(username, 12)}</a></i></b>\n'


    await callback.message.edit_text(text=text, reply_markup=keyboards.back, parse_mode="html", link_preview_options = LinkPreviewOptions(is_disabled=True))


@router.callback_query(F.data == 'back', StateFilter(Match.Team, Match.WatchingChannels, Match.ChoosingToPlay, Match.WatchingRules, Match.WatchingRating))
async def back_to_main(callback: CallbackQuery, state : FSMContext, db: PgSql):
    await state.set_state(Match.Main)
    await callback.message.edit_text(text=f"⛹️5 на 5\n\n{await get_rating_text(callback.from_user.id, db)}", reply_markup=keyboards.keyboard_5v5)

@router.callback_query(F.data == "5v5")
async def show_5v5_keyboard(callback : CallbackQuery, state : FSMContext, db: PgSql):
    await state.set_state(Match.Main)
    await callback.message.edit_text(text=f"⛹️5 на 5\n\n{await get_rating_text(callback.from_user.id, db)}", reply_markup=keyboards.keyboard_5v5)

@router.callback_query(F.data == "play", StateFilter(Match.Main))
async def show_play_keyboard(callback : CallbackQuery, state : FSMContext, db: PgSql):
    # team_ids = await db.conn.fetchrow(f"SELECT {positions[0]}, {positions[1]}, {positions[2]}, {positions[3]}, {positions[4]} FROM user_team WHERE user_id={callback.from_user.id};")
    team_ids = await db.conn.fetchrow(f"SELECT {', '.join(positions)} FROM user_team WHERE user_id = $1 AND ({', '.join(positions)}) NOT NULL", callback.from_user.id)
    if None in team_ids:
        await callback.answer(text="Сперва собери команду!", show_alert=True)
        return

    tickets = await db.conn.fetchval(f"SELECT tickets FROM user_rating WHERE user_id = $1", callback.from_user.id)
    await state.set_state(Match.ChoosingToPlay)
    await callback.message.edit_text(text="⛹️5 на 5", reply_markup=keyboards.craft_match_play_keyboard(tickets))

async def watch_team(callback: CallbackQuery, state : FSMContext, start_pos : str, have : bool):
    await state.set_state(Match.WatchingTeam)
    await state.update_data(current_pos=start_pos, have=have)
    await choose_player(start_pos, callback, state)



categories = ['all', 'bronze', 'silver', 'gold', 'legend', 'diamond']


async def choose_player(position: str, callback : CallbackQuery, state : FSMContext):
    """
    Нет запросов в БД, убрал соединенеи с ней
    """
    await state.set_state(Match.WatchingTeam)
    # conn = db.connection
    # cursor = conn.cursor()
    data = await state.get_data()
    current_pos : int = positions.index(position)
    team : Team = data["team"]
    have : bool= data['have']

    player = team.players[current_pos]
    new_have = player is not None
    text = "Ты никого не выбрал."
    # if new_have:
    #     photo = cards.get_card_photo(player.card_id)
    #     text = player.to_text(data['tactic'])
    #     mediaPhoto = InputMediaPhoto(media=photo, caption=text, parse_mode='html')

    new_keyboard = keyboards.craft_team_keyboard(position, new_have, positions[current_pos - 1], positions[(current_pos + 1) % len(positions)])
    await state.update_data(have=new_have)
    if new_have:
        await image_cache.edit_card_media(callback.from_user.id, callback.message.message_id, player.card_id, player.to_text(data['tactic']), new_keyboard)
        # await callback.message.edit_media(media=mediaPhoto, reply_markup=new_keyboard)
    else:
        if(have):
            await callback.message.delete()
            await bot.send_message(chat_id=callback.from_user.id, text=text, reply_markup=new_keyboard)
        else:
            await callback.message.edit_text(text=text, reply_markup=new_keyboard)
    # cursor.close()



@router.callback_query(F.data == "rewards", StateFilter(Match.Main))
async def rewards(callback: CallbackQuery, state: FSMContext, db: PgSql):
    await state.set_state(Match.WatchingRating)
    user_id = callback.from_user.id
    max_rating = await get_max_rating(user_id, db)
    rewards = await db.conn.fetch("SELECT rating, reward FROM rewards_5v5;")
    text = '🎗Награды\n\n'
    for reward in rewards:
        if max_rating >= reward["rating"]:
            text += '✅'
        else:
            text += '❌'
        text += f' {reward["rating"]}🏆: '
        for key in reward["reward"]:
            if key == 'try':
                text += f'{reward["reward"][key]}🤲 '
                text += '\n         |\n'
            elif key == 'balls':
                text += f'{reward["reward"][key]}🏀 '
                text += '\n         |\n'
            elif key == 'bronze_pack':
                text += f'{reward["reward"][key]}📦🥉 '
    
    await callback.message.edit_text(text, reply_markup=keyboards.back)

rules_count = 8

@router.callback_query(F.data == 'rules', StateFilter(Match.Main))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await state.set_state(Match.WatchingRules)
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(0, rules_count), parse_mode='html', text="""<b><i>Суть игры</i></b>\n
• Каждый STEPbro может собрать свою команду из 5 карточек. Этой командой он атакует чужие, а также в фоновом режиме она защищает его от нападений других STEPbro.\n 
• У каждого игрока есть свой рейтинг, который влияет на его положение в общей таблице.\n
• В конце сезона игроки с наивысшим рейтингом получают призы.""")
    
@router.callback_query(F.data == 'rule_0', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(0, rules_count), parse_mode='html', text="""<b><i>Суть игры</i></b>\n
• Каждый STEPbro может собрать свою команду из 5 карточек. Этой командой он атакует чужие, а также в фоновом режиме она защищает его от нападений других STEPbro.\n 
• У каждого игрока есть свой рейтинг, который влияет на его положение в общей таблице.\n
• В конце сезона игроки с наивысшим рейтингом получают призы.""")
    
@router.callback_query(F.data == 'rule_1', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(1, rules_count), parse_mode='html', text="""<b><i>Подготовка к 5 на 5</i></b>\n
Перед игрой в 5 на 5 необходимо набрать свой состав и выбрать тактику для обороны. Это можно сделать в разделе "Команда".

<b><i>Состав</i></b>\n
• Выставляя игрока на позицию не присущую ему, его все характеристики ухудшаются на 15%.
• В ином случае характеристики не изменяются.

<b><i>Тактика</i></b>\n
• Атакующая (⚔️) - улучшение дриблинга на 12%
• Защитная (🛡) - улучшение защиты на 12%
• Сбалансированная (⚖️) - улучшение дриблинга и защиты на 6%""")
    
@router.callback_query(F.data == 'rule_2', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(2, rules_count), parse_mode='html', text="""<b><i>Билетики</i></b>\n
• За один билетик можно сыграть один матч 5 на 5.
• Каждый день обновляются билетики в 14:00.
• При подписке на все предложенные каналы в разделе "Каналы" ежедневно будут выдаваться 3 билетика вместо 1.
• Если отписаться от канала в разделе "Каналы", ты перестанешь получать дополнительные два билетика за них, но если передумаешь и подпишешься снова, дополнительные два билетика начнут начислять только через неделю.""")
    
@router.callback_query(F.data == 'rule_3', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(3, rules_count), parse_mode='html', text="""<b><i>Рейтинг</i></b>\n
• После нападения на команду существует 3 исхода:
    • Поражение. Отнимается 10 рейтинга + разница в счёте.
    • Ничья. Рейтинг не изменяется.
    • Победа. Прибавляется 10 рейтинга + разница в  счёте.\n
• При нападении на твою команду, рейтинг не будет изменен.""")
    
@router.callback_query(F.data == 'rule_4', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(4, rules_count), parse_mode='html', text="""<b><i>Матч 5 на 5</i></b>\n
Каждый раз, когда ты начинаешь игру в 5 на 5 это значит, что составленная команда "нападает" на команду случайного противника.

<b><i>Ход игры</i></b>\n
• В начале матча нужно выбрать тактику для нападения на команду соперника.
• Игру начинает твоя команда, всего 5 атак.
• В начале атаки мяч оказывается у PG с 50% вероятностью, либо у одного из двух других игроков с лучшим показателем паса.
• Можно выбрать одно из трех действий: пройти самому или отдать пас одному из двух сокомандников.
• После завершения действия, команда противника начинает атаковать в ответ.""")
    
@router.callback_query(F.data == 'rule_5', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(5, rules_count), parse_mode='html', text="""<b><i>Матч 5 на 5</i></b>
<b><i>Проход через соперника</i></b>\n
Перед броском, игрок пытается создать пространство для себя.
У игроков сталкиваются характеристики дриблинга(⛹️‍♂️) и обороны(🛡).
Исходы:
• Свободный бросок. Характеристика броска увеличивается на 20%.
• Сложный бросок. Характеристика броска уменьшается на 10%.
• Защита прессует игрока, отсюда сталкиваются характеристики удержания мяча(👐) и кражи(🥷):
        • Бросок через блок. Характеристика броска уменьшается на 10%, поверх этого отнимается половина от характеристики блока(🚫) защитника.
        • Перехваченный мяч. Соперник начинает атаку, на весь цикл атаки твоя защита снижена на 10%

Характеристики броска, лэй-апа и данка показывают в процентах шанс успеха.""")
    
@router.callback_query(F.data == 'rule_6', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(6, rules_count), parse_mode='html', text="""<b><i>Матч 5 на 5</i></b>
<b><i>Пас</i></b>\n
При попытке отдать пас сравниваются характеристики: пас (🤝) у владеющего мячом и защита (🛡) у защищающегося.
                                     
Исходы:
• Свободный пасс, сталкиваются характеристики: пас(🤝) отдающего и реакция на пасы(🪬) защитника принимающего:
        • Хороший пасс. Ухудшение обороны защищающегося на 10%.
        • Отличный пасс. Ухудшение обороны защищающегося на 20%.
        • Идеальный пасс. Защита противника уничтожена, остается только успешно забить.
                                         
• Защита прессует игрока, отсюда сталкиваются характеристики удержания мяча(👐) и кражы(🥷):
        • Плохой пасс. Ухудшение дриблинга на 15% игрока, которому отдали пасс;
        • Неудачный пасс. Соперник начинает атаку, на весь цикл атаки твоя защита снижена на 10%""")

@router.callback_query(F.data == 'rule_7', StateFilter(Match.WatchingRules))
async def watch_rules(callback: CallbackQuery, state : FSMContext):
    await callback.message.edit_text(reply_markup=keyboards.craft_rule(7, rules_count), parse_mode='html', text="""<b><i>Обозначения</i></b>
<b><i>Характеристики карточек:</i></b>
    3️⃣ - Трехочковый бросок
    2️⃣ - Двухочковый бросок
    ⤴️ - Лэй-ап
    ⤵️ - Данк
    ⛹️‍♂️ - Дриблинг
    🤝 - Пасс
    🎯 - Защита на периметре
    🎨 - Защита в краске
    🚫 - Блок
    🪬 - Реакция на пасы в защите
    👐 - Удержание мяча
    🥷 - Кража

<b><i>5 на 5:</i></b>
    📍 - Позиция игрока
    🛡 - Защита и в краске, и на периметре""")
    
    

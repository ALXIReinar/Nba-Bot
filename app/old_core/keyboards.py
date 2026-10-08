from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# from app.modules.cards.service import CardsService
# from app.modules.cards.sql_queries import CardsQueries

# from app.modules.workshop.sql_queries import WorkshopQueries
# from app.modules.workshop.service import WorkshopService

# from app.modules.collection.sql_queries import CollectionQueries
# from app.modules.collection.service import CollectionService

from app.core.bot import logger

def add_back_button(keyboard) -> InlineKeyboardBuilder:
    keyboard.append([InlineKeyboardButton(text="↪Назад", callback_data="back")])
    return keyboard

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤲Получить карту"), KeyboardButton(text="🧍Профиль")],
        [KeyboardButton(text="⛹‍♂️Crossstep")]
    ], 
    resize_keyboard=True,
    input_field_placeholder='Бро, попробуй открыть карту)'
)

end_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Действие закончилось", callback_data='NONE')],
    ]
)

trade_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Готово", callback_data="done")],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

back = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

def craft_back(text="↪Назад", callback_data="back"):
    return InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])

merch = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📏Таблица размерности", callback_data='size_table')],
        [InlineKeyboardButton(text="🖼Фото", callback_data='merch_photo_0')],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

def craft_throw_ball(try_count):
    return InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=f"🏀Кинуть мячик ({try_count})", callback_data='try_throw' if try_count > 0 else 'NONE')],
        [InlineKeyboardButton(text="💳Купить мячики", callback_data='buy_throws')],
        [InlineKeyboardButton(text="❕Правила", callback_data='rule_0'), InlineKeyboardButton(text="📢Каналы", callback_data='watch_channels')],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

accept = InlineKeyboardMarkup(
    inline_keyboard=
    [[InlineKeyboardButton(text="✍️Подтвердить", callback_data="approve")], [InlineKeyboardButton(text="↪Назад", callback_data="back")]])


def approve(index):
    return InlineKeyboardMarkup(
    inline_keyboard=
    [[InlineKeyboardButton(text="❌Нет", callback_data="back")], [InlineKeyboardButton(text="✅Ок", callback_data=f"ok_{index}")]])

workshop_keyboard =  InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔧Скрафтить", callback_data='craft')],
        [InlineKeyboardButton(text="🔨Разобрать", callback_data='rubbish')],
        [InlineKeyboardButton(text='↪️Назад', callback_data='back')]
    ]
)

crossstep_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        # [InlineKeyboardButton(text="🎄Новый год", callback_data='new_year_table')],
        [InlineKeyboardButton(text="🛠Мастерская", callback_data='workshop')],
        [InlineKeyboardButton(text="🤝Обменять", callback_data='trade_cards')],
        # [InlineKeyboardButton(text="🎀Подарить", callback_data='present_card')],
        [InlineKeyboardButton(text="🏀Бросить мячик", callback_data="throw_ball")],
        [InlineKeyboardButton(text="📦Открыть пак", callback_data="packs")],
        [InlineKeyboardButton(text="🛍Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="⛹5 на 5 (бета)", callback_data="5v5")],
        [InlineKeyboardButton(text="📌Про STEP", callback_data="info")]
    ]
)

shop_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏀Мячики", callback_data="shop_throw")],
        [InlineKeyboardButton(text="📦Паки", callback_data="shop_pack")],
        [InlineKeyboardButton(text="👕Мерч", callback_data="shop_merch")],
        [InlineKeyboardButton(text='↪️Назад', callback_data='back')]
    ]
)

def craft_choose_circle(id, callback_data, size):
    keyboard = []
    keyboard.append([InlineKeyboardButton(text='<', callback_data=f'{callback_data}_{(id - 1) % size}'), InlineKeyboardButton(text='>', callback_data=f'{callback_data}_{(id + 1) % size}')])
    keyboard.append([InlineKeyboardButton(text='↪️Назад', callback_data='back')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def craft_pack_keyboard(have, id, size, is_shop = False):
    keyboard = []
    if not is_shop:
        keyboard.append([InlineKeyboardButton(text=f"🔓Открыть ({have})", callback_data=f'open_pack_{id}')])

    keyboard.append([InlineKeyboardButton(text=f"💳Купить", callback_data=f'pack_prices_{id}')])
    keyboard.append([InlineKeyboardButton(text='<', callback_data=f'show_pack_{(id - 1) % size}'), InlineKeyboardButton(text='>', callback_data=f'show_pack_{(id + 1) % size}')])
    keyboard.append([InlineKeyboardButton(text='↪️Назад', callback_data='back')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def craft_next_pack_card(next_index, cards_len):
    next_index += 1
    if next_index == cards_len:
        return back
    return InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=f"({next_index}/{cards_len})", callback_data=f'NONE'), InlineKeyboardButton(text=f"Далее", callback_data=f'pack_card_{next_index}')],
    ]
)

def craft_buy_button(price : int):
    return InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=f"💳Заплатить {int(price / 100)},{price % 100:02d} RUB", pay=True)],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

def craft_buy(price_labels : list, callback_name : str, sale = 0):
    inline_keyboard = []
    for i in range(len(price_labels)):
        price = price_labels[i]
        text = f"💳Купить {price.label} "
        if(sale > 0):
            text += f"(📉{int(price.amount * (1 - sale) / 100)}₽)"
        else:
            text += f"({int(price.amount / 100)}₽)"
        inline_keyboard.append([InlineKeyboardButton(text=text, callback_data=F"buy_{callback_name}_{i}")])

    inline_keyboard.append([InlineKeyboardButton(text="↪Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def craft_buy_pack(price_labels : list, pack_id, sale):
    return craft_buy(price_labels, F"pack_{pack_id}", sale)

keyboard_choose_tactic = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⚔️", callback_data="attack"),
        InlineKeyboardButton(text="🛡", callback_data="defense"),
        InlineKeyboardButton(text="⚖️", callback_data="balance")]
    ]
)

keyboard_5v5 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👨‍👨‍👦‍👦Команда", callback_data="my_team"), InlineKeyboardButton(text="🎟Сыграть", callback_data="play")],
        [InlineKeyboardButton(text="🏆Таблица рейтинга", callback_data="rating_table")],
        [InlineKeyboardButton(text="🎗Награды", callback_data="rewards")],
        [InlineKeyboardButton(text="❕Правила", callback_data="rules"), InlineKeyboardButton(text="📢Каналы", callback_data="ticket_channel")],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

keyboard_5v5_team = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👨‍👨‍👦‍👦Состав", callback_data="members")],
        [InlineKeyboardButton(text="💡Тактика", callback_data="tactic")],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

def craft_choose_tactic(tactic : str):
    tactic_btns = [InlineKeyboardButton(text="⚔️", callback_data="attack"), InlineKeyboardButton(text="🛡", callback_data="defense"), InlineKeyboardButton(text="⚖️", callback_data="balance")]
    keyboard = []
    if tactic == "attack":
        tactic_btns[0].text = f"[ {tactic_btns[0].text} ]"
    elif tactic == "defense":
        tactic_btns[1].text = f"[ {tactic_btns[1].text} ]"
    else:
        tactic_btns[2].text = f"[ {tactic_btns[2].text} ]"
    keyboard.append(tactic_btns)
    add_back_button(keyboard)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# TODO: Коллбек заданий теперь не "tasks", а "challenges_main"
profile_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👀Коллекция", callback_data="watch_cards")],
        [InlineKeyboardButton(text="📔Альбом", callback_data="album")],
        [InlineKeyboardButton(text="📆Задания", callback_data="challenges_main")],
        [InlineKeyboardButton(text="📊Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🫂Пригласить друга", callback_data="referal")],
        [InlineKeyboardButton(text="⚙️Настройки", callback_data="settings")]
    ]
)

settings_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄Обновить имя", callback_data="update_username")],
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

number_str = {1:'1️⃣', 2:'2️⃣', 3:'3️⃣', 4:'4️⃣', 5:'5️⃣'}

def craft_task_keyboard(ready_to_reward : bool, index : int):
    keyboard = []
    if ready_to_reward:
        keyboard.append([InlineKeyboardButton(text="Забрать награду🤲", callback_data=f"task_reward_{index}")])

    add_back_button(keyboard)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def craft_tasks_keyboard(tasks : list[int]):
    keyboard = []
    for i in range(len(tasks)):
        text = ''
        if tasks[i] == 0:
            text = f"{number_str[i + 1]} Задание"
        elif tasks[i] == 1:
            text = "🤲 Задание"
        elif tasks[i] == 2:
            text = "✅ Задание"

        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"show_task_{i}")])

    add_back_button(keyboard)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def craft_keyboard_5v5(action : int):
    button_1 = InlineKeyboardButton(text="⛹️‍♂️", callback_data="1")
    button_2 = InlineKeyboardButton(text="🤝", callback_data="2")
    button_3 = InlineKeyboardButton(text="🤝", callback_data="3")
    massive = [button_1, button_2, button_3]
    massive[action - 1].text = f"[ {massive[action - 1].text} ]"
    run_button = [InlineKeyboardButton(text="Выбрать", callback_data="run")]
    return InlineKeyboardMarkup(inline_keyboard=[massive, run_button])

only_choose_attack = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="[ ⛹️‍♂️ ]", callback_data="NONE"), InlineKeyboardButton(text="❌", callback_data="NONE"), InlineKeyboardButton(text="❌", callback_data="NONE")],
        [InlineKeyboardButton(text="Выбрать", callback_data="run")]
    ]
)
#
# def pick_craft_action(cards_count, dubli_count, dust_count, dust_category : str, need_to_craft : int, workshopService: WorkshopService):
#     return InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text=f"👤Самостоятельно ({cards_count})", callback_data="pick_craft_card")],
#         [InlineKeyboardButton(text=f"👥Из дубликатов ({dubli_count})", callback_data="dublicat_craft_card")],
#         [InlineKeyboardButton(text=f"⏩Из первых {need_to_craft}-ти ({min(need_to_craft, cards_count)})", callback_data="all_craft")],
#         [InlineKeyboardButton(text=f"{workshopService.dusts[dust_category].emoji}Из жетонов ({dust_count})", callback_data='dust_craft')],
#         [InlineKeyboardButton(text="↪Назад", callback_data="back")]
#     ])
#
# pick_rubbish_action = InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text="👤Самостоятельно", callback_data="pick_rubbish_card")],
#         [InlineKeyboardButton(text="👥Из дубликатов", callback_data="rubbish_dublicat_card")],
#         [InlineKeyboardButton(text="↪Назад", callback_data="back")]
#     ]
# )
#
# def craft_match_play_keyboard(tickets_count: int, is_season: bool):
#     keyboard = [[InlineKeyboardButton(text="С другом", callback_data="online_match"),
#                 InlineKeyboardButton(text=("Играть " if is_season else "Тренировка ") + f"({tickets_count}🎟)", callback_data="play_ranked" if tickets_count > 0 else "NONE")]]
#     keyboard = add_back_button(keyboard)
#     return craft_keyboard(keyboard)
#
# def craft_team_keyboard(position : str, can_delete : bool, prev : str, next : str):
#     keyboard = [[InlineKeyboardButton(text='<', callback_data=prev), InlineKeyboardButton(text=f'{position}', callback_data='NONE'), InlineKeyboardButton(text='>', callback_data=next)]]
#     if can_delete:
#         keyboard.append([InlineKeyboardButton(text=f"Заменить", callback_data="pick"), InlineKeyboardButton(text=f"Убрать", callback_data='remove')])
#     else:
#         keyboard.append([InlineKeyboardButton(text=f"Выбрать", callback_data="pick")])
#
#     keyboard.append([InlineKeyboardButton(text="↪Назад", callback_data='back')])
#     return craft_keyboard(keyboard)
#
#
# craft_categories = ['silver', 'gold', 'diamond', 'legend']
#
# async def choose_craft_card(user_id, cardsService : CardsService, collectionQueries: CollectionQueries):
#     keyboard = []
#     for category in craft_categories:
#         template = cardsService.categories[category]
#         count = await collectionQueries.get_cards_count_from_user(user_id, template.craft_from)
#         keyboard.append([InlineKeyboardButton(text=f"{template.single_msg} {count}/{template.need_to_craft}", callback_data=template.eng_name)])
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(
#     inline_keyboard=keyboard)
#
# def choose_trade_for_user(received_trades_count, sended_trades_count):
#     possible = sended_trades_count < 3
#     buttons = []
#     if possible:
#         buttons.append([InlineKeyboardButton(text="📝Предложить", callback_data='create_trade')])
#     if received_trades_count > 0:
#         buttons.append([InlineKeyboardButton(text=f"📥Полученные ({received_trades_count})", callback_data='watch_received_trade')])
#     if sended_trades_count > 0:
#         buttons.append([InlineKeyboardButton(text=f"📤Отправленные ({sended_trades_count})", callback_data='watch_sended_trade')])
#     buttons.append([InlineKeyboardButton(text=f"↪Назад", callback_data='back')])
#     return InlineKeyboardMarkup(inline_keyboard=buttons)
#
# all_categories = ['bronze', 'silver', 'gold', 'diamond', 'legend']
# async def choose_category_except_team_for_user(user_id, collectionService: CollectionService, cardsService: CardsService):
#     keyboard = []
#     all = 0
#     for category in all_categories:
#         template = cardsService.categories[category]
#         count = await collectionService.get_cards_count_except_team_from_user(user_id, template.eng_name)
#         all += count
#         keyboard.append([InlineKeyboardButton(text=f"{template.single_msg} ({count})", callback_data=template.eng_name)])
#     keyboard.insert(0, [InlineKeyboardButton(text=f"👥Все ({all})", callback_data='all')])
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
#
# #TODO: Убрать зависимость, просто передавать count
# async def choose_category_for_user(user_id, cardsService : CardsService, collectionQueries : CollectionQueries):
#     keyboard = []
#     all = 0
#     in_row_count = 0
#     row = []
#     for category in all_categories:
#         template = cardsService.categories[category]
#         count = await collectionQueries.get_cards_count_from_user(user_id, template.eng_name)
#         all += count
#         row.append(InlineKeyboardButton(text=f"{template.emoji} ({count})", callback_data=template.eng_name))
#         in_row_count += 1
#         if in_row_count == 2:
#             keyboard.append(row)
#             in_row_count = 0
#             row = []
#     ex_count = await collectionQueries.get_user_exclusive_card_count(user_id)
#     row.append(InlineKeyboardButton(text=f"🌟 ({ex_count})", callback_data='exclusive'))
#     keyboard.append(row)
#     keyboard.append([InlineKeyboardButton(text=f"🎬 ({await collectionQueries.get_user_clips_count(user_id)})", callback_data='clip'), InlineKeyboardButton(text=f"🎞 ({await collectionQueries.get_user_exclips_count(user_id)})", callback_data='ex_clip')])
#     keyboard.insert(0, [InlineKeyboardButton(text=f"👥Все ({all})", callback_data='all')])
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def choose_category(bronze_count, silver_count, gold_count, legend_count, exclusive_count, clip_count, ex_clip_count):
#     all_count = bronze_count + silver_count + gold_count + legend_count
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text=f"👥Все ({all_count})", callback_data='all')],
#         [InlineKeyboardButton(text=f"🥉 ({bronze_count})", callback_data='bronze'),
#         InlineKeyboardButton(text=f"🥈 ({silver_count})", callback_data='silver'),
#         InlineKeyboardButton(text=f"🥇 ({gold_count})", callback_data='gold')],
#         [InlineKeyboardButton(text=f"🎖 ({legend_count})", callback_data='legend'),
#         InlineKeyboardButton(text=f"🌟 ({exclusive_count})", callback_data='exclusive')],
#         [InlineKeyboardButton(text=f"🎬 ({clip_count})", callback_data='clip'),
#          InlineKeyboardButton(text=f"🎞 ({ex_clip_count})", callback_data='ex_clip')]
#         [InlineKeyboardButton(text="↪Назад", callback_data='back')]
#     ])
#
# def craft_rule(index : int, size : int):
#     buttons = []
#     if index != 0:
#         buttons.append(InlineKeyboardButton(text=f"<", callback_data=f'rule_{index-1}'))
#     if index != size - 1:
#         buttons.append(InlineKeyboardButton(text=f">", callback_data=f'rule_{index+1}'))
#     return InlineKeyboardMarkup(inline_keyboard=[
#         buttons,
#         [InlineKeyboardButton(text="↪Назад", callback_data='back')]
#     ])
#
# album_keyboard = InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text=f"🥉Бронза", callback_data='bronze')],
#         [InlineKeyboardButton(text=f"🥈Серебро", callback_data='silver')],
#         [InlineKeyboardButton(text=f"🥇Золото", callback_data='gold')],
#         [InlineKeyboardButton(text=f"🎖Легенды", callback_data='legend')],
#         [InlineKeyboardButton(text=f"💎Алмаз", callback_data='diamond')],
#         [InlineKeyboardButton(text=f"🗄Архив", callback_data='archive')],
#         [InlineKeyboardButton(text="↪Назад", callback_data='back')]
#     ]
# )
#
# def watch_card_keyboard(bronze_count, silver_count, gold_count, legend_count, exclusive_count, clip_count, ex_clip_count):
#     all_count = bronze_count + silver_count + gold_count + legend_count
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text=f"👥Все ({all_count})", callback_data='all_cards')],
#         [InlineKeyboardButton(text=f"🥉Бронза ({bronze_count})", callback_data='bronze_cards')],
#         [InlineKeyboardButton(text=f"🥈Серебро ({silver_count})", callback_data='silver_cards')],
#         [InlineKeyboardButton(text=f"🥇Золото ({gold_count})", callback_data='gold_cards')],
#         [InlineKeyboardButton(text=f"🎖Легенды ({legend_count})", callback_data='legend_cards')],
#         [InlineKeyboardButton(text=f"🌟Эксклюзив ({exclusive_count})", callback_data='exclusive')],
#         [InlineKeyboardButton(text=f"🎬 ({clip_count})", callback_data='clip'),
#          InlineKeyboardButton(text=f"🎞 ({ex_clip_count})", callback_data='ex_clip')],
#         [InlineKeyboardButton(text="↪Назад", callback_data='back')]
#
#     ])
#
# def all_cards_keyboard(current : int, max : int):
#     keyboard = []
#     keyboard = add_choose_option(keyboard, current, max)
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def team_cards_keyboard(current : int, max : int):
#     keyboard = []
#     keyboard = add_choose_option_new(keyboard, current, max)
#     keyboard.append([InlineKeyboardButton(text="Выбрать", callback_data="choose")])
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def add_choose_option(keyboard, current: int, max: int) -> InlineKeyboardBuilder:
#     buttons = []
#     if current != 0:
#         buttons.append(InlineKeyboardButton(text='<', callback_data='prev'))
#     buttons.append(InlineKeyboardButton(text=f'{current + 1}/{max}', callback_data='NONE'))
#     if current != max - 1:
#         buttons.append(InlineKeyboardButton(text='>', callback_data='next'))
#     keyboard.append(buttons)
#     return keyboard
#
#
# def craft_album(current: int, active_buttons: list[int]) -> InlineKeyboardMarkup:
#     keyboard = []
#     buttons = []
#     buttons.append(InlineKeyboardButton(text=f'<', callback_data=f'prev_{current - 1}'))
#     buttons.append(InlineKeyboardButton(text=f'>', callback_data=f'prev_{current + 1}'))
#     first_row = []
#     second_row = []
#     for i, button in enumerate(active_buttons):
#         inline_button = InlineKeyboardButton(text=f' ' * (button == 0) + f'🔲' * (button == -1) + f'🔳' * (button == 1),
#                                             callback_data=f'add_' * (button == 1) + f'del_' * (button == -1) + f'{i}')
#         if i < 3:
#             first_row.append(inline_button)
#         else:
#             second_row.append(inline_button)
#
#     keyboard.append(first_row)
#     keyboard.append(second_row)
#     keyboard.append(buttons)
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def craft_choose(current: int, can_next: bool) -> InlineKeyboardMarkup:
#     keyboard = []
#     buttons = []
#     if current > 0:
#         buttons.append(InlineKeyboardButton(text=f'<', callback_data=f'prev_{current - 1}'))
#     if can_next:
#         buttons.append(InlineKeyboardButton(text=f'>', callback_data=f'prev_{current + 1}'))
#     keyboard.append(buttons)
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def add_choose_option_new(keyboard, current: int, max: int) -> InlineKeyboardBuilder:
#     buttons = []
#     if current != 0:
#         buttons.append(InlineKeyboardButton(text='<', callback_data=f'prev_{current - 1}'))
#     buttons.append(InlineKeyboardButton(text=f'{current + 1}/{max}', callback_data='NONE'))
#     if current != max - 1:
#         buttons.append(InlineKeyboardButton(text='>', callback_data=f'next_{current + 1}'))
#     keyboard.append(buttons)
#     return keyboard
#
# def add_back_button(keyboard) -> InlineKeyboardBuilder:
#     keyboard.append([InlineKeyboardButton(text="↪Назад", callback_data="back")])
#     return keyboard
#
# def add_pick_n_action(keyboard, current_index: int, show_chosen: bool, chosen: bool, action_name: str, action_callback: str, ready_for_action : bool) -> InlineKeyboardBuilder:
#     buttons = []
#     if show_chosen:
#         buttons.append(InlineKeyboardButton(text="❌Убрать" if chosen else "✅Выбрать",
#                                           callback_data=f'remove_{current_index}' if chosen else f'choose_{current_index}'))
#     if ready_for_action:
#         buttons.append(InlineKeyboardButton(text=action_name, callback_data=action_callback))
#     keyboard.append(buttons)
#     return keyboard
#
# def add_button(keyboard, text: str, callback: str):
#     keyboard.append([InlineKeyboardButton(text=text, callback_data=callback)])
#     return keyboard
#
# def craft_keyboard(keyboard):
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def craft_pick_n_action_keyboard(current: int, cards_count: int,
#                                   show_chosen: bool, chosen: bool, action_name: str,
#                                     callback: str, ready_for_action: bool) ->InlineKeyboardMarkup:
#     keyboard = []
#     keyboard = add_choose_option_new(keyboard, current, cards_count)
#     keyboard = add_pick_n_action(keyboard, current, show_chosen, chosen, action_name, callback, ready_for_action)
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# def craft_keyboard_for_craft(current: int, cards_count: int, dublicat_count : int,
#                              show_chosen: bool, chosen: bool, action_name: str,
#                                 callback: str, ready_for_action: bool) -> InlineKeyboardMarkup:
#
#     keyboard = []
#     keyboard = add_choose_option(keyboard, current, cards_count)
#     buttons = []
#     if show_chosen:
#         buttons.append(InlineKeyboardButton(text="❌Убрать" if chosen else "✅Выбрать",
#                                           callback_data='remove' if chosen else 'choose'))
#         if dublicat_count > 0:
#             buttons.append(InlineKeyboardButton(text=f"✅Дубликаты {dublicat_count}", callback_data='choose_dublicat'))
#     if ready_for_action:
#         buttons.append(InlineKeyboardButton(text=action_name, callback_data=callback))
#     keyboard.append(buttons)
#     keyboard = add_pick_n_action(keyboard, show_chosen, chosen, action_name, callback, ready_for_action)
#     keyboard = add_back_button(keyboard)
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# pick_craft_card_method = InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text="👤Самостоятельно", callback_data="pick_craft_card")],
#         [InlineKeyboardButton(text="👥Из дубликатов", callback_data="dublicat_craft_card")],
#         [InlineKeyboardButton(text="🔟Из первых 10-ти", callback_data="all_craft")],
#         [InlineKeyboardButton(text="↪Назад", callback_data="back")]
#     ]
# )
#
# async def choose_craft_rubbish(user_id, collectionQueries: CollectionQueries):
#     silver_count = await collectionQueries.get_cards_count_from_user(user_id, 'silver')
#     gold_count = await collectionQueries.get_cards_count_from_user(user_id, 'gold')
#     legend_count = await collectionQueries.get_cards_count_from_user(user_id, 'legend')
#     diamond_count = await collectionQueries.get_cards_count_from_user(user_id, 'diamond')
#     return InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text=f"🥈Серебро ({silver_count})", callback_data='silver')],
#         [InlineKeyboardButton(text=f"🥇Золото ({gold_count})", callback_data='gold')],
#         [InlineKeyboardButton(text=f"🎖Легенды ({legend_count})", callback_data='legend')],
#         [InlineKeyboardButton(text=f"💎Алмаз ({diamond_count})", callback_data='diamond')],
#         [InlineKeyboardButton(text="↪Назад", callback_data='back')],
#     ]
# )
#
#
# tree_txt = "-s-🌟--↩---🦠-s-s-🦠🔴🦠----🟡🦠🟠---🟣🦠🔵🦠🟢s-🦠🔴🦠🟣🦠-🦠🟢🦠🟠🦠🟡🦠---🪵----c-🪵-d-"
# width = 7
# height = 9
#
# def transform_tree(txt, unlocked):
#     allowed = {'🦠', '🪵', '-', 's', '↩'}
#     chars = list(txt)
#     unlock_pos = -1
#
#     # Идём с конца, ищем первый не открытый
#     for i in range(len(txt)-1, -1, -1):
#         if txt[i] not in allowed and i not in unlocked:
#             unlock_pos = i
#             break
#
#     # Заменяем все не открытые
#     for i, ch in enumerate(chars):
#         if ch not in allowed and i not in unlocked:
#             if i == unlock_pos:
#                 chars[i] = '🔓'
#             else:
#                 chars[i] = '🔒'
#
#     return ''.join(chars)
#
# def prize(prize):
#     if(prize > 0):
#         keyboard = [[InlineKeyboardButton(
#                     text=f"{prize}❄️",
#                     callback_data="get_prize"
#                 )]]
#     else:
#         keyboard = [[InlineKeyboardButton(
#                     text=f"Жди следующего снегопада",
#                     callback_data="NONE"
#                 )]]
#     add_back_button(keyboard)
#
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
#
# def tree(unlocked):
#     new_tree_txt = transform_tree(tree_txt, unlocked)
#     keyboard = []
#     for i in range(height):
#         em_list = []
#         for j in range(width):
#             # Используем новую строку
#             text = new_tree_txt[i * width + j]
#
#             # Дополнительная обработка специальных символов (если нужно)
#             if text == '-':
#                 text = ' '
#             elif text == 's':
#                 text = '❄️'
#             elif text == 'c':
#                 text = '⛄️'
#             elif text == 'd':
#                 text = '🎅🏿'
#
#             callback = f"tree_{i}_{j}"
#
#             if text == '🔓':
#                 callback = f"unlock_{i * width + j}"
#             if text == '↩':
#                 callback = 'back'
#
#             em_list.append(
#                 InlineKeyboardButton(
#                     text=text,
#                     callback_data=callback
#                 )
#             )
#         keyboard.append(em_list)
#
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
# ny_key = InlineKeyboardMarkup(
#     inline_keyboard=[
#         [InlineKeyboardButton(text="🎄Ёлка", callback_data="ny_tree")],
#         [InlineKeyboardButton(text="🍀Лото", callback_data="loto"), InlineKeyboardButton(text="🌨Снегопад", callback_data="free_prize")],
#         [InlineKeyboardButton(text="😈Гринч", callback_data="kotel")],
#         [InlineKeyboardButton(text="↪Назад", callback_data="back")]
#     ]
# )
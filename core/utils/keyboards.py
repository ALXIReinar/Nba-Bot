from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

back = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪Назад", callback_data="back")]
    ]
)

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
        [InlineKeyboardButton(text="🆚Играть с другом", callback_data="pvp_menu")],
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

def add_back_button(keyboard) -> InlineKeyboardBuilder:
    keyboard.append([InlineKeyboardButton(text="↪Назад", callback_data="back")])
    return keyboard

only_choose_attack = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="[ ⛹️‍♂️ ]", callback_data="NONE"), InlineKeyboardButton(text="❌", callback_data="NONE"), InlineKeyboardButton(text="❌", callback_data="NONE")],
        [InlineKeyboardButton(text="Выбрать", callback_data="run")]
    ]
)

def team_cards_keyboard(current : int, max : int):
    keyboard = []
    keyboard = add_choose_option_new(keyboard, current, max)
    keyboard.append([InlineKeyboardButton(text="Выбрать", callback_data="choose")])
    keyboard = add_back_button(keyboard)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def add_choose_option_new(keyboard, current: int, max: int) -> InlineKeyboardBuilder:
    buttons = []
    if current != 0:
        buttons.append(InlineKeyboardButton(text='<', callback_data=f'prev_{current - 1}'))
    buttons.append(InlineKeyboardButton(text=f'{current + 1}/{max}', callback_data='NONE'))
    if current != max - 1:
        buttons.append(InlineKeyboardButton(text='>', callback_data=f'next_{current + 1}'))
    keyboard.append(buttons)
    return keyboard
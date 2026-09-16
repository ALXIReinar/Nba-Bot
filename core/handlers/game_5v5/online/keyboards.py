"""
Клавиатуры для онлайн-режима 5 на 5.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def pvp_invite_keyboard(from_user_id: int) -> InlineKeyboardMarkup:
    """
    Кнопки принятия/отклонения приглашения в PvP матч.
    
    Args:
        from_user_id: ID пользователя, который отправил приглашение
    
    Returns:
        InlineKeyboardMarkup с кнопками [Принять | Отклонить]
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"pvp_accept_{from_user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"pvp_decline_{from_user_id}"
                )
            ]
        ]
    )


def pvp_choose_tactic_keyboard(current_tactic: str | None = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора тактики для онлайн-игры.
    
    Args:
        current_tactic: Текущая выбранная тактика ("defense" | "attack" | "balance" | None)
    
    Returns:
        InlineKeyboardMarkup с кнопками тактик
    """
    tactics = [
        ("⚔️", "pvp_tactic_attack", "attack"),
        ("🛡", "pvp_tactic_defense", "defense"),
        ("⚖️", "pvp_tactic_balance", "balance")
    ]
    
    buttons = []
    for emoji, callback, tactic_name in tactics:
        text = f"[ {emoji} ]" if current_tactic == tactic_name else emoji
        buttons.append(
            InlineKeyboardButton(text=text, callback_data=callback)
        )
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def pvp_game_keyboard(action: int) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора действия в игре.
    
    Args:
        action: Текущее выбранное действие (1 = атака, 2 = пас первому, 3 = пас второму)
    
    Returns:
        InlineKeyboardMarkup с кнопками [1|2|3] и кнопкой "Выбрать"
    """
    # Кнопки выбора действия
    action_buttons = []
    for i in range(1, 4):
        text = f"[ ⛹️‍♂️ ]" if action == i else str(i)
        if i == 1:
            # Атака
            callback = "pvp_1"
        else:
            # Пас
            callback = f"pvp_{i}"
        
        action_buttons.append(
            InlineKeyboardButton(text=text, callback_data=callback)
        )
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            action_buttons,
            [InlineKeyboardButton(text="Выбрать", callback_data="pvp_run")]
        ]
    )


def pvp_only_attack_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура только с кнопкой атаки (когда пасов больше нет).
    
    Returns:
        InlineKeyboardMarkup с одной кнопкой атаки
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="[ ⛹️‍♂️ ]", callback_data="NONE"),
                InlineKeyboardButton(text="❌", callback_data="NONE"),
                InlineKeyboardButton(text="❌", callback_data="NONE")
            ],
            [InlineKeyboardButton(text="Выбрать", callback_data="pvp_run")]
        ]
    )


def pvp_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Меню онлайн-режима.
    
    Returns:
        InlineKeyboardMarkup с инструкциями и кнопкой назад
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↪Назад", callback_data="back")]
        ]
    )

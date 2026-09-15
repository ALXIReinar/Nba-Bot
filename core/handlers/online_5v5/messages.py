"""
Шаблоны сообщений для онлайн-режима 5 на 5.
"""


def get_pvp_menu_message() -> str:
    """
    Сообщение меню онлайн-режима с инструкциями.
    
    Returns:
        str: Текст сообщения
    """
    return (
        "🆚 <b>Играть с другом</b>\n\n"
        "Чтобы пригласить игрока в матч, используй команду:\n"
        "<code>/invite username</code>\n\n"
        "Пример: <code>/invite john_doe</code>\n\n"
        "<b>Правила:</b>\n"
        "• Матч 5 на 5 между двумя игроками\n"
        "• Каждому игроку даётся 2 минуты на действие\n"
        "• Билеты на игру НЕ тратятся\n"
        "• Рейтинг НЕ изменяется\n"
        "• Просто игра ради удовольствия! 🏀"
    )


def get_invite_sent_message(target_username: str) -> str:
    """
    Сообщение об отправке приглашения.
    
    Args:
        target_username: Username пользователя, которому отправлено приглашение
    
    Returns:
        str: Текст сообщения
    """
    return (
        f"✅ Приглашение отправлено игроку @{target_username}\n\n"
        f"⏳ Ожидай ответа (действительно 5 минут)"
    )


def get_invite_received_message(from_username: str) -> str:
    """
    Сообщение о получении приглашения.
    
    Args:
        from_username: Username пользователя, который отправил приглашение
    
    Returns:
        str: Текст сообщения
    """
    return (
        f"🆚 <b>Приглашение в матч!</b>\n\n"
        f"Игрок @{from_username} приглашает тебя сыграть 5 на 5\n\n"
        f"⏱ Приглашение действительно 5 минут"
    )


def get_invite_declined_message(target_username: str) -> str:
    """
    Сообщение об отклонении приглашения (для отправителя).
    
    Args:
        target_username: Username пользователя, который отклонил
    
    Returns:
        str: Текст сообщения
    """
    return (
        f"❌ Игрок @{target_username} отклонил приглашение"
    )


def get_invite_accepted_message() -> str:
    """
    Сообщение о принятии приглашения.
    
    Returns:
        str: Текст сообщения
    """
    return (
        "✅ Приглашение принято!\n\n"
        "🎮 Матч начинается...\n"
        "Выбери тактику для игры:"
    )


def get_choose_tactic_message() -> str:
    """
    Сообщение выбора тактики.
    
    Returns:
        str: Текст сообщения
    """
    return (
        "⛹️ <b>Выбери тактику</b>\n\n"
        "⚔️ <b>Атакующая</b> — улучшение дриблинга на 12%\n"
        "🛡 <b>Защитная</b> — улучшение защиты на 12%\n"
        "⚖️ <b>Сбалансированная</b> — улучшение дриблинга и защиты на 6%\n\n"
        "⏱ У тебя есть 2 минуты на выбор"
    )


def get_waiting_opponent_tactic_message() -> str:
    """
    Сообщение ожидания выбора тактики соперником.
    
    Returns:
        str: Текст сообщения
    """
    return "⏳ Ожидаем выбора тактики соперника..."


def get_coin_toss_start_message() -> str:
    """
    Сообщение о начале "монетки".
    
    Returns:
        str: Текст сообщения
    """
    return "🎲 Определяем, кто начинает первым...\n\n🏀 Бросаем мяч!"


def get_coin_toss_result_message(your_score: int, opponent_score: int) -> str:
    """
    Сообщение с результатом "монетки".
    
    Args:
        your_score: Счёт пользователя (0-3)
        opponent_score: Счёт соперника (0-3)
    
    Returns:
        str: Текст сообщения
    """
    return f"Твой счёт: {your_score}/3\nСчёт соперника: {opponent_score}/3"


def get_you_attack_first_message(cycle: int, your_score: int, opponent_score: int) -> str:
    """
    Сообщение о том, что ты атакуешь первым.
    
    Args:
        cycle: Номер атаки (1-5)
        your_score: Твой счёт
        opponent_score: Счёт соперника
    
    Returns:
        str: Текст сообщения
    """
    return (
        f"⚔️ <b>Ты атакуешь!</b> Атака {cycle}/5\n\n"
        f"<b>Счёт:</b> {your_score} - {opponent_score}"
    )


def get_opponent_attacks_message(cycle: int, your_score: int, opponent_score: int) -> str:
    """
    Сообщение о том, что соперник атакует.
    
    Args:
        cycle: Номер атаки (1-5)
        your_score: Твой счёт
        opponent_score: Счёт соперника
    
    Returns:
        str: Текст сообщения
    """
    return (
        f"🛡 <b>Соперник атакует!</b> Атака {cycle}/5\n\n"
        f"<b>Счёт:</b> {your_score} - {opponent_score}"
    )


def get_waiting_opponent_move_message() -> str:
    """
    Сообщение ожидания хода соперника.
    
    Returns:
        str: Текст сообщения
    """
    return "⏳ Ожидаем хода соперника..."

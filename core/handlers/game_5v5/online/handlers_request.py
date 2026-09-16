from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, CallbackQuery
from redis.asyncio import Redis

from core.config_dir.config import bot, dp
from core.data.online_matches_manager import OnlineMatchesManager
from core.data.postgres import PgSql
from core.handlers.game_5v5.core.rating_header import Team
from core.handlers.game_5v5.online import messages as pvp_messages
from core.handlers.game_5v5.online.keyboards import (
    pvp_invite_keyboard,
    pvp_choose_tactic_keyboard
)
from core.handlers.game_5v5.online.states import OnlineMatch

from core.handlers.game_5v5.online.serializers import serialize_team
from core.utils.anything import InvitePvpCalls
from core.utils.logger_config import log_event
from core.utils.online_timeouts import schedule_turn_timeout

router = Router(name="online_5v5_requests")


@router.message(Command("invite"))
async def invite_user_handler(
    message: Message,
    state: FSMContext,
    redis: Redis,
    db: PgSql
):
    """
    Обработчик команды /invite [username].
    Создаёт запрос на игру и отправляет уведомление цели.
    """
    # 1. Парсим команду
    from_user_id = message.from_user.id
    from_username = message.from_user.username or "Аноним"

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        log_event(f'Приглашение не удалось отправить. Валидация не прошла | tg_id: \033[36m{from_user_id}\033[0m; inp_text: \033[36m{message.text}\033[0m', level='WARNING')
        await message.answer("❌ Укажи username игрока\n\nПример: <code>/invite username</code>")
        return

    target_username = parts[1].strip().lstrip('@')

    # 2. Проверяем, что отправитель не в игре
    matches_manager = OnlineMatchesManager(redis)
    sender_match_id = await matches_manager.get_user_match_id(from_user_id)

    if sender_match_id:
        log_event(f'Приглашение из состояния "в матче" | tg_id: \033[33m{from_user_id}\033[0m; cur_match_id: \033[35m{sender_match_id}\033[0m', level='WARNING')
        await message.answer("❌ Ты уже в игре!")
        return

    # 3. Ищем пользователя в БД
    target_user = await db.users.find_by_username(target_username)
    if not target_user:
        log_event(f"Не удалось пригласить пользователя. Его не существует | tg_id: \033[33m{from_user_id}\033[0m; invite_username: \033[35m{target_username}\033[0m", level='WARNING')
        return

    target_user_id = target_user['user_id']

    # 4. Проверяем, что не приглашаешь сам себя
    if target_user_id == from_user_id:
        log_event(f'Пользователь пригласил сам себя | tg_id: \033[33m{from_user_id}\033[0m; invite_username: \033[35m{target_username}\033[0m')
        await message.answer("❌ Нельзя пригласить самого себя!")
        return

    # 5. Проверяем, что цель не в игре
    target_match_id = await matches_manager.get_user_match_id(target_user_id)

    if target_match_id:
        log_event(f'Приглашаемый пользователь сейчас в матче. Не инвайтим | tg_id: \033[33m{from_user_id}\033[0m; target_tg_id: \033[35m{target_user_id}\033[0m')
        await message.answer(f"❌ Игрок @{target_username} уже в игре")
        return

    # 6. Проверяем, что запрос не дублируется
    existing_request = await matches_manager.get_match_request(
        from_user_id, target_user_id
    )

    if existing_request:
        log_event(f'Дубликат приглашения. Скип | tg_id: \033[33m{from_user_id}\033[0m; target_tg_id: \033[35m{target_user_id}\033[0m')
        await message.answer("⏳ Приглашение уже отправлено, ожидай ответа")
        return

    # 7. Создаём запрос в Redis (TTL = 5 минут)
    created = await matches_manager.create_match_request(
        from_user_id=from_user_id,
        from_username=from_username,
        to_user_id=target_user_id,
        to_username=target_username
    )

    if not created:
        log_event(f'Не удалось создать приглашение! | tg_id: \033[33m{from_user_id}\033[0m; target_tg_id: \033[35m{target_user_id}\033[0m', level='ERROR')
        await message.answer("❌ Не удалось отправить приглашение. Попробуй позже.")
        return

    log_event(f'Приглашение отправлено! | tg_id: \033[33m{from_user_id}\033[0m; target_tg_id: \033[35m{target_user_id}\033[0m',)

    # 8. Отправляем уведомление цели
    try:
        await bot.send_message(
            target_user_id,
            pvp_messages.get_invite_received_message(from_username),
            reply_markup=pvp_invite_keyboard(from_user_id)
        )
    except Exception as e:
        log_event(f'Не удалось отправить сообщение с приглашением 2ому юзеру! | tg_id: \033[33m{from_user_id}\033[0m; target_tg_id: \033[35m{target_user_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')
        await message.answer("❌ Не удалось отправить приглашение игроку")
        await matches_manager.delete_match_request(from_user_id, target_user_id)
        return

    # 9. Подтверждаем отправителю
    await message.answer(pvp_messages.get_invite_sent_message(target_username))

    # 10. Устанавливаем состояние ожидания ответа
    await state.set_state(OnlineMatch.WaitingInviteResponse)



@router.callback_query(F.data.startswith(InvitePvpCalls.pvp_accept_))
async def accept_invite_handler(callback: CallbackQuery, state: FSMContext, redis: Redis, db: PgSql):
    """
    Обработчик принятия приглашения.
    Создаёт матч и переводит обоих игроков в режим выбора тактики.
    """
    # Парсим from_user_id из callback_data
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.from_user.id

    matches_manager = OnlineMatchesManager(redis)

    # 1. Проверяем, что запрос ещё существует
    request = await matches_manager.get_match_request(from_user_id, to_user_id)

    if not request:
        log_event(f'Матч не создан. Приглашение истекло | from_tg_id: \033[33m{from_user_id}\033[0m; to_tg_id: \033[32m{to_user_id}\033[0m', level='WARNING')
        await callback.answer("❌ Приглашение истекло", show_alert=True)
        await callback.message.edit_text("⏱ Приглашение истекло")
        return

    # 2. Проверяем, что оба игрока не в других матчах
    sender_match = await matches_manager.get_user_match_id(from_user_id)
    receiver_match = await matches_manager.get_user_match_id(to_user_id)

    if sender_match:
        log_event(f'Не удалось принять приглашение. Отправитель  сейчас занят | from_tg_id: \033[33m{from_user_id}\033[0m; to_tg_id: \033[32m{to_user_id}\033[0m')
        await callback.answer("❌ Отправитель уже в другой игре", show_alert=True)
        await matches_manager.delete_match_request(from_user_id, to_user_id)
        await callback.message.edit_text("❌ Отправитель уже в другой игре")
        return

    if receiver_match:
        log_event(f'Не удалось принять приглашение. Получатель уже занят | from_tg_id: \033[33m{from_user_id}\033[0m; to_tg_id: \033[32m{to_user_id}\033[0m')
        await callback.answer("❌ Ты уже в игре", show_alert=True)
        return

    # 3. Получаем команды обоих игроков
    player1_team_obj = await Team.get_team_from_user_id(from_user_id, db)
    player2_team_obj = await Team.get_team_from_user_id(to_user_id, db)

    # Проверяем, что команды полные
    if None in player1_team_obj.players:
        log_event(f'Отмена матча команды игроков не укомплектованы! | p1_tg_id: \033[36m{from_user_id}\033[0m; p1_team: {repr(player1_team_obj.players)}; p2_tg_id: \033[36m{to_user_id}\033[0m; p2_team: {repr(player2_team_obj.players)}')
        await callback.answer("❌ У отправителя не собрана команда", show_alert=True)
        await matches_manager.delete_match_request(from_user_id, to_user_id)
        await callback.message.edit_text("❌ У отправителя не собрана команда")
        return

    if None in player2_team_obj.players:
        log_event(f'Отмена матча команды игроков не укомплектованы! | p1_tg_id: \033[36m{from_user_id}\033[0m; p1_team: {repr(player1_team_obj.players)}; p2_tg_id: \033[36m{to_user_id}\033[0m; p2_team: {repr(player2_team_obj.players)}')
        await callback.answer("❌ Сначала собери команду!", show_alert=True)
        return

    player1_team = serialize_team(player1_team_obj)
    player2_team = serialize_team(player2_team_obj)

    # 5. Создаём матч в Redis
    match_id = await matches_manager.create_match(
        player1_id=from_user_id,
        player2_id=to_user_id,
        player1_username=request["from_username"],
        player2_username=request["to_username"],
        player1_team=dict(player1_team),
        player2_team=dict(player2_team)
    )

    # 6. Удаляем запрос
    await matches_manager.delete_match_request(from_user_id, to_user_id)
    log_event(f'Пользователь принял инвайт. Начало матча! | match_id:\033[35m{match_id}\033[0m; from_tg_id: \033[34m{from_user_id}\033[0m; to_tg_id: \033[33m{to_user_id}\033[0m')

    # 7. Отправляем сообщения обоим игрокам о выборе тактики
    await callback.message.edit_text(
        pvp_messages.get_invite_accepted_message()
    )

    await bot.send_message(
        to_user_id,
        pvp_messages.get_choose_tactic_message(),
        reply_markup=pvp_choose_tactic_keyboard()
    )

    try:
        await bot.send_message(
            from_user_id,
            pvp_messages.get_choose_tactic_message(),
            reply_markup=pvp_choose_tactic_keyboard()
        )
    except Exception as e:
        log_event(f'Не удалось отправить сообщения с выбором тактик матча! | tg_id: \033[33m{from_user_id}\033[0m; to_user_id: \033[35m{to_user_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')

    # 8. Переводим обоих в состояние выбора тактики
    # Для приглашённого (текущий пользователь)
    await state.set_state(OnlineMatch.ChoosingTactic)

    # Для приглашающего нужно установить state отдельно через StorageKey!
    storage = dp.storage
    # Используем player_id для обоих параметров (работает и для test_pvp, и без него)
    key_inviter = StorageKey(bot_id=bot.id, chat_id=from_user_id, user_id=from_user_id)
    await storage.set_state(key=key_inviter, state=OnlineMatch.ChoosingTactic)

    # 9. Запускаем первый таймаут (2 минуты на выбор тактики)
    schedule_turn_timeout(match_id, 0, redis)


@router.callback_query(F.data.startswith(InvitePvpCalls.pvp_decline_))
async def decline_invite_handler(callback: CallbackQuery, state: FSMContext, redis: Redis):
    """
    Обработчик отклонения приглашения.
    """
    # Парсим from_user_id из callback_data
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.from_user.id
    
    matches_manager = OnlineMatchesManager(redis)
    
    # 1. Получаем запрос для получения username отправителя
    request = await matches_manager.get_match_request(from_user_id, to_user_id)
    
    if not request:
        log_event(f'Матч не создан. Приглашение истекло удалось выбрать тактики для бафов перед матчем | from_tg_id: \033[33m{from_user_id}\033[0m; to_tg_id: \033[32m{to_user_id}\033[0m', level='WARNING')
        await callback.answer("❌ Приглашение истекло", show_alert=True)
        await callback.message.edit_text("⏱ Приглашение истекло")
        return
    
    # 2. Удаляем запрос
    await matches_manager.delete_match_request(from_user_id, to_user_id)
    log_event(f'Пользователь отклонил инвайт | from_tg_id: \033[34m{from_user_id}\033[0m; to_tg_id: \033[33m{to_user_id}\033[0m')

    # 3. Уведомляем отправителя
    target_username = request["to_username"]
    
    try:
        await bot.send_message(
            from_user_id,
            pvp_messages.get_invite_declined_message(target_username)
        )
    except Exception as e:
        log_event(f'Не удалось отправить сообщение с отказом от приглашения отправителю! | tg_id: \033[33m{from_user_id}\033[0m; to_user_id: \033[35m{to_user_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')


    # 4. Обновляем сообщение для получателя
    await callback.message.edit_text("❌ Ты отклонил приглашение")
    await callback.answer("Приглашение отклонено")

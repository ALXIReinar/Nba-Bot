import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from redis.asyncio import Redis

from core.config_dir.config import bot, env
from core.data.online_matches_manager import OnlineMatchesManager
from core.data.postgres import PgSql
from core.handlers.online_5v5 import messages as pvp_messages
from core.handlers.online_5v5.keyboards import (
    pvp_invite_keyboard,
    pvp_choose_tactic_keyboard
)
from core.handlers.online_5v5.states import OnlineMatch
from core.handlers.rating_header import Team

from core.utils.online_timeouts import schedule_turn_timeout


logger = logging.getLogger(__name__)
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
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Укажи username игрока\n\n"
            "Пример: <code>/invite username</code>"
        )
        return
    
    target_username = parts[1].strip().lstrip('@')

    "chat id спасает при тестах пвп с одного аккаунта (игрок в лс - игрок из группы)"
    from_user_id = message.chat.id if env.test_pvp else message.from_user.id

    from_username = message.from_user.username or "Аноним"
    
    # 2. Проверяем, что отправитель не в игре
    matches_manager = OnlineMatchesManager(redis)
    sender_match_id = await matches_manager.get_user_match_id(from_user_id)
    
    if sender_match_id:
        logger.warning(
            f"User {from_user_id} tried to invite while in match {sender_match_id}"
        )
        await message.answer("❌ Ты уже в игре!")
        return
    
    # 3. Ищем пользователя в БД
    target_user = await db.users.find_by_username(target_username)
    
    if not target_user:
        logger.warning(
            f"User {from_user_id} tried to invite non-existent user '{target_username}'"
        )
        await message.answer(
            f"❌ Пользователь @{target_username} не зарегистрирован в боте"
        )
        return
    
    target_user_id = target_user['user_id']
    
    # 4. Проверяем, что не приглашаешь сам себя
    if target_user_id == from_user_id:
        await message.answer("❌ Нельзя пригласить самого себя!")
        return
    
    # 5. Проверяем, что цель не в игре
    target_match_id = await matches_manager.get_user_match_id(target_user_id)
    
    if target_match_id:
        logger.warning(
            f"User {from_user_id} tried to invite {target_user_id} "
            f"who is already in match {target_match_id}"
        )
        await message.answer(
            f"❌ Игрок @{target_username} уже в игре"
        )
        return
    
    # 6. Проверяем, что запрос не дублируется
    existing_request = await matches_manager.get_match_request(
        from_user_id, target_user_id
    )
    
    if existing_request:
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
        await message.answer("❌ Не удалось отправить приглашение. Попробуй позже.")
        return
    
    logger.info(
        f"✅ User {from_user_id} (@{from_username}) invited "
        f"{target_user_id} (@{target_username}) to PvP match"
    )
    
    # 8. Отправляем уведомление цели
    try:
        await bot.send_message(
            target_user_id,
            pvp_messages.get_invite_received_message(from_username),
            reply_markup=pvp_invite_keyboard(from_user_id)
        )
    except Exception as e:
        logger.error(f"Failed to send invite to {target_user_id}: {e}")
        await message.answer("❌ Не удалось отправить приглашение игроку")
        await matches_manager.delete_match_request(from_user_id, target_user_id)
        return
    
    # 9. Подтверждаем отправителю
    await message.answer(pvp_messages.get_invite_sent_message(target_username))
    
    # 10. Устанавливаем состояние ожидания ответа
    await state.set_state(OnlineMatch.WaitingInviteResponse)




@router.callback_query(F.data.startswith("pvp_accept_"))
async def accept_invite_handler(
    callback: CallbackQuery,
    state: FSMContext,
    redis: Redis,
    db: PgSql
):
    """
    Обработчик принятия приглашения.
    Создаёт матч и переводит обоих игроков в режим выбора тактики.
    """
    # Парсим from_user_id из callback_data
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id
    
    # Сохраняем реальные user_id для FSM (нужны для StorageKey)
    # В test_pvp оба игрока - это один и тот же реальный пользователь
    from_real_user_id = callback.from_user.id  # Реальный user_id (одинаковый для обоих в test_pvp)
    to_real_user_id = callback.from_user.id    # Реальный user_id получателя
    
    matches_manager = OnlineMatchesManager(redis)
    
    # 1. Проверяем, что запрос ещё существует
    request = await matches_manager.get_match_request(from_user_id, to_user_id)
    
    if not request:
        await callback.answer("❌ Приглашение истекло", show_alert=True)
        await callback.message.edit_text("⏱ Приглашение истекло")
        return
    
    # 2. Проверяем, что оба игрока не в других матчах
    sender_match = await matches_manager.get_user_match_id(from_user_id)
    receiver_match = await matches_manager.get_user_match_id(to_user_id)
    
    if sender_match:
        await callback.answer(
            "❌ Отправитель уже в другой игре",
            show_alert=True
        )
        await matches_manager.delete_match_request(from_user_id, to_user_id)
        await callback.message.edit_text("❌ Отправитель уже в другой игре")
        return
    
    if receiver_match:
        await callback.answer("❌ Ты уже в игре", show_alert=True)
        return
    
    # 3. Получаем команды обоих игроков
    player1_team_obj = await Team.get_team_from_user_id(from_user_id, db)
    player2_team_obj = await Team.get_team_from_user_id(to_user_id, db)

    # Проверяем, что команды полные
    if None in player1_team_obj.players:
        await callback.answer(
            "❌ У отправителя не собрана команда",
            show_alert=True
        )
        await matches_manager.delete_match_request(from_user_id, to_user_id)
        await callback.message.edit_text("❌ У отправителя не собрана команда")
        return
    
    if None in player2_team_obj.players:
        await callback.answer("❌ Сначала собери команду!", show_alert=True)
        return
    
    # 4. Сериализуем команды для Redis
    def serialize_team(team: Team) -> dict:
        """Сериализация команды в dict для хранения в Redis"""
        return {
            "players": [
                {
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
                    }
                }
                for p in team.players if p is not None
            ]
        }
    
    player1_team = serialize_team(player1_team_obj)
    player2_team = serialize_team(player2_team_obj)
    
    # 5. Создаём матч в Redis
    match_id = await matches_manager.create_match(
        player1_id=from_user_id,
        player2_id=to_user_id,
        player1_username=request["from_username"],
        player2_username=request["to_username"],
        player1_team=dict(player1_team),
        player2_team=dict(player2_team),
        player1_real_user_id=from_real_user_id,  # Реальный user_id для FSM
        player2_real_user_id=to_real_user_id     # Реальный user_id для FSM
    )
    
    # 6. Удаляем запрос
    await matches_manager.delete_match_request(from_user_id, to_user_id)
    
    logger.info(
        f"✅ Match {match_id} created: {from_user_id} vs {to_user_id}"
    )
    
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
        logger.error(f"Failed to send tactic message to {from_user_id}: {e}")
    
    # 8. Переводим обоих в состояние выбора тактики
    # Для приглашённого (текущий пользователь)
    await state.set_state(OnlineMatch.ChoosingTactic)
    
    # Для приглашающего нужно установить state отдельно через StorageKey!
    from aiogram.fsm.storage.base import StorageKey
    from core.config_dir.config import dp
    
    storage = dp.storage
    # Используем реальный user_id для FSM
    key_inviter = StorageKey(bot_id=bot.id, chat_id=from_user_id, user_id=from_real_user_id)
    await storage.set_state(key=key_inviter, state=OnlineMatch.ChoosingTactic)
    
    # 9. Запускаем первый таймаут (2 минуты на выбор тактики)
    schedule_turn_timeout(match_id, 0, redis)


@router.callback_query(F.data.startswith("pvp_decline_"))
async def decline_invite_handler(
    callback: CallbackQuery,
    state: FSMContext,
    redis: Redis
):
    """
    Обработчик отклонения приглашения.
    """
    # Парсим from_user_id из callback_data
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.message.chat.id if env.test_pvp else callback.from_user.id
    
    matches_manager = OnlineMatchesManager(redis)
    
    # 1. Получаем запрос для получения username отправителя
    request = await matches_manager.get_match_request(from_user_id, to_user_id)
    
    if not request:
        await callback.answer("❌ Приглашение истекло", show_alert=True)
        await callback.message.edit_text("⏱ Приглашение истекло")
        return
    
    # 2. Удаляем запрос
    await matches_manager.delete_match_request(from_user_id, to_user_id)
    
    logger.info(
        f"User {to_user_id} declined invite from {from_user_id}"
    )
    
    # 3. Уведомляем отправителя
    target_username = request["to_username"]
    
    try:
        await bot.send_message(
            from_user_id,
            pvp_messages.get_invite_declined_message(target_username)
        )
    except Exception as e:
        logger.error(f"Failed to send decline notification to {from_user_id}: {e}")
    
    # 4. Обновляем сообщение для получателя
    await callback.message.edit_text("❌ Ты отклонил приглашение")
    await callback.answer("Приглашение отклонено")

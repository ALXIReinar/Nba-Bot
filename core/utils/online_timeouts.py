"""
APScheduler для управления таймаутами PvP матчей.
Проверяет, не истёк ли таймаут хода (2 минуты).
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from core.config_dir.config import bot
from core.data.online_matches_manager import OnlineMatchesManager


logger = logging.getLogger(__name__)

# Singleton scheduler
scheduler = AsyncIOScheduler()


def determine_winner_on_tactic_timeout(match_data: dict) -> tuple[int, int]:
    """
    Определяет победителя и проигравшего при таймауте выбора тактики.
    
    Логика:
    - Если оба не выбрали тактику → проигрывает приглашённый (player2)
    - Если только player1 не выбрал → проигрывает player1
    - Если только player2 не выбрал → проигрывает player2
    - Если оба выбрали (не должно случиться) → проигрывает player2
    
    Args:
        match_data: Данные матча
        
    Returns:
        tuple[winner_id, loser_id]
    """
    player1_id = match_data["player1_id"]
    player2_id = match_data["player2_id"]
    
    player1_tactic = match_data.get("player1_tactic")
    player2_tactic = match_data.get("player2_tactic")
    
    # Если player1 выбрал, а player2 нет
    if player1_tactic and not player2_tactic:
        return player1_id, player2_id
    
    # Если player2 выбрал, а player1 нет
    if player2_tactic and not player1_tactic:
        return player2_id, player1_id
    
    # Если оба не выбрали (или оба выбрали - не должно случиться)
    # Проигрывает приглашённый (player2)
    return player1_id, player2_id


async def check_turn_timeout(match_id: str, turn_number: int, redis: Redis):
    """
    Проверяет, не истёк ли таймаут хода.
    Вызывается через 2 минуты после начала хода.
    
    Args:
        match_id: ID матча
        turn_number: Номер хода, который должен был быть сделан
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        logger.info(f"Match {match_id} not found (probably already finished)")
        return
    
    # Проверяем, совпадает ли turn_number
    if match_data["turn_number"] == turn_number:
        # Ход не был сделан за 2 минуты — засчитываем поражение
        
        # Специальная логика для turn_number = 0 (выбор тактики)
        if turn_number == 0:
            winner_id, loser_id = determine_winner_on_tactic_timeout(match_data)
            logger.warning(
                f"Match {match_id}: tactic selection timeout. "
                f"Winner: {winner_id}, Loser: {loser_id}"
            )
        else:
            # Обычная логика для игрового хода
            loser_id = match_data["current_attacker_id"]
            winner_id = (
                match_data["player2_id"] 
                if loser_id == match_data["player1_id"] 
                else match_data["player1_id"]
            )
            logger.warning(
                f"Match {match_id}: timeout for turn {turn_number}. "
                f"Winner: {winner_id}, Loser: {loser_id}"
            )
        
        await finish_match_by_timeout(match_id, winner_id, loser_id, redis)
    else:
        logger.info(
            f"Match {match_id}: turn {turn_number} already completed "
            f"(current: {match_data['turn_number']})"
        )


def schedule_turn_timeout(match_id: str, turn_number: int, redis: Redis):
    """
    Запланировать проверку таймаута через 2 минуты.
    
    Args:
        match_id: ID матча
        turn_number: Номер хода для проверки
        redis: Redis connection
    """
    job_id = f"pvp_timeout_{match_id}_{turn_number}"
    
    # Удаляем предыдущую задачу, если есть
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    
    # Планируем новую задачу
    scheduler.add_job(
        check_turn_timeout,
        'date',
        run_date=datetime.now() + timedelta(minutes=2),
        args=[match_id, turn_number, redis],
        id=job_id,
        replace_existing=True
    )
    
    logger.info(f"Scheduled timeout check for match {match_id}, turn {turn_number}")


async def finish_match_by_timeout(
    match_id: str,
    winner_id: int,
    loser_id: int,
    redis: Redis
):
    """
    Завершает матч по таймауту.
    
    Args:
        match_id: ID матча
        winner_id: ID победителя
        loser_id: ID проигравшего
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    # Обновляем данные матча
    await matches_manager.update_match(match_id, {
        "state": "finished",
        "winner_id": winner_id,
        "finish_reason": "timeout"
    })
    
    # Отправляем уведомления обоим игрокам
    winner_username = (
        match_data["player1_username"] 
        if winner_id == match_data["player1_id"] 
        else match_data["player2_username"]
    )
    loser_username = (
        match_data["player1_username"] 
        if loser_id == match_data["player1_id"] 
        else match_data["player2_username"]
    )
    
    final_score = match_data["score"]
    winner_score = (
        final_score["player1"] 
        if winner_id == match_data["player1_id"] 
        else final_score["player2"]
    )
    loser_score = (
        final_score["player1"] 
        if loser_id == match_data["player1_id"] 
        else final_score["player2"]
    )
    
    # Разные сообщения для таймаута выбора тактики и игрового хода
    if match_data["turn_number"] == 0:
        # Таймаут выбора тактики
        winner_message = (
            f"🏆 <b>Победа по таймауту!</b>\n\n"
            f"Соперник @{loser_username} не выбрал тактику за 2 минуты.\n\n"
            f"Матч не влияет на рейтинг."
        )
        
        loser_message = (
            f"⏱ <b>Поражение по таймауту</b>\n\n"
            f"Ты не выбрал тактику за 2 минуты.\n\n"
            f"Матч не влияет на рейтинг."
        )
    else:
        # Таймаут игрового хода
        winner_message = (
            f"🏆 <b>Победа по таймауту!</b>\n\n"
            f"Соперник @{loser_username} не сделал ход за 2 минуты.\n\n"
            f"<b>Итоговый счёт:</b> {winner_score} - {loser_score}\n\n"
            f"Матч не влияет на рейтинг."
        )
        
        loser_message = (
            f"⏱ <b>Поражение по таймауту</b>\n\n"
            f"Ты не успел сделать ход за 2 минуты.\n\n"
            f"<b>Итоговый счёт:</b> {loser_score} - {winner_score}\n\n"
            f"Матч не влияет на рейтинг."
        )
    
    try:
        await bot.send_message(winner_id, winner_message)
        await bot.send_message(loser_id, loser_message)
    except Exception as e:
        logger.error(f"Error sending timeout finish messages: {e}")
    
    # Удаляем матч
    await matches_manager.delete_match(match_id)
    
    logger.info(f"Match {match_id} finished by timeout. Winner: {winner_id}")


async def finish_match_by_exit(match_id: str, exit_user_id: int, redis: Redis):
    """
    Завершает матч при выходе игрока.
    
    Args:
        match_id: ID матча
        exit_user_id: ID игрока, который вышел
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    # Определяем победителя и проигравшего
    loser_id = exit_user_id
    winner_id = (
        match_data["player2_id"] 
        if loser_id == match_data["player1_id"] 
        else match_data["player1_id"]
    )
    
    # Обновляем данные матча
    await matches_manager.update_match(match_id, {
        "state": "finished",
        "winner_id": winner_id,
        "finish_reason": "exit"
    })
    
    # Отправляем уведомления
    winner_username = (
        match_data["player1_username"] 
        if winner_id == match_data["player1_id"] 
        else match_data["player2_username"]
    )
    loser_username = (
        match_data["player1_username"] 
        if loser_id == match_data["player1_id"] 
        else match_data["player2_username"]
    )
    
    final_score = match_data["score"]
    winner_score = (
        final_score["player1"] 
        if winner_id == match_data["player1_id"] 
        else final_score["player2"]
    )
    loser_score = (
        final_score["player1"] 
        if loser_id == match_data["player1_id"] 
        else final_score["player2"]
    )
    
    winner_message = (
        f"🏆 <b>Победа!</b>\n\n"
        f"Игрок @{loser_username} вышел из игры.\n\n"
        f"<b>Итоговый счёт:</b> {winner_score} - {loser_score}\n\n"
        f"Матч не влияет на рейтинг."
    )
    
    loser_message = (
        f"❌ <b>Ты вышел из игры</b>\n\n"
        f"Матч завершён. Победитель: @{winner_username}\n\n"
        f"<b>Итоговый счёт:</b> {loser_score} - {winner_score}\n\n"
        f"Матч не влияет на рейтинг."
    )
    
    try:
        await bot.send_message(winner_id, winner_message)
        await bot.send_message(loser_id, loser_message)
    except Exception as e:
        logger.error(f"Error sending exit finish messages: {e}")
    
    # Отменяем все запланированные таймауты для этого матча
    cancel_match_timeouts(match_id)
    
    # Удаляем матч
    await matches_manager.delete_match(match_id)
    
    logger.info(f"Match {match_id} finished by exit. Exited user: {exit_user_id}")


async def finish_match_normal(
    match_id: str,
    winner_id: int | None,
    redis: Redis
):
    """
    Нормальное завершение матча после 5 атак.
    
    Args:
        match_id: ID матча
        winner_id: ID победителя или None при ничьей
        redis: Redis connection
    """
    matches_manager = OnlineMatchesManager(redis)
    match_data = await matches_manager.get_match(match_id)
    
    if not match_data:
        return
    
    # Обновляем данные матча
    await matches_manager.update_match(match_id, {
        "state": "finished",
        "winner_id": winner_id,
        "finish_reason": "normal"
    })
    
    final_score = match_data["score"]
    player1_score = final_score["player1"]
    player2_score = final_score["player2"]
    
    player1_username = match_data["player1_username"]
    player2_username = match_data["player2_username"]
    
    # Формируем итоговое сообщение
    if winner_id is None:
        # Ничья
        result_text = f"🤝 <b>Ничья!</b>"
    elif winner_id == match_data["player1_id"]:
        result_text = f"🏆 <b>Победа @{player1_username}!</b>"
    else:
        result_text = f"🏆 <b>Победа @{player2_username}!</b>"
    
    message = (
        f"{result_text}\n\n"
        f"<b>Итоговый счёт:</b>\n"
        f"@{player1_username}: {player1_score}\n"
        f"@{player2_username}: {player2_score}\n\n"
        f"Матч не влияет на рейтинг."
    )
    
    try:
        await bot.send_message(match_data["player1_id"], message)
        await bot.send_message(match_data["player2_id"], message)
    except Exception as e:
        logger.error(f"Error sending normal finish messages: {e}")
    
    # Отменяем все запланированные таймауты
    cancel_match_timeouts(match_id)
    
    # Удаляем матч
    await matches_manager.delete_match(match_id)
    
    logger.info(f"Match {match_id} finished normally. Winner: {winner_id}")


def cancel_match_timeouts(match_id: str):
    """
    Отменить все запланированные таймауты для матча.
    
    Args:
        match_id: ID матча
    """
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.id.startswith(f"pvp_timeout_{match_id}_"):
            try:
                scheduler.remove_job(job.id)
                logger.info(f"Cancelled timeout job: {job.id}")
            except Exception as e:
                logger.warning(f"Failed to cancel job {job.id}: {e}")

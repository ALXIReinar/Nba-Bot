from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from core.config_dir.config import bot
from core.data.online_matches_manager import OnlineMatchesManager
from core.utils.logger_config import log_event

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
        log_event(f"\033[36m[Bg scheduler]\033[0m Игрок не выбрал тактику(p2 lose)! Техническое поражение | player1_id: {player1_id}, player2_id: {player2_id}")
        return player1_id, player2_id

    # Если player2 выбрал, а player1 нет
    if player2_tactic and not player1_tactic:
        log_event(f"\033[36m[Bg scheduler]\033[0m Игрок не выбрал тактику(p1 lose)! Техническое поражение | player1_id: {player1_id}, player2_id: {player2_id}")
        return player2_id, player1_id

    # Если оба не выбрали (или оба выбрали - не должно случиться)
    # Проигрывает приглашённый (player2)
    log_event(f"\033[36m[Bg scheduler]\033[0m Никто так и не выбрал тактику! Техническое поражение приглашённому! | player1_id: {player1_id}, player2_id: {player2_id}")
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
        log_event(f'\033[36m[Bg scheduler]\033[0m Матч не найден. Не удалось прервать по таймауту | match_id: \033[33m{match_id}\033[0m', level='WARNING')
        return
    
    # Проверяем, совпадает ли turn_number
    if match_data["turn_number"] == turn_number:
        # Ход не был сделан за 2 минуты — засчитываем поражение
        
        # Специальная логика для turn_number = 0 (выбор тактики)
        if turn_number == 0:
            winner_id, loser_id = determine_winner_on_tactic_timeout(match_data)

            log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершён по таймауту игрока | match_id: \033[33m{match_id}\033[0m; winner_id: {winner_id}; loser_id: {loser_id}', level='WARNING')

        else:
            # Обычная логика для игрового хода
            loser_id = match_data["current_attacker_id"]
            winner_id = (
                match_data["player2_id"] 
                if loser_id == match_data["player1_id"] 
                else match_data["player1_id"]
            )
            log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершён по таймауту игрока | match_id: \033[33m{match_id}\033[0m; winner_id: {winner_id}; loser_id: {loser_id}', level='WARNING')

        
        await finish_match_by_timeout(match_id, winner_id, loser_id, redis)
    else:
        log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершился. Скип | match_id: \033[33m{match_id}\033[0m')


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
    log_event(f'\033[36m[Bg scheduler]\033[0m Джоба для таймаутов матчей | turn_num: \033[35m{turn_number}\033[0m; match_id: \033[33m{match_id}\033[0m')


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
        log_event(f'\033[36m[Bg scheduler]\033[0m Матч не найден. Не удалось закончить по таймауту | match_id: \033[33m{match_id}\033[0m', level='WARNING')
        return
    
    # Обновляем данные матча
    await matches_manager.update_match(match_id, {
        "state": "finished",
        "winner_id": winner_id,
        "finish_reason": "timeout"
    })
    
    # Отправляем уведомления обоим игрокам
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
        log_event(f'\033[36m[Bg scheduler]\033[0m Не удалось отправить сообщение о техническом поражении игрокам! | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m; loser_tg_id: \033[35m{loser_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')


    # Удаляем матч
    await matches_manager.delete_match(match_id)
    log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершился по таймауту | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m; loser_tg_id: \033[35m{loser_id}\033[0m')


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
        log_event(f'\033[36m[Bg scheduler]\033[0m Матч не найден. Не удалось закончить по причине выхода из матча одного из игроков | match_id: \033[33m{match_id}\033[0m', level='WARNING')
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
        log_event(f'\033[36m[Bg scheduler]\033[0m Не удалось отправить сообщение о техническом поражении игрокам! | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m; loser_tg_id: \033[35m{loser_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')

    log_event(f'\033[36m[Bg scheduler]\033[0m Отменяем фоновые задачи матча | match_id: \033[35m{match_id}\033[0m')
    # Отменяем все запланированные таймауты для этого матча
    cancel_match_timeouts(match_id)
    
    # Удаляем матч
    await matches_manager.delete_match(match_id)
    log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершился, т.к. кто-то вышел из него | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m; loser_tg_id: \033[35m{loser_id}\033[0m')


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
        log_event(f'\033[36m[Bg scheduler]\033[0m Матч не найден. Не удалось завершить gracefully | match_id: \033[33m{match_id}\033[0m', level='WARNING')
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
        log_event(f'\033[36m[Bg scheduler]\033[0m Не удалось отправить сообщение о итогах матча! | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m; err: \033[31m{repr(e)}\033[0m', level='WARNING')

    # Отменяем все запланированные таймауты
    log_event(f'\033[36m[Bg scheduler]\033[0m Отменяем фоновые задачи матча | match_id: \033[35m{match_id}\033[0m')
    cancel_match_timeouts(match_id)
    
    # Удаляем матч
    await matches_manager.delete_match(match_id)
    log_event(f'\033[36m[Bg scheduler]\033[0m Матч завершился по таймауту | match_id: \033[35m{match_id}\033[0m; winner_tg_id: \033[33m{winner_id}\033[0m')


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
                log_event(f"\033[36m[Bg scheduler]\033[0m Отменили джобу | match_id: \033[33m{match_id}\033[0m; job_id: {job.id}")
            except Exception as e:
                log_event(f"\033[36m[Bg scheduler]\033[0m Не смогли отменить джобу | match_id: \033[33m{match_id}\033[0m; job_id: {job.id}; err: {repr(e)}\033[0m", level='WARNING')

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from app.core.bot import bot
from app.core.logger_config import log_event
from app.db.postgres import PgSql
from app.modules.main.handler import cmd_help
from app.modules.tasks.anything import ChallengesMessages, calculate_and_give_task_packs
from app.modules.tasks.keyboards import show_tasks_list
from app.modules.tasks.service import ChallengesViewer

router = Router()


@router.callback_query(F.data.lower() == "challenges_main")
async def answer_tasks_list(call: CallbackQuery, db: PgSql):
    tasks = await db.challenges.show_user_tasks(call.from_user.id)

    log_event(f'Пользователь открыл вкладку заданий. Строим клаву из них | user_id: \033[31m{call.from_user.id}\033[0m')

    await bot.edit_message_text(
        ChallengesMessages.challenges_main_msg(tasks),
        call.from_user.id,
        call.message.message_id,
        reply_markup=show_tasks_list(tasks)
    )
    await call.answer()


@router.callback_query(F.data == "profile_message")
async def profile_message(call: CallbackQuery, db: PgSql):
    await bot.delete_message(call.from_user.id, call.message.message_id)
    await cmd_help(call.message, db)
    await call.answer()


@router.callback_query(F.data == "challenges_choose_new")
async def answer_tasks_choose_new(call: CallbackQuery, db: PgSql, redis: Redis, state: FSMContext):
    task_set_id, accepted_challenges = await db.challenges.set_select_task_set(call.from_user.id)

    log_event(f'Пользователь переходи выбирает новые задания | task_set_id: \033[31m{task_set_id}\033[0m; user_id: \033[32m{call.from_user.id}\033[0m')
    fsm_data = {'task_set_id': task_set_id, 'accepted_challenges': {}, 'accepted_slots': {}}
    if accepted_challenges:
        fsm_data['accepted_challenges'] = {ac['challenge_id']: ac['challenge_difficulty_id'] for ac in accepted_challenges}
        fsm_data['accepted_slots'] = {ac['challenge_id']: ac['slot'] for ac in accepted_challenges}

    await state.update_data(**fsm_data)

    text, kb = await ChallengesViewer.build_challenges_viewer(0, None, redis, db, state, call.from_user.id, fsm_data['accepted_challenges'])

    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("challenges_pagen_"))
async def change_pagen_challenges(call: CallbackQuery, db: PgSql, redis: Redis, state: FSMContext):
    new_challenge_idx = int(call.data.split("_")[-1])
    text, kb = await ChallengesViewer.build_challenges_viewer(new_challenge_idx, None, redis, db, state, call.from_user.id)

    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    log_event(f'Пользователь листает челленджи | user_id: \033[31m{call.from_user.id}\033[0m; challenge_idx: \033[31m{new_challenge_idx}\033[0m')

    await call.answer()


@router.callback_query(F.data.startswith("challenges_difficulty_"))
async def change_difficulty(call: CallbackQuery, db: PgSql, redis: Redis, state: FSMContext):
    new_challenge_diff_id = int(call.data.split("_")[-1])
    cur_challenge_idx = int(call.data.split("_")[-2])

    text, kb = await ChallengesViewer.build_challenges_viewer(cur_challenge_idx, new_challenge_diff_id, redis, db, state, call.from_user.id)

    try:
        await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    except TelegramBadRequest as e:
        # Кейс, при котором ТГ кидает исключение, если редактируем сообщение без изменений
        pass

    log_event(f'Пользователь смотрит сложности челленджа | user_id: \033[31m{call.from_user.id}\033[0m; challenge_idx: \033[31m{cur_challenge_idx}\033[0m; challenge_difficulty_id: \033[35m{new_challenge_diff_id}\033[0m')
    await call.answer()


@router.callback_query(F.data.startswith("challenges_accept_task_"))
async def accept_task(call: CallbackQuery, db: PgSql, redis: Redis, state: FSMContext):

    ctx_data = await state.get_data()
    task_set_id, acc_challenges, acc_slots = ctx_data.get('task_set_id'), ctx_data.get('accepted_challenges'), ctx_data.get('accepted_slots')
    data = call.data.split('_')
    cur_chal_idx, chal_id, diff_id = int(data[-3]),int(data[-2]), int(data[-1])

    "Потерялась state"
    if task_set_id is None or acc_challenges is None:
        log_event(f'Не смогли добавить таску пользователю. State нет task_set_id, accepted_challenges или accepted_slots | user_id: \033[31m{call.from_user.id}\033[0m', level='WARNING')
        await bot.delete_message(call.from_user.id, call.message.message_id)
        await call.message.answer("⚠️ Не удалось добавить задание. Попробуйте снова")
        await call.answer()
        return

    "Регаем слот в бд"
    slot = await db.challenges.accept_challenge(task_set_id, chal_id, diff_id)
    log_event(f'Пользователь выбрал челлендж. Сохранили в БД и в state | user_id: \033[31m{call.from_user.id}\033[0m; challenge_id: \033[32m{chal_id}\033[0m; challenge_difficulty_id: \033[34m{diff_id}\033[0m; slot: \033[36m{slot}\033[0m; task_set_id: \033[35m{task_set_id}\033[0m')
    if not slot:
        log_event(f'Не удалось выбрать  | user_id: \033[31m{call.from_user.id}\033[0m; challenge_id: \033[32m{chal_id}\033[0m; challenge_difficulty_id: \033[34m{diff_id}\033[0m; task_set_id: \033[35m{task_set_id}\033[0m', level='WARNING')
        await call.message.answer("⚠️ Не удалось добавить задание")
        await call.answer()
        return

    "Синкаем в state"
    acc_challenges[chal_id] = diff_id
    acc_slots[chal_id] = slot
    await state.update_data(accepted_challenges=acc_challenges, accepted_slots=acc_slots)

    text, kb = await ChallengesViewer.build_challenges_viewer(cur_chal_idx, diff_id, redis, db, state, call.from_user.id, acc_challenges)
    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("challenges_decline_task_"))
async def accept_task(call: CallbackQuery, db: PgSql, redis: Redis, state: FSMContext):
    ctx_data = await state.get_data()
    task_set_id, acc_challenges, acc_slots = ctx_data.get('task_set_id'), ctx_data.get('accepted_challenges'), ctx_data.get('accepted_slots')
    data = call.data.split('_')
    cur_chal_idx, chal_id, diff_id = int(data[-3]), int(data[-2]), int(data[-1])

    "Потерялась state"
    if task_set_id is None or acc_challenges is None:
        log_event(f'Не смогли добавить таску пользователю. State нет task_set_id, accepted_challenges или accepted_slots | user_id: \033[31m{call.from_user.id}\033[0m', level='WARNING')
        await bot.delete_message(call.from_user.id, call.message.message_id)
        await call.message.answer("⚠️ Не удалось добавить задание. Попробуйте снова")
        await call.answer()
        return

    "Регаем слот в бд"
    res = await db.challenges.decline_challenge(task_set_id, chal_id, acc_slots[chal_id])
    log_event(f'Пользователь отменил челлендж. Удалили ищ БД и state | user_id: \033[31m{call.from_user.id}\033[0m; challenge_id: \033[32m{chal_id}\033[0m; challenge_difficulty_id: \033[34m{diff_id}\033[0m; task_set_id: \033[35m{task_set_id}\033[0m')
    if not res:
        log_event(f'Не удалось отменить выбор челленджа | user_id: \033[31m{call.from_user.id}\033[0m; challenge_id: \033[32m{chal_id}\033[0m; challenge_difficulty_id: \033[34m{diff_id}\033[0m; task_set_id: \033[35m{task_set_id}\033[0m',level='WARNING')
        await call.message.answer("⚠️ Не удалось удалить задание")
        await call.answer()
        return

    "Синкаем в state"
    del acc_challenges[chal_id]
    del acc_slots[chal_id]
    await state.update_data(accepted_challenges=acc_challenges, accepted_slots=acc_slots)

    text, kb = await ChallengesViewer.build_challenges_viewer(cur_chal_idx, diff_id, redis, db, state, call.from_user.id, acc_challenges)
    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == 'challenges_confirm_task_set')
async def confirm_task_set(call: CallbackQuery, db: PgSql, state: FSMContext):
    await bot.delete_message(call.from_user.id, call.message.message_id)
    ctx_data = await state.get_data()
    task_set_id = ctx_data.get('task_set_id')

    "Старое сообщение/слетела state"
    if not task_set_id:
        log_event(f'Не удалось активировать набор заданий с таймером | user_id: \033[31m{call.from_user.id}\033[0m; task_set_id: \033[32m{task_set_id}\033[0m;', level='WARNING')
        await bot.delete_message(call.from_user.id, call.message.message_id)
        await call.message.answer("⚠️ Не удалось запустить таймер заданий. Попробуйте снова")
        await call.answer()
        return


    res = await db.challenges.activate_task_set_timer(task_set_id)
    if res:
        await call.message.answer('Задания активированы! У тебя есть 7 дней на выполнение!')

    await call.answer()


@router.callback_query(F.data.startswith('challenges_tasks_'))
async def task_view(call: CallbackQuery, db: PgSql):
    task_id = int(call.data.split('_')[-1])
    text, kb = await ChallengesViewer.view_user_task(task_id, db)
    if not kb:
        log_event(f'Челлендж не найден | task_id: \033[31m{task_id}\033[0m; user_id: \033[33m{call.from_user.id}\033[0m', level='ERROR')
    else:
        log_event(f'Отобразили челлендж | task_id: \033[32m{task_id}\033[0m; user_id: \033[35m{call.from_user.id}\033[0m')

    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("challenges_collect_rewards_all_"))
async def collect_rewards_all(call: CallbackQuery, db: PgSql):

    task_set_id = int(call.data.split('_')[-1])
    accrual_res = await db.challenges.collect_rewards(task_set_id=task_set_id)
    if not accrual_res:
        log_event(f"Попытка дюпа награды | user_id: \033[31m{call.from_user.id}\033[0m; task_set_id: \033[33m{task_set_id}\033[0m", level='WARNING')
        await call.answer()
        return

    "Вычисляем, сколько паков нужно начислить"
    await calculate_and_give_task_packs(accrual_res['user_id'], accrual_res['credit_packs_in_exp'], db.conn)
    await call.answer()
    await answer_tasks_list(call, db)


@router.callback_query(F.data.startswith("challenges_reward_task_"))
async def reward_task_view(call: CallbackQuery, db: PgSql):
    task_id = int(call.data.split('_')[-1])
    res = await db.challenges.collect_rewards(task_id=task_id)
    if not res:
        log_event(f'Не удалось собрать награду. task_set_id не существует | task_id: \033[32m{task_id}\033[0m; user_id: \033[31m{call.from_user.id}\033[0m', level='WARNING')
        await call.answer()
        return

    await calculate_and_give_task_packs(res['user_id'], res['credit_packs_in_exp'], db.conn)
    await call.answer()

    text, kb = await ChallengesViewer.view_user_task(task_id, db)
    await bot.edit_message_text(text, call.from_user.id, call.message.message_id, reply_markup=kb)


"""
======================================================================================
Функционал для демо
======================================================================================
"""

@router.message(Command('complete_task'))
async def complete_task(message: Message, db: PgSql):
    """
    НЕ УЧИТЫВАЕТ ПРОЦЕНТ ВЫПОЛНЕНИЯ ЗАДАНИЙ НАБОРА.

    Такие кейсы(3/4 уже готовы, сейчас комплитим 4) переводят набор заданий в "completed" в обычных условиях
    """
    task_id = int(message.text.split()[-1])

    await db.challenges.conn.execute('''
    UPDATE user_challenges SET status = 3 -- reward_ready
    WHERE id = $1
    ''', task_id)
    log_event(f'Таска переведна в ревард_реади | task_id: \033[32m{task_id}\033[0m; user_id: \033[33m{message.from_user.id}\033[0m', level='WARNING')

@router.message(Command('set_task_set_in_progress'))
async def complete_task(message: Message, db: PgSql):
    task_set_id = int(message.text.split()[-1])

    await db.challenges.conn.execute('''
    UPDATE user_challenges SET status = 2 -- in_progress
    WHERE task_set_id = $1
    ''', task_set_id)
    await db.challenges.conn.execute('''
    UPDATE challenges_tasks_set SET status = 2 -- in_progress
    WHERE id = $1
    ''', task_set_id)
    log_event(f'Набор заданий и сами задания переведены в ин_прогресс | task_set_id: \033[35m{task_set_id}\033[0m; user_id: \033[36m{message.from_user.id}\033[0m', level='WARNING')

@router.message(Command('complete_task_set'))
async def complete_task(message: Message, db: PgSql):
    """
    Переводит таски в состояние достпа к наградам. Система полагается ,
    что  reward_ready таски находятся в in_progerss наборе заданий(task_set_id)
    """
    task_set_id = int(message.text.split()[-1])

    await db.challenges.conn.execute('''
    UPDATE user_challenges SET status = 3 -- reward_ready
    WHERE task_set_id = $1
    ''', task_set_id)
    await db.challenges.conn.execute('''
    UPDATE challenges_tasks_set SET status = 2 -- in_progress
    WHERE id = $1
    ''', task_set_id)
    log_event(f'Набор заданий переведён в  ин_прогресс, а таски - в ревард_реади | task_set_id: \033[35m{task_set_id}\033[0m; user_id: \033[36m{message.from_user.id}\033[0m', level='WARNING')


@router.message(Command('add_progress'))
async def add_progress_on_tasks(message: Message, db: PgSql):
    """
    Прогресс заданий добавляется через общий запрос для всех челленджей
    Сами челленджи имеют привязку к challenges_actions(таблица действий, которые происходят в боте. Челленджи выполняются по мере повторения этих действий)

    Эту-функцию запрос и класс с challenges_actions необходимо интегрировать в код, где происходят эти самый "действия"
    """
    splitted = message.text.split()
    challenge_id, add_progress = int(splitted[-2]), int(splitted[-1])

    await ChallengesViewer.add_task_progress(challenge_id, message.from_user.id, add_progress, db)
    await message.answer(f"✅ Выполнено!")
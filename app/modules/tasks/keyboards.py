from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.logger_config import log_event
from app.modules.tasks.anything import ChallengeStatuses, ChallengesTasksSetStatuses


def show_tasks_list(tasks_list: list):
    kb = InlineKeyboardBuilder()

    log_mes = f'Содержимое клавиатуры | task_list_len: \033[36m{len(tasks_list)}\033[0m'
    # Кнопка быстрого сбора наград
    any_task_reward_ready = False

    # Если заданий нет, нужно предоставить возможность выбрать их
    show_choose_tasks_btn = True

    tasks_list.sort(key=lambda x: x['slot'])
    for task in tasks_list:

        # Таски отображаются только если набор в in_progress, completed, closed
        # Выбрать новые таски можно только если набор closed или draft
        if task['task_set_status'] in {ChallengesTasksSetStatuses.in_progress, ChallengesTasksSetStatuses.completed}:
            show_choose_tasks_btn = False

        smile_prefix = ChallengeStatuses.emoji_slots_map.get(task['slot'], "⏹️")

        # Для кнопки сбора всех наград
        if task['status'] == ChallengeStatuses.reward_ready:
            any_task_reward_ready = True

        # Меняем смайлик, если таска не in_progress
        if task['status'] != ChallengeStatuses.in_progress:
            smile_prefix = ChallengeStatuses.emoji_statuses.get(task['status']) or smile_prefix # Если статус не учтён в датаклассе оставляем смайлик-слота

        kb.button(text=f'{smile_prefix} Задание', callback_data=f"challenges_tasks_{task['id']}")

    if any_task_reward_ready: # task доступен после 1ой итерации цикла, task_set_id у всех тасок один и тот же
        kb.button(text="🤲 Забрать все награды", callback_data=f"challenges_collect_rewards_all_{task['task_set_id']}")
        log_mes += "; collect_rewards_all_btn: True"

    "Пользователь НЕ может выбрать новые задания с неполученными наградами за старые"
    if show_choose_tasks_btn and not any_task_reward_ready:
        kb.button(text="🔍Выбрать новые задания", callback_data="challenges_choose_new")
        log_mes += "; choose_new_btn: True"

    kb.button(text="↪️Назад", callback_data="profile_message")
    kb.adjust(1)

    # для лога
    any_task = tasks_list[0] if tasks_list else None
    log_mes += f"; task_set_info: \033[33m{repr(any_task)}\033[0m"
    log_event(log_mes)

    return kb.as_markup()


def challenges_slider(
    cur_challenge_idx: int,
    total_challenges: int,
    cur_challenge_difficulty_id: int,
    challenge_obj: dict,
    accepted_challenges: dict[int, int],
):
    kb_sizes = []
    prev_idx = cur_challenge_idx - 1 if cur_challenge_idx != 0 else total_challenges - 1
    next_idx = cur_challenge_idx + 1 if cur_challenge_idx < total_challenges - 1 else 0

    challenge_id = challenge_obj['id']
    accepted_challenges_qty = len(accepted_challenges)
    accepted_factor = accepted_challenges.get(challenge_id, 0) == cur_challenge_difficulty_id

    "Сборка кнопок для сложностей челенджа"
    kb = InlineKeyboardBuilder()
    if not accepted_factor and accepted_challenges_qty < 4:

        dif_sizes = 0
        "Отображаем сложности только, если челлендж НЕ выбран"
        for difficulty in challenge_obj['challenge_difficulties']:
            diff_id = difficulty['challenge_difficulty_id']

            dif_btn_text = str(difficulty['goal'])

            "Выделяем выбранную сложность"
            if diff_id == cur_challenge_difficulty_id:
                dif_btn_text = f'[{dif_btn_text}]'
            kb.button(text=dif_btn_text, callback_data=f"challenges_difficulty_{cur_challenge_idx}_{diff_id}")
            dif_sizes += 1
        kb_sizes = [dif_sizes] + kb_sizes

    "Статичные кнопки"
    # Чекбокс челенджа
    if accepted_factor:
        kb.button(text='❌Убрать', callback_data=f"challenges_decline_task_{cur_challenge_idx}_{challenge_id}_{cur_challenge_difficulty_id}")
        kb_sizes.append(2)
    elif not accepted_factor and accepted_challenges_qty < 4:
        kb.button(text='✅Выбрать', callback_data=f"challenges_accept_task_{cur_challenge_idx}_{challenge_id}_{cur_challenge_difficulty_id}")
        kb_sizes.append(2)
    else:
        # Кейс, при котором Задание НЕ выбрано, но пользователь УЖЕ выбрал 4 задания
        # В таком случае он не может выбрать 5ое задание(или убрать несуществующее)
        kb_sizes.append(1)

    # Кнопка - счётчик. Превращаем в кнопку подтверждения набора заданий, если пользователь набрал 4 задания
    if accepted_challenges_qty == 4:
        kb.button(text="✅Подтвердить задания", callback_data="challenges_confirm_task_set")
    else:
        kb.button(text=f"{accepted_challenges_qty}/4", callback_data="none")

    "Пагинация"
    kb.button(text='<-', callback_data=f'challenges_pagen_{prev_idx}')
    kb.button(text=f'{cur_challenge_idx + 1}/{total_challenges}', callback_data=f'None')
    kb.button(text='->', callback_data=f'challenges_pagen_{next_idx}')
    kb.button(text="↪️Назад", callback_data="challenges_main")

    kb.adjust(*(kb_sizes + [3, 1]))
    return kb.as_markup()


def task_view_actions(task_id: int, task_status: int):
    kb = InlineKeyboardBuilder()
    if task_status == ChallengeStatuses.reward_ready:
        kb.button(text='🤲 Забрать награду', callback_data=f"challenges_reward_task_{task_id}")
    kb.button(text="↪️Назад", callback_data='challenges_main')
    kb.adjust(1)
    return kb.as_markup()
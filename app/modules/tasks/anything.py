from dataclasses import dataclass
from datetime import timedelta, datetime

from asyncpg import Connection

from app.core.logger_config import log_event


class ChallengeDifficulties:
    easy: int = 1
    medium: int = 2
    hard: int = 3
    general: int = 4

    challenge_difficulties_map: dict = {
        1: "Лёгкая🟢",
        2: "Средняя🟡",
        3: "Сложная🔴",
        4: "Общая🔷"
    }

class ChallengeStatuses:
    pending: int = 1
    in_progress: int = 2
    reward_ready: int = 3
    completed: int = 4
    expired: int = 5

    emoji_slots_map: dict = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣"}
    emoji_statuses: dict = {
        reward_ready: "💰",
        completed: "✅",
        expired: "❌",
    }

@dataclass
class ChallengesCategories:
    collections: int = 1
    invite_friends: int = 2
    pvp_5v5: int = 3
    throw_ball: int = 4

@dataclass
class ChallengesTasksSetStatuses:
    draft: int = 1
    in_progress: int = 2
    completed: int = 3
    closed: int = 4

@dataclass
class Challenges:
    invite_friends: int = 1                 # "Пригласи {goal} друзей по ссылке в профиле"
    craft_or_open_cards: int = 2            # "Скрафть или открой {goal} карточек"
    goal_through_block_5v5: int = 3         # "Забей {goal} раз через блок в 5 на 5"
    craft_or_open_silver_cards: int = 4     # "Скрафть или открой {goal} серебрянных карточек"
    craft_or_open_gold_cards: int = 5       # "Скрафть или открой {goal} золотую карточку"
    craft_cards: int = 6                    # "Скрафть {goal} карточек"
    throw_balls: int = 7                    # "Кинь {goal} мячиков"
    craft_or_open_diamond_cards: int = 8    # "Скрафть или открой {goal} алмаз карточку"
    craft_or_open_legend_cards: int = 9     # "Скрафть или открой {goal} легенд карточку"
    disassembly_cards: int = 10             # "Разбери {goal} карточек"
    victory_5v5: int = 11                   # "Одержи {goal} побед в 5 на 5"
    pass_5v5: int = 12                      # "Сделай {goal} пасов в 5 на 5"
    goal_3point_5v5: int = 13               # "Забей 3х очковый {goal} раз в 5 на 5"
    win_same_team: int =  14                # "Победи одним и тем же составом команды в {goal} матчей"

class ChallengesMessages:
    @classmethod
    def challenges_main_msg(cls, tasks: list):
        msg_map = {
            4: """
📆Задания
Время на выполнение истекло
            """,
            2: """
📆Задания
На выполнение <b>{date}</b>
""",
            3: """
📆Задания
Ты выполнил все задания! \nТы сможешь выбрать следующие через <b>{date}</b>
""",
            1: """
📆Задания
Ты можешь выбрать задания на неделю
"""
        }

        if not tasks:
            return msg_map[ChallengesTasksSetStatuses.draft]

        task_set_info = tasks[0]
        task_set_status = task_set_info["task_set_status"]
        if task_set_status in {ChallengesTasksSetStatuses.in_progress, ChallengesTasksSetStatuses.completed}:
            end_date = task_set_info["started_at"] + timedelta(days=7)
            time_left = end_date - datetime.now()

            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            formatted_date = f"{days} д. {hours} ч. {minutes} м."
            return msg_map[task_set_status].format(date=formatted_date)


        return msg_map[task_set_status]


async def calculate_and_give_task_packs(user_id, packs_in_exp, conn: Connection):
    to_credit_packs = packs_in_exp // 1000

    log_event(f'Начислили основную награду. Паков к начислению за exp | packs_count: \033[32m{to_credit_packs}\033[0m; user_id: \033[31m{user_id}\033[0m')

    if to_credit_packs > 0:
        # TODO: уточни, правильно ли дёргаю добавление паков
        # await services.packs.add_packs('tasks', to_credit_packs, user_id, conn)
        log_event(f"Паки начислены! | user_id: \033[31m{user_id}\033[0m; packs_count: \033[36m{to_credit_packs}\033[0m")
        return True

    return False

class RedisKeys:
    general_challenges = "nba_bot:tg-bot:cache_probe:challenges:v1"

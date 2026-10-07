import json

from asyncpg import Connection

from app.db.postgres import PgSql
from app.modules.base_service import BaseService


class   Task:
    def __init__(self, name: str, description: str, max: int, reward: int):
        self.name = name
        self.description = description
        self.max = max
        self.current = 0
        self.rewarded = False
        self.reward = reward

    def toJsonElement(self):
        rewarded = 'true' if self.rewarded else 'false'
        return f'"{self.name}":' + " {\n" + f'"current": {self.current},\n"rewarded": {rewarded},\n "max": {self.max},\n "reward": {self.reward},\n "description": "{self.description}"\n' + "}"

    @staticmethod
    def fromJson(name: str, data: dict) -> 'Task':
        task = Task(
            name=name,
            description=data["description"],
            max=data["max"],
            reward=data["reward"]
        )
        task.current = data["current"]
        task.rewarded = data["rewarded"]
        return task

class TasksService(BaseService):
    def __init__(self, db: PgSql):
        super().__init__(db)
        schedule.scheduler.add_job(self.UpdateAllUsersTasks, 'cron', day_of_week=0,hour=0,minute=0)

    #actions
        self.cards_getted_action = "cards_getted"
        self.bronze_cards_getted_action = "bronze_cards_getted"
        self.silver_cards_getted_action = "silver_cards_getted"
        self.gold_cards_getted_action = "gold_cards_getted"
        self.legend_cards_getted_action = "legend_cards_getted"
        self.diamond_cards_getted_action = 'diamond_cards_getted'
        self.refferers_made_action = "refferers_made"
        self.crafted_cards_action = "crafted_cards"
        self.balls_thrown_action = "balls_thrown"
        self.trade_made = "trades_made"
        self.present_made = "presents_made"
        self.games_played = "games_played"
        self.games_loosed = "games_loosed"
        self.games_winned = "games_winned"
        self.exclusive_cards_getted = "exclusive_cards_getted"
        self.ex_clips_getted = "ex_clips_getted"
        self.clips_getted = "clips_getted"

        self.category_action = {
            'bronze': self.bronze_cards_getted_action,
            'silver': self.silver_cards_getted_action,
            'gold': self.gold_cards_getted_action,
            'legend': self.legend_cards_getted_action,
            'diamond': self.diamond_cards_getted_action
        }

        self.PossibleTasks = [
            Task(self.refferers_made_action, "Пригласи 2 друзей по ссылке в профиле", 2, 5),
            Task(self.cards_getted_action, "Открой 40 карточек", 40, 5),
            Task(self.bronze_cards_getted_action, "Открой 25 бронзовых карточек", 25, 5),
            Task(self.silver_cards_getted_action, "Скрафть или открой 5 серебрянных карточек", 5, 5),
            Task(self.gold_cards_getted_action, "Скрафть или открой 1 золотую карточку", 1, 5),
            #Task(legend_cards_getted_action, "Скрафть или открой 1 легендарную карточку", 1, 5),
            Task(self.crafted_cards_action, "Скрафть 5 карточек", 5, 5),
            Task(self.balls_thrown_action, "Кинь 5 мячиков", 5, 5),
            ]

async def PerformAction(self, action_name: str, user_id: int, connection: Connection | None = None):
        task_desc = None
        current_task = None
        async with self._connection(connection) as conn:
                await conn.execute(
                    f"""
                    UPDATE user_stats
                    SET {action_name} = {action_name} + 1
                    WHERE user_id = $1;
                    """,
                    user_id,
                )

                raw = await conn.fetchval(
                    """
                    SELECT tasks
                    FROM user_tasks
                    WHERE user_id = $1
                    FOR UPDATE;
                    """,
                    user_id,
                )

                if raw:
                    tasks = json.loads(raw) if isinstance(raw, str) else raw
                    current_task = tasks.get(action_name)

                    if current_task is not None:
                        current_task["current"] += 1


                        if current_task["current"] >= current_task["max"]:
                            task_desc = current_task["description"]

                        await conn.execute(
                            """
                            UPDATE user_tasks
                            SET tasks = $1::jsonb
                            WHERE user_id = $2;
                            """,
                            json.dumps(tasks, ensure_ascii=False),
                            user_id,
                        )

        if current_task is not None and current_task["current"] == current_task["max"]:
            await bot.send_message(
                text=f'Ты выполнил задание "{task_desc}"\n\nСкорей забирай награду🤲!',
                chat_id=user_id,
            )

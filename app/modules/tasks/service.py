import orjson
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis

from app.core.config import env, bot
from app.core.logger_config import log_event
from app.db.postgres import PgSql
from app.modules.tasks.anything import RedisKeys, ChallengeDifficulties, ChallengeStatuses
from app.modules.tasks.keyboards import challenges_slider, task_view_actions


class ChallengesViewer:
    @staticmethod
    def _assemble_challenge_text(challenge, selected_difficulty):
        reward_part = f'\nСложность: {ChallengeDifficulties.challenge_difficulties_map[selected_difficulty['challenge_difficulty_id']]}\n'
        if selected_difficulty['reward_throw'] > 0:
            reward_part += f"🏀{selected_difficulty['reward_throw']}\n"
        if selected_difficulty['reward_try'] > 0:
            reward_part += f"👐{selected_difficulty['reward_try']}\n"
        if selected_difficulty['reward_exp'] > 0:
            reward_part += f"💡{selected_difficulty['reward_exp']}\n"
        text = challenge['descr'].format(goal=selected_difficulty['goal']) + reward_part
        return text

    @staticmethod
    def _assemble_task_text(challenge):
        reward_part = f'\nСложность: {ChallengeDifficulties.challenge_difficulties_map[challenge['challenge_difficulty_id']]}\n'
        reward_part += f"({challenge['progress']}/{challenge['goal']})\n\n"
        if challenge['reward_throw'] > 0:
            reward_part += f"🏀{challenge['reward_throw']}\n"
        if challenge['reward_try'] > 0:
            reward_part += f"👐{challenge['reward_try']}\n"
        if challenge['reward_exp'] > 0:
            reward_part += f"💡{challenge['reward_exp']}\n"
        text = challenge['descr'].format(goal=challenge['goal']) + reward_part
        return text

    @staticmethod
    async def get_updated_challenges(redis: Redis, db: PgSql, user_id: int):
        challenges_raw = await redis.get(RedisKeys.general_challenges)

        if not challenges_raw:
            challenges = await db.challenges.get_challenges()
            log_event(f'Отобразили челленджи, обновили кэш в Redis | challenges_count: \033[36m{len(challenges)}\033[0m', level='WARNING')

            # TODO: проблемы с сериализатором jsonb/json полей. Сейчас json - строки вместо python объектов
            challenges_pre_json = []
            for row in challenges:
                row = dict(row)
                row['challenge_difficulties'] = orjson.loads(row['challenge_difficulties'])
                challenges_pre_json.append(row)
            # TODO: Когда починится - challenges_pre_json = [dict(r) for r in challenges]

            await redis.set(RedisKeys.general_challenges, orjson.dumps(challenges_pre_json), ex=env.challenges_ttl)
        else:
            challenges_pre_json = orjson.loads(challenges_raw)
            log_event(f'Кэш хит. Челленджи | challenges_count: \033[32m{len(challenges_pre_json)}\033[0m')

        # Фильтруем по персональной выборке пользователя
        user_challenge_ids = await db.challenges.get_user_challenge_ids(user_id)
        filtered_challenges = [ch for ch in challenges_pre_json if ch['id'] in user_challenge_ids]
        log_event(f'Персональная выборка | user_id: \033[31m{user_id}\033[0m; challenges_count: \033[33m{len(filtered_challenges)}\033[0m')
        return filtered_challenges


    @classmethod
    async def build_challenges_viewer(
            cls,
            idx: int,
            cur_challenge_difficulty_id: int | None,
            redis: Redis,
            db: PgSql,
            state: FSMContext,
            user_id: int,
            accepted_challenges: dict[int, int] = None,
    ):
        """
        По дефолту выбираем первую сложность для челленджа. "Пользователь не выбирает её перед появлением сам". Нужна логика "if is None"
        """
        challenges = await cls.get_updated_challenges(redis, db, user_id)
        if not challenges:
            log_event(f'В БД нет челленджей!!!', level='ERROR')
            return "⚒️Что-то пошло не так, попробуйте позже", None

        challenge = challenges[idx]

        "Подгружаем acc челленджи"
        if accepted_challenges is None:
            accepted_challenges = (await state.get_data()).get('accepted_challenges', {})

        # Отображаем сложность "выбранного" челленджа
        if acc_diff_id := accepted_challenges.get(challenge['id']):
            cur_challenge_difficulty = [ch_diff for ch_diff in challenge['challenge_difficulties'] if ch_diff['challenge_difficulty_id'] == acc_diff_id][0]

        # По умолчанию отображаем выбранной первую сложность по челленджу
        elif cur_challenge_difficulty_id is None:
            cur_challenge_difficulty = challenge['challenge_difficulties'][0]
        else:
            # Берём метаданные по сложности. Нужно перебрать список
            cur_challenge_difficulty = [ch_diff for ch_diff in challenge['challenge_difficulties'] if ch_diff['challenge_difficulty_id'] == cur_challenge_difficulty_id][0]
        chal_diff_id = cur_challenge_difficulty['challenge_difficulty_id']

        "Собираем текст"
        text = cls._assemble_challenge_text(challenge, cur_challenge_difficulty)
        "Клава"
        if accepted_challenges is None:
            accepted_challenges = (await state.get_data()).get('accepted_challenges', {})

        kb = challenges_slider(idx, len(challenges), chal_diff_id, challenge, accepted_challenges)
        log_event(f'Отобразили челлендж | challenge_id: \033[35m{challenge['id']}\033[0m; challenge_difficulty_id: \033[32m{chal_diff_id}\033[0m; accepted_challenges: \033[33m{accepted_challenges}\033[0m')
        return text, kb

    @classmethod
    async def view_user_task(cls, task_id: int, db: PgSql):
        task_challenge_info = await db.challenges.get_challenge_info(task_id)
        if not task_challenge_info:
            return "⚒️ Не удалось найти челлендж! Попробуйте позже", None

        text = cls._assemble_task_text(task_challenge_info)
        kb = task_view_actions(task_id, task_challenge_info['status'])
        return text, kb

    @classmethod
    async def add_task_progress(cls, challenge_id: int, user_id: int, progress: int, db: PgSql):
        """
        Отправляет уведомление о выполненных заданиях, если прогресс достиг цели

        Args:
            - challenge_id: айди задания. Брать из Challenges
            - user_id: Юзер, который выполнил действие
            - progress: Сколько прогресса добавить
            - db: соединение с БД
        """
        log_event(f'Юзер выполнил действие. Добавляем прогресс к его таскам | action_id: \033[32m{challenge_id}\033[0m; progress: \033[35m{progress}\033[0m; user_id: \033[31m{user_id}\033[0m')
        affected_tasks = await db.challenges.add_progress_by_action(challenge_id, user_id, progress)

        "Уведомляем пользователя о готовности наград за задания"
        reward_ready_tasks = [at for at in affected_tasks if at['status'] == ChallengeStatuses.reward_ready]
        if reward_ready_tasks:
            text = f'🎉 Задания выполнены\n\nТы можешь получить награды за (<b>{', '.join([str(rrt['slot']) for rrt in reward_ready_tasks])}</b>) задания!'
            await bot.send_message(user_id, text)

        log_event(f'Затронутые челленджи | action_id: \033[32m{challenge_id}\033[0m; user_id: \033[31m{user_id}\033[0m; affected_tasks: \033[36m{affected_tasks}\033[0m')
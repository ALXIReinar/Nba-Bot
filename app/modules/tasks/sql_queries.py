from asyncpg import Connection, UniqueViolationError

from app.core.logger_config import log_event
from app.modules.tasks.anything import ChallengesTasksSetStatuses, ChallengeStatuses, ChallengesCategories


class ChallengesQueries:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def show_user_tasks(self, user_id: int):
        """
        Lazy evaluate. Управляем статусами заданий только когда пользователь хочет посмотреть задания

        Пробуем закрыть набор заданий(Например по истечению недели от started_at)
        Всегда Отображаем самый свежий набор заданий
        """
        query_1 = '''
        WITH expire_task_set AS (
            UPDATE challenges_tasks_set 
            SET status = $4 -- closed
            WHERE user_id = $1
                AND now() > started_at + interval '7 days'
                AND status IN ($2, $3) -- in_progress, completed
            RETURNING id
        )
        UPDATE user_challenges 
        SET status = $5 -- expired
        FROM expire_task_set
        WHERE user_challenges.task_set_id = expire_task_set.id
            AND user_challenges.status = $6 -- in_progress
        RETURNING user_challenges.id
        '''
        query_2 = """
        WITH last_task_set AS (
            SELECT id FROM challenges_tasks_set WHERE user_id = $1 AND status != $2
            ORDER BY id DESC LIMIT 1
        )
        SELECT uc.id, uc.task_set_id, uc.status, uc.slot, cts.status AS task_set_status, cts.started_at
        FROM user_challenges uc
        JOIN last_task_set lts ON lts.id = uc.task_set_id
        LEFT JOIN challenges_tasks_set cts ON cts.id = uc.task_set_id
        """
        await self.conn.execute(
            query_1,
            user_id,
            ChallengesTasksSetStatuses.in_progress,
            ChallengesTasksSetStatuses.completed,
            ChallengesTasksSetStatuses.closed,
            ChallengeStatuses.expired,
            ChallengeStatuses.in_progress,
        )
        return await self.conn.fetch(query_2, user_id, ChallengeStatuses.pending)

    async def get_challenges(self):
        query = '''
        WITH challenges_difficulties AS (
            SELECT challenge_id,
                COALESCE(json_agg(
                    json_build_object(
                        'goal', goal,
                        'challenge_difficulty_id', challenge_difficulty_id,
                        'reward_exp', reward_exp,
                        'reward_try', reward_try,
                        'reward_throw', reward_throw
                    ) ORDER BY challenge_difficulty_id  
                ), '[]'::json) AS challenge_difficulties
            FROM challenges_rewards
            GROUP BY challenge_id
        )
        SELECT c.id, c.descr, cd.challenge_difficulties::jsonb
        FROM challenges c
        JOIN challenges_difficulties cd ON cd.challenge_id = c.id
        ORDER BY c.id
        '''
        return await self.conn.fetch(query)

    async def get_user_challenge_ids(self, user_id: int):
        """Получить список challenge_id для персональной выборки пользователя"""
        query = 'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1'
        rows = await self.conn.fetch(query, user_id)
        return [row['challenge_id'] for row in rows]

    async def set_select_task_set(self, user_id, filter_by_difficulty_id: int = None):
        """
        Создаёт draft набор заданий и генерирует персональную выборку челленджей.
        
        Args:
            user_id: ID пользователя
            filter_by_difficulty_id: Опциональный фильтр по сложности.
                - Если None (по умолчанию): выбираются челленджи с любыми наградами ``(ЗАБЫТЬ ПРО ЭТОТ ПАРАМЕТР В ПРОД-КОДЕ)``
                - Если указано (1, 2 или 3): выбираются только челленджи с наградами для этой сложности (Реализовано для тестов, чтобы бороться с рандомом)
        
        Returns:
            tuple: (task_set_id, accepted_challenges)
        """
        query_ins = '''
        INSERT INTO challenges_tasks_set (user_id, status) VALUES ($1, $2) 
        ON CONFLICT (user_id) WHERE status = ANY (ARRAY[$2, $3, $4]) DO NOTHING RETURNING id
        '''

        query_read_set = 'SELECT id FROM challenges_tasks_set WHERE user_id = $1 AND status = $2'
        query_read_meta = '''
        SELECT challenge_id, challenge_difficulty_id, slot FROM user_challenges WHERE task_set_id = $1
        '''

        query_reset_layout = 'DELETE FROM challenges_user_layout WHERE user_id = $1'
        query_generate_layout = '''
        -- Генерируем случайную выборку из 8 заданий с заданным распределением(4 - из 5 на 5, 2 - коллекции, и т.д.) по категориям
        WITH valid_challenges AS (
            -- Выбираем только челленджи с хотя бы одной наградой
            -- Опционально фильтруем по конкретной сложности (для тестов)
            SELECT DISTINCT c.id as challenge_id, c.category_id
            FROM challenges c
            INNER JOIN challenges_rewards cr ON cr.challenge_id = c.id
            WHERE ($6::int IS NULL OR cr.challenge_difficulty_id = $6)
        ),
        invite_friends AS (
            -- 1 из "Пригласи друга" (category_id = 2)
            SELECT challenge_id, 1 as priority
            FROM valid_challenges
            WHERE category_id = $2
            ORDER BY random()
            LIMIT 1
        ),
        collections AS (
            -- 2 из "Коллекции" (category_id = 1)
            SELECT challenge_id, 2 as priority
            FROM valid_challenges
            WHERE category_id = $1
            ORDER BY random()
            LIMIT 2
        ),
        throw_balls AS (
            -- 1 из "Кинь мячик" (category_id = 4)
            SELECT challenge_id, 3 as priority
            FROM valid_challenges
            WHERE category_id = $4
            ORDER BY random()
            LIMIT 1
        ),
        five_vs_five AS (
            -- 4 из "5 на 5" (category_id = 3)
            SELECT challenge_id, 4 as priority
            FROM valid_challenges
            WHERE category_id = $3
            ORDER BY random()
            LIMIT 4
        ),
        random_selection AS (
            SELECT * FROM invite_friends
            UNION ALL
            SELECT * FROM collections
            UNION ALL
            SELECT * FROM throw_balls
            UNION ALL
            SELECT * FROM five_vs_five
        )
        INSERT INTO challenges_user_layout (user_id, challenge_id)
        SELECT $5, challenge_id
        FROM random_selection
        ORDER BY priority, challenge_id
        '''

        task_set_id = await self.conn.fetchval(
            query_ins, user_id,
            ChallengesTasksSetStatuses.draft, ChallengesTasksSetStatuses.in_progress, ChallengesTasksSetStatuses.completed
        )
        if task_set_id:

            # Удаляем старую выборку челленджей
            await self.conn.execute(query_reset_layout, user_id)
            "Рекомендую перенести на питон: брать все челленджи и в коде формировать рандом выборку по категориям"
            await self.conn.execute(
                query_generate_layout,
                ChallengesCategories.collections,
                ChallengesCategories.invite_friends,
                ChallengesCategories.pvp_5v5,
                ChallengesCategories.throw_ball,
                user_id,
                filter_by_difficulty_id,  # Передаём опциональный фильтр
            )

            log_event(f'Сгенерировали персональную выборку челленджей для пользователя | user_id: \033[32m{user_id}\033[0m', level='WARNING')
            return task_set_id, []

        # 2 запроса, т.к. обязательно нужен task_set_id.
        # Если задачи не выбраны, то task_set_id тоже не будет
        task_set_id = await self.conn.fetchval(query_read_set, user_id, ChallengesTasksSetStatuses.draft)
        
        if not task_set_id:
            return None, []
            
        return task_set_id, await self.conn.fetch(query_read_meta, task_set_id)

    async def accept_challenge(self, task_set_id: int, challenge_id: int, challenge_difficulty_id: int):
        query = '''
        INSERT INTO user_challenges (task_set_id, challenge_id, challenge_difficulty_id, slot)
        SELECT $1, $2, $3, s.slot
        FROM generate_series(1, 4) AS s(slot)
        WHERE s.slot NOT IN ( 
            SELECT slot FROM user_challenges WHERE task_set_id = $1 AND status = $4
        )
        AND EXISTS (
            SELECT 1 FROM challenges_tasks_set 
            WHERE id = $1 AND status = $5 -- только для draft наборов
        )
        ORDER BY s.slot ASC LIMIT 1
        RETURNING slot
        '''
        try:
            slot = await self.conn.fetchval(
                query, 
                task_set_id, 
                challenge_id, 
                challenge_difficulty_id, 
                ChallengeStatuses.pending,
                ChallengesTasksSetStatuses.draft
            )
            if slot is None:
                # Все 4 слота заняты
                return False, None
            return True, slot

        except UniqueViolationError:
            return False, None
    async def decline_challenge(self, task_set_id: int, challenge_id: int, slot: int):
        """Строгая фильтрация гарантирует, что таску возможно удалить ТОЛЬКО на этапе формирования списка заданий"""
        query = '''
        DELETE FROM user_challenges
        WHERE task_set_id = $1 
          AND challenge_id = $2
          AND slot = $3
          AND status = $4
        RETURNING id
        '''
        return await self.conn.fetchval(query, task_set_id, challenge_id, slot, ChallengeStatuses.pending)

    async def activate_task_set_timer(self, task_set_id: int):
        query = '''
        WITH switch_task_set_timer AS (
            UPDATE challenges_tasks_set SET status = $2, started_at = now()
            WHERE id = $1
              AND status = $3 AND (SELECT COUNT(*) FROM user_challenges WHERE task_set_id = $1 AND status = $5) = 4 -- должно быть ровно 4 задания(лимит на выполнение)
            RETURNING id AS upd_task_set_id
        )
        UPDATE user_challenges SET status = $4
        FROM switch_task_set_timer
        WHERE user_challenges.task_set_id = switch_task_set_timer.upd_task_set_id AND status = $5
        RETURNING id
        '''
        return await self.conn.fetchval(
            query,
            task_set_id,
            ChallengesTasksSetStatuses.in_progress,
            ChallengesTasksSetStatuses.draft,
            ChallengeStatuses.in_progress,
            ChallengeStatuses.pending,
        )

    async def get_challenge_info(self, task_id: int):
        query = '''
        SELECT c.descr, us.challenge_id, us.challenge_difficulty_id, us.status, cr.reward_throw, cr.reward_exp, cr.reward_try, cr.goal, us.progress
        FROM user_challenges us
        JOIN challenges c ON us.challenge_id = c.id
        JOIN challenges_rewards cr ON cr.challenge_id = us.challenge_id AND cr.challenge_difficulty_id = us.challenge_difficulty_id
        WHERE us.id = $1
        '''
        return await self.conn.fetchrow(query, task_id)

    async def collect_rewards(self, task_set_id: int = None, task_id: int = None):
        """
        Если указан task_set_id, то task_id игнорируется
        """
        "Хоть какой-то из id должен быть"
        if not task_set_id and not task_id:
            return {}

        if task_set_id is not None:
            # сбор заданий одной кнопкой
            tasks_scope = 'task_set_id = $6'
            params = (task_set_id,)
        elif task_id is not None:
            # Ветка для точечного сбора наград по конкретному заданию
            "Выясняем task_set_id для автосмены статуса набора заданий"
            tasks_scope = 'id = $7'
            task_set_id = await self.conn.fetchval('SELECT task_set_id FROM user_challenges WHERE id = $1', task_id)
            params = (task_set_id, task_id)
            if not task_set_id:
                return None


        query = f'''
        WITH post_complete_tasks AS (
            UPDATE user_challenges SET status = $4 -- completed
            WHERE {tasks_scope} AND status = $3 -- reward_ready. Гарантирует начисление только один раз
            RETURNING id AS task_id, challenge_difficulty_id, task_set_id
        ),
        remaining_tasks AS (
            -- Подсчитываем несобранные задания, ИСКЛЮЧАЯ только что собранные
            SELECT COUNT(*) AS remaining_count
            FROM user_challenges uc
            WHERE uc.task_set_id = $6
            AND uc.status IN ($5, $3) -- in_progress или reward_ready
            AND uc.id NOT IN (SELECT task_id FROM post_complete_tasks) -- Исключаем собранные
        ),
        complete_task_set AS (
            UPDATE challenges_tasks_set 
            SET status = $1 -- completed
            WHERE id = $6
                AND status NOT IN ($1, $2) -- completed, closed
                -- Набор completed только если не осталось несобранных заданий
                AND (SELECT remaining_count FROM remaining_tasks) = 0
            RETURNING id
        )
        UPDATE users
        SET exp = MOD(users.exp + user_rewards.add_exp, 1000),
            throw_count = throw_count + user_rewards.add_throw,
            additional_try = additional_try + user_rewards.add_try   
        FROM (
            SELECT us.task_set_id AS cur_task_set_id,
                cts.user_id AS rewards_user_id, 
                SUM(cr.reward_exp) AS add_exp,
                SUM(cr.reward_try) AS add_try,
                SUM(cr.reward_throw) AS add_throw,
                (SELECT exp FROM users WHERE user_id = cts.user_id) AS old_exp  -- Сохраняем старое значение exp
            FROM user_challenges us
            JOIN post_complete_tasks pct ON us.id = pct.task_id
            JOIN challenges_tasks_set cts ON us.task_set_id = cts.id
            JOIN challenges_rewards cr ON cr.challenge_id = us.challenge_id AND us.challenge_difficulty_id = cr.challenge_difficulty_id
			GROUP BY cur_task_set_id, rewards_user_id
        ) AS user_rewards
        WHERE users.user_id = user_rewards.rewards_user_id
        RETURNING user_id, (user_rewards.old_exp + user_rewards.add_exp) AS credit_packs_in_exp -- Возвращаем сумму ДО применения MOD
        '''
        return await self.conn.fetchrow(
            query,
            ChallengesTasksSetStatuses.completed,
            ChallengesTasksSetStatuses.closed,
            ChallengeStatuses.reward_ready,
            ChallengeStatuses.completed,
            ChallengeStatuses.in_progress,
            *params
        )


    async def add_progress_by_action(self, challenge_id: int, user_id: int, add_progress: int):
        if add_progress <= 0:
            log_event(f'Попытка добавить некорректный прогресс | user_id: {user_id}, challenge_id: {challenge_id}, add_progress: {add_progress}', level='WARNING')
            return []
        
        query = '''
        UPDATE user_challenges AS uc
        SET 
            progress = LEAST(uc.progress + $3, cr.goal),
            status = CASE 
                WHEN (uc.progress + $3) >= cr.goal THEN $5::smallint 
                ELSE uc.status
            END
        FROM challenges_tasks_set cts, challenges_rewards cr
        WHERE uc.task_set_id = cts.id
            AND cr.challenge_id = uc.challenge_id 
            AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            AND uc.challenge_id = $1
            AND cts.user_id = $2
            AND uc.status = $4  -- Только задания в статусе in_progress
            AND cts.status = $6  -- Только из in_progress набора заданий
        RETURNING
            uc.id AS task_id,
            uc.challenge_id,
            uc.slot,
            uc.status
        '''
        return await self.conn.fetch(
            query, 
            challenge_id, 
            user_id, 
            add_progress, 
            ChallengeStatuses.in_progress, 
            ChallengeStatuses.reward_ready, 
            ChallengesTasksSetStatuses.in_progress
        )

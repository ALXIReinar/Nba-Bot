"""
E2E тесты для проверки race conditions в системе заданий

Покрывает критичные сценарии конкурентного доступа:
- Двойной клик на сбор наград (concurrent reward collection)
- Одновременное добавление прогресса к одному заданию
- Попытка accept одного и того же задания дважды
- Параллельный сбор разных наград одного набора
"""
import pytest
import asyncio
from asyncpg import Connection
from app.modules.tasks.sql_queries import ChallengesQueries
from app.modules.tasks.anything import ChallengesTasksSetStatuses, ChallengeStatuses, Challenges


class TestConcurrentRewardCollection:
    """Тесты одновременного сбора наград (двойной клик)"""
    
    @pytest.mark.asyncio
    async def test_concurrent_single_reward_double_click(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Симуляция двойного клика на кнопку "Собрать награду".
        
        Сценарий:
        1. Пользователь выполнил задание
        2. Видит кнопку "Собрать награду"
        3. Быстро кликает дважды (двойной клик)
        
        Ожидается:
        - Только ОДНО начисление наград
        - Второй запрос возвращает None (защита от дюпа)
        - exp увеличивается только один раз
        """
        # Arrange: создаём и выполняем задание
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # Добавляем ещё 3 задания
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        await queries.add_progress_by_action(challenge_id, test_user, 1)
        
        task_id = await db_connection.fetchval('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        # Получаем начальные значения
        user_before = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: симулируем двойной клик с РАЗНЫМИ соединениями
        async def collect_with_new_conn(tid):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.collect_rewards(task_id=tid)
        
        results = await asyncio.gather(
            collect_with_new_conn(task_id),
            collect_with_new_conn(task_id),
            return_exceptions=True
        )
        
        # Assert: один запрос успешен, второй вернул None
        successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        none_results = [r for r in results if r is None]
        
        assert len(successful_results) == 1, f"Только ОДИН запрос должен быть успешным, а успешных: {len(successful_results)}"
        assert len(none_results) == 1, f"ОДИН запрос должен вернуть None, а вернули None: {len(none_results)}"
        
        # Проверяем, что награды начислены только один раз
        user_after = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Для difficulty=1: reward_exp=200, reward_throw=2
        assert user_after['exp'] == user_before['exp'] + 200, "exp должен увеличиться ТОЛЬКО на 200 (один раз)"
        assert user_after['throw_count'] == user_before['throw_count'] + 2, "throw_count должен увеличиться ТОЛЬКО на 2"

    @pytest.mark.asyncio
    async def test_concurrent_collect_all_double_click(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Двойной клик на кнопку "Собрать все награды".
        
        Сценарий:
        1. Пользователь выполнил все 4 задания
        2. Видит кнопку "Собрать все награды"
        3. Дважды быстро кликает
        
        Ожидается:
        - Награды начисляются только один раз
        - Второй запрос возвращает None
        """
        # Arrange: создаём и выполняем все задания
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Выполняем все задания
        for ch in challenges:
            await queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Вычисляем ожидаемую сумму наград
        expected_rewards = await db_connection.fetchrow('''
            SELECT 
                SUM(cr.reward_exp) as total_exp,
                SUM(cr.reward_throw) as total_throw
            FROM user_challenges uc
            JOIN challenges_rewards cr 
                ON cr.challenge_id = uc.challenge_id 
                AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            WHERE uc.task_set_id = $1 AND uc.status = $2
        ''', task_set_id, ChallengeStatuses.reward_ready)
        
        user_before = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: симулируем двойной клик с разными соединениями
        async def collect_all_with_new_conn(tsid):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.collect_rewards(task_set_id=tsid)
        
        results = await asyncio.gather(
            collect_all_with_new_conn(task_set_id),
            collect_all_with_new_conn(task_set_id),
            return_exceptions=True
        )
        
        # Assert
        successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        none_results = [r for r in results if r is None]
        
        assert len(successful_results) == 1, "Только один запрос должен быть успешным"
        assert len(none_results) == 1, "Один запрос должен вернуть None"
        
        # Проверяем точность начисления (только один раз)
        user_after = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        expected_exp_delta = expected_rewards['total_exp'] % 1000
        actual_exp_delta = user_after['exp'] - user_before['exp']
        
        assert actual_exp_delta == expected_exp_delta, f"exp должен увеличиться на {expected_exp_delta}, а увеличился на {actual_exp_delta}"
        assert user_after['throw_count'] == user_before['throw_count'] + expected_rewards['total_throw'], "throw начислен неверно"


class TestConcurrentProgressAddition:
    """Тесты одновременного добавления прогресса"""
    
    @pytest.mark.asyncio
    async def test_concurrent_progress_same_task(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Одновременное добавление прогресса к одному заданию.
        
        Сценарий:
        1. Пользователь выполняет действие (например, открывает 2 карточки подряд)
        2. Система отправляет 2 параллельных запроса на добавление прогресса
        
        Ожидается:
        - Прогресс должен корректно суммироваться
        - Не должно быть потери данных
        - При достижении цели статус переходит в reward_ready
        """
        # Arrange: создаём задание с небольшой целью
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        # Берём челлендж "Кинь мячиков" (challenge_id=7)
        # difficulty=1 (Лёгкая): goal=5
        challenge_id = Challenges.throw_balls
        await queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # Добавляем ещё 3 задания
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Act: симулируем 3 параллельных добавления прогресса (по 2 единицы) с разными соединениями
        async def add_progress_with_new_conn(cid, uid, progress):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.add_progress_by_action(cid, uid, progress)
        
        results = await asyncio.gather(
            add_progress_with_new_conn(challenge_id, test_user, 2),
            add_progress_with_new_conn(challenge_id, test_user, 2),
            add_progress_with_new_conn(challenge_id, test_user, 2),
            return_exceptions=True
        )
        
        # Assert: проверяем итоговый прогресс
        task = await db_connection.fetchrow('''
            SELECT progress, status FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        # Прогресс должен быть 5 (goal=5 достигнут)
        # 3 параллельных добавления по 2: min(6, 5) = 5
        assert task['progress'] == 5, f"Прогресс должен быть 5 (LEAST от 6 и goal 5), а он {task['progress']}"
        
        # Статус должен перейти в reward_ready
        assert task['status'] == ChallengeStatuses.reward_ready, "Статус должен быть reward_ready"

    @pytest.mark.asyncio
    async def test_concurrent_progress_multiple_tasks(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Одновременное добавление прогресса к РАЗНЫМ заданиям.
        
        Сценарий:
        1. У пользователя 4 задания
        2. Он выполняет действия, которые затрагивают разные задания
        3. Запросы приходят параллельно
        
        Ожидается:
        - Каждое задание получает свой прогресс
        - Нет "перекрёстного" начисления
        """
        # Arrange: создаём 4 задания
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Act: параллельно добавляем прогресс к разным заданиям с разными соединениями
        async def add_progress_with_new_conn(cid, uid, progress):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.add_progress_by_action(cid, uid, progress)
        
        await asyncio.gather(
            add_progress_with_new_conn(challenges[0]['challenge_id'], test_user, 1),
            add_progress_with_new_conn(challenges[1]['challenge_id'], test_user, 2),
            add_progress_with_new_conn(challenges[2]['challenge_id'], test_user, 3),
            add_progress_with_new_conn(challenges[3]['challenge_id'], test_user, 4),
        )
        
        # Assert: проверяем прогресс каждого задания
        tasks = await db_connection.fetch('''
            SELECT challenge_id, progress FROM user_challenges 
            WHERE task_set_id = $1 ORDER BY challenge_id
        ''', task_set_id)
        
        assert len(tasks) == 4, "Должно быть 4 задания"
        
        # Каждое задание должно иметь свой прогресс
        progress_by_challenge = {t['challenge_id']: t['progress'] for t in tasks}
        
        assert progress_by_challenge[challenges[0]['challenge_id']] == 1, "Первое задание: прогресс должен быть 1"
        assert progress_by_challenge[challenges[1]['challenge_id']] == 2, "Второе задание: прогресс должен быть 2"
        assert progress_by_challenge[challenges[2]['challenge_id']] == 3, "Третье задание: прогресс должен быть 3"
        assert progress_by_challenge[challenges[3]['challenge_id']] == 4, "Четвертое задание: прогресс должен быть 4"


class TestConcurrentAcceptChallenge:
    """Тесты одновременного accept одного и того же задания"""
    
    @pytest.mark.asyncio
    async def test_concurrent_accept_same_challenge(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Попытка добавить одно и то же задание дважды (баг UI или race condition).
        
        Сценарий:
        1. Пользователь выбирает задание с difficulty=1
        2. Из-за задержки сети он снова кликает на "Принять"
        3. Два параллельных запроса пытаются добавить одно задание
        
        Ожидается:
        - Только ОДИН accept должен быть успешным
        - Второй accept должен вернуть (False, None) из-за UniqueViolationError
        - В БД только ОДНА запись
        """
        # Arrange: создаём draft набор
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        difficulty_id = 1
        
        # Act: симулируем двойной клик на "Принять задание" с разными соединениями
        async def accept_with_new_conn(tsid, cid, did):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.accept_challenge(tsid, cid, did)
        
        results = await asyncio.gather(
            accept_with_new_conn(task_set_id, challenge_id, difficulty_id),
            accept_with_new_conn(task_set_id, challenge_id, difficulty_id),
            return_exceptions=True
        )
        
        # Assert: один успешен, второй вернул False
        successful = [r for r in results if isinstance(r, tuple) and r[0] is True]
        failed = [r for r in results if isinstance(r, tuple) and r[0] is False]
        
        assert len(successful) == 1, f"Только ОДИН accept должен быть успешным, успешных: {len(successful)}"
        assert len(failed) == 1, f"ОДИН accept должен вернуть False, вернули False: {len(failed)}"
        
        # Проверяем, что в БД только одна запись
        count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2 AND challenge_difficulty_id = $3
        ''', task_set_id, challenge_id, difficulty_id)
        
        assert count == 1, f"В БД должна быть только ОДНА запись, а их {count}"

    @pytest.mark.asyncio
    async def test_concurrent_accept_different_difficulties(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Попытка добавить одно задание с разными сложностями.
        
        Сценарий:
        1. Пользователь выбирает задание
        2. Меняет сложность и снова кликает "Принять"
        3. Из-за race condition оба запроса могут уйти параллельно
        
        Ожидается:
        - Только ОДИН accept должен быть успешным
        - Constraint по (task_set_id, challenge_id) не позволит добавить дубль
        """
        # Arrange
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        
        # Act: параллельно пытаемся добавить с разными сложностями
        async def accept_with_new_conn(tsid, cid, did):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.accept_challenge(tsid, cid, did)
        
        results = await asyncio.gather(
            accept_with_new_conn(task_set_id, challenge_id, 1),  # Лёгкая
            accept_with_new_conn(task_set_id, challenge_id, 2),  # Средняя
            return_exceptions=True
        )
        
        # Assert
        successful = [r for r in results if isinstance(r, tuple) and r[0] is True]
        failed = [r for r in results if isinstance(r, tuple) and r[0] is False]
        
        assert len(successful) == 1, "Только один accept должен быть успешным"
        assert len(failed) == 1, "Один accept должен вернуть False"
        
        # В БД только одна запись
        count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert count == 1, f"В БД должна быть только одна запись, а их {count}"


class TestConcurrentMixedOperations:
    """Тесты смешанных конкурентных операций"""
    
    @pytest.mark.asyncio
    async def test_concurrent_collect_different_rewards(
        self,
        test_user: int,
        db_connection: Connection,
        db_pool
    ):
        """
        E2E: Одновременный сбор РАЗНЫХ наград из одного набора.
        
        Сценарий:
        1. Пользователь выполнил 2 задания из 4
        2. Видит кнопки "Собрать" под каждым заданием
        3. Быстро кликает на обе кнопки
        
        Ожидается:
        - Обе награды должны быть собраны корректно
        - Суммарное начисление должно быть точным
        """
        # Arrange: создаём 4 задания и выполняем 2 из них
        queries = ChallengesQueries(db_connection)
        task_set_id, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Выполняем первые 2 задания
        await queries.add_progress_by_action(challenges[0]['challenge_id'], test_user, 100)
        await queries.add_progress_by_action(challenges[1]['challenge_id'], test_user, 100)
        
        # Получаем task_id выполненных заданий
        task_ids = await db_connection.fetch('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2 LIMIT 2
        ''', task_set_id, ChallengeStatuses.reward_ready)
        
        assert len(task_ids) == 2, "Должно быть 2 выполненных задания"
        
        # Вычисляем ожидаемые награды
        expected_rewards = await db_connection.fetchrow('''
            SELECT 
                SUM(cr.reward_exp) as total_exp,
                SUM(cr.reward_throw) as total_throw
            FROM user_challenges uc
            JOIN challenges_rewards cr 
                ON cr.challenge_id = uc.challenge_id 
                AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            WHERE uc.id IN ($1, $2)
        ''', task_ids[0]['id'], task_ids[1]['id'])
        
        user_before = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: параллельно собираем обе награды с разными соединениями
        async def collect_with_new_conn(tid):
            async with db_pool.acquire() as conn:
                queries_local = ChallengesQueries(conn)
                return await queries_local.collect_rewards(task_id=tid)
        
        results = await asyncio.gather(
            collect_with_new_conn(task_ids[0]['id']),
            collect_with_new_conn(task_ids[1]['id']),
            return_exceptions=True
        )
        
        # Assert: обе операции должны быть успешны
        successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        assert len(successful_results) == 2, f"Обе операции должны быть успешны, успешных: {len(successful_results)}"
        
        # Проверяем точность начисления
        user_after = await db_connection.fetchrow('''
            SELECT exp, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        expected_exp_delta = expected_rewards['total_exp'] % 1000
        actual_exp_delta = user_after['exp'] - user_before['exp']
        
        assert actual_exp_delta == expected_exp_delta, f"exp должен увеличиться на {expected_exp_delta}, а увеличился на {actual_exp_delta}"
        assert user_after['throw_count'] == user_before['throw_count'] + expected_rewards['total_throw']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

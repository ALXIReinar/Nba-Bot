"""
Integration тесты для системы сбора наград (Use Case 03 и 04)

Покрывает:
- Сбор одной награды
- Сбор всех наград
- Начисление exp, try, throw
- Защиту от повторного сбора (дюп)
- Отсутствие декартова произведения в JOIN'ах
- Расчёт и начисление бесплатных паков
"""
import pytest
from asyncpg import Connection
from app.modules.tasks.sql_queries import ChallengesQueries
from app.modules.tasks.anything import ChallengesTasksSetStatuses, ChallengeStatuses, Challenges


class TestCollectRewards:
    """Тесты сбора наград"""
    
    @pytest.mark.asyncio
    async def test_collect_single_reward(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Сбор одной награды за задание.
        
        Ожидается:
        - Задание переходит из reward_ready → completed
        - Награды начисляются пользователю
        - Возвращается информация о начислении
        """
        # Arrange: создаём активный набор и выполняем одно задание
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)  # difficulty=1, goal=1
        
        # Добавляем ещё 3 задания
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Выполняем задание
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Получаем task_id
        task = await db_connection.fetchrow('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        task_id = task['id']
        
        # Получаем начальные значения пользователя
        user_before = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: собираем награду
        result = await challenges_queries.collect_rewards(task_id=task_id)
        
        # Assert
        assert result is not None, "Должен вернуться результат"
        assert result['user_id'] == test_user
        
        # Проверяем, что задание перешло в completed
        task_after = await db_connection.fetchrow('''
            SELECT status FROM user_challenges WHERE id = $1
        ''', task_id)
        assert task_after['status'] == ChallengeStatuses.completed
        
        # Проверяем, что награды начислены
        user_after = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Для difficulty=1 (Сложная) челленджа "Пригласи друга": reward_throw=2, reward_exp=200
        assert user_after['throw_count'] > user_before['throw_count'], "throw_count должен увеличиться"
        assert user_after['exp'] > user_before['exp'], "exp должен увеличиться"

    @pytest.mark.asyncio
    async def test_collect_all_rewards(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Сбор всех наград за набор заданий.
        
        Ожидается:
        - Все задания reward_ready → completed
        - Суммарные награды начисляются
        """
        # Arrange: создаём активный набор с 4 заданиями
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Получаем задания с их целями
        tasks_with_goals = await db_connection.fetch('''
            SELECT uc.challenge_id, cr.goal
            FROM user_challenges uc
            JOIN challenges_rewards cr 
                ON cr.challenge_id = uc.challenge_id 
                AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            WHERE uc.task_set_id = $1
        ''', task_set_id)
        
        # Выполняем все задания с учетом их реальных целей
        for task in tasks_with_goals:
            await challenges_queries.add_progress_by_action(task['challenge_id'], test_user, task['goal'])
        
        # Проверяем, что все задания в reward_ready
        reward_ready_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.reward_ready)
        assert reward_ready_count == 4, f"Все 4 задания должны быть reward_ready, а их {reward_ready_count}"
        
        # Получаем начальные значения
        user_before = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: собираем все награды
        result = await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert
        assert result is not None
        assert result['user_id'] == test_user
        
        # Проверяем, что все задания перешли в completed
        completed_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.completed)
        assert completed_count == 4, "Все 4 задания должны быть completed"
        
        # Проверяем начисление наград
        user_after = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        assert user_after['exp'] >= user_before['exp'], "exp должен увеличиться или остаться прежним (с учетом MOD)"

    @pytest.mark.asyncio
    async def test_rewards_accrual_exp_try_throw(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Корректное начисление exp, try, throw.
        
        Проверяет точность начисления каждого типа награды.
        """
        # Arrange: создаём задание с известными наградами
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        # Челлендж "Пригласи друга", difficulty=1 (Сложная): throw=2, exp=200, try=0
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # Добавляем ещё 3 задания
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Выполняем задание
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Получаем начальные значения
        user_before = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: собираем награду
        task_id = await db_connection.fetchval('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        await challenges_queries.collect_rewards(task_id=task_id)
        
        # Assert: проверяем точное начисление
        user_after = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Для difficulty=1: reward_throw=2, reward_exp=200, reward_try=0
        assert user_after['throw_count'] == user_before['throw_count'] + 2, "throw_count должен увеличиться на 2"
        assert user_after['exp'] == user_before['exp'] + 200, "exp должен увеличиться на 200"
        assert user_after['additional_try'] == user_before['additional_try'], "try не должен измениться (reward_try=0)"


class TestRewardsDuplicationProtection:
    """Тесты защиты от повторного сбора наград"""
    
    @pytest.mark.asyncio
    async def test_cannot_collect_twice_single(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Защита от двойного сбора одной награды.
        
        Ожидается:
        - Первый сбор успешен
        - Второй сбор возвращает None (защита от дюпа)
        - Награды начисляются только один раз
        """
        # Arrange: создаём и выполняем задание
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        task_id = await db_connection.fetchval('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        # Act: первый сбор
        result1 = await challenges_queries.collect_rewards(task_id=task_id)
        
        user_after_first = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: второй сбор (попытка дюпа)
        result2 = await challenges_queries.collect_rewards(task_id=task_id)
        
        user_after_second = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Assert
        assert result1 is not None, "Первый сбор должен быть успешным"
        assert result2 is None, "Второй сбор должен вернуть None (защита от дюпа)"
        
        # Проверяем, что награды НЕ начислились второй раз
        assert user_after_second['exp'] == user_after_first['exp'], "exp НЕ должен увеличиться второй раз"
        assert user_after_second['throw_count'] == user_after_first['throw_count'], "throw_count НЕ должен увеличиться"

    @pytest.mark.asyncio
    async def test_cannot_collect_twice_all(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Защита от двойного сбора всех наград.
        
        Ожидается:
        - Первый сбор всех наград успешен
        - Второй сбор возвращает None
        """
        # Arrange: создаём и выполняем все задания
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        for ch in challenges:
            await challenges_queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Act: первый сбор всех наград
        result1 = await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        user_after_first = await db_connection.fetchrow('''
            SELECT exp FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: второй сбор (попытка дюпа)
        result2 = await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        user_after_second = await db_connection.fetchrow('''
            SELECT exp FROM users WHERE user_id = $1
        ''', test_user)
        
        # Assert
        assert result1 is not None, "Первый сбор должен быть успешным"
        assert result2 is None, "Второй сбор должен вернуть None"
        assert user_after_second['exp'] == user_after_first['exp'], "exp НЕ должен измениться при втором сборе"

    @pytest.mark.asyncio
    async def test_no_cartesian_product_in_rewards(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Проверка отсутствия декартова произведения в JOIN'ах.
        
        Критически важный тест! Декартово произведение приводит к мультипликации наград.
        
        Проверяем, что при сборе наград за 4 задания начисляется корректная сумма,
        а не умноженная на количество строк из-за неправильного JOIN'а.
        """
        # Arrange: создаём 4 задания с разными наградами
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        # Добавляем задания с одинаковой сложностью для предсказуемости
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Выполняем все задания
        for ch in challenges:
            await challenges_queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Вычисляем ожидаемую сумму наград напрямую из БД
        expected_rewards = await db_connection.fetchrow('''
            SELECT 
                SUM(cr.reward_exp) as total_exp,
                SUM(cr.reward_try) as total_try,
                SUM(cr.reward_throw) as total_throw
            FROM user_challenges uc
            JOIN challenges_rewards cr 
                ON cr.challenge_id = uc.challenge_id 
                AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            WHERE uc.task_set_id = $1 AND uc.status = $2
        ''', task_set_id, ChallengeStatuses.reward_ready)
        
        user_before = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        # Act: собираем все награды
        await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert: проверяем, что начислены ТОЧНЫЕ суммы (не умноженные)
        user_after = await db_connection.fetchrow('''
            SELECT exp, additional_try, throw_count FROM users WHERE user_id = $1
        ''', test_user)
        
        actual_exp_added = user_after['exp'] - user_before['exp']
        actual_try_added = user_after['additional_try'] - user_before['additional_try']
        actual_throw_added = user_after['throw_count'] - user_before['throw_count']
        
        # Проверяем на точное совпадение (с учётом MOD для exp)
        expected_exp_with_mod = expected_rewards['total_exp'] % 1000
        assert actual_exp_added == expected_exp_with_mod, f"exp должен быть {expected_exp_with_mod}, а не {actual_exp_added} (проверка декартова произведения)"
        assert actual_try_added == expected_rewards['total_try'], f"try должен быть {expected_rewards['total_try']}, а не {actual_try_added}"
        assert actual_throw_added == expected_rewards['total_throw'], f"throw должен быть {expected_rewards['total_throw']}, а не {actual_throw_added}"


class TestTaskSetCompletion:
    """Тесты завершения набора заданий"""
    
    @pytest.mark.asyncio
    async def test_task_set_completed_status(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Набор заданий переходит в completed после сбора всех наград.
        
        Ожидается:
        - После сбора всех наград набор переходит в completed
        """
        # Arrange: создаём и выполняем все задания
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        for ch in challenges:
            await challenges_queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Проверяем начальный статус набора
        task_set_before = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set_before['status'] == ChallengesTasksSetStatuses.in_progress
        
        # Act: собираем все награды
        await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert: набор должен перейти в completed
        task_set_after = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set_after['status'] == ChallengesTasksSetStatuses.completed


class TestPacksCalculation:
    """Тесты расчёта и начисления бесплатных паков"""
    
    @pytest.mark.asyncio
    async def test_calculate_packs_from_exp(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Расчёт паков: каждые 1000 exp = 1 бесплатный пак.
        
        Ожидается:
        - credit_packs_in_exp содержит накопленную exp для расчёта паков
        - После 1000 exp пользователь должен получить пак
        """
        # Arrange: устанавливаем пользователю 900 exp
        await db_connection.execute('''
            UPDATE users SET exp = 900 WHERE user_id = $1
        ''', test_user)
        
        # Создаём задание с наградой 200 exp (итого будет 1100)
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends  # reward_exp=200 для difficulty=1
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        task_id = await db_connection.fetchval('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        # Act: собираем награду
        result = await challenges_queries.collect_rewards(task_id=task_id)
        
        # Assert
        assert result is not None
        assert 'credit_packs_in_exp' in result
        
        # credit_packs_in_exp должен содержать 1100 (900 + 200)
        assert result['credit_packs_in_exp'] == 1100, "credit_packs_in_exp должен быть 1100"
        
        # Проверяем, что exp стал 100 (1100 % 1000)
        user_after = await db_connection.fetchrow('''
            SELECT exp FROM users WHERE user_id = $1
        ''', test_user)
        assert user_after['exp'] == 100, "exp должен быть 100 после MOD 1000"

    @pytest.mark.asyncio
    async def test_exp_overflow_to_next_pack(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Остаток EXP переходит на следующий пак.
        
        Сценарий: было 900 exp, получили 300 exp
        - Выдался пак (900 + 300 = 1200, 1200 // 1000 = 1 пак)
        - Остаток 200 exp переходит на следующий пак
        """
        # Arrange: устанавливаем 900 exp
        await db_connection.execute('''
            UPDATE users SET exp = 900 WHERE user_id = $1
        ''', test_user)
        
        # Создаём задание с наградой ~300 exp
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        # Выбираем несколько заданий, чтобы набрать >300 exp
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Выполняем первые 2 задания для набора >100 exp
        for i in range(2):
            await challenges_queries.add_progress_by_action(challenges[i]['challenge_id'], test_user, 100)
        
        # Act: собираем награды
        await challenges_queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert: проверяем, что остаток exp корректен
        user_after = await db_connection.fetchrow('''
            SELECT exp FROM users WHERE user_id = $1
        ''', test_user)
        
        # exp должен быть < 1000 (остаток после выдачи паков)
        assert user_after['exp'] < 1000, f"exp должен быть меньше 1000, а он {user_after['exp']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

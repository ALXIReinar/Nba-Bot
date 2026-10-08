"""
E2E тесты полного жизненного цикла системы заданий

Покрывает сквозные сценарии работы пользователя:
- Полный цикл: выбор → выполнение → сбор наград → получение паков
- Множественные циклы заданий
- Частичное выполнение с истечением срока
- Интеграция с системой exp и паков
"""
import pytest
from datetime import datetime, timedelta
from asyncpg import Connection
from app.modules.tasks.sql_queries import ChallengesQueries
from app.modules.tasks.anything import (
    ChallengesTasksSetStatuses, 
    ChallengeStatuses, 
    Challenges,
    calculate_and_give_task_packs
)


class TestCompleteUserJourney:
    """Тесты полного пользовательского пути"""
    
    @pytest.mark.asyncio
    async def test_complete_user_journey_happy_path(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Полный успешный путь пользователя от выбора до получения паков.
        
        Шаги:
        1. Пользователь заходит в раздел "Задания"
        2. Генерируется персональная выборка из 8 челленджей
        3. Выбирает 4 задания (принимает их)
        4. Активирует таймер на 7 дней
        5. Постепенно выполняет все задания
        6. Собирает все награды
        7. Получает бесплатные паки за накопленный exp
        
        Проверяем:
        - Корректность всех переходов между статусами
        - Точность начисления наград
        - Расчёт и начисление паков
        """
        queries = ChallengesQueries(db_connection)
        
        # Шаг 1-2: Заходим в задания, генерируется выборка
        # Используем filter_by_difficulty_id=1 для гарантированной выборки челленджей с наградами для difficulty=1
        task_set_id, meta = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        assert task_set_id is not None, "Должен создаться draft набор"
        assert meta == [], "Изначально задания не выбраны"
        
        # Проверяем, что создалась персональная выборка из 8 челленджей
        user_layout = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1
        ''', test_user)
        assert len(user_layout) == 8, "Должна быть выборка из 8 челленджей"
        
        # Шаг 3: Выбираем 4 задания
        selected_challenges = user_layout[:4]
        for ch in selected_challenges:
            success, slot = await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
            assert success is True, f"Accept должен быть успешным для challenge_id={ch['challenge_id']}"
        
        # Проверяем статус заданий
        accepted_tasks = await db_connection.fetch('''
            SELECT id, status, slot FROM user_challenges 
            WHERE task_set_id = $1 ORDER BY slot
        ''', task_set_id)
        assert len(accepted_tasks) == 4, "Должно быть 4 выбранных задания"
        assert all(t['status'] == ChallengeStatuses.pending for t in accepted_tasks), "Все задания должны быть pending"
        
        # Шаг 4: Активируем таймер
        result = await queries.activate_task_set_timer(task_set_id)
        assert result is not None, "Таймер должен активироваться"
        
        # Проверяем статусы после активации
        task_set = await db_connection.fetchrow('''
            SELECT status, started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set['status'] == ChallengesTasksSetStatuses.in_progress, "Набор должен быть in_progress"
        assert task_set['started_at'] is not None, "Должна быть установлена дата старта"
        
        tasks_after_activation = await db_connection.fetch('''
            SELECT status FROM user_challenges WHERE task_set_id = $1
        ''', task_set_id)
        assert all(t['status'] == ChallengeStatuses.in_progress for t in tasks_after_activation), "Все задания должны быть in_progress"
        
        # Шаг 5: Постепенно выполняем все задания
        for task in accepted_tasks:
            challenge_id = await db_connection.fetchval('''
                SELECT challenge_id FROM user_challenges WHERE id = $1
            ''', task['id'])
            
            # Добавляем большой прогресс (100) для гарантированного выполнения
            affected = await queries.add_progress_by_action(challenge_id, test_user, 100)
            assert len(affected) > 0, f"Прогресс должен быть добавлен для task_id={task['id']}"
        
        # Проверяем, что все задания перешли в reward_ready
        reward_ready_tasks = await db_connection.fetch('''
            SELECT id FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.reward_ready)
        assert len(reward_ready_tasks) == 4, "Все 4 задания должны быть reward_ready"
        
        # Шаг 6: Собираем все награды
        user_before = await db_connection.fetchrow('''
            SELECT exp, throw_count, additional_try FROM users WHERE user_id = $1
        ''', test_user)
        
        result = await queries.collect_rewards(task_set_id=task_set_id)
        assert result is not None, "Сбор наград должен быть успешным"
        assert 'credit_packs_in_exp' in result, "Должен вернуться credit_packs_in_exp"
        
        # Проверяем начисление наград
        user_after = await db_connection.fetchrow('''
            SELECT exp, throw_count, additional_try FROM users WHERE user_id = $1
        ''', test_user)
        
        assert user_after['exp'] >= 0, "exp должен быть корректным (с учётом MOD 1000)"
        assert user_after['throw_count'] > user_before['throw_count'], "throw_count должен увеличиться"
        
        # Проверяем, что набор перешёл в completed
        final_task_set = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert final_task_set['status'] == ChallengesTasksSetStatuses.completed, "Набор должен быть completed"
        
        # Шаг 7: Проверяем расчёт паков
        packs_to_give = result['credit_packs_in_exp'] // 1000
        assert packs_to_give >= 0, "Количество паков должно быть неотрицательным"
        
        # Если набрали хотя бы 1000 exp, должен выдаться хотя бы 1 пак
        if result['credit_packs_in_exp'] >= 1000:
            assert packs_to_give >= 1, f"При {result['credit_packs_in_exp']} exp должен выдаться хотя бы 1 пак"

    @pytest.mark.asyncio
    async def test_partial_completion_journey(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Частичное выполнение заданий - пользователь выполнил не все.
        
        Сценарий:
        1. Пользователь выбрал 4 задания
        2. Активировал таймер
        3. Выполнил только 2 из 4 заданий
        4. Собрал награды за выполненные
        5. Набор остаётся in_progress (не переходит в completed)
        """
        queries = ChallengesQueries(db_connection)
        
        # Arrange: выбираем и активируем задания
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Act: выполняем только первые 2 задания
        await queries.add_progress_by_action(challenges[0]['challenge_id'], test_user, 100)
        await queries.add_progress_by_action(challenges[1]['challenge_id'], test_user, 100)
        
        # Собираем награды за эти 2 задания
        result = await queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert: набор НЕ должен перейти в completed
        task_set = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set['status'] == ChallengesTasksSetStatuses.in_progress, "Набор должен остаться in_progress"
        
        # Проверяем статусы заданий
        completed_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.completed)
        
        in_progress_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.in_progress)
        
        assert completed_count == 2, "Должно быть 2 completed задания"
        assert in_progress_count == 2, "Должно быть 2 in_progress задания"


class TestMultipleCycles:
    """Тесты множественных циклов заданий"""
    
    @pytest.mark.asyncio
    async def test_multiple_task_cycles(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Пользователь проходит несколько полных циклов заданий.
        
        Сценарий:
        1. Первый цикл: выбор → выполнение → сбор наград
        2. Второй цикл: новый выбор → выполнение → сбор наград
        
        Проверяем:
        - Корректное закрытие предыдущего цикла
        - Создание нового draft набора после завершения
        - Генерация новой персональной выборки
        """
        queries = ChallengesQueries(db_connection)
        
        # ===== ЦИКЛ 1 =====
        task_set_id_1, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges_1 = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges_1:
            await queries.accept_challenge(task_set_id_1, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id_1)
        
        # Выполняем все задания
        for ch in challenges_1:
            await queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Собираем награды
        await queries.collect_rewards(task_set_id=task_set_id_1)
        
        # Проверяем, что первый набор completed
        task_set_1_status = await db_connection.fetchval('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id_1)
        assert task_set_1_status == ChallengesTasksSetStatuses.completed, "Первый набор должен быть completed"
        
        # ===== ЦИКЛ 2 =====
        # Попытка создать новый набор ДОЛЖНА ПРОВАЛИТЬСЯ (completed набор блокирует)
        task_set_id_attempt, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        assert task_set_id_attempt is None, "Не должен создаться новый набор, пока completed набор не истёк"
        
        # Симулируем истечение 7 дней - сдвигаем started_at на 8 дней назад
        await db_connection.execute('''
            UPDATE challenges_tasks_set
            SET started_at = now() - interval '8 days'
            WHERE id = $1
        ''', task_set_id_1)
        
        # Вызываем show_user_tasks, чтобы закрыть просроченный набор
        await queries.show_user_tasks(test_user)
        
        # Проверяем, что первый набор перешёл в closed
        task_set_1_status_after = await db_connection.fetchval('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id_1)
        assert task_set_1_status_after == ChallengesTasksSetStatuses.closed, "Набор должен стать closed после истечения срока"
        
        # Теперь создаём новый набор
        task_set_id_2, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        # Проверяем, что создался НОВЫЙ набор (не тот же самый)
        assert task_set_id_2 != task_set_id_1, "Должен создаться новый набор заданий"
        
        # Проверяем, что сгенерировалась НОВАЯ персональная выборка
        challenges_2 = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 ORDER BY challenge_id
        ''', test_user)
        
        assert len(challenges_2) == 8, "Должна быть новая выборка из 8 челленджей"
        
        # Выбираем задания для второго цикла
        for ch in challenges_2[:4]:
            await queries.accept_challenge(task_set_id_2, ch['challenge_id'], 1)
        
        # Проверяем, что задания относятся ко второму набору
        second_cycle_tasks = await db_connection.fetch('''
            SELECT task_set_id FROM user_challenges WHERE task_set_id = $1
        ''', task_set_id_2)
        assert len(second_cycle_tasks) == 4, "Во втором цикле должно быть 4 задания"
        assert all(t['task_set_id'] == task_set_id_2 for t in second_cycle_tasks), "Все задания должны относиться ко второму набору"


class TestTaskExpiration:
    """Тесты истечения срока заданий"""
    
    @pytest.mark.asyncio
    async def test_task_set_expiration_after_7_days(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Истечение срока выполнения заданий через 7 дней.
        
        Сценарий:
        1. Пользователь активировал задания
        2. Прошло 7 дней
        3. Пользователь заходит в раздел "Задания"
        4. Система закрывает просроченный набор
        5. Невыполненные задания переходят в expired
        
        Проверяем:
        - Автоматическое закрытие при вызове show_user_tasks
        - Корректные переходы статусов
        """
        queries = ChallengesQueries(db_connection)
        
        # Arrange: создаём и активируем задания
        task_set_id, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Выполняем только 2 задания
        await queries.add_progress_by_action(challenges[0]['challenge_id'], test_user, 100)
        await queries.add_progress_by_action(challenges[1]['challenge_id'], test_user, 100)
        
        # Собираем награды за выполненные
        await queries.collect_rewards(task_set_id=task_set_id)
        
        # Act: симулируем истечение 7 дней - сдвигаем started_at на 8 дней назад
        await db_connection.execute('''
            UPDATE challenges_tasks_set 
            SET started_at = now() - interval '8 days'
            WHERE id = $1
        ''', task_set_id)
        
        # Пользователь заходит в раздел заданий (вызывается show_user_tasks)
        tasks = await queries.show_user_tasks(test_user)
        
        # Assert: набор должен закрыться
        task_set_status = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set_status['status'] == ChallengesTasksSetStatuses.closed, "Набор должен быть closed"
        
        # Проверяем статусы заданий
        expired_tasks = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.expired)
        
        completed_tasks = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.completed)
        
        # 2 задания были собраны (completed), 2 просрочены (expired)
        assert completed_tasks == 2, "Должно быть 2 completed задания"
        assert expired_tasks == 2, "Должно быть 2 expired задания"

    @pytest.mark.asyncio
    async def test_completed_set_not_expired(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Полностью выполненный набор закрывается после 7 дней.
        
        Сценарий:
        1. Пользователь выполнил все 4 задания и собрал награды
        2. Набор перешёл в completed
        3. Прошло 7 дней
        4. Пользователь заходит в задания
        
        Ожидается:
        - Набор переходит из completed в closed (архивируется)
        """
        queries = ChallengesQueries(db_connection)
        
        # Arrange: выполняем все задания
        task_set_id, _ = await queries.set_select_task_set(test_user, filter_by_difficulty_id=1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Выполняем ВСЕ задания
        for ch in challenges:
            await queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Собираем все награды
        await queries.collect_rewards(task_set_id=task_set_id)
        
        # Проверяем, что набор completed
        task_set_before = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set_before['status'] == ChallengesTasksSetStatuses.completed
        
        # Act: симулируем истечение срока
        await db_connection.execute('''
            UPDATE challenges_tasks_set 
            SET started_at = now() - interval '8 days'
            WHERE id = $1
        ''', task_set_id)
        
        # Вызываем show_user_tasks
        await queries.show_user_tasks(test_user)
        
        # Assert: completed набор ДОЛЖЕН стать closed
        task_set_after = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set_after['status'] == ChallengesTasksSetStatuses.closed, "Completed набор должен закрыться после 7 дней"


class TestExpCalculationAndPacks:
    """Тесты расчёта exp и начисления паков"""
    
    @pytest.mark.asyncio
    async def test_exp_accumulation_across_tasks(
        self,
        test_user: int,
        db_connection: Connection
    ):
        """
        E2E: Накопление exp от нескольких заданий и получение паков.
        
        Сценарий:
        1. Пользователь начинает с 900 exp
        2. Выполняет 4 задания с разными наградами exp
        3. Собирает награды
        4. Получает паки за накопленный exp (каждые 1000 exp = 1 пак)
        
        Проверяем:
        - Корректное суммирование exp
        - Применение MOD 1000 для остатка
        - Правильный расчёт количества паков
        """
        queries = ChallengesQueries(db_connection)
        
        # Arrange: устанавливаем начальный exp = 900
        await db_connection.execute('''
            UPDATE users SET exp = 900 WHERE user_id = $1
        ''', test_user)
        
        # Создаём и выполняем задания
        task_set_id, _ = await queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for ch in challenges:
            await queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await queries.activate_task_set_timer(task_set_id)
        
        # Выполняем все задания
        for ch in challenges:
            await queries.add_progress_by_action(ch['challenge_id'], test_user, 100)
        
        # Вычисляем ожидаемый exp
        total_reward_exp = await db_connection.fetchval('''
            SELECT SUM(cr.reward_exp)
            FROM user_challenges uc
            JOIN challenges_rewards cr 
                ON cr.challenge_id = uc.challenge_id 
                AND cr.challenge_difficulty_id = uc.challenge_difficulty_id
            WHERE uc.task_set_id = $1
        ''', task_set_id)
        
        expected_total_exp = 900 + total_reward_exp  # Начальный + награды
        expected_packs = expected_total_exp // 1000
        expected_remaining_exp = expected_total_exp % 1000
        
        # Act: собираем награды
        result = await queries.collect_rewards(task_set_id=task_set_id)
        
        # Assert
        assert result['credit_packs_in_exp'] == expected_total_exp, f"credit_packs_in_exp должен быть {expected_total_exp}"
        
        # Проверяем exp пользователя после сбора
        user_after = await db_connection.fetchrow('''
            SELECT exp FROM users WHERE user_id = $1
        ''', test_user)
        
        assert user_after['exp'] == expected_remaining_exp, f"Остаток exp должен быть {expected_remaining_exp}"
        
        # Проверяем расчёт паков
        packs_to_give = result['credit_packs_in_exp'] // 1000
        assert packs_to_give == expected_packs, f"Должно быть {expected_packs} паков"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Integration тесты для системы выполнения заданий (Use Case 02)

Покрывает:
- Добавление прогресса к заданиям
- Автоматический переход в reward_ready
- Накопление прогресса
- Работу с несколькими заданиями
"""
import pytest
from asyncpg import Connection
from app.modules.tasks.sql_queries import ChallengesQueries
from app.modules.tasks.anything import ChallengesTasksSetStatuses, ChallengeStatuses, Challenges


class TestAddTaskProgress:
    """Тесты добавления прогресса к заданиям"""
    
    @pytest.mark.asyncio
    async def test_add_progress_to_task(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Добавление прогресса к заданию увеличивает значение progress.
        
        Ожидается:
        - progress увеличивается на переданное значение
        - Задание остаётся в статусе in_progress
        """
        # Arrange: создаём активный набор с заданием
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        # Получаем challenge "Пригласи друга" с целью 3
        challenge_id = Challenges.invite_friends
        _, slot = await challenges_queries.accept_challenge(task_set_id, challenge_id, 2)  # difficulty=2 (Средняя), goal=3
        
        # Добавляем ещё 3 задания для активации
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: добавляем прогресс (но не до конца)
        affected_tasks = await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert
        task = await db_connection.fetchrow('''
            SELECT progress, status FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert task['progress'] == 1, "Прогресс должен увеличиться на 1"
        assert task['status'] == ChallengeStatuses.in_progress, "Статус должен остаться in_progress"
        assert len(affected_tasks) == 1, "Должно быть затронуто 1 задание"

    @pytest.mark.asyncio
    async def test_auto_switch_to_reward_ready(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Автоматический переход в reward_ready при достижении цели.
        
        Ожидается:
        - При достижении goal задание переходит в reward_ready
        - progress = goal
        """
        # Arrange: создаём активный набор с заданием goal=1
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)  # goal=1
        
        # Добавляем ещё 3 задания для активации
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: добавляем прогресс до достижения цели
        affected_tasks = await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert
        task = await db_connection.fetchrow('''
            SELECT progress, status FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert task['progress'] == 1, "Прогресс должен быть равен goal"
        assert task['status'] == ChallengeStatuses.reward_ready, "Статус должен переключиться в reward_ready"
        
        # Проверяем, что затронутое задание вернулось со статусом reward_ready
        assert affected_tasks[0]['status'] == ChallengeStatuses.reward_ready

    @pytest.mark.asyncio
    async def test_progress_cannot_exceed_goal(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Прогресс не превышает goal.
        
        Ожидается:
        - Если добавляем прогресс больше goal, он ограничивается goal
        - Используется LEAST(progress + add, goal)
        """
        # Arrange: создаём активный набор с заданием goal=1
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)  # goal=1
        
        # Добавляем ещё 3 задания для активации
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: добавляем прогресс больше чем goal (100 вместо 1)
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 100)
        
        # Assert
        task = await db_connection.fetchrow('''
            SELECT progress FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert task['progress'] == 1, "Прогресс НЕ должен превышать goal (должен быть 1, а не 100)"

    @pytest.mark.asyncio
    async def test_add_progress_to_multiple_tasks(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Прогресс добавляется только к заданиям из in_progress набора.
        
        Сценарий: пользователь имеет 2 набора с одинаковым challenge_id:
        - Старый набор (closed) с заданием in_progress
        - Новый набор (in_progress) с заданием in_progress
        
        Ожидается: обновляется только задание из in_progress набора.
        """
        # Arrange: создаём 2 набора заданий с одинаковым challenge_id
        
        # Первый набор (будет закрыт, но задания останутся in_progress)
        task_set_id_1, _ = await challenges_queries.set_select_task_set(test_user)
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id_1, challenge_id, 1)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id_1, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id_1)
        
        # Закрываем первый набор (задания остаются in_progress)
        await db_connection.execute('''
            UPDATE challenges_tasks_set SET status = $1
            WHERE id = $2
        ''', ChallengesTasksSetStatuses.closed, task_set_id_1)
        
        # Второй набор (новый, активный)
        await db_connection.execute('DELETE FROM challenges_user_layout WHERE user_id = $1', test_user)
        task_set_id_2, _ = await challenges_queries.set_select_task_set(test_user)
        await challenges_queries.accept_challenge(task_set_id_2, challenge_id, 1)
        
        challenges_2 = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges_2:
            await challenges_queries.accept_challenge(task_set_id_2, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id_2)
        
        # Act: добавляем прогресс (должно затронуть только задание из in_progress набора)
        affected_tasks = await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert: только задание из in_progress набора обновится
        assert len(affected_tasks) == 1, "Должно быть затронуто только 1 задание (из in_progress набора)"
        assert affected_tasks[0]['challenge_id'] == challenge_id
        assert affected_tasks[0]['status'] == ChallengeStatuses.reward_ready
        
        # Проверяем, что задание из закрытого набора НЕ обновилось
        old_task = await db_connection.fetchrow('''
            SELECT progress FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id_1, challenge_id)
        assert old_task['progress'] == 0, "Задание из закрытого набора НЕ должно обновиться"

    @pytest.mark.asyncio
    async def test_add_progress_only_to_in_progress_tasks(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Прогресс добавляется только к заданиям со статусом in_progress.
        
        Ожидается:
        - Задания в pending, reward_ready, completed не затрагиваются
        """
        # Arrange: создаём набор с заданием, но НЕ активируем его
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # НЕ активируем таймер -> задания остаются в pending
        
        # Act: пытаемся добавить прогресс
        affected_tasks = await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert: прогресс НЕ должен добавиться
        assert len(affected_tasks) == 0, "Прогресс НЕ должен добавляться к pending заданиям"
        
        task = await db_connection.fetchrow('''
            SELECT progress, status FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert task['progress'] == 0, "Прогресс должен остаться 0"
        assert task['status'] == ChallengeStatuses.pending

    @pytest.mark.asyncio
    async def test_progress_accumulates(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Прогресс накапливается при повторных вызовах.
        
        Ожидается:
        - Несколько вызовов add_progress суммируются
        """
        # Arrange: создаём активный набор с заданием goal=5
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        await challenges_queries.accept_challenge(task_set_id, challenge_id, 3)  # difficulty=3 (Лёгкая), goal=5
        
        # Добавляем ещё 3 задания для активации
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: добавляем прогресс несколько раз
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 2)
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert
        task = await db_connection.fetchrow('''
            SELECT progress FROM user_challenges 
            WHERE task_set_id = $1 AND challenge_id = $2
        ''', task_set_id, challenge_id)
        
        assert task['progress'] == 4, "Прогресс должен накопиться: 2 + 1 + 1 = 4"

    @pytest.mark.asyncio
    async def test_returns_affected_tasks(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Метод возвращает список затронутых заданий с метаданными.
        
        Ожидается:
        - Возвращается список с task_id, challenge_id, slot, status
        """
        # Arrange: создаём активный набор с заданием
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge_id = Challenges.invite_friends
        _, slot = await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # Добавляем ещё 3 задания для активации
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout 
            WHERE user_id = $1 AND challenge_id != $2 LIMIT 3
        ''', test_user, challenge_id)
        
        for ch in challenges:
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: добавляем прогресс до завершения
        affected_tasks = await challenges_queries.add_progress_by_action(challenge_id, test_user, 1)
        
        # Assert: проверяем структуру возвращаемых данных
        assert len(affected_tasks) == 1
        
        task_info = affected_tasks[0]
        assert 'task_id' in task_info
        assert 'challenge_id' in task_info
        assert 'slot' in task_info
        assert 'status' in task_info
        
        assert task_info['challenge_id'] == challenge_id
        assert task_info['slot'] == slot
        assert task_info['status'] == ChallengeStatuses.reward_ready


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

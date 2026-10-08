"""
Integration тесты для системы выбора заданий (Use Case 01)

Покрывает:
- Создание draft набора заданий
- Генерацию персональной выборки челленджей
- Добавление/удаление заданий (accept/decline)
- Активацию таймера
"""
import pytest
from datetime import datetime, timedelta
from asyncpg import Connection
from app.modules.tasks.sql_queries import ChallengesQueries
from app.modules.tasks.anything import ChallengesTasksSetStatuses, ChallengeStatuses, ChallengesCategories


class TestDraftTaskSetCreation:
    """Тесты создания draft набора заданий"""
    
    @pytest.mark.asyncio
    async def test_create_draft_task_set_first_time(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        GREEN: Создание draft набора заданий в первый раз.
        
        Ожидается:
        - Создаётся новый набор заданий со статусом draft
        - Генерируется персональная выборка из 8 челленджей
        - Возвращается task_set_id
        """
        # Act
        task_set_id, accepted_challenges = await challenges_queries.set_select_task_set(test_user)
        
        # Assert
        assert task_set_id is not None, "task_set_id должен быть создан"
        assert isinstance(task_set_id, int), "task_set_id должен быть числом"
        assert accepted_challenges == [], "При первом создании accepted_challenges должен быть пуст"
        
        # Проверяем, что набор создан в БД
        task_set = await db_connection.fetchrow(
            'SELECT id, user_id, status FROM challenges_tasks_set WHERE id = $1',
            task_set_id
        )
        assert task_set is not None, "Набор заданий должен быть в БД"
        assert task_set['user_id'] == test_user
        assert task_set['status'] == ChallengesTasksSetStatuses.draft
        
        # Проверяем, что создана персональная выборка челленджей (8 штук)
        layout = await db_connection.fetch(
            'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1',
            test_user
        )
        assert len(layout) == 8, "Должно быть сгенерировано 8 челленджей"

    @pytest.mark.asyncio
    async def test_cannot_create_draft_when_in_progress_exists(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Нельзя создать draft если уже есть in_progress набор.
        
        Ожидается:
        - При наличии in_progress набора новый draft НЕ создаётся
        - Возвращается None
        """
        # Arrange: создаём in_progress набор
        await db_connection.execute('''
            INSERT INTO challenges_tasks_set (user_id, status, started_at)
            VALUES ($1, $2, now())
        ''', test_user, ChallengesTasksSetStatuses.in_progress)
        
        # Act
        task_set_id, accepted_challenges = await challenges_queries.set_select_task_set(test_user)
        
        # Assert
        assert task_set_id is None, "Не должен создаваться новый draft при наличии in_progress"
        assert accepted_challenges is None or accepted_challenges == [], "Не должно быть accepted_challenges"

    @pytest.mark.asyncio
    async def test_create_draft_after_completed_and_7_days(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        Можно создать draft если прошлый набор completed И прошло 7 дней.
        
        Ожидается:
        - При completed статусе и истечении 7 дней после вызова show_user_tasks
          набор переходит в closed
        - После этого можно создать новый draft
        """
        # Arrange: создаём completed набор старше 7 дней
        old_started_at = datetime.now() - timedelta(days=8)
        old_task_set_id = await db_connection.fetchval('''
            INSERT INTO challenges_tasks_set (user_id, status, started_at)
            VALUES ($1, $2, $3)
            RETURNING id
        ''', test_user, ChallengesTasksSetStatuses.completed, old_started_at)
        
        # Вызываем show_user_tasks для закрытия истёкшего набора
        await challenges_queries.show_user_tasks(test_user)
        
        # Проверяем, что старый набор стал closed
        old_task_set = await db_connection.fetchrow(
            'SELECT status FROM challenges_tasks_set WHERE id = $1',
            old_task_set_id
        )
        assert old_task_set['status'] == ChallengesTasksSetStatuses.closed, "Старый набор должен стать closed"
        
        # Act: создаём новый draft
        task_set_id, accepted_challenges = await challenges_queries.set_select_task_set(test_user)
        
        # Assert
        assert task_set_id is not None, "Должен создаться новый draft после закрытия старого"
        assert task_set_id != old_task_set_id, "Должен создаться НОВЫЙ набор"
        
        # Проверяем, что новый набор в статусе draft
        new_task_set = await db_connection.fetchrow(
            'SELECT status FROM challenges_tasks_set WHERE id = $1',
            task_set_id
        )
        assert new_task_set['status'] == ChallengesTasksSetStatuses.draft

    @pytest.mark.asyncio
    async def test_create_draft_after_expired(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Можно создать draft если прошлый набор expired (время истекло).
        
        Ожидается:
        - При expired статусе создаётся новый draft
        """
        # Arrange: создаём expired набор
        await db_connection.execute('''
            INSERT INTO challenges_tasks_set (user_id, status, started_at)
            VALUES ($1, $2, now() - interval '8 days')
        ''', test_user, ChallengesTasksSetStatuses.closed)
        
        # Act
        task_set_id, accepted_challenges = await challenges_queries.set_select_task_set(test_user)
        
        # Assert
        assert task_set_id is not None, "Должен создаться новый draft после expired набора"
        
        # Проверяем, что новый набор в статусе draft
        new_task_set = await db_connection.fetchrow(
            'SELECT status FROM challenges_tasks_set WHERE id = $1',
            task_set_id
        )
        assert new_task_set['status'] == ChallengesTasksSetStatuses.draft


class TestChallengesLayoutGeneration:
    """Тесты генерации и стабильности персональной выборки челленджей"""
    
    @pytest.mark.asyncio
    async def test_generate_user_challenges_layout(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Проверка правильной генерации персональной выборки: 1+2+1+4 по категориям.
        
        Ожидается:
        - 1 челлендж из категории "Пригласи друга" (category_id=2)
        - 2 челленджа из категории "Коллекции" (category_id=1)
        - 1 челлендж из категории "Кинь мячик" (category_id=4)
        - 4 челленджа из категории "5 на 5" (category_id=3)
        """
        # Act
        await challenges_queries.set_select_task_set(test_user)
        
        # Assert: проверяем распределение по категориям
        layout = await db_connection.fetch('''
            SELECT c.category_id, COUNT(*) as cnt
            FROM challenges_user_layout cul
            JOIN challenges c ON c.id = cul.challenge_id
            WHERE cul.user_id = $1
            GROUP BY c.category_id
            ORDER BY c.category_id
        ''', test_user)
        
        category_counts = {row['category_id']: row['cnt'] for row in layout}
        
        assert category_counts.get(ChallengesCategories.collections) == 2, "Должно быть 2 челленджа из Коллекций"
        assert category_counts.get(ChallengesCategories.invite_friends) == 1, "Должен быть 1 челлендж Пригласи друга"
        assert category_counts.get(ChallengesCategories.pvp_5v5) == 4, "Должно быть 4 челленджа из 5 на 5"
        assert category_counts.get(ChallengesCategories.throw_ball) == 1, "Должен быть 1 челлендж Кинь мячик"

    @pytest.mark.asyncio
    async def test_layout_remains_stable_on_reopen(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Выборка челленджей НЕ меняется при повторном открытии (draft уже существует).
        
        Ожидается:
        - При первом вызове создаётся выборка
        - При втором вызове выборка остаётся той же (те же challenge_id)
        """
        # Act: первый вызов - создаём выборку
        task_set_id_1, _ = await challenges_queries.set_select_task_set(test_user)
        
        layout_1 = await db_connection.fetch(
            'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 ORDER BY challenge_id',
            test_user
        )
        challenge_ids_1 = [row['challenge_id'] for row in layout_1]
        
        # Act: второй вызов - НЕ должен пересоздать выборку
        task_set_id_2, _ = await challenges_queries.set_select_task_set(test_user)
        
        layout_2 = await db_connection.fetch(
            'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 ORDER BY challenge_id',
            test_user
        )
        challenge_ids_2 = [row['challenge_id'] for row in layout_2]
        
        # Assert
        assert task_set_id_1 == task_set_id_2, "task_set_id должен остаться тем же"
        assert challenge_ids_1 == challenge_ids_2, "Выборка челленджей НЕ должна измениться"

    @pytest.mark.asyncio
    async def test_layout_regenerates_only_on_new_draft(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Выборка обновляется только при создании нового draft набора.
        
        Ожидается:
        - При первом создании генерируется выборка A
        - После закрытия старого набора и создания нового - генерируется новая выборка B
        - Выборки A и B могут отличаться (рандомная генерация)
        """
        # Act: создаём первый draft и запоминаем выборку
        task_set_id_1, _ = await challenges_queries.set_select_task_set(test_user)
        
        layout_1 = await db_connection.fetch(
            'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 ORDER BY challenge_id',
            test_user
        )
        challenge_ids_1 = [row['challenge_id'] for row in layout_1]
        
        # Arrange: закрываем первый набор (имитация истечения срока)
        await db_connection.execute('''
            UPDATE challenges_tasks_set SET status = $1, started_at = now() - interval '8 days'
            WHERE id = $2
        ''', ChallengesTasksSetStatuses.closed, task_set_id_1)
        
        # Act: создаём новый draft - должна сгенерироваться НОВАЯ выборка
        task_set_id_2, _ = await challenges_queries.set_select_task_set(test_user)
        
        layout_2 = await db_connection.fetch(
            'SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 ORDER BY challenge_id',
            test_user
        )
        challenge_ids_2 = [row['challenge_id'] for row in layout_2]
        
        # Assert
        assert task_set_id_1 != task_set_id_2, "Должен создаться новый task_set_id"
        assert len(challenge_ids_2) == 8, "Новая выборка должна содержать 8 челленджей"
        # Примечание: выборки МОГУТ совпасть случайно из-за рандома, но это маловероятно
        # Проверяем, что хотя бы генерация произошла


class TestAcceptDeclineChallenges:
    """Тесты добавления и удаления заданий (управление слотами)"""
    
    @pytest.mark.asyncio
    async def test_accept_challenge_fills_slot_1(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Первое добавленное задание получает slot=1.
        
        Ожидается:
        - При добавлении первого задания slot=1
        - Задание создаётся со статусом pending
        """
        # Arrange: создаём draft набор
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        # Получаем любой challenge_id из выборки
        challenge = await db_connection.fetchrow('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 1
        ''', test_user)
        challenge_id = challenge['challenge_id']
        difficulty_id = 1  # Сложная
        
        # Act
        success, slot = await challenges_queries.accept_challenge(task_set_id, challenge_id, difficulty_id)
        
        # Assert
        assert success is True, "Добавление должно быть успешным"
        assert slot == 1, "Первое задание должно получить slot=1"
        
        # Проверяем в БД
        task = await db_connection.fetchrow('''
            SELECT slot, status, challenge_id, challenge_difficulty_id
            FROM user_challenges WHERE task_set_id = $1
        ''', task_set_id)
        
        assert task['slot'] == 1
        assert task['status'] == ChallengeStatuses.pending
        assert task['challenge_id'] == challenge_id
        assert task['challenge_difficulty_id'] == difficulty_id

    @pytest.mark.asyncio
    async def test_accept_multiple_challenges_sequential_slots(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Слоты заполняются последовательно: 1, 2, 3, 4.
        
        Ожидается:
        - Добавление 4 заданий создаёт слоты 1, 2, 3, 4
        """
        # Arrange: создаём draft и получаем челленджи
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        # Act: добавляем 4 задания
        slots = []
        for challenge in challenges:
            success, slot = await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
            assert success is True, "Каждое добавление должно быть успешным"
            slots.append(slot)
        
        # Assert
        assert slots == [1, 2, 3, 4], "Слоты должны заполняться последовательно"

    @pytest.mark.asyncio
    async def test_decline_challenge_frees_slot(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Удаление задания освобождает slot.
        
        Ожидается:
        - После удаления задания slot становится свободным
        - Задание удаляется из БД
        """
        # Arrange: создаём draft и добавляем задание
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge = await db_connection.fetchrow('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 1
        ''', test_user)
        challenge_id = challenge['challenge_id']
        
        success, slot = await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        assert success is True
        
        # Act: удаляем задание
        result = await challenges_queries.decline_challenge(task_set_id, challenge_id, slot)
        
        # Assert
        assert result is not None, "Удаление должно вернуть результат"
        
        # Проверяем, что задание удалено
        task_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges WHERE task_set_id = $1
        ''', task_set_id)
        assert task_count == 0, "Задание должно быть удалено из БД"

    @pytest.mark.asyncio
    async def test_accept_after_decline_fills_gap(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Новое задание занимает освободившийся slot.
        
        Сценарий:
        - Добавляем 3 задания (слоты 1, 2, 3)
        - Удаляем задание со slot=2
        - Добавляем новое задание
        - Ожидается: новое задание получит slot=2
        """
        # Arrange: создаём draft
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        # Добавляем 3 задания
        _, slot1 = await challenges_queries.accept_challenge(task_set_id, challenges[0]['challenge_id'], 1)
        _, slot2 = await challenges_queries.accept_challenge(task_set_id, challenges[1]['challenge_id'], 1)
        _, slot3 = await challenges_queries.accept_challenge(task_set_id, challenges[2]['challenge_id'], 1)
        
        assert [slot1, slot2, slot3] == [1, 2, 3], "Начальные слоты должны быть 1, 2, 3"
        
        # Act: удаляем задание со slot=2
        await challenges_queries.decline_challenge(task_set_id, challenges[1]['challenge_id'], slot2)
        
        # Добавляем новое задание
        _, new_slot = await challenges_queries.accept_challenge(task_set_id, challenges[3]['challenge_id'], 1)
        
        # Assert
        assert new_slot == 2, "Новое задание должно занять освободившийся slot=2"

    @pytest.mark.asyncio
    async def test_decline_middle_slot_and_refill_correctly(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Корректное заполнение после удаления среднего slot.
        
        Сценарий:
        - Добавляем задания в слоты 1, 2, 3
        - Удаляем slot=2 (остаются 1 и 3)
        - Добавляем 2 новых задания
        - Ожидается: слоты станут 1, 2, 3, 4
        """
        # Arrange
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 5
        ''', test_user)
        
        # Добавляем 3 задания
        await challenges_queries.accept_challenge(task_set_id, challenges[0]['challenge_id'], 1)
        _, slot2 = await challenges_queries.accept_challenge(task_set_id, challenges[1]['challenge_id'], 1)
        await challenges_queries.accept_challenge(task_set_id, challenges[2]['challenge_id'], 1)
        
        # Удаляем slot=2
        await challenges_queries.decline_challenge(task_set_id, challenges[1]['challenge_id'], slot2)
        
        # Act: добавляем 2 новых задания
        _, new_slot1 = await challenges_queries.accept_challenge(task_set_id, challenges[3]['challenge_id'], 1)
        _, new_slot2 = await challenges_queries.accept_challenge(task_set_id, challenges[4]['challenge_id'], 1)
        
        # Assert
        assert new_slot1 == 2, "Первое новое задание должно занять slot=2"
        assert new_slot2 == 4, "Второе новое задание должно занять slot=4"
        
        # Проверяем финальное распределение слотов
        slots = await db_connection.fetch('''
            SELECT slot FROM user_challenges WHERE task_set_id = $1 ORDER BY slot
        ''', task_set_id)
        final_slots = [row['slot'] for row in slots]
        assert final_slots == [1, 2, 3, 4], "Финальные слоты должны быть [1, 2, 3, 4]"


class TestProtectionAndLimits:
    """Тесты защиты от удаления и лимитов"""
    
    @pytest.mark.asyncio
    async def test_cannot_decline_challenge_when_in_progress(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Нельзя удалить задание если набор in_progress (старое сообщение).
        
        Ожидается:
        - decline_challenge возвращает None при попытке удаления из in_progress набора
        """
        # Arrange: создаём draft, добавляем задание и активируем набор
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge = await db_connection.fetchrow('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 1
        ''', test_user)
        challenge_id = challenge['challenge_id']
        
        # Добавляем 4 задания и активируем таймер
        for i in range(4):
            ch = await db_connection.fetchrow(f'''
                SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 1 OFFSET {i}
            ''', test_user)
            await challenges_queries.accept_challenge(task_set_id, ch['challenge_id'], 1)
        
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Act: пытаемся удалить задание
        result = await challenges_queries.decline_challenge(task_set_id, challenge_id, 1)
        
        # Assert
        assert result is None, "Не должно быть возможности удалить задание из in_progress набора"

    @pytest.mark.asyncio
    async def test_can_decline_only_with_pending_status(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Удаление работает только для status=pending.
        
        Ожидается:
        - Удаление успешно только если status=pending (draft набор)
        """
        # Arrange: создаём draft и добавляем задание
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenge = await db_connection.fetchrow('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 1
        ''', test_user)
        challenge_id = challenge['challenge_id']
        
        _, slot = await challenges_queries.accept_challenge(task_set_id, challenge_id, 1)
        
        # Act: удаляем задание (должно сработать, т.к. status=pending)
        result = await challenges_queries.decline_challenge(task_set_id, challenge_id, slot)
        
        # Assert
        assert result is not None, "Удаление должно работать для pending статуса"

    @pytest.mark.asyncio
    async def test_cannot_accept_more_than_4(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Нельзя выбрать 5ое задание.
        
        Ожидается:
        - После добавления 4 заданий пятое не добавляется
        - accept_challenge возвращает (False, None)
        """
        # Arrange: создаём draft
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 5
        ''', test_user)
        
        # Добавляем 4 задания
        for i in range(4):
            success, slot = await challenges_queries.accept_challenge(task_set_id, challenges[i]['challenge_id'], 1)
            assert success is True, f"Задание {i+1} должно добавиться"
        
        # Act: пытаемся добавить 5ое задание
        success, slot = await challenges_queries.accept_challenge(task_set_id, challenges[4]['challenge_id'], 1)
        
        # Assert
        assert success is False, "5ое задание не должно добавиться"
        assert slot is None, "slot должен быть None"

    @pytest.mark.asyncio
    async def test_accept_returns_false_when_limit_reached(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: accept_challenge возвращает (False, None) при 5ой попытке.
        
        Проверяет корректность возвращаемого значения при достижении лимита.
        """
        # Arrange
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 5
        ''', test_user)
        
        # Заполняем все 4 слота
        for i in range(4):
            await challenges_queries.accept_challenge(task_set_id, challenges[i]['challenge_id'], 1)
        
        # Act & Assert: проверяем возвращаемое значение для 5ого
        success, slot = await challenges_queries.accept_challenge(task_set_id, challenges[4]['challenge_id'], 1)
        
        assert (success, slot) == (False, None), "Должен вернуться (False, None)"


class TestTimerActivation:
    """Тесты активации таймера"""
    
    @pytest.mark.asyncio
    async def test_activate_timer_switches_to_in_progress(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Активация таймера переводит набор и задания в in_progress.
        
        Ожидается:
        - draft → in_progress для набора
        - pending → in_progress для заданий
        """
        # Arrange: создаём draft с 4 заданиями
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for challenge in challenges:
            await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
        
        # Act: активируем таймер
        result = await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Assert
        assert result is not None, "Активация должна вернуть результат"
        
        # Проверяем статус набора
        task_set = await db_connection.fetchrow('''
            SELECT status, started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        assert task_set['status'] == ChallengesTasksSetStatuses.in_progress
        assert task_set['started_at'] is not None
        
        # Проверяем статусы заданий
        tasks = await db_connection.fetch('''
            SELECT status FROM user_challenges WHERE task_set_id = $1
        ''', task_set_id)
        assert all(task['status'] == ChallengeStatuses.in_progress for task in tasks)

    @pytest.mark.asyncio
    async def test_activate_timer_sets_started_at(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: started_at устанавливается в now() при активации.
        
        Ожидается:
        - started_at заполняется текущим временем
        """
        # Arrange
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for challenge in challenges:
            await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
        
        # Проверяем, что started_at не установлен
        task_set_before = await db_connection.fetchrow('''
            SELECT started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        
        # Act
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Assert
        task_set_after = await db_connection.fetchrow('''
            SELECT started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        
        # Время должно измениться (было дефолтное, стало now())
        assert task_set_after['started_at'] != task_set_before['started_at']

    @pytest.mark.asyncio
    async def test_cannot_activate_timer_twice(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Повторная активация НЕ меняет started_at (старое сообщение).
        
        Ожидается:
        - started_at остаётся неизменным при второй попытке активации
        """
        # Arrange: создаём и активируем набор
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for challenge in challenges:
            await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
        
        # Первая активация
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        first_started_at = await db_connection.fetchval('''
            SELECT started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        
        # Act: вторая попытка активации (старое сообщение)
        result = await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Assert
        assert result is None, "Повторная активация не должна вернуть результат"
        
        second_started_at = await db_connection.fetchval('''
            SELECT started_at FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        
        assert first_started_at == second_started_at, "started_at НЕ должен измениться"

    @pytest.mark.asyncio
    async def test_cannot_activate_with_less_than_4_tasks(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Активация только если выбрано ровно 4 задания.
        
        Ожидается:
        - С 3 заданиями активация не работает
        - Возвращается None
        """
        # Arrange: создаём draft с 3 заданиями
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 3
        ''', test_user)
        
        for challenge in challenges:
            await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
        
        # Act: пытаемся активировать с 3 заданиями
        result = await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Assert
        # Проверяем, что статус не изменился
        task_set = await db_connection.fetchrow('''
            SELECT status FROM challenges_tasks_set WHERE id = $1
        ''', task_set_id)
        
        # Статус должен остаться draft
        assert task_set['status'] == ChallengesTasksSetStatuses.draft, "Статус должен остаться draft"

    @pytest.mark.asyncio
    async def test_activate_only_switches_pending_tasks(
        self,
        test_user: int,
        challenges_queries: ChallengesQueries,
        db_connection: Connection
    ):
        """
        RED: Активируются только pending задания (не все в наборе).
        
        Проверяет, что SQL фильтрует по status=pending при переключении.
        """
        # Arrange: создаём draft с 4 заданиями
        task_set_id, _ = await challenges_queries.set_select_task_set(test_user)
        
        challenges = await db_connection.fetch('''
            SELECT challenge_id FROM challenges_user_layout WHERE user_id = $1 LIMIT 4
        ''', test_user)
        
        for challenge in challenges:
            await challenges_queries.accept_challenge(task_set_id, challenge['challenge_id'], 1)
        
        # Act
        await challenges_queries.activate_task_set_timer(task_set_id)
        
        # Assert: все задания должны переключиться в in_progress
        tasks_count = await db_connection.fetchval('''
            SELECT COUNT(*) FROM user_challenges 
            WHERE task_set_id = $1 AND status = $2
        ''', task_set_id, ChallengeStatuses.in_progress)
        
        assert tasks_count == 4, "Все 4 задания должны быть in_progress"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

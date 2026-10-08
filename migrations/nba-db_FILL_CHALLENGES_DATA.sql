-- ============================================================
-- Заполнение справочников
-- ============================================================

-- Категории челленджей
INSERT INTO public.challenges_categories OVERRIDING SYSTEM VALUE VALUES 
    (1, 'Коллекции'),
    (2, 'Пригласи друга'),
    (3, '5 на 5'),
    (4, 'Кинь мячик');

-- Сложности челленджей
INSERT INTO public.challenges_difficulties OVERRIDING SYSTEM VALUE VALUES 
    (1, 'Сложная'),
    (2, 'Средняя'),
    (3, 'Лёгкая'),
    (4, 'Общая');

-- Статусы челленджей
INSERT INTO public.challenges_statuses OVERRIDING SYSTEM VALUE VALUES 
    (1, 'in_progress'),
    (2, 'reward_ready'),
    (3, 'completed'),
    (4, 'expired');

-- Статусы наборов заданий
INSERT INTO public.tasks_set_statuses OVERRIDING SYSTEM VALUE VALUES 
    (1, 'draft'),
    (2, 'in_progress'),
    (3, 'completed'),
    (4, 'closed');

-- Статусы пользовательских челленджей
INSERT INTO public.user_challenges_statuses OVERRIDING SYSTEM VALUE VALUES 
    (1, 'pending'),
    (2, 'in_progress'),
    (3, 'reward_ready'),
    (4, 'completed'),
    (5, 'expired');

-- ============================================================
-- Заполнение основных данных
-- ============================================================

-- Челленджи
INSERT INTO public.challenges OVERRIDING SYSTEM VALUE VALUES 
    (1, 2, 'Пригласи {goal} друзей по ссылке в профиле'),
    (2, 1, 'Скрафть или открой {goal} карточек'),
    (3, 3, 'Забей {goal} раз через блок в 5 на 5'),
    (4, 1, 'Скрафть или открой {goal} серебрянных карточек'),
    (5, 1, 'Скрафть или открой {goal} золотую карточку'),
    (6, 1, 'Скрафть {goal} карточек'),
    (7, 4, 'Кинь {goal} мячиков'),
    (8, 1, 'Скрафть или открой {goal} алмаз карточку'),
    (9, 1, 'Скрафть или открой {goal} легенд карточку'),
    (10, 1, 'Разбери {goal} карточек'),
    (11, 3, 'Одержи {goal} побед в 5 на 5'),
    (12, 3, 'Сделай {goal} пасов в 5 на 5'),
    (13, 3, 'Забей 3х очковый {goal} раз в 5 на 5 '),
    (14, 3, 'Победи одним и тем же составом команды в {goal} матчей');

-- Награды за челленджи
INSERT INTO public.challenges_rewards OVERRIDING SYSTEM VALUE VALUES 
    -- Челлендж 1: Пригласи друзей
    (3, 1, 1, 1, 200, 0, 2),
    (5, 3, 1, 2, 400, 0, 5),
    (4, 5, 1, 3, 700, 0, 10),
    -- Челлендж 2: Скрафть карточки (общая версия, без указания типа)
    (7, 35, 2, 1, 100, 3, 0),
    (8, 45, 2, 2, 200, 5, 0),
    (9, 60, 2, 3, 300, 7, 0),
    -- Челлендж 3: Забей через блок
    (33, 3, 3, 1, 100, 10, 0),
    (34, 5, 3, 2, 200, 10, 0),
    (32, 10, 3, 3, 300, 15, 0),
    -- Челлендж 4: Серебрянные карточки
    (11, 4, 4, 1, 100, 3, 0),
    (10, 7, 4, 2, 200, 5, 0),
    (12, 10, 4, 3, 300, 10, 0),
    -- Челлендж 5: Золотая карточка
    (14, 1, 5, 2, 200, 5, 0),
    (13, 2, 5, 3, 300, 10, 0),
    -- Челлендж 6: Скрафть карточки
    (15, 5, 6, 1, 100, 5, 0),
    (17, 10, 6, 2, 200, 10, 0),
    (16, 15, 6, 3, 300, 15, 0),
    -- Челлендж 7: Кинь мячики
    (19, 5, 7, 1, 100, 3, 0),
    (20, 10, 7, 2, 200, 10, 0),
    (18, 20, 7, 3, 300, 15, 0),
    -- Челлендж 8: Алмаз карточка
    (21, 1, 8, 3, 300, 10, 0),
    -- Челлендж 9: Легенд карточка
    (22, 1, 9, 3, 300, 15, 0),
    -- Челлендж 10: Разбери карточки
    (24, 5, 10, 1, 100, 5, 0),
    (25, 10, 10, 2, 200, 10, 0),
    (23, 15, 10, 3, 300, 15, 0),
    -- Челлендж 11: Победы в 5 на 5
    (27, 3, 11, 1, 100, 10, 0),
    (28, 5, 11, 2, 200, 15, 0),
    (26, 10, 11, 3, 300, 25, 0),
    -- Челлендж 12: Пасы в 5 на 5
    (30, 25, 12, 1, 100, 5, 0),
    (29, 50, 12, 2, 200, 10, 0),
    (31, 75, 12, 3, 300, 15, 0),
    -- Челлендж 13: 3х очковые
    (36, 5, 13, 1, 100, 5, 0),
    (37, 10, 13, 2, 200, 10, 0),
    (35, 20, 13, 3, 300, 15, 0),
    -- Челлендж 14: Победи одним составом
    (38, 5, 14, 3, 300, 30, 0);

-- ============================================================
-- Установка значений последовательностей (sequences)
-- ============================================================

SELECT pg_catalog.setval('public.challenges_categories_id_seq', 4, true);
SELECT pg_catalog.setval('public.challenges_difficulties_id_seq', 4, true);
SELECT pg_catalog.setval('public.challenges_id_seq', 14, true);
SELECT pg_catalog.setval('public.challenges_rewards_id_seq', 38, true);
SELECT pg_catalog.setval('public.challenges_statuses_id_seq', 4, true);
SELECT pg_catalog.setval('public.tasks_set_statuses_id_seq', 4, true);
SELECT pg_catalog.setval('public.user_challenges_statuses_id_seq', 5, true);

-- Эти последовательности начинаются с 1 (данных пока нет)
SELECT pg_catalog.setval('public.challenges_tasks_set_id_seq', 1, false);
SELECT pg_catalog.setval('public.challenges_user_layout_id_seq', 1, false);
SELECT pg_catalog.setval('public.user_challenges_id_seq', 1, false);

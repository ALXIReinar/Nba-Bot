-- ============================================================
-- Тестовый скрипт для проверки миграций
-- ============================================================
-- Этот файл НЕ является миграцией!
-- Используется только для проверки корректности SQL-синтаксиса
-- ============================================================

BEGIN;

-- Проверка: все таблицы с суффиксом challenges
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_name LIKE '%challenge%'
ORDER BY table_name;

-- Проверка: все FK constraints для таблиц challenges
SELECT 
    tc.constraint_name, 
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
LEFT JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_schema = 'public'
    AND tc.table_name LIKE '%challenge%'
ORDER BY tc.table_name, tc.constraint_name;

-- Проверка: статистика по данным
SELECT 'challenges_categories' as table_name, COUNT(*) as row_count FROM challenges_categories
UNION ALL
SELECT 'challenges_difficulties', COUNT(*) FROM challenges_difficulties
UNION ALL
SELECT 'challenges_statuses', COUNT(*) FROM challenges_statuses
UNION ALL
SELECT 'tasks_set_statuses', COUNT(*) FROM tasks_set_statuses
UNION ALL
SELECT 'user_challenges_statuses', COUNT(*) FROM user_challenges_statuses
UNION ALL
SELECT 'challenges', COUNT(*) FROM challenges
UNION ALL
SELECT 'challenges_rewards', COUNT(*) FROM challenges_rewards;

-- Проверка: колонка exp в users
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'users'
  AND column_name = 'exp';

ROLLBACK;

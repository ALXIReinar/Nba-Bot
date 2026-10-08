# Миграции БД

## Порядок выполнения миграций

Миграции должны выполняться **строго в указанном порядке**:

### 1. `nba-db_ADD_CHALLENGES_TABLES.sql`
Создаёт все новые таблицы с суффиксом `challenges`:
- **Справочные таблицы** (должны быть созданы первыми):
  - `challenges_categories` — категории челленджей
  - `challenges_difficulties` — уровни сложности
  - `challenges_statuses` — статусы челленджей
  - `tasks_set_statuses` — статусы наборов заданий
  - `user_challenges_statuses` — статусы пользовательских челленджей

- **Основные таблицы**:
  - `challenges` — описания челленджей
  - `challenges_rewards` — распределение наград по сложностям для челленджей
  - `challenges_tasks_set` — наборы заданий пользователей
  - `challenges_user_layout` — персональная выборка челленджей для пользователя
  - `user_challenges` — челленджи пользователя

### 2. `nba-db_FILL_CHALLENGES_DATA.sql`
Заполняет таблицы начальными данными:
- Справочники (категории, сложности, статусы)
- 14 челленджей с описаниями
- 38 вариантов наград (разные сложности для челленджей)
- Установка значений sequences для автоинкрементных ID

### 3. `nba-db_UPDATE_EXISTS_TABLES.sql`
Вносит изменения в существующие таблицы:
- Добавляет колонку `exp` (experience points) в таблицу `users`

## Структура данных

### Категории челленджей
1. **Коллекции** — задания на крафт и открытие карточек
2. **Пригласи друга** — задания на приглашение пользователей
3. **5 на 5** — задания в игровом режиме PvP
4. **Кинь мячик** — задания на использование мячиков

### Сложности
1. **Сложная** — высокие цели, большие награды
2. **Средняя** — средние цели и награды
3. **Лёгкая** — низкие цели, небольшие награды
4. **Общая** — универсальная сложность (не используется в текущих челленджах)

### Жизненный цикл челленджа

#### Статусы набора заданий (`challenges_tasks_set`)
1. `draft` — пользователь выбирает задания (можно добавлять/удалять)
2. `in_progress` — задания активны, идёт выполнение (7 дней)
3. `completed` — все задания выполнены и награды собраны
4. `closed` — набор закрыт по истечении времени

#### Статусы пользовательского челленджа (`user_challenges`)
1. `pending` — челлендж добавлен в набор, но набор ещё в draft
2. `in_progress` — челлендж активен, идёт выполнение
3. `reward_ready` — цель достигнута, награда готова к получению
4. `completed` — награда получена
5. `expired` — челлендж истёк (не выполнен за 7 дней)

## Бизнес-логика

### Распределение по категориям в выборке
- 1 челлендж из категории "Пригласи друга"
- 2 челленджа из категории "Коллекции"
- 1 челлендж из категории "Кинь мячик"
- 4 челленджа из категории "5 на 5"


## Проверка миграции

После выполнения миграций проверь:

```sql
-- Проверка созданных таблиц
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name LIKE '%challenge%'
ORDER BY table_name;

-- Проверка данных в справочниках
SELECT * FROM challenges_categories;
SELECT * FROM challenges_difficulties;
SELECT * FROM challenges;

-- Проверка колонки exp в users
SELECT column_name, data_type, column_default 
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'users'
  AND column_name = 'exp';
```

## Откат миграций

Если нужно откатить миграции (в обратном порядке):

```sql
-- 3. Удалить колонку exp
ALTER TABLE public.users DROP COLUMN IF EXISTS exp;

-- 2. Очистить данные (опционально, если таблицы будут удалены)
-- TRUNCATE TABLE challenges_rewards, user_challenges, challenges_user_layout, 
--              challenges_tasks_set, challenges CASCADE;

-- 1. Удалить все таблицы с суффиксом challenges
DROP TABLE IF EXISTS user_challenges CASCADE;
DROP TABLE IF EXISTS challenges_user_layout CASCADE;
DROP TABLE IF EXISTS challenges_tasks_set CASCADE;
DROP TABLE IF EXISTS challenges_rewards CASCADE;
DROP TABLE IF EXISTS challenges CASCADE;
DROP TABLE IF EXISTS user_challenges_statuses CASCADE;
DROP TABLE IF EXISTS challenges_statuses CASCADE;
DROP TABLE IF EXISTS tasks_set_statuses CASCADE;
DROP TABLE IF EXISTS challenges_difficulties CASCADE;
DROP TABLE IF EXISTS challenges_categories CASCADE;
```

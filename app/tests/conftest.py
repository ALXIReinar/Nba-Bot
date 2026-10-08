"""
Фикстуры для тестирования системы заданий
"""
import os
import pytest
import asyncpg
from asyncpg import Connection
from dotenv import load_dotenv


# Назначаем файл для переменных оркужения. СТРОГО ДО ИМПОРТА КОНФИГА
os.environ['ENV_FILE'] = '.env.bot.test'

from app.core.config import pool_settings, env

# Параметры подключения к тестовой БД из переменных окружения

@pytest.fixture(scope="session", autouse=True)
def ensure_test_database():
    """Проверяет что используется тестовая БД"""
    os.environ['PYTHONUTF8'] = '1'
    assert isinstance(env.postgres_db, str), "env.pg_db is not set"
    assert env.postgres_db.startswith("test_"), f"Refusing to run tests against non-test database: {env.postgres_db}"


@pytest.fixture(scope='function')
async def db_pool():
    """Пул соединений с тестовой БД"""
    pool = await asyncpg.create_pool(**pool_settings)
    yield pool
    await pool.close()


@pytest.fixture(scope='function')
async def db_connection(db_pool) -> Connection:
    """Отдельное соединение для каждого теста из пула"""
    async with db_pool.acquire() as conn:
        yield conn


@pytest.fixture(autouse=True)
async def clean_db(db_connection: Connection):
    """
    Автоматическая очистка динамических таблиц перед каждым тестом.
    
    Очищаем только таблицы, которые изменяются в процессе работы:
    - users (пользователи)
    - user_challenges (выбранные задания)
    - challenges_tasks_set (наборы заданий)
    - challenges_user_layout (персональная выборка челленджей)
    
    Статические таблицы (challenges, challenges_rewards и т.д.) НЕ трогаем.
    """
    await db_connection.execute('''
        TRUNCATE TABLE 
            user_challenges,
            challenges_tasks_set,
            challenges_user_layout,
            users
        CASCADE
    ''')
    yield
    # После теста тоже очищаем для чистоты
    await db_connection.execute('''
        TRUNCATE TABLE 
            user_challenges,
            challenges_tasks_set,
            challenges_user_layout,
            users
        CASCADE
    ''')


@pytest.fixture
async def test_user(db_connection: Connection) -> int:
    """
    Создаёт тестового пользователя и возвращает его user_id.
    
    Returns:
        int: user_id созданного пользователя (по умолчанию 12345)
    """
    user_id = 12345
    username = 'test_user'
    
    await db_connection.execute('''
        INSERT INTO users (user_id, username, throw_count, count_get, additional_try, exp)
        VALUES ($1, $2, 0, 6, 0, 0)
    ''', user_id, username)
    
    return user_id


@pytest.fixture
async def test_user_with_exp(db_connection: Connection) -> int:
    """
    Создаёт тестового пользователя с определённым количеством EXP.
    Полезно для тестирования начисления паков.
    
    Returns:
        int: user_id созданного пользователя (по умолчанию 54321)
    """
    user_id = 54321
    username = 'test_user_with_exp'
    
    await db_connection.execute('''
        INSERT INTO users (user_id, username, throw_count, count_get, additional_try, exp)
        VALUES ($1, $2, 0, 6, 0, 900)
    ''', user_id, username)
    
    return user_id


@pytest.fixture
async def challenges_queries(db_connection: Connection):
    """
    Возвращает экземпляр ChallengesQueries для выполнения запросов к БД.
    """
    from app.modules.tasks.sql_queries import ChallengesQueries
    return ChallengesQueries(db_connection)

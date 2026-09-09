from contextlib import asynccontextmanager

from redis.asyncio import Redis

from core.config_dir.config import redis_settings


@asynccontextmanager
async def get_redis_connection():
    redis = Redis(**redis_settings)
    try:
        yield redis
    finally:
        await redis.aclose()


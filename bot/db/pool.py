"""
Управление asyncpg.Pool: создание и закрытие соединений с PostgreSQL.
"""

import asyncpg

from bot.config import settings


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
    )

"""
Утилиты авторизации: проверка админских прав через БД.
"""

import asyncpg

from bot.config import settings
from bot.db.repositories import admins as admins_repo


async def is_admin(pool: asyncpg.Pool, user_id: int) -> bool:
    """Проверка, есть ли user_id в таблице admins."""
    return await admins_repo.is_admin(pool, user_id)


async def add_admin(
    pool: asyncpg.Pool,
    user_id: int,
    first_name: str,
    username: str | None = None,
) -> None:
    """Добавление пользователя в таблицу admins."""
    await admins_repo.add_admin(pool, user_id, first_name, username)


def verify_admin_hash(command_hash: str) -> bool:
    """Проверка хеша из команды /admin_<hash>."""
    return command_hash == settings.ADMIN_SECRET_HASH


def verify_init_secret(secret: str) -> bool:
    """Проверка одноразового токена для /init_admin."""
    return secret == settings.INIT_ADMIN_SECRET

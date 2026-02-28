"""
Репозиторий для таблицы admins.
Заменяет in-memory set[int] в bot/utils/auth.py.
"""

from __future__ import annotations

import asyncpg


async def is_admin(pool: asyncpg.Pool, telegram_id: int) -> bool:
    row = await pool.fetchrow(
        "SELECT 1 FROM admins WHERE telegram_id = $1 AND is_active = TRUE",
        telegram_id,
    )
    return row is not None


async def add_admin(
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
    username: str | None = None,
) -> None:
    await pool.execute(
        """
        INSERT INTO admins (telegram_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_id) DO UPDATE
            SET is_active  = TRUE,
                username   = EXCLUDED.username,
                first_name = EXCLUDED.first_name
        """,
        telegram_id,
        username,
        first_name,
    )

"""
Репозиторий для таблицы bot_settings (key-value).
"""

from __future__ import annotations

import asyncpg


async def get_setting(pool: asyncpg.Pool, key: str, default: str = "") -> str:
    row = await pool.fetchrow(
        "SELECT value FROM bot_settings WHERE key = $1", key
    )
    return row["value"] if row else default


async def set_setting(pool: asyncpg.Pool, key: str, value: str) -> None:
    await pool.execute(
        """
        INSERT INTO bot_settings (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        key, value,
    )

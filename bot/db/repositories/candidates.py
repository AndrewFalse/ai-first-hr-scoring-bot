"""
Репозиторий для таблицы candidates.
"""

from __future__ import annotations

import asyncpg


async def get_active_session(
    pool: asyncpg.Pool, telegram_id: int
) -> asyncpg.Record | None:
    """Возвращает текущую сессию in_progress, если есть."""
    return await pool.fetchrow(
        "SELECT * FROM candidates WHERE telegram_id = $1 AND status = 'in_progress'",
        telegram_id,
    )


async def get_last_scored_session(
    pool: asyncpg.Pool, telegram_id: int
) -> asyncpg.Record | None:
    """Возвращает последнюю завершённую сессию, если есть."""
    return await pool.fetchrow(
        """
        SELECT * FROM candidates
        WHERE telegram_id = $1 AND status = 'scored'
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        telegram_id,
    )


async def create_candidate(
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
    last_name: str | None = None,
    patronymic: str | None = None,
    username: str | None = None,
) -> int:
    """Создаёт новую запись кандидата, возвращает id."""
    row = await pool.fetchrow(
        """
        INSERT INTO candidates (telegram_id, username, first_name, last_name, patronymic)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        telegram_id,
        username,
        first_name,
        last_name,
        patronymic,
    )
    return row["id"]


async def set_phone(pool: asyncpg.Pool, candidate_id: int, phone: str) -> None:
    await pool.execute(
        "UPDATE candidates SET phone_number = $1 WHERE id = $2",
        phone,
        candidate_id,
    )


async def delete_sessions(pool: asyncpg.Pool, telegram_id: int) -> int:
    """Удаляет все сессии кандидата (CASCADE удаляет ответы, скоринг и пр.).
    Возвращает количество удалённых строк."""
    result = await pool.execute(
        "DELETE FROM candidates WHERE telegram_id = $1",
        telegram_id,
    )
    # asyncpg возвращает строку вида "DELETE N"
    return int(result.split()[-1])


async def set_source(pool: asyncpg.Pool, candidate_id: int, source: str) -> None:
    """source: 'hh' | 'telegram' | 'other'"""
    await pool.execute(
        "UPDATE candidates SET source = $1 WHERE id = $2",
        source,
        candidate_id,
    )


async def mark_scored(pool: asyncpg.Pool, candidate_id: int) -> None:
    await pool.execute(
        """
        UPDATE candidates
        SET status = 'scored', finished_at = NOW()
        WHERE id = $1
        """,
        candidate_id,
    )


async def get_by_id(
    pool: asyncpg.Pool, candidate_id: int
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT * FROM candidates WHERE id = $1", candidate_id
    )


async def get_screening_stats(pool: asyncpg.Pool) -> asyncpg.Record:
    """Статистика прошедших скрининг для админ-панели."""
    return await pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'scored')                                              AS total,
            COUNT(*) FILTER (WHERE status = 'scored' AND DATE(finished_at) = CURRENT_DATE)        AS today,
            COUNT(*) FILTER (WHERE status = 'scored' AND finished_at >= NOW() - INTERVAL '7 days') AS week
        FROM candidates
        """
    )


async def reset_candidates(pool: asyncpg.Pool) -> None:
    """Удаляет всех кандидатов (CASCADE удалит ответы, скоринг, GitHub-данные)."""
    await pool.execute("DELETE FROM candidates")


async def get_stats(pool: asyncpg.Pool) -> asyncpg.Record:
    """Возвращает агрегированную статистику для админ-панели."""
    return await pool.fetchrow(
        """
        SELECT
            COUNT(*)                                    AS total,
            COUNT(*) FILTER (WHERE status = 'scored')  AS scored_count,
            ROUND(AVG(sr.total_score), 1)               AS avg_score,
            COUNT(*) FILTER (WHERE sr.is_hot = TRUE)   AS hot_count
        FROM candidates c
        LEFT JOIN scoring_results sr ON sr.candidate_id = c.id
        """
    )


async def get_top_candidates(
    pool: asyncpg.Pool, limit: int = 3
) -> list[asyncpg.Record]:
    """Топ кандидатов по total_score."""
    return await pool.fetch(
        """
        SELECT c.id, c.first_name, c.last_name, sr.total_score, sr.summary, sr.is_hot
        FROM candidates c
        JOIN scoring_results sr ON sr.candidate_id = c.id
        ORDER BY sr.total_score DESC
        LIMIT $1
        """,
        limit,
    )

"""
Репозиторий для таблицы question_analyses.
Хранит per-question фидбэк и флаг уточняющего вопроса.
"""

from __future__ import annotations

import asyncpg


async def insert_question_analysis(
    pool: asyncpg.Pool,
    candidate_id: int,
    question_seq: int,
    feedback_text: str,
    needs_followup: bool,
    followup_text: str | None,
) -> None:
    await pool.execute(
        """
        INSERT INTO question_analyses
            (candidate_id, question_seq, feedback_text, needs_followup, followup_text)
        VALUES ($1, $2, $3, $4, $5)
        """,
        candidate_id,
        question_seq,
        feedback_text,
        needs_followup,
        followup_text,
    )


async def get_pending_followups(
    pool: asyncpg.Pool, candidate_id: int
) -> list[asyncpg.Record]:
    """Возвращает записи с needs_followup=True, отсортированные по question_seq."""
    return await pool.fetch(
        """
        SELECT question_seq, feedback_text, followup_text
        FROM question_analyses
        WHERE candidate_id = $1 AND needs_followup = TRUE
        ORDER BY question_seq
        """,
        candidate_id,
    )


async def count_completed(pool: asyncpg.Pool, candidate_id: int) -> int:
    """Количество завершённых анализов для кандидата."""
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM question_analyses WHERE candidate_id = $1",
        candidate_id,
    )
    return row["cnt"]

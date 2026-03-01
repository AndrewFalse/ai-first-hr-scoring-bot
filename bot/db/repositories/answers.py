"""
Репозиторий для таблицы candidate_answers.
"""

from __future__ import annotations

import asyncpg


async def add_question(
    pool: asyncpg.Pool,
    candidate_id: int,
    seq_number: int,
    question_text: str,
    is_adaptive: bool = False,
) -> int:
    """Вставляет вопрос (без ответа), возвращает id строки."""
    row = await pool.fetchrow(
        """
        INSERT INTO candidate_answers (candidate_id, seq_number, question_text, is_adaptive)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        candidate_id,
        seq_number,
        question_text,
        is_adaptive,
    )
    return row["id"]


async def set_answer(
    pool: asyncpg.Pool, answer_id: int, answer_text: str
) -> None:
    """Обновляет ответ по id строки."""
    await pool.execute(
        """
        UPDATE candidate_answers
        SET answer_text = $1, answered_at = NOW()
        WHERE id = $2
        """,
        answer_text,
        answer_id,
    )


async def get_answers(
    pool: asyncpg.Pool, candidate_id: int
) -> list[asyncpg.Record]:
    """Возвращает все вопросы + ответы сессии, отсортированные по seq_number."""
    return await pool.fetch(
        """
        SELECT seq_number, question_text, answer_text, is_adaptive, answered_at
        FROM candidate_answers
        WHERE candidate_id = $1
        ORDER BY seq_number
        """,
        candidate_id,
    )


async def get_next_seq_number(pool: asyncpg.Pool, candidate_id: int) -> int:
    """Возвращает следующий порядковый номер вопроса."""
    row = await pool.fetchrow(
        "SELECT COALESCE(MAX(seq_number), 0) + 1 AS next FROM candidate_answers WHERE candidate_id = $1",
        candidate_id,
    )
    return row["next"]


async def get_unanswered_question(
    pool: asyncpg.Pool, candidate_id: int
) -> asyncpg.Record | None:
    """Возвращает первый вопрос без ответа (для восстановления сессии)."""
    return await pool.fetchrow(
        """
        SELECT id, seq_number, question_text, is_adaptive
        FROM candidate_answers
        WHERE candidate_id = $1 AND answer_text IS NULL
        ORDER BY seq_number
        LIMIT 1
        """,
        candidate_id,
    )


async def count_answered_base(pool: asyncpg.Pool, candidate_id: int) -> int:
    """Считает количество отвеченных базовых (не адаптивных) вопросов."""
    row = await pool.fetchrow(
        """
        SELECT COUNT(*) AS cnt
        FROM candidate_answers
        WHERE candidate_id = $1 AND is_adaptive = FALSE AND answer_text IS NOT NULL
        """,
        candidate_id,
    )
    return row["cnt"]

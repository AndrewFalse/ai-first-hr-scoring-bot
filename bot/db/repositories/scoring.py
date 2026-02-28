"""
Репозиторий для таблиц scoring_results и followup_questions.
"""

from __future__ import annotations

import asyncpg


async def insert_scoring_result(
    pool: asyncpg.Pool,
    candidate_id: int,
    delegation_score: int,
    delegation_reasoning: str,
    delegation_quote: str,
    decomposition_score: int,
    decomposition_reasoning: str,
    decomposition_quote: str,
    criticality_score: int,
    criticality_reasoning: str,
    criticality_quote: str,
    total_score: int,
    summary: str,
    is_hot: bool,
) -> int:
    row = await pool.fetchrow(
        """
        INSERT INTO scoring_results (
            candidate_id,
            delegation_score, delegation_reasoning, delegation_quote,
            decomposition_score, decomposition_reasoning, decomposition_quote,
            criticality_score, criticality_reasoning, criticality_quote,
            total_score, summary, is_hot
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
        )
        RETURNING id
        """,
        candidate_id,
        delegation_score, delegation_reasoning, delegation_quote,
        decomposition_score, decomposition_reasoning, decomposition_quote,
        criticality_score, criticality_reasoning, criticality_quote,
        total_score, summary, is_hot,
    )
    return row["id"]


async def insert_followup_questions(
    pool: asyncpg.Pool,
    candidate_id: int,
    questions: list[dict],
) -> None:
    """
    questions: [{"question_text": str, "rationale": str}, ...]
    seq_number присваивается автоматически начиная с 1.
    """
    await pool.executemany(
        """
        INSERT INTO followup_questions (candidate_id, seq_number, question_text, rationale)
        VALUES ($1, $2, $3, $4)
        """,
        [
            (candidate_id, idx + 1, q["question_text"], q["rationale"])
            for idx, q in enumerate(questions)
        ],
    )


async def get_scoring_result(
    pool: asyncpg.Pool, candidate_id: int
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT * FROM scoring_results WHERE candidate_id = $1", candidate_id
    )


async def get_followup_questions(
    pool: asyncpg.Pool, candidate_id: int
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT seq_number, question_text, rationale
        FROM followup_questions
        WHERE candidate_id = $1
        ORDER BY seq_number
        """,
        candidate_id,
    )

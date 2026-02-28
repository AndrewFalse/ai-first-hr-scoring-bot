"""
Репозиторий для таблицы scoring_results.
"""

from __future__ import annotations

import asyncpg


async def insert_scoring_result(
    pool: asyncpg.Pool,
    candidate_id: int,
    task_decomposition_score: int,
    task_decomposition_reasoning: str,
    prompting_tools_score: int,
    prompting_tools_reasoning: str,
    critical_thinking_score: int,
    critical_thinking_reasoning: str,
    total_score: int,
    summary: str,
    recommendation: str,
    is_hot: bool,
) -> int:
    row = await pool.fetchrow(
        """
        INSERT INTO scoring_results (
            candidate_id,
            task_decomposition_score, task_decomposition_reasoning,
            prompting_tools_score, prompting_tools_reasoning,
            critical_thinking_score, critical_thinking_reasoning,
            total_score, summary, recommendation, is_hot
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
        )
        RETURNING id
        """,
        candidate_id,
        task_decomposition_score, task_decomposition_reasoning,
        prompting_tools_score, prompting_tools_reasoning,
        critical_thinking_score, critical_thinking_reasoning,
        total_score, summary, recommendation, is_hot,
    )
    return row["id"]


async def get_scoring_result(
    pool: asyncpg.Pool, candidate_id: int
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT * FROM scoring_results WHERE candidate_id = $1", candidate_id
    )

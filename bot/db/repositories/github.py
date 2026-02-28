"""
Репозиторий для таблицы github_analyses.
"""

from __future__ import annotations

import datetime

import asyncpg


async def upsert_github_analysis(
    pool: asyncpg.Pool,
    candidate_id: int,
    repo_url: str,
    has_readme: bool,
    commit_count: int,
    primary_language: str | None,
    last_commit_at: datetime.datetime | None,
    readme_snippet: str | None,
) -> None:
    await pool.execute(
        """
        INSERT INTO github_analyses
            (candidate_id, repo_url, has_readme, commit_count, primary_language,
             last_commit_at, readme_snippet, fetched_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (candidate_id) DO UPDATE
            SET repo_url         = EXCLUDED.repo_url,
                has_readme       = EXCLUDED.has_readme,
                commit_count     = EXCLUDED.commit_count,
                primary_language = EXCLUDED.primary_language,
                last_commit_at   = EXCLUDED.last_commit_at,
                readme_snippet   = EXCLUDED.readme_snippet,
                fetched_at       = NOW()
        """,
        candidate_id,
        repo_url,
        has_readme,
        commit_count,
        primary_language,
        last_commit_at,
        readme_snippet,
    )


async def get_github_analysis(
    pool: asyncpg.Pool, candidate_id: int
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT * FROM github_analyses WHERE candidate_id = $1", candidate_id
    )

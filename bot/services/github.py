"""
Сервис для работы с GitHub API.
Валидация ссылок и извлечение сигналов из репозитория.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from github import Github, GithubException, UnknownObjectException

from bot.config import settings

logger = logging.getLogger(__name__)

_REPO_RE = re.compile(r"github\.com/([^/]+)/([^/\s?#]+)")


def _parse_owner_repo(url: str) -> tuple[str, str] | None:
    m = _REPO_RE.search(url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    repo = repo.removesuffix(".git")
    return owner, repo


class GitHubService:
    """Извлечение данных из GitHub-репозитория кандидата."""

    def __init__(self) -> None:
        token = settings.GITHUB_TOKEN
        # Ignore placeholder / empty tokens — fall back to anonymous (60 req/h)
        if token and not token.startswith("your_"):
            self._gh = Github(token)
        else:
            self._gh = Github()
            if token:
                logger.warning("GITHUB_TOKEN looks like a placeholder, using anonymous access")

    def _validate_url_sync(self, url: str) -> tuple[bool, str]:
        parsed = _parse_owner_repo(url)
        if not parsed:
            return False, "Не удалось распознать owner/repo из ссылки."
        owner, repo_name = parsed
        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            if repo.private:
                return False, "Репозиторий приватный."
            return True, ""
        except UnknownObjectException:
            return False, "Репозиторий не найден."
        except GithubException as e:
            logger.warning("GitHub API error for %s: status=%s data=%s", url, e.status, e.data)
            return False, f"GitHub API error: {e.status}"
        except Exception as e:
            logger.exception("GitHub validate_url failed for %s", url)
            return False, str(e)

    def _get_repo_data_sync(self, url: str) -> dict[str, Any] | None:
        parsed = _parse_owner_repo(url)
        if not parsed:
            return None
        owner, repo_name = parsed
        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")

            # README
            has_readme = False
            readme_snippet = None
            try:
                readme = repo.get_readme()
                has_readme = True
                content = readme.decoded_content.decode("utf-8", errors="ignore")
                readme_snippet = content[:500].strip()
            except UnknownObjectException:
                pass

            # Commit count (first page, capped at 100 to avoid rate limits)
            try:
                commits = repo.get_commits()
                commit_count = commits.totalCount
            except GithubException:
                commit_count = 0

            # Last commit date
            last_commit_at = None
            try:
                last = repo.get_commits()[0]
                last_commit_at = last.commit.committer.date
            except (GithubException, IndexError):
                pass

            return {
                "repo_url": repo.html_url,
                "has_readme": has_readme,
                "commit_count": commit_count,
                "primary_language": repo.language,
                "last_commit_at": last_commit_at,
                "readme_snippet": readme_snippet,
            }
        except Exception:
            logger.exception("GitHub get_repo_data failed for %s", url)
            return None

    async def validate_url(self, url: str) -> tuple[bool, str]:
        """Валидация GitHub-ссылки. Возвращает (is_valid, error_message)."""
        return await asyncio.to_thread(self._validate_url_sync, url)

    async def get_repo_data(self, url: str) -> dict[str, Any] | None:
        """
        Извлечение сигналов из репозитория:
        README, количество коммитов, основной язык, дата последнего коммита.
        """
        return await asyncio.to_thread(self._get_repo_data_sync, url)

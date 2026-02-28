"""
Сервис для работы с GitHub API.
Валидация ссылок и извлечение сигналов из репозитория.
"""

from typing import Any

from bot.config import settings


class GitHubService:
    """Извлечение данных из GitHub-репозитория кандидата."""

    def __init__(self) -> None:
        # TODO: инициализация PyGithub клиента
        pass

    async def validate_url(self, url: str) -> tuple[bool, str]:
        """
        Валидация GitHub-ссылки.
        Возвращает (is_valid, error_message).
        """
        # TODO: проверить формат URL, доступность репо
        pass

    async def get_repo_data(self, url: str) -> dict[str, Any]:
        """
        Извлечение сигналов из репозитория:
        - README (наличие и содержание)
        - количество коммитов
        - основной язык
        - дата последнего коммита
        """
        # TODO: запросы к GitHub API
        pass

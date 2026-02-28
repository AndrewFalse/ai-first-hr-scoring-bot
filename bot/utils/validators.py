"""
Валидаторы входных данных: ссылки, текст ответов.
"""

import re

GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$"
)


def is_valid_github_url(url: str) -> bool:
    """Проверка, что строка — корректная ссылка на GitHub-репозиторий."""
    return bool(GITHUB_URL_PATTERN.match(url.strip()))


def is_meaningful_answer(text: str, min_length: int = 20) -> bool:
    """Проверка, что ответ кандидата не слишком короткий."""
    return len(text.strip()) >= min_length

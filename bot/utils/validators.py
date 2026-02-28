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


_FULL_NAME_RE = re.compile(
    r'^[A-Za-zА-ЯЁа-яё][a-zA-ZА-Яа-яёЁ\-]+'
    r'(\s+[A-Za-zА-ЯЁа-яё][a-zA-ZА-Яа-яёЁ\-]+){1,2}$'
)


def is_valid_full_name(text: str) -> bool:
    """Проверка, что строка содержит корректное ФИО (минимум фамилия + имя).
    Допускается ввод строчными буквами — нормализация происходит в parse_full_name."""
    return bool(_FULL_NAME_RE.match(text.strip()))


def parse_full_name(text: str) -> tuple[str, str, str | None]:
    """Разбивает ФИО на части, приводит каждое слово к Title Case.
    Возвращает (фамилия, имя, отчество | None)."""
    parts = [p.title() for p in text.strip().split()]
    return parts[0], parts[1], parts[2] if len(parts) > 2 else None

"""
Загрузчик текстовых сообщений для хендлеров.

Формат файла: секции начинаются с '## KEY' на отдельной строке.
Пример:

    ## WELCOME
    Привет! Добро пожаловать...

    ## FAREWELL
    Спасибо за уделённое время!
"""

from pathlib import Path


def load_messages(path: Path) -> dict[str, str]:
    """Парсит файл с секциями ## KEY и возвращает словарь {key: text}."""
    content = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections

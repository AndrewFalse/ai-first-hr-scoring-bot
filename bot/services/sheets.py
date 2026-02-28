"""
Сервис для работы с Google Sheets API.
Экспорт результатов скрининга.
"""

from typing import Any

from bot.config import settings


class SheetsService:
    """Экспорт данных кандидатов в Google Sheets."""

    def __init__(self) -> None:
        # TODO: инициализация gspread клиента
        pass

    async def export_candidate(self, candidate_data: dict[str, Any]) -> None:
        """Запись данных одного кандидата в таблицу."""
        # TODO: добавить строку в Google Sheet
        pass

    async def export_all(self, candidates: list[dict[str, Any]]) -> str:
        """
        Выгрузка всех кандидатов.
        Возвращает ссылку на Google Sheet.
        """
        # TODO: массовая запись
        pass

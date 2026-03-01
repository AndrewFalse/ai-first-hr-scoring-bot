"""
Сервис для работы с Google Sheets API.
Автоматический экспорт результатов скрининга после каждого собеседования.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from bot.config import settings

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Дата",
    "Telegram ID", "Username", "Имя", "Фамилия", "Отчество", "Телефон", "Источник",
    # Базовые вопросы (5 шт.)
    "Вопрос 1", "Ответ 1",
    "Вопрос 2", "Ответ 2",
    "Вопрос 3", "Ответ 3",
    "Вопрос 4", "Ответ 4",
    "Вопрос 5", "Ответ 5",
    # Уточняющие вопросы (до 2)
    "Уточн. вопрос 1", "Уточн. ответ 1",
    "Уточн. вопрос 2", "Уточн. ответ 2",
    # Скоринг (без рекомендации)
    "Декомпозиция (балл)", "Декомпозиция (коммент)",
    "Промптинг+инструменты (балл)", "Промптинг+инструменты (коммент)",
    "Критическое мышление (балл)", "Критическое мышление (коммент)",
    "Итого", "Описание кандидата",
    # GitHub
    "GitHub URL", "Язык", "Коммитов", "Описание GitHub",
    # Вопросы для живого интервью (одна ячейка)
    "Потенциальные вопросы для собеседования",
]


class SheetsService:
    """Экспорт данных кандидатов в Google Sheets."""

    def __init__(self) -> None:
        self._enabled = bool(settings.GOOGLE_CREDENTIALS_JSON and settings.GOOGLE_SHEET_ID)
        if not self._enabled:
            logger.warning("Google Sheets not configured — export disabled")

    def _get_client(self) -> gspread.Client:
        creds_dict = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        return gspread.authorize(credentials)

    def _append_sync(self, row: list) -> None:
        gc = self._get_client()
        sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
        ws = sh.sheet1
        # Добавить заголовки если лист пуст
        if not ws.get_all_values():
            ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def export_candidate(self, row: list) -> None:
        """Добавляет строку с данными кандидата в Google Sheet."""
        if not self._enabled:
            return
        try:
            await asyncio.to_thread(self._append_sync, row)
            logger.info("Google Sheets export successful")
        except Exception:
            logger.exception("Google Sheets export failed")

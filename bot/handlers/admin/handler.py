"""
Хэндлеры админа: авторизация, просмотр кандидатов, экспорт.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.utils.messages import load_messages

_MSG_PATH = Path(__file__).parent / "messages.txt"
MSG = load_messages(_MSG_PATH)

router = Router(name="admin")


@router.message(Command("init_admin"))
async def cmd_init_admin(
    message: Message, db_pool: asyncpg.Pool
) -> None:
    """Первичная регистрация админа по одноразовому токену."""
    # TODO: проверить secret_key, добавить user_id в whitelist
    pass


@router.message(F.text.startswith("/admin_"))
async def cmd_admin(
    message: Message, db_pool: asyncpg.Pool
) -> None:
    """Вход в админ-панель по secret-хешу."""
    # TODO: проверить хеш + user_id, показать дашборд (MSG["DASHBOARD"])
    pass


@router.message(Command("top"))
async def cmd_top(
    message: Message, db_pool: asyncpg.Pool
) -> None:
    """Топ-3 кандидата с кратким объяснением."""
    # TODO: достать топ кандидатов из хранилища, отформатировать MSG["TOP_CANDIDATE"]
    pass


@router.message(Command("candidate"))
async def cmd_candidate(
    message: Message, db_pool: asyncpg.Pool
) -> None:
    """Полная карточка кандидата: ответы + reasoning."""
    # TODO: показать подробную информацию по ID (MSG["CANDIDATE_CARD"])
    pass


@router.message(Command("export"))
async def cmd_export(
    message: Message, db_pool: asyncpg.Pool
) -> None:
    """Выгрузка результатов в Google Sheet."""
    # TODO: вызвать SheetsService.export(), показать MSG["EXPORT_SUCCESS"]
    pass

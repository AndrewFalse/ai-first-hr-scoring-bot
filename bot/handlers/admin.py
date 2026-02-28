"""
Хэндлеры админа: авторизация, просмотр кандидатов, экспорт.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from bot.utils.auth import is_admin

router = Router(name="admin")


@router.message(Command("init_admin"))
async def cmd_init_admin(message: Message) -> None:
    """Первичная регистрация админа по одноразовому токену."""
    # TODO: проверить secret_key, добавить user_id в whitelist
    pass


@router.message(F.text.startswith("/admin_"))
async def cmd_admin(message: Message) -> None:
    """Вход в админ-панель по secret-хешу."""
    # TODO: проверить хеш + user_id, показать дашборд
    pass


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    """Топ-3 кандидата с кратким объяснением."""
    # TODO: достать топ кандидатов из хранилища
    pass


@router.message(Command("candidate"))
async def cmd_candidate(message: Message) -> None:
    """Полная карточка кандидата: ответы + reasoning."""
    # TODO: показать подробную информацию по ID
    pass


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    """Выгрузка результатов в Google Sheet."""
    # TODO: вызвать SheetsService.export()
    pass

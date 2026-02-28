"""
Хэндлеры админа: авторизация, просмотр кандидатов, экспорт.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.states import AdminStates
from bot.services.voice import VoiceService
from bot.utils.messages import load_messages

_MSG_PATH = Path(__file__).parent / "messages.txt"
MSG = load_messages(_MSG_PATH)

_voice = VoiceService()

router = Router(name="admin")


@router.message(Command("test_voice"))
async def cmd_test_voice(
    message: Message, state: FSMContext
) -> None:
    """Тест транскрибации: ожидаем голосовое от администратора."""
    await state.set_state(AdminStates.waiting_voice_test)
    await message.answer("Отправь голосовое сообщение — я покажу транскрипцию.")


@router.message(AdminStates.waiting_voice_test, F.voice)
async def process_voice_test(
    message: Message, state: FSMContext
) -> None:
    """Транскрибирует голосовое и возвращает результат."""
    await state.clear()
    status = await message.answer("⏳ Транскрибирую...")
    audio = await message.bot.download(message.voice.file_id)
    result = await _voice.transcribe(audio, filename=f"voice_{message.voice.file_unique_id}.ogg")
    await status.delete()
    if result:
        await message.answer(f"<b>Транскрипция:</b>\n\n{result}", parse_mode="HTML")
    else:
        await message.answer("❌ Транскрибация не удалась. Проверь настройки OPENROUTER_AUDIO_MODEL.")


@router.message(AdminStates.waiting_voice_test)
async def process_voice_test_wrong(
    message: Message, state: FSMContext
) -> None:
    """Напоминает отправить именно голосовое."""
    await message.answer("Нужно голосовое сообщение. Отправь его или /cancel для отмены.")


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, state: FSMContext
) -> None:
    await state.clear()
    await message.answer("Отменено.")


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

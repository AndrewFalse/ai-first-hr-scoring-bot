"""
Хэндлеры админа: авторизация, панель управления, топ-3, порог уведомлений, сброс БД.
"""

from __future__ import annotations

import asyncpg
from aiogram import Router, F
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import settings
from bot.db.repositories import admins as admins_repo
from bot.db.repositories import candidates as candidates_repo
from bot.db.repositories import settings as settings_repo
from bot.handlers.states import AdminStates
from bot.services.voice import VoiceService

_voice = VoiceService()
router = Router(name="admin")


# ---------------------------------------------------------------------------
# Фильтр: только зарегистрированные администраторы
# ---------------------------------------------------------------------------

class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, db_pool: asyncpg.Pool) -> bool:
        return await admins_repo.is_admin(db_pool, message.from_user.id)


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Топ-3 кандидата", callback_data="admin:top3"),
            InlineKeyboardButton(text="⚙️ Изменить порог", callback_data="admin:set_threshold"),
        ],
        [
            InlineKeyboardButton(text="🗑 Сбросить базу данных", callback_data="admin:reset_db"),
        ],
    ])


def _confirm_reset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, сбросить", callback_data="admin:confirm_reset"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel"),
    ]])


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Назад", callback_data="admin:back"),
    ]])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

async def _dashboard_text(db_pool: asyncpg.Pool) -> str:
    stats = await candidates_repo.get_screening_stats(db_pool)
    threshold = await settings_repo.get_setting(db_pool, "hot_threshold", "7.0")
    avg = stats["avg_score"] if stats["avg_score"] is not None else "—"
    return (
        "👑 <b>Панель администратора</b>\n\n"
        "📊 <b>Прошло скрининг:</b>\n"
        f"• Всего: <b>{stats['total']}</b>\n"
        f"• Сегодня: <b>{stats['today']}</b>\n"
        f"• За 7 дней: <b>{stats['week']}</b>\n"
        f"• Средний балл: <b>{avg}/10</b>\n\n"
        f"⚙️ Порог уведомлений: <b>{threshold}/10</b>"
    )


# ---------------------------------------------------------------------------
# /admin <пароль>
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def cmd_admin(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    if not settings.ADMIN_SECRET:
        await message.answer("❌ ADMIN_SECRET не настроен в .env.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() != settings.ADMIN_SECRET:
        await message.answer("❌ Неверный пароль.")
        return

    await admins_repo.add_admin(
        db_pool,
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username,
    )
    await state.set_state(AdminStates.dashboard)
    await message.answer(
        await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


# ---------------------------------------------------------------------------
# /start для администратора
# ---------------------------------------------------------------------------

@router.message(CommandStart(), IsAdmin())
async def cmd_start_admin(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    await state.set_state(AdminStates.dashboard)
    await message.answer(
        await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


# ---------------------------------------------------------------------------
# /candidate — выход из режима администратора
# ---------------------------------------------------------------------------

@router.message(Command("candidate"))
async def cmd_switch_to_candidate(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    await admins_repo.deactivate_admin(db_pool, message.from_user.id)
    await state.clear()
    await message.answer(
        "Переключился в режим кандидата. Напиши /start чтобы начать скрининг."
    )


# ---------------------------------------------------------------------------
# Кнопка «Топ-3 кандидата»
# ---------------------------------------------------------------------------

@router.callback_query(AdminStates.dashboard, F.data == "admin:top3")
async def show_top3(callback: CallbackQuery, db_pool: asyncpg.Pool) -> None:
    await callback.answer()
    top = await candidates_repo.get_top_candidates(db_pool, limit=3)

    if not top:
        await callback.message.edit_text(
            "Пока нет кандидатов с результатами.",
            reply_markup=_back_keyboard(),
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["📋 <b>Топ-3 кандидата</b>\n"]
    for i, c in enumerate(top):
        name = f"{c['first_name']} {c['last_name'] or ''}".strip()
        contact = f"@{c['username']}" if c["username"] else name
        phone = c["phone_number"] or "не указан"
        avg = round(c["total_score"] / 3, 1)
        summary = (c["summary"] or "")[:120]
        lines.append(
            f"{medals[i]} <b>{contact}</b> | {phone} | <b>{avg}/10</b>\n"
            f"   <i>{summary}</i>"
        )

    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=_back_keyboard(),
    )


# ---------------------------------------------------------------------------
# Кнопка «Изменить порог»
# ---------------------------------------------------------------------------

@router.callback_query(AdminStates.dashboard, F.data == "admin:set_threshold")
async def prompt_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.setting_threshold)
    await callback.message.edit_text(
        "⚙️ Введи новый порог уведомлений (от <b>0.0</b> до <b>10.0</b>):\n\n"
        "Кандидаты со средним баллом ≥ порога будут отправляться в чат рекрутеров.",
        reply_markup=_back_keyboard(),
    )


@router.message(AdminStates.setting_threshold, F.text)
async def save_threshold(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    try:
        value = round(float(message.text.replace(",", ".")), 1)
        if not (0.0 <= value <= 10.0):
            raise ValueError
    except ValueError:
        await message.answer("Введи число от 0.0 до 10.0 (например: 7.5)")
        return

    await settings_repo.set_setting(db_pool, "hot_threshold", str(value))
    await state.set_state(AdminStates.dashboard)
    await message.answer(
        f"✅ Порог установлен: <b>{value}/10</b>\n\n"
        + await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


# ---------------------------------------------------------------------------
# Кнопка «Назад»
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin:back")
async def go_back(callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool) -> None:
    await callback.answer()
    await state.set_state(AdminStates.dashboard)
    await callback.message.edit_text(
        await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


# ---------------------------------------------------------------------------
# Кнопка «Сбросить БД»
# ---------------------------------------------------------------------------

@router.callback_query(AdminStates.dashboard, F.data == "admin:reset_db")
async def reset_db_prompt(callback: CallbackQuery, db_pool: asyncpg.Pool) -> None:
    if not await admins_repo.is_admin(db_pool, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ <b>Удалить всех кандидатов?</b>\n\n"
        "Сессии, ответы и результаты скоринга будут удалены.\n"
        "Данные в Google Sheets сохранятся.",
        reply_markup=_confirm_reset_keyboard(),
    )


@router.callback_query(AdminStates.dashboard, F.data == "admin:cancel")
async def cancel_reset(callback: CallbackQuery, db_pool: asyncpg.Pool) -> None:
    await callback.answer()
    await callback.message.edit_text(
        await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


@router.callback_query(AdminStates.dashboard, F.data == "admin:confirm_reset")
async def confirm_reset(callback: CallbackQuery, db_pool: asyncpg.Pool) -> None:
    if not await admins_repo.is_admin(db_pool, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await candidates_repo.reset_candidates(db_pool)
    await callback.message.edit_text(
        "✅ <b>База данных очищена.</b>\n\n"
        + await _dashboard_text(db_pool),
        reply_markup=_dashboard_keyboard(),
    )


# ---------------------------------------------------------------------------
# /test_voice — тест транскрибации
# ---------------------------------------------------------------------------

@router.message(Command("test_voice"))
async def cmd_test_voice(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_voice_test)
    await message.answer("Отправь голосовое сообщение — я покажу транскрипцию.")


@router.message(AdminStates.waiting_voice_test, F.voice)
async def process_voice_test(message: Message, state: FSMContext) -> None:
    await state.clear()
    status = await message.answer("⏳ Транскрибирую...")
    audio = await message.bot.download(message.voice.file_id)
    result = await _voice.transcribe(audio, filename=f"voice_{message.voice.file_unique_id}.ogg")
    await status.delete()
    if result:
        await message.answer(f"<b>Транскрипция:</b>\n\n{result}")
    else:
        await message.answer("❌ Транскрибация не удалась.")


@router.message(AdminStates.waiting_voice_test)
async def process_voice_test_wrong(message: Message) -> None:
    await message.answer("Нужно голосовое сообщение.")

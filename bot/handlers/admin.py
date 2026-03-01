"""
Хэндлеры админа: авторизация, панель управления, сброс БД.
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
from bot.handlers.states import AdminStates

router = Router(name="admin")


# ---------------------------------------------------------------------------
# Фильтр: только для зарегистрированных администраторов
# ---------------------------------------------------------------------------

class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, db_pool: asyncpg.Pool) -> bool:
        return await admins_repo.is_admin(db_pool, message.from_user.id)


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Сбросить базу данных", callback_data="admin:reset_db"),
    ]])


def _confirm_reset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, сбросить", callback_data="admin:confirm_reset"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel"),
    ]])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

async def _dashboard_text(db_pool: asyncpg.Pool) -> str:
    stats = await candidates_repo.get_screening_stats(db_pool)
    return (
        "👑 <b>Панель администратора</b>\n\n"
        "📊 <b>Прошло скрининг:</b>\n"
        f"• Всего: <b>{stats['total']}</b>\n"
        f"• Сегодня: <b>{stats['today']}</b>\n"
        f"• За 7 дней: <b>{stats['week']}</b>"
    )


# ---------------------------------------------------------------------------
# /admin <пароль> — вход в панель
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def cmd_admin(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    if not settings.ADMIN_SECRET:
        await message.answer("❌ Пароль администратора не настроен в .env.")
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
# /start для администратора — открывает панель (не кандидатский флоу)
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
async def cmd_switch_to_candidate(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Переключился в режим кандидата. Напиши /start чтобы начать скрининг."
    )


# ---------------------------------------------------------------------------
# Кнопки дашборда
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

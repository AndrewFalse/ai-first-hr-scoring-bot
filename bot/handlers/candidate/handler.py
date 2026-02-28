"""
Хэндлеры кандидата: /start, онбординг, приём ответов, GitHub-ссылка, показ скоринга.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot.db.repositories import answers as answers_repo
from bot.db.repositories import candidates as candidates_repo
from bot.db.repositories import github as github_repo
from bot.db.repositories import scoring as scoring_repo
from bot.handlers.states import CandidateStates
from bot.config import settings
from bot.services.github import GitHubService
from bot.services.llm import LLMService
from bot.utils.messages import load_messages
from bot.utils.validators import is_valid_full_name, parse_full_name

_MSG_PATH = Path(__file__).parent / "messages.txt"
MSG = load_messages(_MSG_PATH)

BASE_QUESTIONS = ["QUESTION_1", "QUESTION_2", "QUESTION_3"]

_SOURCE_LABELS = {"hh": "HeadHunter", "telegram": "Telegram", "other": "Другой источник"}

_VOICE_LIMIT_SECONDS = 120

_llm = LLMService()
_github = GitHubService()

router = Router(name="candidate")


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def _contact_keyboard() -> ReplyKeyboardMarkup:
    """ReplyKeyboard — единственный способ запросить контакт в Telegram."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _source_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="HeadHunter", callback_data="source:hh"),
        InlineKeyboardButton(text="Telegram", callback_data="source:telegram"),
        InlineKeyboardButton(text="Другой источник", callback_data="source:other"),
    ]])


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить номер", callback_data="edit:phone")],
        [
            InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data="edit:name"),
            InlineKeyboardButton(text="✏️ Изменить источник", callback_data="edit:source"),
        ],
        [InlineKeyboardButton(text="✅ Всё верно, продолжить", callback_data="confirm")],
    ])


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Начать интервью", callback_data="start_interview"),
    ]])


def _answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Повторить", callback_data="answer:retry"),
        InlineKeyboardButton(text="➡️ Продолжить", callback_data="answer:confirm"),
    ]])


# ---------------------------------------------------------------------------
# /reset_db  (только для тестирования)
# ---------------------------------------------------------------------------

@router.message(Command("reset_db"))
async def cmd_reset_db(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    """Удаляет все сессии текущего пользователя. Только для тестирования."""
    deleted = await candidates_repo.delete_sessions(db_pool, message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ Сброс выполнен: удалено сессий — {deleted}.\n\nОтправь /start для нового прохождения."
    )


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    telegram_id = message.from_user.id

    scored = await candidates_repo.get_last_scored_session(db_pool, telegram_id)
    if scored:
        await message.answer(MSG["ALREADY_COMPLETED"])
        return

    active = await candidates_repo.get_active_session(db_pool, telegram_id)
    if active:
        await _resume_session(message, state, db_pool, active["id"])
        return

    await state.clear()
    await state.set_state(CandidateStates.waiting_contact)
    await message.answer(MSG["WELCOME"], reply_markup=_contact_keyboard())


# ---------------------------------------------------------------------------
# Онбординг: контакт → ФИО → источник → подтверждение
# ---------------------------------------------------------------------------

@router.message(CandidateStates.waiting_contact, F.contact)
async def process_contact(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    data = await state.get_data()
    if data.get("editing_field") == "phone":
        await state.update_data(editing_field=None)
        await message.answer("Номер обновлён.", reply_markup=ReplyKeyboardRemove())
        await _send_confirm_card(message, state)
        return

    await message.answer(MSG["CONTACT_RECEIVED"], reply_markup=ReplyKeyboardRemove())
    await state.set_state(CandidateStates.waiting_name)


@router.message(CandidateStates.waiting_name)
async def process_name(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    text = message.text.strip()
    if not is_valid_full_name(text):
        await message.answer(MSG["NAME_INVALID"])
        return

    last_name, first_name, patronymic = parse_full_name(text)
    await state.update_data(last_name=last_name, first_name=first_name, patronymic=patronymic)

    data = await state.get_data()
    if data.get("editing_field") == "name":
        await state.update_data(editing_field=None)
        await _send_confirm_card(message, state)
        return

    await message.answer(MSG["SOURCE_QUESTION"], reply_markup=_source_keyboard())
    await state.set_state(CandidateStates.waiting_source)


@router.callback_query(CandidateStates.waiting_source, F.data.startswith("source:"))
async def process_source(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    source = callback.data.split(":")[1]
    await state.update_data(source=source)
    await callback.answer()

    data = await state.get_data()
    if data.get("editing_field") == "source":
        await state.update_data(editing_field=None)
        await callback.message.edit_reply_markup(reply_markup=None)
        await _send_confirm_card(callback.message, state)
        return

    # Первичный выбор источника: превращаем сообщение в карточку подтверждения
    full_name = data["last_name"] + " " + data["first_name"]
    if data.get("patronymic"):
        full_name += " " + data["patronymic"]
    text = MSG["CONFIRM_DATA"].format(
        full_name=full_name,
        phone=data["phone"],
        source=_SOURCE_LABELS[source],
    )
    await callback.message.edit_text(text, reply_markup=_confirm_keyboard())
    await state.set_state(CandidateStates.confirming)


@router.callback_query(CandidateStates.confirming, F.data == "confirm")
async def process_confirm(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()

    candidate_id = await candidates_repo.create_candidate(
        db_pool,
        telegram_id=callback.from_user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        patronymic=data.get("patronymic"),
        username=callback.from_user.username,
    )
    await candidates_repo.set_phone(db_pool, candidate_id, data["phone"])
    await candidates_repo.set_source(db_pool, candidate_id, data["source"])

    await callback.message.edit_text(MSG["CONFIRMED"])
    await callback.answer()

    # Показываем инструкцию с кнопкой — вопрос задаётся только после нажатия
    await state.set_state(CandidateStates.pre_interview)
    await state.update_data(candidate_id=candidate_id)
    await callback.message.answer(MSG["INSTRUCTION"], reply_markup=_start_keyboard())


@router.callback_query(CandidateStates.confirming, F.data == "edit:phone")
async def edit_phone(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    await state.update_data(editing_field="phone")
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(CandidateStates.waiting_contact)
    await callback.message.answer(
        "Нажмите кнопку, чтобы поделиться новым номером телефона:",
        reply_markup=_contact_keyboard(),
    )
    await callback.answer()


@router.callback_query(CandidateStates.confirming, F.data == "edit:name")
async def edit_name(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    await state.update_data(editing_field="name")
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(CandidateStates.waiting_name)
    await callback.message.answer("Введите новое ФИО:")
    await callback.answer()


@router.callback_query(CandidateStates.confirming, F.data == "edit:source")
async def edit_source(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    await state.update_data(editing_field="source")
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(CandidateStates.waiting_source)
    await callback.message.answer("Выберите новый источник:", reply_markup=_source_keyboard())
    await callback.answer()


@router.callback_query(CandidateStates.pre_interview, F.data == "start_interview")
async def start_interview(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    candidate_id: int = data["candidate_id"]
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _ask_base_question(callback.message, state, db_pool, candidate_id, question_index=0)


# ---------------------------------------------------------------------------
# Ответы на вопросы (текст или голос)
# ---------------------------------------------------------------------------

@router.message(CandidateStates.answering, F.text | F.voice)
async def process_answer(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    # Голосовое сообщение: проверяем длину
    if message.voice:
        if message.voice.duration > _VOICE_LIMIT_SECONDS:
            await message.answer(MSG["VOICE_TOO_LONG"])
            return
        pending_answer = f"[Голосовое сообщение, {message.voice.duration}с]"
    else:
        pending_answer = message.text

    # Храним ответ в FSM до подтверждения — в БД не пишем
    await state.update_data(pending_answer=pending_answer)
    await message.answer(MSG["ANSWER_RECEIVED"], reply_markup=_answer_keyboard())
    await state.set_state(CandidateStates.confirming_answer)


@router.callback_query(CandidateStates.confirming_answer, F.data == "answer:confirm")
async def confirm_answer(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    candidate_id: int = data["candidate_id"]
    question_index: int = data["question_index"]
    followup_done: bool = data["followup_done"]
    current_answer_id: int = data["current_answer_id"]
    pending_answer: str = data["pending_answer"]
    current_question_text: str = data["current_question_text"]

    # Сохраняем подтверждённый ответ в БД
    await answers_repo.set_answer(db_pool, current_answer_id, pending_answer)

    # Меняем сообщение на подтверждение, убираем кнопки
    await callback.message.edit_text("Ответ записан.")
    await callback.answer()

    if followup_done:
        await _advance_to_next(callback.message, state, db_pool, candidate_id, question_index)
        return

    # Адаптивный анализ через LLM
    history = [
        {"question": row["question_text"], "answer": row["answer_text"]}
        for row in await answers_repo.get_answers(db_pool, candidate_id)
        if row["answer_text"]
    ]
    processing_msg = await callback.message.answer(MSG["PROCESSING"])
    analysis = await _llm.analyze_answer(current_question_text, pending_answer, history)
    await processing_msg.delete()

    if analysis and analysis.get("needs_followup") and analysis.get("followup_question"):
        followup_text: str = analysis["followup_question"]
        seq = await answers_repo.get_next_seq_number(db_pool, candidate_id)
        followup_id = await answers_repo.add_question(
            db_pool, candidate_id, seq, followup_text, is_adaptive=True
        )
        await state.set_state(CandidateStates.answering)
        await state.update_data(
            followup_done=True,
            current_answer_id=followup_id,
            current_question_text=followup_text,
            pending_answer=None,
        )
        await callback.message.answer(followup_text)
        return

    await _advance_to_next(callback.message, state, db_pool, candidate_id, question_index)


@router.callback_query(CandidateStates.confirming_answer, F.data == "answer:retry")
async def retry_answer(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    question_text: str = data["current_question_text"]

    await state.update_data(pending_answer=None)
    await callback.message.edit_text(MSG["ANSWER_RETRY"])
    await callback.answer()

    await callback.message.answer(question_text)
    await state.set_state(CandidateStates.answering)


# ---------------------------------------------------------------------------
# GitHub-ссылка
# ---------------------------------------------------------------------------

@router.message(CandidateStates.waiting_github)
async def process_github_link(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    candidate_id: int = data["candidate_id"]
    url = message.text.strip()

    if "github.com/" not in url:
        await message.answer(MSG["GITHUB_INVALID"])
        return

    validating_msg = await message.answer(MSG["VALIDATING_REPO"])
    is_valid, error_msg = await _github.validate_url(url)
    await validating_msg.delete()

    if not is_valid:
        await message.answer(MSG["GITHUB_NOT_FOUND"])
        return

    github_data = await _github.get_repo_data(url)
    if github_data:
        await github_repo.upsert_github_analysis(
            db_pool,
            candidate_id=candidate_id,
            repo_url=github_data["repo_url"],
            has_readme=github_data["has_readme"],
            commit_count=github_data["commit_count"],
            primary_language=github_data["primary_language"],
            last_commit_at=github_data["last_commit_at"],
            readme_snippet=github_data["readme_snippet"],
        )

    scoring_msg = await message.answer(MSG["SCORING_IN_PROGRESS"])
    answers = await answers_repo.get_answers(db_pool, candidate_id)
    answers_list = [
        {"question": row["question_text"], "answer": row["answer_text"]}
        for row in answers
        if row["answer_text"]
    ]
    scoring = await _llm.generate_scoring(answers_list, github_data)
    await scoring_msg.delete()

    if scoring:
        total = (
            scoring["delegation"]["score"]
            + scoring["decomposition"]["score"]
            + scoring["criticality"]["score"]
        )
        is_hot = total >= settings.HOT_THRESHOLD

        await scoring_repo.insert_scoring_result(
            db_pool,
            candidate_id=candidate_id,
            delegation_score=scoring["delegation"]["score"],
            delegation_reasoning=scoring["delegation"]["reasoning"],
            delegation_quote=scoring["delegation"]["quote"],
            decomposition_score=scoring["decomposition"]["score"],
            decomposition_reasoning=scoring["decomposition"]["reasoning"],
            decomposition_quote=scoring["decomposition"]["quote"],
            criticality_score=scoring["criticality"]["score"],
            criticality_reasoning=scoring["criticality"]["reasoning"],
            criticality_quote=scoring["criticality"]["quote"],
            total_score=total,
            summary=scoring.get("summary", ""),
            is_hot=is_hot,
        )

        await candidates_repo.mark_scored(db_pool, candidate_id)
        await _show_scoring(message, scoring, total)

    await state.set_state(CandidateStates.finished)
    await message.answer(MSG["FAREWELL"])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

async def _send_confirm_card(message: Message, state: FSMContext) -> None:
    """Отправляет новую карточку подтверждения данных с кнопками редактирования."""
    data = await state.get_data()
    full_name = data["last_name"] + " " + data["first_name"]
    if data.get("patronymic"):
        full_name += " " + data["patronymic"]
    text = MSG["CONFIRM_DATA"].format(
        full_name=full_name,
        phone=data["phone"],
        source=_SOURCE_LABELS[data["source"]],
    )
    await message.answer(text, reply_markup=_confirm_keyboard())
    await state.set_state(CandidateStates.confirming)


async def _ask_base_question(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    candidate_id: int,
    question_index: int,
) -> None:
    question_text = MSG[BASE_QUESTIONS[question_index]]
    seq = await answers_repo.get_next_seq_number(db_pool, candidate_id)
    answer_id = await answers_repo.add_question(
        db_pool, candidate_id, seq, question_text, is_adaptive=False
    )
    await state.set_state(CandidateStates.answering)
    await state.set_data({
        "candidate_id": candidate_id,
        "question_index": question_index,
        "followup_done": False,
        "current_answer_id": answer_id,
        "current_question_text": question_text,
        "pending_answer": None,
    })
    await message.answer(question_text)


async def _advance_to_next(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    candidate_id: int,
    question_index: int,
) -> None:
    next_index = question_index + 1
    if next_index < len(BASE_QUESTIONS):
        await _ask_base_question(message, state, db_pool, candidate_id, next_index)
    else:
        await state.set_state(CandidateStates.waiting_github)
        await state.set_data({"candidate_id": candidate_id})
        await message.answer(MSG["GITHUB_REQUEST"])


async def _resume_session(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    candidate_id: int,
) -> None:
    pending = await answers_repo.get_unanswered_question(db_pool, candidate_id)

    if pending:
        answered_base = await answers_repo.count_answered_base(db_pool, candidate_id)
        if pending["is_adaptive"]:
            question_index = answered_base - 1
            followup_done = True
        else:
            question_index = answered_base
            followup_done = False

        await state.set_state(CandidateStates.answering)
        await state.set_data({
            "candidate_id": candidate_id,
            "question_index": question_index,
            "followup_done": followup_done,
            "current_answer_id": pending["id"],
            "current_question_text": pending["question_text"],
            "pending_answer": None,
        })
        await message.answer(MSG["SESSION_RESUMED"])
        await message.answer(pending["question_text"])
        return

    answered_base = await answers_repo.count_answered_base(db_pool, candidate_id)
    if answered_base >= len(BASE_QUESTIONS):
        await state.set_state(CandidateStates.waiting_github)
        await state.set_data({"candidate_id": candidate_id})
        await message.answer(MSG["SESSION_RESUMED"])
        await message.answer(MSG["GITHUB_REQUEST"])


async def _show_scoring(
    message: Message,
    scoring: dict,
    total: int,
) -> None:
    criterion_names = {
        "delegation": "Делегирование AI",
        "decomposition": "Декомпозиция",
        "criticality": "Критичность",
    }

    await message.answer(MSG["SCORING_HEADER"])

    for key, name in criterion_names.items():
        criterion = scoring[key]
        text = MSG["SCORING_CRITERION"].format(
            criterion=name,
            score=criterion["score"],
            reasoning=criterion["reasoning"],
            quote=criterion["quote"],
        )
        await message.answer(text)

    await message.answer(
        MSG["SCORING_TOTAL"].format(
            total=total,
            summary=scoring.get("summary", ""),
        )
    )

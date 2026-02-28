"""
Хэндлеры кандидата: /start, онбординг, приём ответов, GitHub-ссылка, показ скоринга.
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
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
from bot.db.repositories import question_analyses as question_analyses_repo
from bot.db.repositories import scoring as scoring_repo
from bot.handlers.states import CandidateStates, SupportStates
from bot.config import settings
from bot.services.github import GitHubService
from bot.services.llm import LLMService
from bot.services.voice import VoiceService
from bot.utils.messages import load_messages
from bot.utils.validators import is_valid_full_name, parse_full_name

logger = logging.getLogger(__name__)

_MSG_PATH = Path(__file__).parent / "messages.txt"
MSG = load_messages(_MSG_PATH)

BASE_QUESTIONS = ["QUESTION_1", "QUESTION_2", "QUESTION_3", "QUESTION_4", "QUESTION_5"]

# Primary axes evaluated per question (used for follow-up threshold and background analysis)
# New order: pipeline(0), tools(1), IDE(2), prompting(3), product(4)
_PRIMARY_AXES: dict[int, list[str]] = {
    0: ["task_decomposition"],
    1: ["prompting_tools"],
    2: ["prompting_tools"],
    3: ["prompting_tools"],
    4: ["task_decomposition", "critical_thinking"],
}

_SOURCE_LABELS = {"hh": "HeadHunter", "telegram": "Telegram", "other": "Другой источник"}

_VOICE_LIMIT_SECONDS = 120

_llm = LLMService()
_github = GitHubService()
_voice = VoiceService()

# Module-level: background analysis tasks per candidate_id
_analysis_tasks: dict[int, list[asyncio.Task]] = {}

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
        InlineKeyboardButton(text="✏️ Изменить", callback_data="answer:edit"),
        InlineKeyboardButton(text="✅ Отправить", callback_data="answer:submit"),
    ]])


def _github_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="github:skip"),
    ]])


# ---------------------------------------------------------------------------
# /support
# ---------------------------------------------------------------------------

@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportStates.waiting_message)
    await message.answer(MSG["SUPPORT_PROMPT"])


@router.message(SupportStates.waiting_message, F.text)
async def process_support_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not settings.SUPPORT_CHAT_ID:
        await message.answer(MSG["SUPPORT_UNAVAILABLE"])
        return
    user = message.from_user
    username = f"@{user.username}" if user.username else "без username"
    forwarded = (
        f"📨 Обращение в поддержку\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 {user.id}\n\n"
        f"{message.text}"
    )
    await message.bot.send_message(settings.SUPPORT_CHAT_ID, forwarded)
    await message.answer(MSG["SUPPORT_SENT"])


@router.message(SupportStates.waiting_message)
async def process_support_non_text(message: Message, state: FSMContext) -> None:
    await message.answer(MSG["SUPPORT_TEXT_ONLY"])


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

_VOICE_MIN_SECONDS = 5

@router.message(CandidateStates.answering, F.text | F.voice)
async def process_answer(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    if message.voice:
        if message.voice.duration < _VOICE_MIN_SECONDS:
            await message.answer(MSG["VOICE_TOO_SHORT"])
            return
        if message.voice.duration > _VOICE_LIMIT_SECONDS:
            await message.answer(MSG["VOICE_TOO_LONG"])
            return
        transcribing_msg = await message.answer(MSG["VOICE_TRANSCRIBING"])
        audio = await message.bot.download(message.voice.file_id)
        transcription = await _voice.transcribe(
            audio, filename=f"voice_{message.voice.file_unique_id}.ogg"
        )
        await transcribing_msg.delete()
        if not transcription:
            await message.answer(MSG["VOICE_TRANSCRIPTION_FAILED"])
            return
        pending_answer = transcription
        label = "Голосовое распознано:"
    else:
        pending_answer = message.text
        label = "Твой ответ:"

    await state.update_data(pending_answer=pending_answer)
    await message.answer(
        MSG["ANSWER_PREVIEW"].format(label=label, answer=pending_answer),
        reply_markup=_answer_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(CandidateStates.confirming_answer)


@router.callback_query(CandidateStates.confirming_answer, F.data == "answer:submit")
async def confirm_answer(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    candidate_id: int = data["candidate_id"]
    question_index: int = data["question_index"]
    followup_done: bool = data.get("followup_done", False)
    current_answer_id: int = data["current_answer_id"]
    current_seq_number: int = data.get("current_seq_number", 1)
    current_question_text: str = data["current_question_text"]
    pending_answer: str = data["pending_answer"]

    await callback.answer()
    await answers_repo.set_answer(db_pool, current_answer_id, pending_answer)
    await callback.message.edit_text("Ответ принят.")

    is_last_base_question = (question_index == len(BASE_QUESTIONS) - 1) and not followup_done

    if is_last_base_question:
        await _wait_for_analyses_and_ask_followups(
            callback, state, db_pool, candidate_id, question_index,
            pending_answer, current_question_text, current_seq_number,
        )
        return

    if followup_done:
        followup_queue: list[str] = data.get("followup_queue", [])
        if followup_queue:
            fup_text = followup_queue[0]
            remaining = followup_queue[1:]
            seq = await answers_repo.get_next_seq_number(db_pool, candidate_id)
            answer_id = await answers_repo.add_question(
                db_pool, candidate_id, seq, fup_text, is_adaptive=True
            )
            await state.update_data(
                followup_queue=remaining,
                current_answer_id=answer_id,
                current_seq_number=seq,
                current_question_text=fup_text,
                pending_answer=None,
            )
            await state.set_state(CandidateStates.answering)
            await callback.message.answer(fup_text)
            return
        await state.set_state(CandidateStates.waiting_github)
        await state.set_data({"candidate_id": candidate_id})
        await callback.message.answer(MSG["GITHUB_REQUEST"], reply_markup=_github_keyboard())
        return

    # ASYNC PATH for Q1–Q4: fire background analysis, immediately advance to next question
    history = [
        {"question": row["question_text"], "answer": row["answer_text"]}
        for row in await answers_repo.get_answers(db_pool, candidate_id)
        if row["answer_text"]
    ]
    task = asyncio.create_task(
        _background_analyze(
            db_pool=db_pool,
            candidate_id=candidate_id,
            question_seq=current_seq_number,
            question_text=current_question_text,
            answer_text=pending_answer,
            history=history,
            question_index=question_index,
        )
    )
    _analysis_tasks.setdefault(candidate_id, []).append(task)
    task.add_done_callback(
        lambda t, cid=candidate_id: _analysis_tasks[cid].remove(t)
        if t in _analysis_tasks.get(cid, []) else None
    )

    await _advance_to_next(callback.message, state, db_pool, candidate_id, question_index)


@router.callback_query(CandidateStates.confirming_answer, F.data == "answer:edit")
async def edit_answer(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    pending_answer: str = data.get("pending_answer", "")

    await callback.answer()
    await callback.message.edit_text(
        MSG["ANSWER_EDIT"].format(answer=pending_answer),
        parse_mode="HTML",
    )
    await state.set_state(CandidateStates.answering)


# ---------------------------------------------------------------------------
# GitHub-ссылка
# ---------------------------------------------------------------------------

@router.callback_query(CandidateStates.waiting_github, F.data == "github:skip")
async def skip_github(
    callback: CallbackQuery, state: FSMContext, db_pool: asyncpg.Pool
) -> None:
    data = await state.get_data()
    candidate_id: int = data["candidate_id"]
    await callback.answer()
    await callback.message.edit_text(MSG["GITHUB_SKIPPED"])
    await _run_scoring(callback.message, state, db_pool, candidate_id, github_data=None)


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

        # Validate GitHub ownership against candidate's name
        owner_login = github_data.get("owner_login", "")
        if owner_login:
            row = await db_pool.fetchrow(
                "SELECT first_name, last_name FROM candidates WHERE id = $1", candidate_id
            )
            if row:
                validation = await _llm.validate_github_ownership(
                    candidate_first_name=row["first_name"],
                    candidate_last_name=row["last_name"] or "",
                    github_login=owner_login,
                    github_display_name=github_data.get("owner_name"),
                )
                if validation is not None:
                    if validation.get("is_owner", True):
                        await message.answer(MSG["GITHUB_OWNERSHIP_VALID"])
                    else:
                        await message.answer(MSG["GITHUB_OWNERSHIP_WARN"])

    await _run_scoring(message, state, db_pool, candidate_id, github_data=github_data)


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
        "followup_queue": [],
        "current_answer_id": answer_id,
        "current_seq_number": seq,
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
        await message.answer(MSG["GITHUB_REQUEST"], reply_markup=_github_keyboard())


async def _background_analyze(
    db_pool: asyncpg.Pool,
    candidate_id: int,
    question_seq: int,
    question_text: str,
    answer_text: str,
    history: list[dict],
    question_index: int,
) -> None:
    """Фоновый анализ ответа кандидата. Ошибки не прерывают основной поток."""
    try:
        primary_axes = _PRIMARY_AXES.get(question_index, [])
        result = await _llm.analyze_answer(question_text, answer_text, history, primary_axes)
        if result:
            await question_analyses_repo.insert_question_analysis(
                db_pool,
                candidate_id=candidate_id,
                question_seq=question_seq,
                feedback_text=result.get("feedback", ""),
                needs_followup=result.get("needs_followup", False),
                followup_text=result.get("followup_question"),
            )
    except Exception:
        logger.exception(
            "Background analysis failed for candidate=%d seq=%d", candidate_id, question_seq
        )


async def _wait_for_analyses_and_ask_followups(
    callback: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    candidate_id: int,
    question_index: int,
    last_answer: str,
    question_text: str,
    question_seq: int,
) -> None:
    """
    Синхронная точка после Q5:
    1. Показывает загрузочное сообщение
    2. Анализирует Q5 синхронно (голос к этому моменту уже транскрибирован)
    3. Дожидается фоновых задач Q1-Q4
    4. Удаляет загрузочное сообщение
    5. Задаёт follow-up вопросы или переходит к GitHub
    """
    analyzing_msg = await callback.message.answer(MSG["ANALYZING_ANSWERS"])
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")

    history = [
        {"question": row["question_text"], "answer": row["answer_text"]}
        for row in await answers_repo.get_answers(db_pool, candidate_id)
        if row["answer_text"]
    ]
    primary_axes = _PRIMARY_AXES[question_index]
    q5_result = await _llm.analyze_answer(question_text, last_answer, history, primary_axes)
    if q5_result:
        await question_analyses_repo.insert_question_analysis(
            db_pool,
            candidate_id=candidate_id,
            question_seq=question_seq,
            feedback_text=q5_result.get("feedback", ""),
            needs_followup=q5_result.get("needs_followup", False),
            followup_text=q5_result.get("followup_question"),
        )

    # Wait for any still-running Q1-Q4 background tasks
    pending = list(_analysis_tasks.get(candidate_id, []))
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    await analyzing_msg.delete()

    # Collect follow-up queue (max 2 total)
    followups = await question_analyses_repo.get_pending_followups(db_pool, candidate_id)
    followup_texts = [
        f["followup_text"] for f in followups[:2] if f["followup_text"]
    ]

    if followup_texts:
        fup_text = followup_texts[0]
        remaining = followup_texts[1:]
        seq = await answers_repo.get_next_seq_number(db_pool, candidate_id)
        answer_id = await answers_repo.add_question(
            db_pool, candidate_id, seq, fup_text, is_adaptive=True
        )
        await state.set_state(CandidateStates.answering)
        await state.set_data({
            "candidate_id": candidate_id,
            "question_index": question_index,
            "followup_done": True,
            "followup_queue": remaining,
            "current_answer_id": answer_id,
            "current_seq_number": seq,
            "current_question_text": fup_text,
            "pending_answer": None,
        })
        await callback.message.answer(fup_text)
        return

    # No follow-ups → proceed to GitHub
    await state.set_state(CandidateStates.waiting_github)
    await state.set_data({"candidate_id": candidate_id})
    await callback.message.answer(MSG["GITHUB_REQUEST"], reply_markup=_github_keyboard())


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
            "followup_queue": [],
            "current_answer_id": pending["id"],
            "current_seq_number": pending["seq_number"],
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
        await message.answer(MSG["GITHUB_REQUEST"], reply_markup=_github_keyboard())


async def _run_scoring(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    candidate_id: int,
    github_data: dict | None,
) -> None:
    """Запрашивает LLM-скоринг, сохраняет результат и показывает кандидату."""
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
        total = min(
            scoring["task_decomposition"]["score"]
            + scoring["prompting_tools"]["score"]
            + scoring["critical_thinking"]["score"],
            30,
        )
        is_hot = total >= settings.HOT_THRESHOLD

        await scoring_repo.insert_scoring_result(
            db_pool,
            candidate_id=candidate_id,
            task_decomposition_score=scoring["task_decomposition"]["score"],
            task_decomposition_reasoning=scoring["task_decomposition"]["reasoning"],
            prompting_tools_score=scoring["prompting_tools"]["score"],
            prompting_tools_reasoning=scoring["prompting_tools"]["reasoning"],
            critical_thinking_score=scoring["critical_thinking"]["score"],
            critical_thinking_reasoning=scoring["critical_thinking"]["reasoning"],
            total_score=total,
            summary=scoring.get("summary", ""),
            recommendation=scoring.get("recommendation", "consider"),
            is_hot=is_hot,
        )
        await candidates_repo.mark_scored(db_pool, candidate_id)
        await _show_scoring(message, scoring, total)

    await state.set_state(CandidateStates.finished)
    await message.answer(MSG["FAREWELL"])


async def _show_scoring(message: Message, scoring: dict, total: int) -> None:
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer(
        MSG["SCORING_RESULT"].format(
            task_decomposition_score=scoring["task_decomposition"]["score"],
            task_decomposition_reasoning=scoring["task_decomposition"]["reasoning"],
            prompting_tools_score=scoring["prompting_tools"]["score"],
            prompting_tools_reasoning=scoring["prompting_tools"]["reasoning"],
            critical_thinking_score=scoring["critical_thinking"]["score"],
            critical_thinking_reasoning=scoring["critical_thinking"]["reasoning"],
            total=total,
            summary=scoring.get("summary", ""),
        )
    )

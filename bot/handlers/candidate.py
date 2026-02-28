"""
Хэндлеры кандидата: /start, приём ответов, GitHub-ссылка, показ скоринга.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.handlers.states import CandidateStates
from bot.services.llm import LLMService
from bot.services.github import GitHubService

router = Router(name="candidate")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие и начало скрининга."""
    # TODO: приветственное сообщение, переход к первому вопросу
    pass


@router.message(CandidateStates.answering)
async def process_answer(message: Message, state: FSMContext) -> None:
    """Приём ответа кандидата, анализ контекста, следующий вопрос или уточнение."""
    # TODO: сохранить ответ, вызвать LLM для анализа, выбрать следующий шаг
    pass


@router.message(CandidateStates.waiting_github)
async def process_github_link(message: Message, state: FSMContext) -> None:
    """Приём и валидация GitHub-ссылки."""
    # TODO: валидация ссылки, получение данных репо, финальный скоринг
    pass

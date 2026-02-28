"""
Сервис для работы с OpenRouter API (OpenAI-совместимый интерфейс).
Анализ контекста ответов и генерация скоринга.
"""

from typing import Any

from openai import AsyncOpenAI

from bot.config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMService:
    """Обёртка над OpenRouter API для скоринга кандидатов."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._model = settings.OPENROUTER_MODEL

    async def analyze_answer(
        self, question: str, answer: str, context: list[dict[str, str]]
    ) -> dict[str, Any]:
        """
        Анализ ответа кандидата в контексте предыдущих ответов.
        Возвращает: нужен ли уточняющий вопрос, текст следующего вопроса.
        """
        # TODO: промпт для адаптивного анализа
        pass

    async def generate_scoring(
        self,
        answers: list[dict[str, str]],
        github_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Финальный скоринг кандидата по трём критериям.
        Возвращает JSON с полями: delegation, decomposition, criticality,
        каждое содержит score (1-10), reasoning, quote.
        """
        # TODO: промпт для скоринга, парсинг JSON-ответа
        pass

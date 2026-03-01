"""
Сервис для работы с OpenRouter API (OpenAI-совместимый интерфейс).
Анализ ответов кандидата и генерация Pentagon-скоринга.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from bot.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_SCORING_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "scoring.txt"

_AXIS_RUBRIC = """
Три критерия оценки (0–10):

• task_decomposition — Декомпозиция задачи + AI-планирование
  0–3: Нет понимания где и зачем использовать AI
  4–6: Базовое разделение задач, без системного подхода к AI
  7–10: Чёткая декомпозиция, понимает trade-offs, знает когда AI уместен

• prompting_tools — Промптинг + экосистема инструментов
  0–3: Базовые промпты без итерации, знает 1–2 инструмента
  4–6: Есть систематика в промптах, знает несколько инструментов
  7–10: Структурированные промпты, верификация, широкое знание экосистемы

• critical_thinking — Критическое мышление к AI
  0–3: Доверяет AI без критической проверки
  4–6: Проверяет результаты, понимает основные ограничения
  7–10: Системная верификация, понимает где AI ошибается
"""


class LLMService:
    """Обёртка над OpenRouter API для скоринга кандидатов."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._model = settings.OPENROUTER_MODEL

    async def _call_llm(self, system: str, user: str) -> str | None:
        """Выполняет запрос к LLM, возвращает текст ответа или None при ошибке."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception:
            logger.exception("LLM request failed")
            return None

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        """Парсит JSON из ответа LLM, убирая markdown-обёртки если есть."""
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last ``` lines
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON: %.200s", text)
            return None

    async def analyze_answer(
        self,
        question: str,
        answer: str,
        context: list[dict[str, str]],
        primary_axes: list[str],
    ) -> dict[str, Any] | None:
        """
        Анализ ответа кандидата в фоне после подтверждения.

        Возвращает:
        {
            "feedback": str,           # 2–4 предложения для итогового отчёта
            "needs_followup": bool,    # True если оценка по primary axis ≤ 3
            "followup_question": str | None,
        }
        """
        context_str = ""
        if context:
            lines = []
            for i, item in enumerate(context, 1):
                if item.get("answer"):
                    lines.append(f"Вопрос {i}: {item['question']}\nОтвет {i}: {item['answer']}")
            context_str = "\n\n".join(lines)

        primary_axes_str = ", ".join(primary_axes) if primary_axes else "все оси"

        system_prompt = f"""Ты — старший технический рекрутер, оценивающий кандидата на позицию Junior AI-first Developer.

{_AXIS_RUBRIC}

Твоя задача: проанализировать один ответ кандидата и вернуть краткий фидбэк + решение об уточняющем вопросе.

Ключевые оси для этого вопроса: {primary_axes_str}
Уточняющий вопрос нужен ТОЛЬКО если оценка по ЛЮБОЙ из ключевых осей ≤ 3.

Правила уточняющего вопроса (если нужен):
- Ровно один вопрос, 1–2 предложения максимум
- Нацелен на конкретную слабую область, которую кандидат не раскрыл
- Не повторяет и не перефразирует вопросы из истории переписки
- Не перечисляет несколько подвопросов через «или», «и», «а также»
- Конкретный и узкий, а не широкий обзорный вопрос

Верни ответ строго в формате JSON без markdown-обёртки:
{{
  "feedback": "<2–4 предложения на русском, основанные на фактах ответа, без оценочных суждений типа 'хорошо' или 'плохо'>",
  "needs_followup": <true или false>,
  "followup_question": "<один конкретный вопрос 1–2 предложения на русском если needs_followup=true, иначе null>"
}}"""

        user_content = f"Вопрос: {question}\n\nОтвет кандидата: {answer}"
        if context_str:
            user_content += f"\n\nКонтекст предыдущих ответов:\n{context_str}"

        raw = await self._call_llm(system_prompt, user_content)
        return self._parse_json(raw)

    async def generate_interview_questions(
        self,
        answers: list[dict[str, str]],
        scoring: dict[str, Any],
    ) -> list[str]:
        """
        Генерирует 1–2 вопроса для живого собеседования на основе ответов и скоринга.
        Нацелены на слабые места кандидата.
        """
        scoring_summary = (
            f"Декомпозиция: {scoring['task_decomposition']['score']}/10 — "
            f"{scoring['task_decomposition']['reasoning']}\n"
            f"Промптинг+инструменты: {scoring['prompting_tools']['score']}/10 — "
            f"{scoring['prompting_tools']['reasoning']}\n"
            f"Критическое мышление: {scoring['critical_thinking']['score']}/10 — "
            f"{scoring['critical_thinking']['reasoning']}"
        )
        answers_str = "\n\n".join(
            f"Вопрос: {a['question']}\nОтвет: {a['answer']}"
            for a in answers
            if a.get("answer")
        )
        system = (
            "Ты — технический рекрутер. Сформулируй 1–2 вопроса для живого собеседования "
            "с кандидатом на позицию AI Automation Engineer.\n"
            "Вопросы должны:\n"
            "- Углублять именно слабые места, выявленные скорингом\n"
            "- Быть конкретными, не общими\n"
            "- Помочь рекрутеру лучше понять реальный опыт кандидата\n"
            "- Быть сформулированы как вопросы к кандидату, а не как задания\n\n"
            'Верни JSON без markdown: {"questions": ["вопрос 1", "вопрос 2"]}'
        )
        user = f"Ответы кандидата:\n{answers_str}\n\nРезультаты скоринга:\n{scoring_summary}"
        raw = await self._call_llm(system, user)
        result = self._parse_json(raw)
        if result and isinstance(result.get("questions"), list):
            return [q for q in result["questions"] if q][:2]
        return []

    async def generate_github_description(
        self,
        github_data: dict,
    ) -> str | None:
        """Генерирует краткое описание GitHub-репозитория кандидата (1–2 предложения)."""
        has_readme = "есть" if github_data.get("has_readme") else "нет"
        prompt = (
            f"Репозиторий кандидата:\n"
            f"- Язык: {github_data.get('primary_language') or 'не определён'}\n"
            f"- Коммитов: {github_data.get('commit_count', 0)}\n"
            f"- README: {has_readme}\n"
            f"- Последний коммит: {github_data.get('last_commit_at') or 'неизвестно'}\n"
            f"- Фрагмент README: {github_data.get('readme_snippet') or 'нет'}\n\n"
            "Напиши краткое описание этого репозитория в 1–2 предложения на русском: "
            "что это за проект, насколько он живой и серьёзный. "
            "Без упоминания URL. Только текст, без JSON."
        )
        try:
            response = await self._client.chat.completions.create(
                model=settings.OPENROUTER_VALIDATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return (response.choices[0].message.content or "").strip() or None
        except Exception:
            logger.exception("GitHub description generation failed")
            return None

    async def validate_github_ownership(
        self,
        candidate_first_name: str,
        candidate_last_name: str,
        github_login: str,
        github_display_name: str | None,
    ) -> dict[str, Any] | None:
        """
        Проверяет, совпадает ли GitHub-аккаунт с данными кандидата.
        Использует лёгкую модель для быстрой валидации.
        """
        display = github_display_name or "не указано"
        prompt = (
            f"Кандидат:\n"
            f"- Имя: {candidate_first_name}\n"
            f"- Фамилия: {candidate_last_name}\n\n"
            f"GitHub-аккаунт репозитория:\n"
            f"- Username: {github_login}\n"
            f"- Display name: {display}\n\n"
            "Задача: определить, скорее всего ли этот GitHub принадлежит данному кандидату.\n"
            "Учитывай транслитерацию, частичное совпадение, сокращения.\n"
            "Если display name не указан — ориентируйся только на username.\n\n"
            "Верни строго JSON без markdown:\n"
            '{"is_owner": <true/false>, "confidence": "<high|medium|low>", "reason": "<1 предложение на русском>"}'
        )
        try:
            response = await self._client.chat.completions.create(
                model=settings.OPENROUTER_VALIDATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = response.choices[0].message.content
            return self._parse_json(raw)
        except Exception:
            logger.exception("GitHub ownership validation failed")
            return None

    async def generate_scoring(
        self,
        answers: list[dict[str, str]],
        github_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Финальный Pentagon-скоринг кандидата по 5 осям.

        Возвращает JSON с полями: ai_in_product, vibe_coding, prompt_engineering,
        tool_awareness, pipeline_thinking (каждое: score + reasoning),
        total_score, summary, recommendation, recommendation_reason.
        """
        try:
            system_prompt = _SCORING_PROMPT_PATH.read_text(encoding="utf-8")
        except OSError:
            logger.error("scoring.txt not found at %s", _SCORING_PROMPT_PATH)
            return None

        answers_str = "\n\n".join(
            f"Вопрос {i}: {item['question']}\nОтвет: {item['answer']}"
            for i, item in enumerate(answers, 1)
            if item.get("answer")
        )

        github_str = ""
        if github_data:
            github_str = f"""
Данные GitHub-репозитория:
- URL: {github_data.get('repo_url', 'N/A')}
- README: {'есть' if github_data.get('has_readme') else 'нет'}
- Количество коммитов: {github_data.get('commit_count', 0)}
- Основной язык: {github_data.get('primary_language') or 'не определён'}
- Последний коммит: {github_data.get('last_commit_at') or 'неизвестно'}
- Фрагмент README: {github_data.get('readme_snippet') or 'нет'}
"""

        user_content = f"Ответы кандидата:\n\n{answers_str}"
        if github_str:
            user_content += f"\n\n{github_str}"

        raw = await self._call_llm(system_prompt, user_content)
        return self._parse_json(raw)

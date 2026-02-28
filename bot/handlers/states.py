"""
FSM-состояния для диалога с кандидатом.
"""

from aiogram.fsm.state import StatesGroup, State


class CandidateStates(StatesGroup):
    answering = State()       # Кандидат отвечает на вопросы
    waiting_github = State()  # Ожидание GitHub-ссылки
    finished = State()        # Скрининг завершён

"""
FSM-состояния для диалога с кандидатом и администратором.
"""

from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    dashboard          = State()  # Открыта панель администратора
    waiting_voice_test = State()  # Ожидание голосового для теста транскрибации


class SupportStates(StatesGroup):
    waiting_message = State()  # Ожидание сообщения для поддержки


class CandidateStates(StatesGroup):
    # Онбординг
    waiting_contact   = State()  # Ожидание шаринга контакта
    waiting_name      = State()  # Ввод ФИО
    waiting_source    = State()  # Выбор источника (inline-кнопки)
    confirming        = State()  # Подтверждение данных
    # Пре-интервью
    pre_interview      = State()  # Показана инструкция, ждём нажатия «Начать»
    # Интервью
    answering          = State()  # Кандидат отвечает на вопросы (текст или голос)
    confirming_answer  = State()  # Ожидание подтверждения ответа кандидатом
    waiting_github     = State()  # Ожидание GitHub-ссылки
    finished           = State()  # Скрининг завершён
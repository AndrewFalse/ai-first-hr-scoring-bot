# 🤖 AI-First HR Scoring Bot

Telegram-бот для автоматизированной оценки кандидатов с помощью искусственного интеллекта. Бот анализирует резюме и профили соискателей, выставляет скоринговые баллы и помогает HR-специалистам принимать обоснованные решения по найму.

---

## 📋 Содержание

- [О проекте](#о-проекте)
- [Архитектура](#архитектура)
- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Установка и запуск](#установка-и-запуск)
  - [Вариант 1: Docker (рекомендуется)](#вариант-1-docker-рекомендуется)
  - [Вариант 2: Локальный запуск](#вариант-2-локальный-запуск)
- [Конфигурация](#конфигурация)
- [Переменные окружения](#переменные-окружения)
- [Использование Makefile](#использование-makefile)
- [Промпты и кастомизация](#промпты-и-кастомизация)
- [Деплой](#деплой)
- [Разработка](#разработка)

---

## О проекте

**AI-First HR Scoring Bot** — это интеллектуальный Telegram-бот, разработанный для автоматизации первичного скрининга кандидатов в HR-процессах. Бот использует языковые модели для анализа и скоринга резюме, что позволяет значительно ускорить подбор персонала.

### Ключевые возможности

- 📄 **Анализ резюме** — автоматический разбор и структурирование данных из резюме
- 🏆 **AI-скоринг** — оценка кандидатов по заданным критериям с помощью LLM
- 💬 **Telegram-интерфейс** — удобное взаимодействие через мессенджер
- 📊 **Детальные отчёты** — подробная аналитика по каждому кандидату
- ⚙️ **Гибкие промпты** — настраиваемые критерии оценки под конкретные вакансии
- 🐳 **Docker-поддержка** — лёгкий деплой в любой среде

---

## Архитектура

```
┌─────────────────────────────────────────────┐
│               Telegram API                  │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│              Bot (Python)                   │
│  ┌──────────────────────────────────────┐  │
│  │          Handlers / Router           │  │
│  └──────────────────┬───────────────────┘  │
│                     │                       │
│  ┌──────────────────▼───────────────────┐  │
│  │         AI Scoring Engine            │  │
│  │  (LLM + промпты из /prompts/)        │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│              Infrastructure                 │
│         (Docker / docker-compose)           │
└─────────────────────────────────────────────┘
```

---

## Структура проекта

```
ai-first-hr-scoring-bot/
│
├── bot/                    # Основной код бота
│   ├── handlers/           # Обработчики команд и сообщений
│   ├── services/           # Бизнес-логика и сервисы
│   └── utils/              # Вспомогательные утилиты
│
├── infra/                  # Инфраструктурные скрипты и конфиги
│
├── prompts/                # Системные и пользовательские промпты для LLM
│
├── .env.example            # Пример файла с переменными окружения
├── .gitignore
├── CLAUDE.md               # Инструкции для Claude Code
├── Dockerfile              # Docker-образ приложения
├── Makefile                # Удобные команды для управления проектом
├── docker-compose.yml      # Конфигурация Docker Compose
└── requirements.txt        # Python-зависимости
```

---

## Требования

### Для запуска через Docker (рекомендуется)

- [Docker](https://docs.docker.com/get-docker/) версии 20.10+
- [Docker Compose](https://docs.docker.com/compose/install/) версии 2.0+
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))
- API-ключ языковой модели (OpenAI / Anthropic / другой)

### Для локального запуска

- Python 3.10+
- pip
- Telegram Bot Token
- API-ключ языковой модели

---

## Установка и запуск

### Шаг 0: Клонирование репозитория

```bash
git clone https://github.com/AndrewFalse/ai-first-hr-scoring-bot.git
cd ai-first-hr-scoring-bot
```

---

### Вариант 1: Docker (рекомендуется)

**1. Создайте файл `.env` на основе примера:**

```bash
cp .env.example .env
```

**2. Откройте `.env` и заполните необходимые переменные:**

```bash
nano .env  # или vim .env / code .env
```

**3. Запустите через Docker Compose:**

```bash
docker-compose up -d
```

**4. Проверьте, что бот запущен:**

```bash
docker-compose logs -f
```

**5. Остановка:**

```bash
docker-compose down
```

---

### Вариант 2: Локальный запуск

**1. Создайте и активируйте виртуальное окружение:**

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**2. Установите зависимости:**

```bash
pip install -r requirements.txt
```

**3. Создайте файл `.env`:**

```bash
cp .env.example .env
```

**4. Заполните переменные окружения в `.env`**

**5. Запустите бота:**

```bash
python -m bot
# или
python bot/main.py
```

---

## Конфигурация

Все настройки бота задаются через переменные окружения в файле `.env`. Скопируйте `.env.example` и заполните значения:

```bash
cp .env.example .env
```

---

## Переменные окружения

Скопируйте `.env.example` и заполните каждое значение:

```bash
cp .env.example .env
```

Полное содержимое `.env.example` с пояснениями:

```dotenv
# ─────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────

# Токен вашего Telegram-бота.
# Получить: откройте @BotFather в Telegram → /newbot → скопируйте токен.
BOT_TOKEN=your_telegram_bot_token


# ─────────────────────────────────────────────────────────
# OpenRouter API — единый шлюз к множеству LLM-моделей
# Документация: https://openrouter.ai
# ─────────────────────────────────────────────────────────

# API-ключ OpenRouter.
# Получить: зарегистрируйтесь на openrouter.ai → раздел "Keys" → "Create Key".
OPENROUTER_API_KEY=your_openrouter_api_key

# Основная языковая модель для скоринга и анализа резюме.
# Формат: "провайдер/название-модели".
# Пример: anthropic/claude-sonnet-4-5, openai/gpt-4o, google/gemini-2-flash
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5

# Модель для работы с аудио (расшифровка голосовых сообщений и т.п.)
OPENROUTER_AUDIO_MODEL=openai/gpt-audio-mini

# Лёгкая и быстрая модель для первичной валидации входных данных.
# Используется там, где не нужна тяжёлая аналитика — экономит токены.
OPENROUTER_VALIDATION_MODEL=google/gemini-3-flash-preview


# ─────────────────────────────────────────────────────────
# GITHUB
# ─────────────────────────────────────────────────────────

# Personal Access Token для работы с GitHub API.
# Нужен, если бот проверяет GitHub-профили кандидатов.
# Получить: github.com → Settings → Developer settings → Personal access tokens → Generate new token.
# Минимальные права: read:user, read:org (если нужны данные организации).
GITHUB_TOKEN=your_github_personal_access_token


# ─────────────────────────────────────────────────────────
# GOOGLE SHEETS — таблица для хранения результатов скоринга
# ─────────────────────────────────────────────────────────
#
# Пошаговая настройка:
# 1. Создай Google Cloud Project: console.cloud.google.com
# 2. Включи Google Sheets API и Google Drive API
#    (APIs & Services → Enable APIs → найди оба и включи)
# 3. Создай Service Account:
#    IAM & Admin → Service Accounts → Create → скачай JSON-ключ
# 4. Скопируй всё содержимое JSON-файла в одну строку
#    и вставь как значение GOOGLE_CREDENTIALS_JSON (см. ниже)
# 5. Расшарь свою Google Sheet с email сервисного аккаунта
#    (поле "client_email" внутри JSON) — дай роль "Редактор"
# 6. Возьми ID таблицы из URL:
#    docs.google.com/spreadsheets/d/<ВОТ_ЭТО_И_ЕСТЬ_ID>/edit

# JSON-ключ сервисного аккаунта Google (всё в одну строку без переносов).
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n","client_email":"bot@project.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}

# ID Google Sheets таблицы, куда будут записываться результаты.
# Берётся из URL: docs.google.com/spreadsheets/d/<SHEET_ID>/edit
GOOGLE_SHEET_ID=your_google_sheet_id


# ─────────────────────────────────────────────────────────
# ADMIN — настройки администратора и уведомлений
# ─────────────────────────────────────────────────────────


# Telegram Chat ID чата технической поддержки.
# Узнать свой ID: напишите боту @userinfobot в Telegram.
SUPPORT_CHAT_ID=366060437

# Пароль для получения админских прав
# Вызывается командой /admin <ADMIN_SECRET>
ADMIN_SECRET=one_time_init_token

# Telegram Chat ID рекрутера — куда бот будет присылать уведомления
# о новых горячих кандидатах и результатах скоринга.
RECRUITER_CHAT_ID=telegram_chat_id_for_notifications


# ─────────────────────────────────────────────────────────
# DATABASE — PostgreSQL база данных
# ─────────────────────────────────────────────────────────

# Пароль для пользователя PostgreSQL (используется в DATABASE_URL).
# Замените на надёжный пароль перед деплоем.
DB_PASSWORD=change_me_strong_password

# Полная строка подключения к PostgreSQL.
# Формат: postgresql://<user>:<password>@<host>:<port>/<dbname>
# При запуске через docker-compose host = имя сервиса из compose-файла (обычно "db" или "postgres").
DATABASE_URL=postgresql://bot:change_me_strong_password@localhost:5432/hr_screening


# ─────────────────────────────────────────────────────────
# SCORING — параметры системы оценки кандидатов
# ─────────────────────────────────────────────────────────

# Порог "горячего" кандидата. Максимальный балл: 30.
# Если total_score кандидата >= HOT_THRESHOLD — он попадает в "горячих"
# и рекрутер получает приоритетное уведомление.
HOT_THRESHOLD=21
```

> ⚠️ Никогда не коммитьте файл `.env` в репозиторий. Он уже добавлен в `.gitignore`.

---

## Использование Makefile

Проект содержит `Makefile` с удобными командами:

```bash
# Запустить бота через Docker
make up

# Остановить
make down

# Пересобрать образ и перезапустить
make rebuild

# Посмотреть логи
make logs

# Запустить в dev-режиме локально
make run

# Установить зависимости
make install

# Запустить линтер / форматирование
make lint
make format
```

Полный список команд:

```bash
make help
```

---

## Промпты и кастомизация

Директория `prompts/` содержит шаблоны промптов для языковой модели. Вы можете редактировать их, чтобы адаптировать логику скоринга под конкретные вакансии или критерии оценки.

Каждый промпт отвечает за свой этап анализа — например, первичный разбор резюме, оценка hard skills, оценка soft skills, итоговый скоринг.

---

## Деплой

### На сервере (VPS/Dedicated)

1. Установите Docker и Docker Compose на сервер
2. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/AndrewFalse/ai-first-hr-scoring-bot.git
   cd ai-first-hr-scoring-bot
   ```
3. Заполните `.env`
4. Запустите:
   ```bash
   docker-compose up -d
   ```

Бот будет работать в фоне. Для автозапуска при перезагрузке сервера добавьте `restart: always` в `docker-compose.yml` (уже может быть настроено).

---

## Разработка

### Добавление новых обработчиков

Новые команды и хендлеры добавляются в директорию `bot/handlers/`.

### Изменение логики скоринга

Логика оценки кандидатов находится в `bot/services/`. Промпты для LLM — в `prompts/`.

### Форматирование кода

```bash
make format
make lint
```

---

## Лицензия

Проект распространяется без явно указанной лицензии. Уточняйте у автора репозитория.

---

## Контакты

Автор: [@AndrewFalse](https://github.com/AndrewFalse)  
Репозиторий: [github.com/AndrewFalse/ai-first-hr-scoring-bot](https://github.com/AndrewFalse/ai-first-hr-scoring-bot)

"""
Конфигурация приложения. Загрузка переменных из .env.
"""

from dataclasses import dataclass, field
from os import getenv

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: getenv("BOT_TOKEN", ""))

    # OpenRouter API
    OPENROUTER_API_KEY: str = field(default_factory=lambda: getenv("OPENROUTER_API_KEY", ""))
    OPENROUTER_MODEL: str = field(default_factory=lambda: getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4"))

    # GitHub
    GITHUB_TOKEN: str = field(default_factory=lambda: getenv("GITHUB_TOKEN", ""))

    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS: str = field(
        default_factory=lambda: getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials.json")
    )
    GOOGLE_SHEET_ID: str = field(default_factory=lambda: getenv("GOOGLE_SHEET_ID", ""))

    # Admin
    ADMIN_SECRET_HASH: str = field(default_factory=lambda: getenv("ADMIN_SECRET_HASH", ""))
    INIT_ADMIN_SECRET: str = field(default_factory=lambda: getenv("INIT_ADMIN_SECRET", ""))
    RECRUITER_CHAT_ID: str = field(default_factory=lambda: getenv("RECRUITER_CHAT_ID", ""))

    # Database
    DATABASE_URL: str = field(default_factory=lambda: getenv("DATABASE_URL", ""))

    # Скоринг
    HOT_THRESHOLD: int = field(
        default_factory=lambda: int(getenv("HOT_THRESHOLD", "21"))
    )


settings = Settings()

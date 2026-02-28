"""
Утилиты авторизации: проверка админских прав, whitelist.
"""

from bot.config import settings

# In-memory whitelist (в проде можно заменить на файл/БД)
_admin_whitelist: set[int] = set()


def is_admin(user_id: int) -> bool:
    """Проверка, есть ли user_id в whitelist админов."""
    return user_id in _admin_whitelist


def add_admin(user_id: int) -> None:
    """Добавление user_id в whitelist."""
    _admin_whitelist.add(user_id)


def verify_admin_hash(command_hash: str) -> bool:
    """Проверка хеша из команды /admin_<hash>."""
    return command_hash == settings.ADMIN_SECRET_HASH


def verify_init_secret(secret: str) -> bool:
    """Проверка одноразового токена для /init_admin."""
    return secret == settings.INIT_ADMIN_SECRET

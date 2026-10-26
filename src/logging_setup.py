"""Журнал работы и перехват необработанных ошибок.

Exe собирается без консоли, поэтому вывод traceback уходил в никуда:
при падении у пользователя не оставалось никаких следов. Здесь лог
пишется в файл, а необработанное исключение показывается окном
со ссылкой на этот файл.
"""

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from app_info import ORGANIZATION

_log_path = None


def log_directory():
    """Папка рядом с профилем пользователя: каталог с exe может быть
    защищён от записи (например, Program Files)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = os.path.join(base, ORGANIZATION, "logs")
    os.makedirs(directory, exist_ok=True)
    return directory


def log_file_path():
    return _log_path


def setup_logging():
    """Настраивает запись в файл с ограничением размера."""
    global _log_path
    if _log_path is not None:
        return _log_path

    _log_path = os.path.join(log_directory(), "app.log")
    handler = RotatingFileHandler(
        _log_path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Дублируем в консоль, когда она есть (запуск из исходников).
    if sys.stderr is not None and sys.stderr.isatty():
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(console)
    return _log_path


def install_exception_hook(show_dialog=None):
    """Пишет необработанное исключение в лог и показывает его пользователю."""
    previous_hook = sys.excepthook

    def hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("crash").critical(
            "Необработанная ошибка", exc_info=(exc_type, exc_value, exc_traceback)
        )
        if show_dialog is not None:
            text = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
            try:
                show_dialog(text, _log_path)
            except Exception:
                logging.getLogger("crash").exception("Не удалось показать окно ошибки")

    sys.excepthook = hook

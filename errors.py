"""Ошибки обработки, понятные пользователю на его языке.

Раньше обработчик бросал исключения с готовым русским текстом, и в
английском интерфейсе очередь показывала ошибки по-русски. Теперь ошибка
несёт ключ перевода и поля, а текст собирается в момент показа — поэтому
он верен и после того, как язык переключили уже после обработки.

Классы наследуют и привычные ValueError / RuntimeError: код, который
ловит их по типу (подбор FPS, тесты), работает как прежде.
"""

from i18n import tr


class LocalizedError(Exception):
    """Ошибка с ключом перевода. detail — сырой хвост (вывод FFmpeg),
    который не переводится и дописывается после сообщения."""

    def __init__(self, key, detail="", **fields):
        super().__init__(key)
        self.key = key
        self.detail = detail
        self.fields = fields

    def text(self):
        message = tr(self.key, **self.fields)
        return f"{message}\n{self.detail}" if self.detail else message

    def __str__(self):
        return self.text()


class LocalizedValueError(LocalizedError, ValueError):
    pass


class LocalizedRuntimeError(LocalizedError, RuntimeError):
    pass


class LocalizedFileNotFoundError(LocalizedError, FileNotFoundError):
    pass


def as_message(error):
    """Что хранить в очереди: сама ошибка, если её можно перевести позже,
    иначе её текст."""
    if isinstance(error, LocalizedError):
        return error
    return str(error) or type(error).__name__


def message_text(message):
    """Текст сообщения на текущем языке. Принимает строку, ошибку или None."""
    if not message:
        return ""
    return message.text() if isinstance(message, LocalizedError) else str(message)


def first_line(message):
    text = message_text(message)
    return text.splitlines()[0] if text else ""

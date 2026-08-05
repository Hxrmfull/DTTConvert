"""Фиксация языка интерфейса на время прогона набора.

Окно берёт язык из QSettings, а при пустом значении — из системной локали.
Наборы сверяют русские подписи и мерят их ширину, поэтому язык надо задать
до создания окна: иначе на машине с английской локалью — или после того,
как язык переключили руками, — набор падал бы, причём выглядело бы это как
поломка очереди, а не как разные подписи.

Прежнее значение возвращается на выходе: прогон тестов не должен менять
язык самой программы.
"""

import atexit

from PyQt6.QtCore import QSettings

# Из app_info, а не строкой: при переименовании приложения наборы иначе
# правили бы настройки, которых программа уже не читает.
from app_info import ORGANIZATION


def pin_language(code="ru"):
    """Ставит язык на время прогона и восстанавливает прежний при выходе."""
    store = QSettings(ORGANIZATION, ORGANIZATION)
    saved = store.value("language", "", type=str)
    store.setValue("language", code)
    store.sync()

    def _restore():
        if saved:
            store.setValue("language", saved)
        else:
            # Пустое значение — не то же самое, что «русский»: при нём
            # программа берёт язык системы.
            store.remove("language")
        store.sync()

    atexit.register(_restore)

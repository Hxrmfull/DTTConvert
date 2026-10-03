"""Отдельный профиль настроек и фиксация языка на время прогона набора.

Наборы работают в собственной ветке настроек (TEST_ORGANIZATION), а не
в настоящей: раньше test_features очищал настройки целиком, и после
прогона тестов у пользователя сбрасывались папка сохранения, язык и
размер окна. Модуль импортируется до main_window, поэтому подмена имени
организации успевает дойти до окна.

Окно берёт язык из QSettings, а при пустом значении — из системной локали.
Наборы сверяют русские подписи и мерят их ширину, поэтому язык надо задать
до создания окна: иначе на машине с английской локалью набор падал бы,
причём выглядело бы это как поломка очереди, а не как разные подписи.
"""

import app_info

TEST_ORGANIZATION = "DTTConvertTests"
app_info.ORGANIZATION = TEST_ORGANIZATION

from PyQt6.QtCore import QSettings  # noqa: E402


def pin_language(code="ru"):
    """Ставит язык в тестовом профиле. Проверка обновлений в тестах не
    нужна: сеть сделала бы прогон медленным и зависимым от GitHub."""
    store = QSettings(TEST_ORGANIZATION, TEST_ORGANIZATION)
    store.setValue("language", code)
    store.setValue("check_updates", False)
    store.sync()

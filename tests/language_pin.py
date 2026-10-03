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

import os

import app_info

TEST_ORGANIZATION = "DTTConvertTests"
app_info.ORGANIZATION = TEST_ORGANIZATION

import atexit  # noqa: E402

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

# Окна тестов на экран не выводятся: прогон не мелькает окнами и не
# мешает работать. WA_DontShowOnScreen, а не платформа offscreen: та на
# Windows не видит системных шрифтов, и проверки вёрстки мерили бы чужие
# метрики. Окно при этом «показано» по всем правилам — раскладка,
# отрисовка, активация и фокус работают как обычно. Видеть окна можно,
# задав переменную окружения DTT_SHOW_TEST_WINDOWS=1.
if not os.environ.get("DTT_SHOW_TEST_WINDOWS"):
    _show = QWidget.show

    def _show_off_screen(widget):
        if widget.isWindow():
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        _show(widget)

    QWidget.show = _show_off_screen


def pin_language(code="ru"):
    """Ставит язык в тестовом профиле. Проверка обновлений в тестах не
    нужна: сеть сделала бы прогон медленным и зависимым от GitHub."""
    store = QSettings(TEST_ORGANIZATION, TEST_ORGANIZATION)
    store.setValue("language", code)
    store.setValue("check_updates", False)
    store.sync()


def release_windows():
    """Удаляет все окна, пока QApplication ещё жив.

    Иначе окна и приложение разбирает сам Python при завершении, в
    произвольном порядке, и Qt изредка падал (access violation) уже после
    того, как набор отработал и напечатал результат. Зовётся и
    автоматически при выходе — для наборов, которые выходят по sys.exit
    в конце модуля.
    """
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        # Список снят заранее: удаление окна удаляет и его дочерние окна
        # (контейнеры выпадающих списков), их обёртки уже недействительны.
        if not sip.isdeleted(widget):
            sip.delete(widget)


atexit.register(release_windows)

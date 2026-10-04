import logging
import os
import sys

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from app_info import APP_ID, APP_NAME, migrate_legacy_settings, version_string
from logging_setup import install_exception_hook, setup_logging
from styles import build_stylesheet
from main_window import MainWindow


def resource_path(name):
    """Ищет файл рядом с исходниками, рядом с exe или внутри сборки."""
    directories = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        directories.append(bundle_dir)
    directories.append(os.path.dirname(os.path.abspath(__file__)))
    directories.append(os.path.dirname(os.path.abspath(sys.executable)))
    for directory in directories:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _apply_taskbar_identity():
    """Без собственного AppUserModelID Windows показывает на панели задач
    значок интерпретатора Python, а не иконку приложения."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        logging.getLogger(__name__).debug("Не удалось задать AppUserModelID", exc_info=True)


def _show_crash_dialog(message, log_path):
    QMessageBox.critical(
        None,
        "Произошла ошибка",
        f"{message}\n\nПодробности записаны в журнал:\n{log_path}",
    )


def main():
    log_path = setup_logging()
    install_exception_hook(_show_crash_dialog)
    logging.getLogger(__name__).info("Запуск %s %s", APP_NAME, version_string())

    _apply_taskbar_identity()

    app = QApplication(sys.argv)
    # До создания окна: оно читает сохранённые размер, язык и папку
    # сохранения прямо в конструкторе.
    if migrate_legacy_settings():
        logging.getLogger(__name__).info("Настройки перенесены с прежнего имени")
    app.setStyle("Fusion")
    # Меню появляются своей анимацией (widgets.PopupMenu); системная
    # анимация меню Windows наложилась бы на неё.
    app.setEffectEnabled(Qt.UIEffect.UI_AnimateMenu, False)
    app.setEffectEnabled(Qt.UIEffect.UI_FadeMenu, False)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(version_string())
    # Стили собираются после создания QApplication: иконки стрелок рисуются
    # через QPixmap, а он требует уже поднятого приложения.
    app.setStyleSheet(build_stylesheet())

    icon_path = resource_path("icon.ico") or resource_path("icon.png")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.log_path = log_path
    window.show()

    exit_code = app.exec()
    # Окно удаляется явно, пока приложение ещё живо. Иначе их разбирает
    # сам Python при выходе из main() в произвольном порядке: если
    # QApplication уходит раньше окна, Qt изредка падает (access violation)
    # уже после закрытия — настройки сохранены, но процесс завершается
    # аварийно. Найдено по тестам: около одного запуска из пятнадцати.
    sip.delete(window)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

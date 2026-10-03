"""Вёрстка при обычном размере окна: ничего не обрезано.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_layout_normal.py
"""
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
WORK_ROOT = os.path.join(tempfile.gettempdir(), "mcs_tests")
os.makedirs(WORK_ROOT, exist_ok=True)

import sys
OUT = WORK_ROOT

from PyQt6.QtWidgets import (QApplication, QMessageBox, QLabel, QPushButton,
                             QAbstractSpinBox, QCheckBox, QComboBox, QScrollArea)
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv); app.setStyle("Fusion")
from styles import build_stylesheet
app.setStyleSheet(build_stylesheet())
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

from language_pin import pin_language, release_windows
pin_language()  # вёрстка проверяется на обоих языках, старт — от русского

from main_window import MainWindow, idle_status, DEFAULT_WINDOW_SIZE
w = MainWindow()
# Окно восстанавливает сохранённую геометрию, а проверять надо
# размер по умолчанию — иначе тест зависит от прошлых запусков.
w.resize(*DEFAULT_WINDOW_SIZE)
w.show()

TABS = {0: "Основная", 1: "Telegram", 2: "Twitch", 3: "Discord", 4: "WhatsApp"}
TYPES = (QLabel, QPushButton, QAbstractSpinBox, QCheckBox, QComboBox)

def run():
    problems = []
    scroll = w.findChild(QScrollArea, "SettingsScroll")
    print(f"окно по умолчанию: {w.width()}x{w.height()}")

    for index, name in TABS.items():
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        page = w.settings_tabs.currentWidget()

        vbar = scroll.verticalScrollBar()
        hbar = scroll.horizontalScrollBar()
        if vbar.isVisible() or vbar.maximum() > 0:
            problems.append(f"{name}: нужна вертикальная прокрутка (max={vbar.maximum()})")
        if hbar.isVisible() or hbar.maximum() > 0:
            problems.append(f"{name}: нужна горизонтальная прокрутка (max={hbar.maximum()})")

        viewport = scroll.viewport()
        for child in page.findChildren(TYPES):
            if not child.isVisible():
                continue
            g = child.geometry()
            if g.width() <= 0 or g.height() <= 0:
                continue
            top_left = child.mapTo(viewport, child.rect().topLeft())
            bottom = top_left.y() + g.height()
            right = top_left.x() + g.width()
            text = (child.text()[:26] if hasattr(child, "text") else type(child).__name__)
            if bottom > viewport.height() + 1:
                problems.append(f"{name}: '{text}' обрезан снизу ({bottom} > {viewport.height()})")
            if right > viewport.width() + 1:
                problems.append(f"{name}: '{text}' обрезан справа ({right} > {viewport.width()})")

        w.grab().save(os.path.join(OUT, f"vis_{index}.png"))
        print(f"  {name}: проверено {len(page.findChildren(TYPES))} элементов")

    # Ключевые элементы должны реально присутствовать на своих вкладках
    # На широком окне лишняя ширина должна доставаться очереди, а не
    # растягивать поля настроек через всю панель.
    from main_window import SETTINGS_PANEL_MAX_WIDTH
    queue_before = w.file_list.width()
    w.resize(1920, 1040)
    app.processEvents()
    panel = w.splitter.widget(1)
    if panel.width() > SETTINGS_PANEL_MAX_WIDTH:
        problems.append(
            f"панель настроек растянулась до {panel.width()} px "
            f"(предел {SETTINGS_PANEL_MAX_WIDTH})"
        )
    if w.file_list.width() <= queue_before:
        problems.append("очередь не получила лишнюю ширину окна")
    w.resize(*DEFAULT_WINDOW_SIZE)
    app.processEvents()

    # Заголовки групп должны отличаться от самих настроек, иначе сливаются.
    from PyQt6.QtWidgets import QLabel as _QLabel
    captions = [c for c in w.settings_tabs.findChildren(_QLabel)
                if c.objectName() == "GroupCaption"]
    if not captions:
        problems.append("заголовков групп не нашлось")
    sheet = app.styleSheet()
    rule = sheet[sheet.index("QLabel#GroupCaption"):]
    rule = rule[:rule.index("}")]
    if "border-bottom" not in rule:
        problems.append("заголовок группы не подчёркнут линией")

    # Подписи вкладок не должны обрезаться. Выбранная вкладка рисуется
    # жирнее обычной, поэтому меряем именно жирным начертанием.
    from PyQt6.QtGui import QFont, QFontMetrics
    for index, button in enumerate(w.tab_buttons):
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        bold = QFont(button.font())
        bold.setWeight(QFont.Weight.DemiBold)
        needed = QFontMetrics(bold).horizontalAdvance(button.text()) + 26
        if button.width() < needed:
            problems.append(
                f"вкладка «{button.text()}»: подпись обрезана "
                f"({button.width()} < {needed})"
            )

    w.settings_tabs.setCurrentIndex(0); app.processEvents()
    if not w.fps_checkbox.isVisible():
        problems.append("Основная: чекбокс FPS не виден")
    for widget, name in ((w.rotate_combo, "поворот"), (w.flip_combo, "отражение"),
                         (w.trim_end_spin, "конец фрагмента"),
                         (w.quality_spin, "качество"), (w.target_size_spin, "целевой размер"),
                         (w.audio_combo, "звук")):
        if not widget.isVisible():
            problems.append(f"Основная: {name} не виден")
    w.settings_tabs.setCurrentIndex(1); app.processEvents()
    if not w.tg_duration_spin.isVisible():
        problems.append("Telegram: поле длительности не видно")
    w.settings_tabs.setCurrentIndex(3); app.processEvents()
    if not w.discord_hint_label.isVisible():
        problems.append("Discord: подсказка не видна")

    # Худший случай для вкладки Telegram: выбран видеофайл, поэтому под
    # полями фрагмента появляется строка о его длительности. Без файла в
    # очереди эта строка пуста, и переполнение проходило мимо теста.
    import subprocess
    clip = os.path.join(OUT, "клип_вёрстка.mp4")
    if not os.path.isfile(clip):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                        "-i", "testsrc=duration=8:size=320x240:rate=25",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", clip],
                       capture_output=True, check=True)
    w.output_dir = OUT
    w._on_scan_finished([clip], [])
    w.file_list.setCurrentRow(0)
    # Длительность приходит из фонового опроса; чтобы тест не зависел от
    # гонки, отдаём её тем же путём, каким её приносит воркер.
    w._on_queue_info_ready(clip, {"width": 320, "height": 240,
                                  "duration": 8.0, "fps": 25.0})
    w._apply_telegram_preset("tg_sticker_webm")
    w.settings_tabs.setCurrentIndex(1)
    app.processEvents()
    if not w.tg_source_label.text().strip():
        problems.append("Telegram: строка о длительности пуста, случай не проверен")
    if scroll.verticalScrollBar().maximum() > 0:
        problems.append(
            f"Telegram: с выбранным видео нужна прокрутка "
            f"(max={scroll.verticalScrollBar().maximum()})"
        )
    # И «Основная» с выбранным файлом: на ней теперь все настройки сразу.
    w.settings_tabs.setCurrentIndex(0)
    app.processEvents()
    if scroll.verticalScrollBar().maximum() > 0:
        problems.append(
            f"Основная: с выбранным файлом нужна прокрутка "
            f"(max={scroll.verticalScrollBar().maximum()})"
        )
    w._on_clear_list()
    app.processEvents()

    # Устаревшая надпись о пресете не должна оставаться при пустой очереди
    w._apply_telegram_preset("tg_sticker_webm")
    w._on_clear_list()
    app.processEvents()
    if w.current_file_label.text() != idle_status():
        problems.append(f"статус не сброшен после очистки: {w.current_file_label.text()!r}")

    # То же самое по-английски: строки другой длины, и подписи вкладок
    # с полями настроек могут не поместиться там, где помещались раньше.
    import i18n
    from PyQt6.QtGui import QFont as _QFont, QFontMetrics as _QFontMetrics
    was = i18n.current_language()
    w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
    app.processEvents()
    scroll = w.findChild(QScrollArea, "SettingsScroll")
    for index, name in TABS.items():
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        vbar = scroll.verticalScrollBar()
        hbar = scroll.horizontalScrollBar()
        if vbar.maximum() > 0:
            problems.append(f"[en] {name}: нужна вертикальная прокрутка ({vbar.maximum()})")
        if hbar.maximum() > 0:
            problems.append(f"[en] {name}: нужна горизонтальная прокрутка ({hbar.maximum()})")
    for index, button in enumerate(w.tab_buttons):
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        bold = _QFont(button.font())
        bold.setWeight(_QFont.Weight.DemiBold)
        needed = _QFontMetrics(bold).horizontalAdvance(button.text()) + 26
        if button.width() < needed:
            problems.append(
                f"[en] вкладка «{button.text()}»: подпись обрезана "
                f"({button.width()} < {needed})"
            )
    w.language_combo.setCurrentIndex(w.language_combo.findData(was))
    app.processEvents()

    print()
    if problems:
        print(f"ПРОБЛЕМ: {len(problems)}")
        for p in problems: print("  -", p)
    else:
        print("всё видно без прокрутки, статус корректен")
    # Закрываем окно: иначе фоновые потоки доживают до выхода
    # интерпретатора и Qt изредка завершает процесс с ошибкой.
    w.close()
    app.processEvents()
    # Цикл завершается кодом через app.exit, а sys.exit — уже после него:
    # sys.exit прямо из обработчика таймера выходил из Python, пока цикл
    # событий Qt ещё на стеке, и процесс изредка падал при завершении.
    app.exit(1 if problems else 0)

QTimer.singleShot(700, run)
exit_code = app.exec()
release_windows()
sys.exit(exit_code)

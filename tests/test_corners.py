"""Углы панелей при появлении полосы прокрутки.

Полоса прокрутки раньше заливала себя цветом окна и «пробивала» фон
карточки — в углах просвечивало приложение. Тест ищет именно это:
цвет окна внутри карточки. Сама зона скругления прозрачна законно,
поэтому её не проверяем, а отдельно убеждаемся, что дуга нарисована.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_corners.py
"""
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
WORK_ROOT = os.path.join(tempfile.gettempdir(), "mcs_tests")
os.makedirs(WORK_ROOT, exist_ok=True)

from PyQt6.QtCore import QRect, QTimer
from PyQt6.QtWidgets import QApplication, QFrame, QMessageBox, QScrollArea

app = QApplication(sys.argv)
app.setStyle("Fusion")
from styles import build_stylesheet

app.setStyleSheet(build_stylesheet())
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

from language_pin import pin_language
pin_language()  # у английских подписей другая длина

import time

from main_window import MainWindow, THEME_FADE_MS
from styles import palette, theme_for_tab

# Фон окна общий для всех тем, а карточка и рамка у вкладок площадок свои.
WINDOW_BG = palette()["window_bg"]
SIZES = [(1140, 790), (1050, 730), (1000, 700), (980, 680)]

window = MainWindow()
window.show()


def card_rect(card):
    return QRect(card.mapTo(window, card.rect().topLeft()), card.size())


def probe():
    problems = []
    card = window.findChild(QFrame, "SettingsCardFrame")
    scroll = window.findChild(QScrollArea, "SettingsScroll")
    assert card is not None and scroll is not None, "карточка настроек не найдена"

    for width, height in SIZES:
        window.resize(width, height)
        app.processEvents()
        for tab in range(window.settings_tabs.count()):
            window.settings_tabs.setCurrentIndex(tab)
            # Смена темы плавная: ждём, пока снимок прежних цветов растает.
            deadline = time.monotonic() + (THEME_FADE_MS + 120) / 1000.0
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            colors = palette(theme_for_tab(tab))
            CARD_BG, BORDER = colors["surface"], colors["card_border"]
            has_bar = scroll.verticalScrollBar().maximum() > 0
            image = window.grab().toImage()
            rect = card_rect(card)
            label = f"{width}x{height} вкладка {tab} (полоса={has_bar})"

            # 1. Фон окна не должен просвечивать внутри карточки.
            for name, y in (("сверху", rect.top() + 5), ("снизу", rect.bottom() - 5)):
                holes = [
                    x for x in range(rect.left() + 12, rect.right() - 11)
                    if image.pixelColor(x, y).name() == WINDOW_BG
                ]
                if holes:
                    problems.append(f"{label}: фон окна внутри карточки {name}, {len(holes)} px")

            # 2. Дуги скруглённых углов нарисованы: рядом с каждым углом
            #    должны встречаться и пиксели рамки, и заливка карточки.
            corners = {
                "верх-лево": (range(rect.left(), rect.left() + 12),
                              range(rect.top(), rect.top() + 12)),
                "верх-право": (range(rect.right() - 11, rect.right() + 1),
                               range(rect.top(), rect.top() + 12)),
                "низ-лево": (range(rect.left(), rect.left() + 12),
                             range(rect.bottom() - 11, rect.bottom() + 1)),
                "низ-право": (range(rect.right() - 11, rect.right() + 1),
                              range(rect.bottom() - 11, rect.bottom() + 1)),
            }
            for name, (xs, ys) in corners.items():
                border_pixels = 0
                card_pixels = 0
                for x in xs:
                    for y in ys:
                        colour = image.pixelColor(x, y).name()
                        if colour == BORDER:
                            border_pixels += 1
                        elif colour == CARD_BG:
                            card_pixels += 1
                if border_pixels < 3:
                    problems.append(f"{label}: угол {name} без рамки ({border_pixels} px)")
                if card_pixels < 10:
                    problems.append(f"{label}: угол {name} не залит карточкой ({card_pixels} px)")

    print()
    if problems:
        print(f"ПРОБЛЕМ С УГЛАМИ: {len(problems)}")
        for problem in problems[:15]:
            print("  -", problem)
    else:
        print(f"углы целы: {len(SIZES)} размеров x {window.settings_tabs.count()} вкладки")
    window.close()
    app.processEvents()
    app.quit()
    sys.exit(1 if problems else 0)


QTimer.singleShot(700, probe)
sys.exit(app.exec())

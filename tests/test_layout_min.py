"""Вёрстка при минимальном размере окна: элементы не наезжают.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_layout_min.py
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
                             QAbstractSpinBox, QComboBox)
from PyQt6.QtCore import QTimer
app = QApplication(sys.argv); app.setStyle("Fusion")
from styles import build_stylesheet
app.setStyleSheet(build_stylesheet())
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

from language_pin import pin_language, release_windows
pin_language()  # ширина подписей зависит от языка

from main_window import MainWindow
w = MainWindow()
w.resize(w.minimumWidth(), w.minimumHeight())
w.show()

TABS = {0: "Основная", 1: "Telegram", 2: "Twitch", 3: "Discord", 4: "WhatsApp",
        5: "Kick", 6: "YouTube"}

def tab_bar_problems(window, prefix=""):
    """Кнопки вкладок не налезают друг на друга и не выходят за строку.

    Каждая кнопка держит ширину своей подписи, поэтому при нехватке места
    они не сжимаются, а наезжают одна на другую — проверка «подпись
    помещается в кнопку» этого не видит.
    """
    from PyQt6.QtCore import QPoint
    found = []
    # Порядок вкладок пользователь меняет сам — сверяем по месту на экране.
    # Карандаш порядка вкладок стоит последним в той же строке.
    widgets = sorted(window.tab_buttons, key=lambda b: b.mapTo(window, QPoint()).x())
    widgets.append(window.tab_order_button)
    edges = [(w, w.mapTo(window, QPoint()).x(), w.mapTo(window, QPoint()).x() + w.width())
             for w in widgets]
    for (left, _, left_end), (right, right_start, _) in zip(edges, edges[1:]):
        if left_end > right_start:
            found.append(f"{prefix}«{left.text()}» и «{right.text() or 'карандаш'}» налезают")
    panel = window.right_panel
    panel_end = panel.mapTo(window, QPoint()).x() + panel.width()
    if edges[-1][2] > panel_end:
        found.append(f"{prefix}кнопка порядка вкладок выходит за панель")
    return found


def visible_widgets(page):
    out = []
    for child in page.findChildren((QLabel, QPushButton, QAbstractSpinBox, QComboBox)):
        if not child.isVisible():
            continue
        g = child.geometry()
        if g.width() <= 0 or g.height() <= 0:
            continue
        out.append((child, child.mapTo(w, child.rect().topLeft()), g.size()))
    return out

def overlaps(a, b):
    """Площадь пересечения двух виджетов; сами виджеты здесь не нужны."""
    pa, sa = a[1], a[2]
    pb, sb = b[1], b[2]
    ax1, ay1, ax2, ay2 = pa.x(), pa.y(), pa.x()+sa.width(), pa.y()+sa.height()
    bx1, by1, bx2, by2 = pb.x(), pb.y(), pb.x()+sb.width(), pb.y()+sb.height()
    ix = max(0, min(ax2,bx2) - max(ax1,bx1))
    iy = max(0, min(ay2,by2) - max(ay1,by1))
    return ix * iy

def label_of(x):
    t = x[0].text() if hasattr(x[0], "text") else ""
    return f"{type(x[0]).__name__}('{t[:28]}')"

def run():
    problems = []
    print(f"окно: {w.width()}x{w.height()} (минимум {w.minimumWidth()}x{w.minimumHeight()})")
    for index, name in TABS.items():
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        page = w.settings_tabs.currentWidget()
        widgets = visible_widgets(page)
        for i in range(len(widgets)):
            for j in range(i+1, len(widgets)):
                a, b = widgets[i], widgets[j]
                if a[0].isAncestorOf(b[0]) or b[0].isAncestorOf(a[0]):
                    continue
                area = overlaps(a, b)
                if area > 12:
                    problems.append((name, label_of(a), label_of(b), area))
        w.grab().save(os.path.join(OUT, f"min_{index}.png"))
        print(f"  {name}: виджетов {len(widgets)}")

    # содержимое не должно вылезать за нижнюю границу окна
    for index, name in TABS.items():
        w.settings_tabs.setCurrentIndex(index)
        app.processEvents()
        page = w.settings_tabs.currentWidget()
        for child, pos, size in visible_widgets(page):
            if pos.y() + size.height() > w.height() + 2:
                problems.append((name, label_of((child,pos,size)), "ВЫХОДИТ ВНИЗ ЗА ОКНО", 0))
            if pos.x() + size.width() > w.width() + 2:
                problems.append((name, label_of((child,pos,size)), "ОБРЕЗАН СПРАВА", 0))

    for problem in tab_bar_problems(w):
        problems.append(("строка вкладок", problem, "", 0))

    print()
    if problems:
        print(f"НАЙДЕНО ПЕРЕКРЫТИЙ: {len(problems)}")
        for p in problems[:15]:
            print("  ", p)
    else:
        print("перекрытий нет")
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

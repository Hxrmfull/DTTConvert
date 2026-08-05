"""Тёмная тема приложения.

Стрелки списков и счётчиков Qt не умеет рисовать средствами QSS
(CSS-приём с нулевым размером и рамками даёт квадраты), поэтому нужные
иконки генерируются один раз при запуске и подставляются в стили.
"""

import os
import tempfile

_STYLESHEET_TEMPLATE = """
QWidget {
    background-color: #1e1f26;
    color: #e6e6e6;
    font-family: "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1f26;
}

/* Фон прозрачный: иначе подписи рисуют прямоугольник цвета окна
   поверх более светлой карточки настроек. */
QLabel {
    color: #e6e6e6;
    background: transparent;
}

QLabel#TitleLabel {
    font-size: 16px;
    font-weight: 600;
    color: #f5f5f7;
}

QLabel#HintLabel {
    color: #9a9ba5;
    font-size: 12px;
}

QLabel#SectionLabel {
    color: #8a8dfc;
    font-weight: 600;
    font-size: 13px;
    padding: 0 0 2px 2px;
}

/* Вкладки-«таблетки» и карточка настроек. Раньше здесь был QTabWidget,
   но Qt не рисует дуги скруглённых углов у его ::pane — рамка получалась
   разорванной. Обычный виджет скругляется корректно. */
QPushButton#TabButton {
    background: #292a34;
    color: #aeb0bc;
    border: 1px solid #3a3b48;
    border-radius: 6px;
    /* Поля по бокам скромные: вкладок четыре, и при 16 px самая длинная
       подпись переставала помещаться в узкую правую панель и обрезалась. */
    padding: 7px 12px;
    font-weight: 500;
}

QPushButton#TabButton:hover {
    background: #323440;
    color: #e6e6e6;
}

QPushButton#TabButton:checked {
    background: #3a3d63;
    color: #ffffff;
    border-color: #676b9c;
    font-weight: 600;
}

/* Фон и рамку рисует контейнер: Qt не закрашивает фон под полосой
   прокрутки, и в углах карточки просвечивал фон окна. */
QFrame#SettingsCardFrame {
    background: #24252e;
    border: 1px solid #45475f;
    border-radius: 8px;
}

/* Непрозрачный фон цвета карточки: под полосой прокрутки Qt рисует
   фон окна, а сюда полоса уже не достаёт до скруглённых углов. */
QScrollArea#SettingsScroll {
    background: #24252e;
    border: none;
}

QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

QStackedWidget#SettingsCard {
    border: none;
    background: transparent;
}

/* Страницы прозрачные, иначе их прямоугольный фон закрывает
   скруглённые углы карточки. */
QWidget#SettingsPage {
    background: transparent;
    border: none;
}

QListWidget {
    background-color: #24252e;
    border: 1px solid #45475f;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    padding: 8px;
    border-radius: 6px;
    margin-bottom: 2px;
}

QListWidget::item:selected {
    background-color: #3a3d63;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #2c2e3a;
}

QPushButton {
    background-color: #33354a;
    color: #f0f0f5;
    border: 1px solid #55587a;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3d4060;
    border: 1px solid #565a80;
}

QPushButton:pressed {
    background-color: #2a2c3e;
}

/* Недоступная кнопка: заметно бледнее и без рамки-«кнопочности»,
   чтобы её нельзя было спутать с активной. */
QPushButton:disabled {
    background-color: #232430;
    color: #55566a;
    border: 1px dashed #34364a;
}

QPushButton#StartButton {
    background-color: #6c63ff;
    border: 1px solid #7a72ff;
    color: #ffffff;
    font-weight: 700;
    padding: 10px 20px;
    font-size: 14px;
}

QPushButton#StartButton:hover {
    background-color: #7a72ff;
}

QPushButton#StartButton:disabled {
    background-color: #2b2b3a;
    border: 1px dashed #45475f;
    color: #6a6b7c;
}

QPushButton#StopButton {
    background-color: #4a2c33;
    border: 1px solid #6c3a44;
    color: #ffb3bb;
    /* Те же метрики, что у StartButton, иначе кнопки разной высоты. */
    font-weight: 700;
    padding: 10px 20px;
    font-size: 14px;
}

QPushButton#StopButton:hover {
    background-color: #5c333c;
}

QPushButton#StopButton:disabled {
    background-color: #2b2629;
    border: 1px dashed #45383c;
    color: #6b5c60;
}

/* Главное действие в очереди — выделено акцентом. */
QPushButton#PrimaryButton {
    background-color: #3b3670;
    border: 1px solid #6c63ff;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #494290;
    border-color: #8a83ff;
}

/* Убирающие/разрушительные действия — приглушены. */
QPushButton#QuietButton {
    background-color: #2a2b35;
    border: 1px solid #3a3b48;
    color: #a9abb8;
}

QPushButton#QuietButton:hover {
    background-color: #3a2f34;
    border-color: #6c3a44;
    color: #ffc9cf;
}

/* Пресеты Telegram/Twitch: выбранный остаётся подсвеченным. */
QPushButton#PresetButton {
    text-align: center;
    padding: 7px 10px;
    min-height: 16px;
}

QPushButton#PresetButton:checked {
    background-color: #3a3d63;
    border: 1px solid #8a83ff;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PresetButton:checked:hover {
    background-color: #464a76;
}

/* Подсказка к выбранному пресету — выноска с акцентной полосой слева,
   иначе строка текста висит в воздухе и выглядит инородно. */
QLabel#HintCallout {
    color: #c2c4d0;
    font-size: 12px;
    background: #2b2d3b;
    border-left: 3px solid #6c63ff;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 9px 11px;
}

/* Заголовок группы настроек. Подчёркнут линией во всю ширину: раньше это
   была просто мелкая серая строка, и она терялась среди самих настроек. */
QLabel#GroupCaption {
    color: #9ea2c8;
    font-size: 10px;
    font-weight: 700;
    padding: 7px 0 3px 2px;
    border-bottom: 1px solid #3c3f5c;
    margin-bottom: 3px;
}

/* Пояснение мелким шрифтом — отделено полосой сверху, а не просто
   брошено под кнопками. */
QLabel#VersionLabel {
    color: #55566a;
    font-size: 11px;
    padding: 0 6px 6px 0;
}

QLabel#NoteLabel {
    color: #7e808c;
    font-size: 11px;
    border-top: 1px solid #33343f;
    padding: 8px 3px 0 3px;
}

/* Нижняя панель отделена линией: раньше блок сохранения сливался
   с кнопками очереди, стоящими прямо над ним. */
QWidget#BottomPanel {
    border-top: 1px solid #2f3040;
}

QLabel#PreviewBox {
    background-color: #202129;
    border: 1px solid #45475f;
    border-radius: 8px;
    color: #5f6070;
    font-size: 11px;
}

QLineEdit#ReadOnlyPath {
    background-color: #202129;
    color: #a9abb8;
    border: 1px solid #3a3b48;
}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #24252e;
    border: 1px solid #3a3b48;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e6e6e6;
    selection-background-color: #6c63ff;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    border: 1px solid #565a80;
}

/* Стрелка выпадающего списка: без неё поле неотличимо от обычного ввода. */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 22px;
}

QComboBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 10px;
    height: 7px;
    margin-right: 8px;
}

QComboBox::down-arrow:disabled {
    image: url("__ARROW_DOWN_OFF__");
}

/* Выпадающий список: своя карточка со скруглением и «воздухом» вокруг
   пунктов. По умолчанию Qt рисует плоский прямоугольник впритык к тексту,
   и на тёмной теме он выглядит инородно рядом со скруглёнными полями. */
QComboBox QAbstractItemView {
    background-color: #272834;
    border: 1px solid #45475f;
    border-radius: 8px;
    selection-background-color: #3a3d63;
    outline: none;
    padding: 5px;
}

QComboBox QAbstractItemView::item {
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 20px;
    border: none;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #32344a;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #4a4d7a;
    color: #ffffff;
}

/* Заголовок группы форматов: не выбирается, поэтому и выглядит как
   подпись, а не как пункт списка. */
/* Заголовок группы: цвет ему задаёт сам элемент (setForeground), поэтому
   ни здесь, ни у самого списка цвет не указан — любое правило QSS с color
   перебило бы цвет элемента, и подписи групп сливались бы с форматами. */
QComboBox QAbstractItemView::item:disabled {
    background: transparent;
    padding: 9px 8px 4px 8px;
    min-height: 0;
}

/* Счётчики: стрелки вверх/вниз, иначе поле выглядит как обычный ввод. */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    background-color: #2c2e3a;
    border-left: 1px solid #3a3b48;
    border-top-right-radius: 6px;
    width: 18px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    background-color: #2c2e3a;
    border-left: 1px solid #3a3b48;
    border-bottom-right-radius: 6px;
    width: 18px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #3d4060;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("__ARROW_UP__");
    width: 9px;
    height: 6px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 9px;
    height: 6px;
}

QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {
    image: url("__ARROW_UP_OFF__");
}

QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {
    image: url("__ARROW_DOWN_OFF__");
}

QCheckBox {
    spacing: 8px;
    color: #d7d8e0;
    background: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #4a4c60;
    background-color: #24252e;
}

QCheckBox::indicator:checked {
    background-color: #6c63ff;
    border: 1px solid #7a72ff;
}

QProgressBar {
    background-color: #24252e;
    border: 1px solid #45475f;
    border-radius: 6px;
    text-align: center;
    color: #e6e6e6;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #6c63ff;
    border-radius: 5px;
}

/* Цвет фона совпадает с панелями, внутри которых полосы появляются
   (список файлов и карточка настроек). «transparent» здесь не работает:
   Qt всё равно заливает полосу цветом из палитры окна, и в углах
   панелей просвечивал фон приложения. */
QScrollBar:vertical {
    background: #24252e;
    width: 12px;
    /* Без отступов: в них Qt рисует фон окна, и по краям панели
       оставались светлые просветы. Воздух даёт padding у ползунка. */
    margin: 0;
    padding: 3px 2px;
}

QScrollBar:horizontal {
    background: #24252e;
    height: 12px;
    margin: 0;
    padding: 2px 3px;
}

QScrollBar::handle:horizontal {
    background: #3a3b48;
    border-radius: 4px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #4a4c60;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: #24252e;
}

QScrollBar::handle:vertical {
    background: #3a3b48;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #4a4c60;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QSplitter::handle:horizontal {
    background-color: #1e1f26;
    width: 14px;
    /* Тонкая полоска-указатель по центру зазора между панелями. */
    image: none;
    border-left: 6px solid #1e1f26;
    border-right: 6px solid #1e1f26;
}

QSplitter::handle:horizontal:hover {
    border-left-color: #2c2e3a;
    border-right-color: #2c2e3a;
    background-color: #45475f;
}

QMessageBox {
    background-color: #24252e;
}

QToolTip {
    background-color: #2c2e3a;
    color: #e6e6e6;
    border: 1px solid #45475f;
    padding: 4px;
}
"""


def _draw_arrow(path, color, pointing_down):
    """Рисует маленький треугольник и сохраняет его в PNG для QSS."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QColor, QPainter, QPixmap, QPolygon

    width, height = 18, 12
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    margin_x, margin_y = 3, 3
    if pointing_down:
        points = [
            QPoint(margin_x, margin_y),
            QPoint(width - margin_x, margin_y),
            QPoint(width // 2, height - margin_y),
        ]
    else:
        points = [
            QPoint(margin_x, height - margin_y),
            QPoint(width - margin_x, height - margin_y),
            QPoint(width // 2, margin_y),
        ]
    painter.drawPolygon(QPolygon(points))
    painter.end()
    pixmap.save(path, "PNG")


def build_stylesheet():
    """Готовит таблицу стилей с уже сгенерированными иконками стрелок."""
    assets_dir = os.path.join(tempfile.gettempdir(), "media_converter_studio_assets")
    os.makedirs(assets_dir, exist_ok=True)

    icons = {
        "__ARROW_DOWN__": ("arrow_down.png", "#b9bbc9", True),
        "__ARROW_UP__": ("arrow_up.png", "#b9bbc9", False),
        "__ARROW_DOWN_OFF__": ("arrow_down_off.png", "#5f6070", True),
        "__ARROW_UP_OFF__": ("arrow_up_off.png", "#5f6070", False),
    }

    stylesheet = _STYLESHEET_TEMPLATE
    for placeholder, (file_name, color, pointing_down) in icons.items():
        icon_path = os.path.join(assets_dir, file_name)
        try:
            _draw_arrow(icon_path, color, pointing_down)
        except Exception:
            # Без иконок Qt нарисует стрелки сам — интерфейс не сломается.
            continue
        # В QSS путь всегда через прямые слэши, даже на Windows.
        stylesheet = stylesheet.replace(placeholder, icon_path.replace("\\", "/"))
    return stylesheet


# Совместимость: часть кода ожидает готовую строку стилей.
DARK_STYLESHEET = _STYLESHEET_TEMPLATE

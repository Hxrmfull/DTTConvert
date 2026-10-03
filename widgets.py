"""Собственные элементы управления.

ToggleSwitch — переключатель-тумблер вместо галочки. Наследуется от
QCheckBox, поэтому isChecked/setChecked/stateChanged работают как раньше,
и остальной код менять не нужно.
"""

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import (QAbstractButton, QCheckBox, QLabel, QStyle,
                             QStyledItemDelegate, QStyleOptionViewItem)

from styles import palette

TRACK_WIDTH = 38
TRACK_HEIGHT = 20
KNOB_MARGIN = 3
TEXT_GAP = 10



def toggle_colors(colors):
    """Цвета тумблера из палитры темы (см. styles.palette)."""
    return {
        "track_off": colors["toggle_track_off"],
        "track_off_border": colors["check_border"],
        "track_on": colors["accent"],
        "track_on_border": colors["accent_bright"],
        "knob_off": colors["toggle_knob_off"],
        "knob_on": colors["bright_text"],
        "track_off_disabled": colors["toggle_track_off_disabled"],
        "track_on_disabled": colors["toggle_track_on_disabled"],
        "knob_disabled": colors["faint_text"],
        "text": colors["check_text"],
        "text_disabled": colors["faint_text"],
        "focus": colors["focus_ring"],
    }


class ToggleSwitch(QCheckBox):
    """Переключатель: ползунок ездит влево-вправо и меняет цвет дорожки."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._offset = 0.0
        # Тумблер рисуется вручную, и таблица стилей до него не доходит:
        # цвета темы он получает через set_palette.
        self._colors = toggle_colors(palette())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Фокус только с клавиатуры: после щелчка мышью рамка фокуса
        # оставалась бы на тумблере и выглядела как ещё одно состояние.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate_to_state)

    def set_palette(self, colors):
        """Перекрашивает тумблер под тему (полная палитра styles.palette)."""
        self._colors = toggle_colors(colors)
        self.update()

    def _animate_to_state(self, checked):
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset)

    def sizeHint(self):
        base = super().sizeHint()
        metrics = self.fontMetrics()
        width = TRACK_WIDTH + (TEXT_GAP + metrics.horizontalAdvance(self.text())
                               if self.text() else 0)
        return base.expandedTo(base.__class__(width, max(TRACK_HEIGHT + 4, base.height())))

    def minimumSizeHint(self):
        # Подпись тумблера не сокращается: в тесной строке внизу окна
        # «Перезаписывать существующие файлы» обрезалось до «Перезаписывать су».
        return self.sizeHint()

    def hitButton(self, pos):
        # Кликабельна вся строка, а не только сама дорожка.
        return self.contentsRect().contains(pos)

    def setChecked(self, checked):
        super().setChecked(checked)
        # При программной установке анимация не нужна — сразу конечное положение.
        if not self._animation.state():
            self._offset = 1.0 if checked else 0.0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        enabled = self.isEnabled()
        checked = self.isChecked()
        colors = self._colors

        top = (self.height() - TRACK_HEIGHT) / 2
        track = QRectF(0, top, TRACK_WIDTH, TRACK_HEIGHT)

        if not enabled:
            track_color = colors["track_on_disabled"] if checked else colors["track_off_disabled"]
            border_color = track_color
            knob_color = colors["knob_disabled"]
        elif checked:
            track_color = colors["track_on"]
            border_color = colors["track_on_border"]
            knob_color = colors["knob_on"]
        else:
            track_color = colors["track_off"]
            border_color = colors["track_off_border"]
            knob_color = colors["knob_off"]

        radius = TRACK_HEIGHT / 2
        # Фокус клавиатуры — белая обводка дорожки в 2 px. Снаружи кольцу
        # места нет: дорожка начинается у самого края виджета, а расширять
        # тумблер нельзя — это сдвинуло бы вёрстку вкладок.
        if self.hasFocus():
            painter.setPen(QPen(QColor(colors["focus"]), 2))
            outline = track.adjusted(1, 1, -1, -1)
        else:
            painter.setPen(QPen(QColor(border_color), 1))
            outline = track.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(track_color))
        painter.drawRoundedRect(outline, radius, radius)

        diameter = TRACK_HEIGHT - KNOB_MARGIN * 2
        travel = TRACK_WIDTH - diameter - KNOB_MARGIN * 2
        knob_x = KNOB_MARGIN + travel * self._offset
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(knob_color))
        painter.drawEllipse(QRectF(knob_x, top + KNOB_MARGIN, diameter, diameter))

        if self.text():
            painter.setPen(QColor(colors["text"] if enabled else colors["text_disabled"]))
            text_rect = self.rect().adjusted(int(TRACK_WIDTH + TEXT_GAP), 0, 0, 0)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self.text(),
            )
        painter.end()


class ElidedLabel(QLabel):
    """Однострочная подпись, которая сокращается многоточием, а не
    распирает строку.

    text() возвращает полный текст, а не сокращённый: на него опираются
    тесты и экранный диктор. Полный текст показывается и в подсказке, пока
    подпись сокращена. Нужна для строки состояния внизу окна: итог
    обработки с кнопками «Открыть папку» и «Отчёт» туда не помещался и
    обрезался на полуслове, вместе с тумблером перезаписи.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._own_tooltip = ""

    def setToolTip(self, text):
        self._own_tooltip = text
        super().setToolTip(text)

    def minimumSizeHint(self):
        # Ширину отдаём соседям: сокращённая подпись лучше обрезанной кнопки.
        hint = super().minimumSizeHint()
        return QSize(self.fontMetrics().horizontalAdvance("…") * 4, hint.height())

    def paintEvent(self, _event):
        painter = QPainter(self)
        rect = self.contentsRect()
        full = self.text()
        elided = self.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight,
                                               rect.width())
        # Подсказка с полным текстом — только пока он не виден целиком.
        QLabel.setToolTip(self, full if elided != full else self._own_tooltip)
        self.style().drawItemText(
            painter, rect, int(self.alignment()), self.palette(), self.isEnabled(),
            elided, QPalette.ColorRole.WindowText)
        painter.end()


class MenuLabel(QLabel):
    """Подпись с контекстным меню, до которого можно добраться с клавиатуры.

    Номер версии открывает папку журнала двойным щелчком, а меню —
    правым. Мышью это работало, с клавиатуры — нет: подпись не брала
    фокус. Теперь до неё доходит Tab, а Enter, пробел, клавиша меню или
    Shift+F10 открывают то же меню.
    """

    menuRequested = pyqtSignal(QPoint)

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.menuRequested)

    def keyPressEvent(self, event):
        key = event.key()
        shift_f10 = (key == Qt.Key.Key_F10
                     and event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
                   Qt.Key.Key_Menu) or shift_f10:
            self.menuRequested.emit(self.rect().center())
            return
        super().keyPressEvent(event)


class ButtonCursorFilter(QObject):
    """Курсор подсказывает состояние: «рука» у доступной кнопки и
    «запрещено» у недоступной."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.EnabledChange and isinstance(watched, QAbstractButton):
            apply_button_cursor(watched)
        return False


def apply_button_cursor(button):
    button.setCursor(
        Qt.CursorShape.PointingHandCursor if button.isEnabled()
        else Qt.CursorShape.ForbiddenCursor
    )


class GroupHeaderDelegate(QStyledItemDelegate):
    """Приглушает заголовки групп в выпадающем списке форматов.

    Ни правило QSS `::item:disabled`, ни `setForeground` у самого элемента
    до текста не доходят: таблица стилей, заданная списку, перебивает
    и палитру элемента, и цвет из правила. Поэтому цвет подставляется
    прямо в палитру отрисовки — это единственный способ, который работает.
    """

    def __init__(self, header_color, parent=None, separator_color=None):
        super().__init__(parent)
        self._header_color = QColor(header_color)
        self._separator_color = QColor(separator_color or palette()["caption_line"])

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        # Черта над заголовком группы, кроме самого первого: без неё группы
        # сливались в один длинный список.
        if index.flags() & Qt.ItemFlag.ItemIsEnabled or index.row() == 0:
            return
        painter.save()
        painter.setPen(self._separator_color)
        y = option.rect.top() + 1
        painter.drawLine(option.rect.left() + 6, y, option.rect.right() - 6, y)
        painter.restore()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        for group in (QPalette.ColorGroup.Normal, QPalette.ColorGroup.Active,
                      QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
            for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                         QPalette.ColorRole.ButtonText):
                option.palette.setColor(group, role, self._header_color)


# Части подписи строки очереди: имя файла, хвост «(длительность) → формат»
# и подробность (процент или текст ошибки). Строку целиком держит обычный
# текст элемента — его читают тесты и экранный диктор, а делегат по этим
# частям решает, что сокращать, когда строка не помещается.
ITEM_PARTS_ROLE = Qt.ItemDataRole.UserRole + 1


def fit_item_text(metrics, available, name, tail, extra=""):
    """Подпись строки очереди в заданную ширину.

    Сокращается в первую очередь подробность (справа), потом имя файла —
    посередине, чтобы остались и начало, и расширение. Хвост «→ формат»
    не трогается: ради него строку и читают. Горизонтальной прокрутки у
    очереди нет — раньше длинное имя уводило за край и формат, и точку
    состояния.
    """
    full = name + tail + extra
    if metrics.horizontalAdvance(full) <= available:
        return full
    tail_width = metrics.horizontalAdvance(tail)
    min_name = min(metrics.horizontalAdvance(name), metrics.averageCharWidth() * 18)
    if extra:
        room = available - tail_width - min_name
        extra = metrics.elidedText(extra, Qt.TextElideMode.ElideRight, max(0, room))
    room = available - tail_width - metrics.horizontalAdvance(extra)
    name = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, max(0, room))
    text = name + tail + extra
    if metrics.horizontalAdvance(text) > available:
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, available)
    return text


class StatusDotDelegate(QStyledItemDelegate):
    """Рисует строку очереди и значок состояния у её правого края.

    Раньше состояние было текстом в скобках — значок считывается быстрее.
    Значки различаются не только цветом, но и формой: «готово» и
    «ожидание» при нарушениях цветового зрения иначе не различить.
    """

    # Состояние → роль цвета в палитре. Прерванный файл — не ошибка
    # и не успех, поэтому у него отдельный цвет.
    STATUS_ROLES = {
        "Ожидание": "status_pending",
        "Обработка": "status_processing",
        "Готово": "status_done",
        "Ошибка": "status_error",
        "Остановлено": "status_stopped",
    }
    DOT_RADIUS = 5
    RIGHT_PADDING = 16
    # Место под значок справа от текста: сам значок и зазор до подписи.
    STATUS_COLUMN = 22

    def __init__(self, status_of, parent=None):
        super().__init__(parent)
        self._status_of = status_of
        colors = palette()
        self._colors = {status: colors[role] for status, role in self.STATUS_ROLES.items()}

    def sizeHint(self, option, index):
        # Ширина строки — не по тексту, а минимальная: тогда список растягивает
        # строки ровно на свою ширину и не заводит горизонтальную прокрутку.
        size = super().sizeHint(option, index)
        return QSize(1, size.height())

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        parts = index.data(ITEM_PARTS_ROLE)
        widget = opt.widget
        style = widget.style() if widget is not None else None
        if parts and style is not None:
            text_rect = style.subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, opt, widget)
            available = text_rect.width() - self.STATUS_COLUMN
            opt.text = fit_item_text(opt.fontMetrics, available, *parts)
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        else:
            super().paint(painter, option, index)
        status = self._status_of(index)
        color = self._colors.get(status)
        if color is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        centre = QPointF(option.rect.right() - self.RIGHT_PADDING,
                         option.rect.center().y() + 1)
        self._draw_status_mark(painter, status, centre, QColor(color))
        painter.restore()

    def _draw_status_mark(self, painter, status, centre, color):
        r = self.DOT_RADIUS
        if status == "Готово":
            pen = QPen(color, 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath(QPointF(centre.x() - r, centre.y()))
            path.lineTo(centre.x() - r * 0.3, centre.y() + r * 0.7)
            path.lineTo(centre.x() + r, centre.y() - r * 0.8)
            painter.drawPath(path)
        elif status == "Ошибка":
            pen = QPen(color, 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            d = r * 0.8
            painter.drawLine(QPointF(centre.x() - d, centre.y() - d),
                             QPointF(centre.x() + d, centre.y() + d))
            painter.drawLine(QPointF(centre.x() - d, centre.y() + d),
                             QPointF(centre.x() + d, centre.y() - d))
        elif status == "Остановлено":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            side = r * 1.6
            painter.drawRoundedRect(QRectF(centre.x() - side / 2, centre.y() - side / 2,
                                           side, side), 1.5, 1.5)
        elif status == "Ожидание":
            # Пустое кольцо: файл ещё не трогали.
            painter.setPen(QPen(color, 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(centre, r - 0.8, r - 0.8)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(centre, r, r)

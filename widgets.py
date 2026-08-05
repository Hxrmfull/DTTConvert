"""Собственные элементы управления.

ToggleSwitch — переключатель-тумблер вместо галочки. Наследуется от
QCheckBox, поэтому isChecked/setChecked/stateChanged работают как раньше,
и остальной код менять не нужно.
"""

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QAbstractButton, QCheckBox, QStyledItemDelegate

TRACK_WIDTH = 38
TRACK_HEIGHT = 20
KNOB_MARGIN = 3
TEXT_GAP = 10

COLORS = {
    "track_off": "#383a48",
    "track_off_border": "#4a4c60",
    "track_on": "#6c63ff",
    "track_on_border": "#8a83ff",
    "knob_off": "#b9bbc9",
    "knob_on": "#ffffff",
    "track_off_disabled": "#26272f",
    "track_on_disabled": "#3a3760",
    "knob_disabled": "#5f6070",
    "text": "#d7d8e0",
    "text_disabled": "#5f6070",
}


class ToggleSwitch(QCheckBox):
    """Переключатель: ползунок ездит влево-вправо и меняет цвет дорожки."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._offset = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate_to_state)

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

        top = (self.height() - TRACK_HEIGHT) / 2
        track = QRectF(0, top, TRACK_WIDTH, TRACK_HEIGHT)

        if not enabled:
            track_color = COLORS["track_on_disabled"] if checked else COLORS["track_off_disabled"]
            border_color = track_color
            knob_color = COLORS["knob_disabled"]
        elif checked:
            track_color = COLORS["track_on"]
            border_color = COLORS["track_on_border"]
            knob_color = COLORS["knob_on"]
        else:
            track_color = COLORS["track_off"]
            border_color = COLORS["track_off_border"]
            knob_color = COLORS["knob_off"]

        painter.setPen(QPen(QColor(border_color), 1))
        painter.setBrush(QColor(track_color))
        radius = TRACK_HEIGHT / 2
        painter.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        diameter = TRACK_HEIGHT - KNOB_MARGIN * 2
        travel = TRACK_WIDTH - diameter - KNOB_MARGIN * 2
        knob_x = KNOB_MARGIN + travel * self._offset
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(knob_color))
        painter.drawEllipse(QRectF(knob_x, top + KNOB_MARGIN, diameter, diameter))

        if self.text():
            painter.setPen(QColor(COLORS["text"] if enabled else COLORS["text_disabled"]))
            text_rect = self.rect().adjusted(int(TRACK_WIDTH + TEXT_GAP), 0, 0, 0)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self.text(),
            )
        painter.end()


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

    SEPARATOR_COLOR = "#3c3f5c"

    def __init__(self, header_color, parent=None):
        super().__init__(parent)
        self._header_color = QColor(header_color)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        # Черта над заголовком группы, кроме самого первого: без неё группы
        # сливались в один длинный список.
        if index.flags() & Qt.ItemFlag.ItemIsEnabled or index.row() == 0:
            return
        painter.save()
        painter.setPen(QColor(self.SEPARATOR_COLOR))
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


class StatusDotDelegate(QStyledItemDelegate):
    """Рисует цветную точку состояния справа в строке очереди.

    Раньше состояние было текстом в скобках — цвет считывается быстрее.
    """

    STATUS_COLORS = {
        "Ожидание": "#6f7180",
        "Обработка": "#6c63ff",
        "Готово": "#4caf7d",
        "Ошибка": "#e05561",
        # Прерванный файл — не ошибка и не успех, поэтому отдельный цвет.
        "Остановлено": "#c9a227",
    }
    DOT_RADIUS = 5
    RIGHT_PADDING = 16

    def __init__(self, status_of, parent=None):
        super().__init__(parent)
        self._status_of = status_of

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setWidth(size.width() + self.DOT_RADIUS * 2 + self.RIGHT_PADDING)
        return size

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        status = self._status_of(index)
        color = self.STATUS_COLORS.get(status)
        if color is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        centre_x = option.rect.right() - self.RIGHT_PADDING
        centre_y = option.rect.center().y() + 1
        r = self.DOT_RADIUS
        painter.drawEllipse(QRectF(centre_x - r, centre_y - r, r * 2, r * 2))
        painter.restore()

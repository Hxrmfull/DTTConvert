"""Предпросмотр результата в макете чата площадки.

Показывает выбранный файл так, как его увидят в чате: смайлик Twitch
в строке чата на 28 px, эмодзи Discord в сообщении и крупным, стикер
Telegram и WhatsApp отдельно в переписке. Так сразу видно, читается ли
картинка в настоящем размере и как работает режим «заполнить квадрат».

Это не готовый файл, а та же геометрия, что применит обработчик:
вписывание или заполнение квадрата, поворот и отражение, размер на
экране. Лимиты веса здесь не проверяются — это дело обработки.
"""

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QImage, QMovie, QPainter,
                         QPainterPath, QPixmap, QTransform)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from i18n import tr

# Нижняя граница подобрана по самой тесной вкладке — Telegram с выбранным
# видео: выше неё вкладке понадобилась бы прокрутка при размере окна по
# умолчанию (см. tests/test_layout_normal.py).
PREVIEW_MIN_HEIGHT = 64
PREVIEW_MAX_HEIGHT = 170
PADDING = 12
# Мелкие подписи сцены («крупно», «кадр из видео», время сообщения).
# Было 10 px — на тёмном фоне чата они читались с трудом.
CAPTION_PX = 11
# Высота строки под подписью «крупно».
CAPTION_HEIGHT = 16

# Цвета сцен — из тёмных тем самих площадок, чтобы макет узнавался.
SCENES = {
    "twitch": {"bg": "#0e0e10", "panel": "#18181b", "text": "#efeff1",
               "muted": "#adadb8", "name": "#bf94ff", "accent": "#9146ff"},
    "discord": {"bg": "#313338", "panel": "#2b2d31", "text": "#dbdee1",
                "muted": "#949ba4", "name": "#f0b232", "accent": "#5865f2"},
    "telegram": {"bg": "#0e1621", "panel": "#182533", "text": "#f5f5f5",
                 # Приглушённый текст светлее, чем в самом Telegram: #6d7f8f
                 # давал 3,8 на пузыре сообщения — меньше AA.
                 "muted": "#8597a8", "name": "#64b5ef", "accent": "#2ea6ff"},
    "whatsapp": {"bg": "#0b141a", "panel": "#202c33", "text": "#e9edef",
                 "muted": "#8696a0", "name": "#25d366", "accent": "#00a884"},
}

# Прозрачность макета, пока пресет площадки не выбран.
INACTIVE_OPACITY = 0.3

SHAPE_SQUARE = "square"
SHAPE_STICKER = "sticker"


def render_emote(image, size, shape=SHAPE_SQUARE, fill=False, device_ratio=1.0):
    """Картинка в той геометрии, которую даст обработчик.

    SHAPE_SQUARE — квадрат size×size: вписать с прозрачными полями или
    заполнить с обрезкой по центру. SHAPE_STICKER — большая сторона
    равна size, пропорции сохраняются (стикер Telegram).
    """
    if image is None or image.isNull() or size <= 0:
        return QPixmap()
    pixels = max(1, int(round(size * device_ratio)))
    if shape == SHAPE_STICKER:
        scaled = image.scaled(pixels, pixels, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        pixmap = QPixmap.fromImage(scaled)
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap
    mode = (Qt.AspectRatioMode.KeepAspectRatioByExpanding if fill
            else Qt.AspectRatioMode.KeepAspectRatio)
    scaled = image.scaled(pixels, pixels, mode, Qt.TransformationMode.SmoothTransformation)
    canvas = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage((pixels - scaled.width()) // 2, (pixels - scaled.height()) // 2,
                      scaled)
    painter.end()
    pixmap = QPixmap.fromImage(canvas)
    pixmap.setDevicePixelRatio(device_ratio)
    return pixmap


def transformed(image, rotate=0, flip_horizontal=False, flip_vertical=False):
    """Поворот по часовой и отражение — в том же порядке, что у обработчика."""
    if image is None or image.isNull():
        return image
    if rotate % 360:
        image = image.transformed(QTransform().rotate(rotate % 360))
    if flip_horizontal or flip_vertical:
        image = image.mirrored(flip_horizontal, flip_vertical)
    return image


class ChatPreview(QWidget):
    """Макет чата одной площадки с выбранным файлом внутри."""

    def __init__(self, platform, parent=None):
        super().__init__(parent)
        self.platform = platform
        self._source = None        # исходный кадр без правок
        self._frame = None         # кадр с поворотом и отражением
        self._is_video = False
        self._movie = None
        self._code = ""
        self._fill = False
        self._transform = (0, False, False)
        self._active = True
        self._cache = {}
        self.setMinimumHeight(PREVIEW_MIN_HEIGHT)
        self.setMaximumHeight(PREVIEW_MAX_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # --- данные ---

    def sizeHint(self):
        return QSize(420, PREVIEW_MAX_HEIGHT)

    def minimumSizeHint(self):
        return QSize(200, PREVIEW_MIN_HEIGHT)

    def set_preset(self, code, fill):
        if (code, fill) == (self._code, self._fill):
            return
        self._code = code
        self._fill = bool(fill)
        self._cache.clear()
        self.update()

    def set_active(self, active):
        """Приглушает макет, пока пресет площадки не выбран: на выходе будет
        обычный формат, и показывать «вот так это будет в чате» нечестно."""
        active = bool(active)
        if active != self._active:
            self._active = active
            self.update()

    def set_transform(self, rotate, flip_horizontal, flip_vertical):
        value = (int(rotate) % 360, bool(flip_horizontal), bool(flip_vertical))
        if value == self._transform:
            return
        self._transform = value
        self._apply_transform()

    def set_image(self, image, is_video=False):
        """Неподвижный кадр. None — файла нет, показывается подсказка."""
        self._stop_movie()
        self._source = image if image is not None and not image.isNull() else None
        self._is_video = is_video
        self._apply_transform()

    def set_movie(self, path, first_frame=None):
        """Анимация (GIF, WEBP): проигрывается, пока предпросмотр на экране."""
        self._stop_movie()
        movie = QMovie(path)
        if not movie.isValid() or movie.frameCount() == 1:
            self.set_image(first_frame)
            return
        movie.setCacheMode(QMovie.CacheMode.CacheNone)
        movie.frameChanged.connect(self._on_movie_frame)
        self._movie = movie
        self._is_video = False
        self._source = first_frame
        self._apply_transform()
        if self.isVisible():
            movie.start()

    def has_content(self):
        return self._frame is not None

    def _stop_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie.frameChanged.disconnect(self._on_movie_frame)
            self._movie.deleteLater()
            self._movie = None

    def _on_movie_frame(self, _number):
        image = self._movie.currentImage() if self._movie is not None else None
        if image is None or image.isNull():
            return
        # Кадры анимации крупные, а показываются в десятки пикселей —
        # уменьшаем сразу, чтобы не масштабировать большой кадр трижды.
        if image.width() > 320 or image.height() > 320:
            image = image.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        self._source = image
        self._apply_transform()

    def _apply_transform(self):
        self._frame = transformed(self._source, *self._transform) if self._source else None
        self._cache.clear()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._movie is None:
            return
        # start() не снимает паузу, а скрытая вкладка ставит анимацию именно
        # на паузу — без этой ветки после возврата на вкладку смайлик замирал.
        if self._movie.state() == QMovie.MovieState.Paused:
            self._movie.setPaused(False)
        else:
            self._movie.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        # Скрытые вкладки анимацию не крутят: иначе декодировались бы кадры,
        # которые никто не видит.
        if self._movie is not None:
            self._movie.setPaused(True)

    # --- отрисовка ---

    def _emote(self, size, shape=SHAPE_SQUARE):
        key = (int(size), shape)
        pixmap = self._cache.get(key)
        if pixmap is None:
            pixmap = render_emote(self._frame, size, shape, self._fill,
                                  self.devicePixelRatioF())
            self._cache[key] = pixmap
        return pixmap

    def _scene(self):
        return SCENES.get(self.platform, SCENES["discord"])

    def _font(self, pixel_size, bold=False):
        font = QFont(self.font())
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        return font

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scene = self._scene()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QColor(scene["bg"]))
        painter.setClipPath(path)

        if self._frame is None:
            painter.setPen(QColor(scene["muted"]))
            painter.setFont(self._font(12))
            painter.drawText(rect.adjusted(PADDING, 0, -PADDING, 0),
                             int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                             tr("preview_empty"))
            painter.end()
            return

        if not self._active:
            painter.setOpacity(INACTIVE_OPACITY)
        paint = {
            "twitch": self._paint_twitch,
            "discord": self._paint_discord,
            "telegram": self._paint_telegram,
            "whatsapp": self._paint_whatsapp,
        }.get(self.platform, self._paint_discord)
        paint(painter, rect, scene)

        if self._is_video:
            painter.setPen(QColor(scene["muted"]))
            painter.setFont(self._font(CAPTION_PX))
            painter.drawText(rect.adjusted(0, 0, -8, -5),
                             int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
                             tr("preview_video_note"))
        painter.end()

    def _draw_text(self, painter, x, baseline, text, color, font):
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(int(x), int(baseline), text)
        return x + QFontMetrics(font).horizontalAdvance(text)

    def _zoom_tile(self, painter, rect, scene, size, shape=SHAPE_SQUARE):
        """Крупный вариант справа: виден рисунок целиком, с полями или обрезкой."""
        side = int(min(size, rect.height() - PADDING * 2 - CAPTION_HEIGHT))
        if side < 24:
            return rect.right()
        x = rect.right() - PADDING - side
        y = rect.top() + PADDING
        painter.fillRect(QRectF(x - 4, y - 4, side + 8, side + 8), QColor(scene["panel"]))
        pixmap = self._emote(side, shape)
        painter.drawPixmap(int(x + (side - pixmap.width() / pixmap.devicePixelRatio()) / 2),
                           int(y + (side - pixmap.height() / pixmap.devicePixelRatio()) / 2),
                           pixmap)
        painter.setPen(QColor(scene["muted"]))
        painter.setFont(self._font(CAPTION_PX))
        painter.drawText(QRectF(x - 10, y + side + 2, side + 20, CAPTION_HEIGHT),
                         int(Qt.AlignmentFlag.AlignHCenter), tr("preview_zoom"))
        return x - 12

    def _paint_twitch(self, painter, rect, scene):
        code = self._code
        if code == "twitch_badge_pack":
            badge, inline, zoom = 18, 0, 72
        elif code == "seventv_emote":
            badge, inline, zoom = 0, 32, 128
        else:
            badge, inline, zoom = 0, 28, 112
        right = self._zoom_tile(painter, rect, scene, zoom)
        line_height = max(28, inline)
        y = rect.top() + PADDING + 6
        name_font = self._font(13, bold=True)
        text_font = self._font(13)
        baseline_shift = (line_height + QFontMetrics(text_font).ascent()) / 2 - 2
        for row in range(2):
            x = rect.left() + PADDING
            if badge:
                painter.drawPixmap(int(x), int(y + (line_height - 18) / 2), self._emote(18))
                x += 22
            else:
                painter.setBrush(QColor(scene["accent"]))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(x, y + (line_height - 16) / 2, 16, 16), 3, 3)
                x += 20
            name = tr("preview_user") + (str(row + 1) if row else "")
            x = self._draw_text(painter, x, y + baseline_shift, name,
                                scene["name"] if not row else "#00b5ad", name_font)
            x = self._draw_text(painter, x, y + baseline_shift, ": ", scene["text"], text_font)
            if row == 0 or not inline:
                x = self._draw_text(painter, x, y + baseline_shift,
                                    tr("preview_msg_twitch") + " ", scene["text"], text_font)
            if inline and x + inline < right:
                painter.drawPixmap(int(x), int(y + (line_height - inline) / 2),
                                   self._emote(inline))
                if row:
                    x += inline + 4
                    if x + inline < right:
                        painter.drawPixmap(int(x), int(y + (line_height - inline) / 2),
                                           self._emote(inline))
            y += line_height + 8
            if y + line_height > rect.bottom() - PADDING:
                break

    def _paint_discord(self, painter, rect, scene):
        sticker = self._code.startswith("discord_sticker")
        x0 = rect.left() + PADDING
        y = rect.top() + PADDING
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(scene["accent"]))
        painter.drawEllipse(QRectF(x0, y, 36, 36))
        x = x0 + 48
        name_font = self._font(13, bold=True)
        x_after = self._draw_text(painter, x, y + 13, tr("preview_user"), scene["name"],
                                  name_font)
        self._draw_text(painter, x_after + 8, y + 13, tr("preview_today"), scene["muted"],
                        self._font(CAPTION_PX))
        available = rect.bottom() - PADDING - (y + 22)
        if sticker:
            side = int(min(160, available))
            painter.drawPixmap(int(x), int(y + 22), self._emote(side))
            return
        text_font = self._font(13)
        line_y = y + 22
        end = self._draw_text(painter, x, line_y + 16, tr("preview_msg_discord") + " ",
                              scene["text"], text_font)
        painter.drawPixmap(int(end), int(line_y + 1), self._emote(22))
        jumbo = int(min(48, available - 30))
        if jumbo >= 24:
            painter.drawPixmap(int(x), int(line_y + 28), self._emote(jumbo))
        self._zoom_tile(painter, rect, scene, 128)

    def _time_pill(self, painter, x, y, scene):
        font = self._font(CAPTION_PX)
        text = "12:00"
        width = QFontMetrics(font).horizontalAdvance(text) + 10
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(QRectF(x - width, y - 16, width, 16), 8, 8)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(x - width, y - 16, width, 16),
                         int(Qt.AlignmentFlag.AlignCenter), text)

    def _paint_telegram(self, painter, rect, scene):
        available = rect.height() - PADDING * 2
        if self._code.startswith("tg_sticker"):
            side = int(min(160, available))
            x = rect.left() + PADDING
            y = rect.top() + PADDING
            pixmap = self._emote(side, SHAPE_STICKER)
            painter.drawPixmap(int(x), int(y), pixmap)
            ratio = pixmap.devicePixelRatio() or 1
            self._time_pill(painter, x + pixmap.width() / ratio,
                            y + pixmap.height() / ratio, scene)
            return
        # Эмодзи: строкой в сообщении и крупным, как одиночное сообщение.
        text_font = self._font(13)
        text = tr("preview_msg_telegram") + " "
        width = QFontMetrics(text_font).horizontalAdvance(text) + 20 + 24
        bubble = QRectF(rect.left() + PADDING, rect.top() + PADDING, width + 16, 40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(scene["panel"]))
        painter.drawRoundedRect(bubble, 12, 12)
        end = self._draw_text(painter, bubble.left() + 12, bubble.top() + 25, text,
                              scene["text"], text_font)
        painter.drawPixmap(int(end), int(bubble.top() + 10), self._emote(20))
        big = int(min(100, available - 50))
        if big >= 32:
            x = bubble.left()
            y = bubble.bottom() + 8
            painter.drawPixmap(int(x), int(y), self._emote(big))
            self._time_pill(painter, x + big + 44, y + big, scene)

    def _paint_whatsapp(self, painter, rect, scene):
        available = rect.height() - PADDING * 2
        if self._code == "whatsapp_tray":
            x = rect.left() + PADDING
            y = rect.top() + PADDING
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(scene["panel"]))
            painter.drawRoundedRect(QRectF(x, y, rect.width() - PADDING * 2, 64), 10, 10)
            painter.drawPixmap(int(x + 8), int(y + 8), self._emote(48))
            self._draw_text(painter, x + 68, y + 28, tr("preview_pack"), scene["text"],
                            self._font(13, bold=True))
            self._draw_text(painter, x + 68, y + 46, "WhatsApp", scene["muted"],
                            self._font(11))
            return
        side = int(min(150, available))
        x = rect.right() - PADDING - side
        y = rect.top() + PADDING
        painter.drawPixmap(int(x), int(y), self._emote(side))
        self._time_pill(painter, x + side, y + side, scene)
        bubble = QRectF(rect.left() + PADDING, y, 120, 34)
        if bubble.right() + 8 < x:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(scene["panel"]))
            painter.drawRoundedRect(bubble, 8, 8)
            self._draw_text(painter, bubble.left() + 10, bubble.top() + 22,
                            tr("preview_msg_whatsapp"), scene["text"], self._font(13))

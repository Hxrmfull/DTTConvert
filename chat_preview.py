"""Предпросмотр результата в макете чата площадки.

Показывает выбранный файл так, как его увидят в чате: смайлик Twitch
в строке чата на 28 px, эмодзи Discord в сообщении и крупным, стикер
Telegram и WhatsApp отдельно в переписке. Так сразу видно, читается ли
картинка в настоящем размере и как работает режим «заполнить квадрат».

Это не готовый файл, а та же геометрия, что применит обработчик:
вписывание или заполнение квадрата, поворот и отражение, размер на
экране. Лимиты веса здесь не проверяются — это дело обработки.
"""

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QImage, QMovie, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF, QTransform)
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
# Время у сообщений во всех сценах.
PREVIEW_TIME = "18:04"

# Чат Twitch: значок у ника, иконка баллов, поле ввода и строка баллов.
TWITCH_BADGE_SIZE = 18
TWITCH_POINTS_SIZE = 20
TWITCH_INPUT_HEIGHT = 30
TWITCH_BALANCE_HEIGHT = 22
# Цвета ников «twitch» и «DJClancy».
TWITCH_NAME_COLORS = ("#bf94ff", "#00b5ad")

# Цвета сцен — из тёмных тем самих площадок, чтобы макет узнавался.
SCENES = {
    "twitch": {"bg": "#0e0e10", "panel": "#18181b", "text": "#efeff1",
               "muted": "#adadb8", "name": "#bf94ff", "accent": "#9146ff",
               "input": "#26262c"},
    # Пишет сам «Discord» — ник белый, как у аккаунта без цветной роли.
    "discord": {"bg": "#313338", "panel": "#2b2d31", "text": "#dbdee1",
                "muted": "#949ba4", "name": "#f2f3f5", "accent": "#5865f2"},
    "telegram": {"bg": "#0e1621", "panel": "#182533", "text": "#f5f5f5",
                 # Приглушённый текст светлее, чем в самом Telegram: #6d7f8f
                 # давал 3,8 на пузыре сообщения — меньше AA.
                 "muted": "#8597a8", "name": "#64b5ef", "accent": "#2ea6ff"},
    "whatsapp": {"bg": "#0b141a", "panel": "#202c33", "text": "#e9edef",
                 "muted": "#8696a0", "name": "#25d366", "accent": "#00a884"},
    "kick": {"bg": "#0b0e0f", "panel": "#191b1f", "text": "#ffffff",
             "muted": "#a3a7ab", "name": "#53fc18", "accent": "#53fc18",
             "input": "#24272c"},
    # Имя спонсора в живом чате YouTube зелёное, обычного зрителя — серое.
    "youtube": {"bg": "#0f0f0f", "panel": "#212121", "text": "#f1f1f1",
                "muted": "#aaaaaa", "name": "#2ba640", "accent": "#ff0000",
                "input": "#272727"},
}

# Чат Kick: значок у ника и цвета ников.
KICK_BADGE_SIZE = 18
KICK_NAME_COLORS = ("#53fc18", "#f2a83b")
# Живой чат YouTube: аватар, значок спонсора у имени, эмодзи в строке.
YOUTUBE_AVATAR_SIZE = 24
YOUTUBE_BADGE_SIZE = 16
YOUTUBE_INLINE_EMOJI = 24
YOUTUBE_AVATAR_COLORS = ("#7e57c2", "#00897b")

# Прозрачность макета, пока пресет площадки не выбран.
INACTIVE_OPACITY = 0.3

SHAPE_SQUARE = "square"
SHAPE_STICKER = "sticker"
# Смайлик 7TV: высота size, ширина по пропорциям (до WIDE_MAX_ASPECT).
SHAPE_WIDE = "wide"
WIDE_MAX_ASPECT = 3.0


# --- нарисованные значки сцен ---
# Рисуются кодом, а не картинками из файлов: так нет сторонних ресурсов,
# и значки чёткие при любом масштабе экрана.

def _scaled(rect, points):
    """Точки в долях квадрата rect (0..1) → координаты на экране."""
    return [QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height())
            for x, y in points]


def draw_star_badge(painter, rect, color):
    """Обычный значок подписчика: белая звезда на скруглённом квадрате."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    radius = rect.width() * 0.22
    painter.drawRoundedRect(rect, radius, radius)
    centre = rect.center()
    outer, inner = rect.width() * 0.34, rect.width() * 0.15
    points = []
    for index in range(10):
        angle = math.pi * index / 5 - math.pi / 2
        length = outer if index % 2 == 0 else inner
        points.append(QPointF(centre.x() + length * math.cos(angle),
                              centre.y() + length * math.sin(angle)))
    # На светлой подложке (зелёный Kick) звезда тёмная, на тёмной — белая.
    light = color.lightnessF() > 0.55
    painter.setBrush(QColor("#0b0e0f") if light else QColor("#ffffff"))
    painter.drawPolygon(QPolygonF(points))
    painter.restore()


def draw_letter_avatar(painter, rect, color, letter):
    """Аватар без картинки: первая буква имени в цветном круге."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(rect)
    font = QFont(painter.font())
    font.setPixelSize(int(rect.height() * 0.55))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), letter.upper())
    painter.restore()


def draw_twitch_gem_badge(painter, rect):
    """Значок «twitch»: белый алмаз на малиновом скруглённом квадрате."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#e00ab8"))
    radius = rect.width() * 0.18
    painter.drawRoundedRect(rect, radius, radius)
    gem = QPolygonF(_scaled(rect, ((0.33, 0.27), (0.67, 0.27), (0.81, 0.43),
                                   (0.5, 0.79), (0.19, 0.43))))
    painter.setBrush(QColor("#ffffff"))
    painter.drawPolygon(gem)
    # Грань алмаза — тонкая линия цвета подложки, иначе это просто пятиугольник.
    pen = QPen(QColor("#e00ab8"), max(1.0, rect.width() * 0.06))
    painter.setPen(pen)
    left, right = _scaled(rect, ((0.22, 0.43), (0.78, 0.43)))
    painter.drawLine(left, right)
    painter.restore()


def draw_twitch_verified_badge(painter, rect):
    """Значок «DJClancy»: белая галочка на фиолетовой «печати» с зубцами."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    centre = rect.center()
    outer, inner = rect.width() / 2, rect.width() / 2 * 0.86
    points = []
    teeth = 8
    for index in range(teeth * 2):
        angle = math.pi * index / teeth - math.pi / 2
        radius = outer if index % 2 == 0 else inner
        points.append(QPointF(centre.x() + radius * math.cos(angle),
                              centre.y() + radius * math.sin(angle)))
    seal = QPolygonF(points)
    color = QColor("#9146ff")
    # Обводка тем же цветом со скруглёнными стыками скругляет и зубцы.
    pen = QPen(color, rect.width() * 0.08)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(color)
    painter.drawPolygon(seal)
    check = QPen(QColor("#ffffff"), rect.width() * 0.13)
    check.setCapStyle(Qt.PenCapStyle.RoundCap)
    check.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(check)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    start, middle, end = _scaled(rect, ((0.31, 0.52), (0.45, 0.65), (0.70, 0.37)))
    path.moveTo(start)
    path.lineTo(middle)
    path.lineTo(end)
    painter.drawPath(path)
    painter.restore()


def draw_twitch_bits(painter, rect):
    """Битсы Twitch — фиолетовый кристалл-треугольник."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#a970ff"))
    painter.drawPolygon(QPolygonF(_scaled(rect, ((0.5, 0.05), (0.92, 0.62),
                                                 (0.5, 0.95), (0.08, 0.62)))))
    painter.setBrush(QColor("#d2b8ff"))
    painter.drawPolygon(QPolygonF(_scaled(rect, ((0.5, 0.05), (0.5, 0.95),
                                                 (0.08, 0.62)))))
    painter.restore()


def draw_twitch_points(painter, rect, color):
    """Стандартная иконка баллов канала: кольцо с «искрой» внутри.

    Её заменяет иконка, которую пользователь делает пресетом баллов."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    width = max(1.5, rect.width() * 0.11)
    painter.setPen(QPen(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = width / 2 + rect.width() * 0.04
    painter.drawEllipse(rect.adjusted(inset, inset, -inset, -inset))
    spark = QPainterPath()
    centre = rect.center()
    size = rect.width() * 0.2
    spark.moveTo(centre.x(), centre.y() - size)
    spark.quadTo(centre.x(), centre.y(), centre.x() + size, centre.y())
    spark.quadTo(centre.x(), centre.y(), centre.x(), centre.y() + size)
    spark.quadTo(centre.x(), centre.y(), centre.x() - size, centre.y())
    spark.quadTo(centre.x(), centre.y(), centre.x(), centre.y() - size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(spark)
    painter.restore()


def draw_smiley_outline(painter, rect, color):
    """Кнопка выбора смайликов в поле ввода — контурная улыбка."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(rect.adjusted(0.8, 0.8, -0.8, -0.8))
    w, h = rect.width(), rect.height()
    painter.drawArc(QRectF(rect.left() + w * 0.28, rect.top() + h * 0.30, w * 0.44, h * 0.42),
                    200 * 16, 140 * 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    for x in (0.36, 0.64):
        painter.drawEllipse(QPointF(rect.left() + w * x, rect.top() + h * 0.40),
                            w * 0.07, w * 0.07)
    painter.restore()


def draw_gear_outline(painter, rect, color):
    """Шестерёнка настроек чата."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    centre = rect.center()
    outer, inner = rect.width() * 0.48, rect.width() * 0.36
    points = []
    teeth = 8
    for index in range(teeth * 4):
        angle = 2 * math.pi * index / (teeth * 4)
        radius = outer if index % 4 in (0, 1) else inner
        points.append(QPointF(centre.x() + radius * math.cos(angle),
                              centre.y() + radius * math.sin(angle)))
    pen = QPen(color, 1.5)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolygon(QPolygonF(points))
    painter.drawEllipse(centre, rect.width() * 0.15, rect.width() * 0.15)
    painter.restore()


def draw_discord_avatar(painter, rect, color):
    """Аватар «пользователя Discord»: белый Clyde на круге фирменного цвета."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(rect)
    # Логотип вписан в прямоугольник 0,6 × 0,46 диаметра по центру.
    w, h = rect.width() * 0.6, rect.width() * 0.46
    left = rect.center().x() - w / 2
    top = rect.center().y() - h / 2

    def at(x, y):
        return QPointF(left + x * w, top + y * h)

    clyde = QPainterPath(at(0.27, 0.04))
    clyde.cubicTo(at(0.40, -0.03), at(0.60, -0.03), at(0.73, 0.04))
    clyde.cubicTo(at(0.87, 0.10), at(0.98, 0.42), at(1.0, 0.83))
    clyde.cubicTo(at(0.93, 0.93), at(0.85, 0.99), at(0.77, 1.0))
    clyde.lineTo(at(0.70, 0.87))
    clyde.cubicTo(at(0.57, 0.92), at(0.43, 0.92), at(0.30, 0.87))
    clyde.lineTo(at(0.23, 1.0))
    clyde.cubicTo(at(0.15, 0.99), at(0.07, 0.93), at(0.0, 0.83))
    clyde.cubicTo(at(0.02, 0.42), at(0.13, 0.10), at(0.27, 0.04))
    clyde.closeSubpath()
    painter.setBrush(QColor("#ffffff"))
    painter.drawPath(clyde)
    painter.setBrush(color)
    for x in (0.35, 0.65):
        painter.drawEllipse(at(x, 0.56), w * 0.085, h * 0.13)
    painter.restore()



def render_emote(image, size, shape=SHAPE_SQUARE, fill=False, device_ratio=1.0):
    """Картинка в той геометрии, которую даст обработчик.

    SHAPE_SQUARE — квадрат size×size: вписать с прозрачными полями или
    заполнить с обрезкой по центру. SHAPE_STICKER — большая сторона
    равна size, пропорции сохраняются (стикер Telegram).
    """
    if image is None or image.isNull() or size <= 0:
        return QPixmap()
    pixels = max(1, int(round(size * device_ratio)))
    if shape == SHAPE_WIDE and not fill:
        aspect = min(image.width() / max(1, image.height()), WIDE_MAX_ASPECT)
        scaled = image.scaled(max(1, int(round(pixels * aspect))), pixels,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        pixmap = QPixmap.fromImage(scaled)
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap
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
        # Статичный пресет: анимация стоит на первом кадре — в файл попадёт
        # именно он. Видео при этом подписано «кадр из видео».
        self._still = False
        self._movie_from_video = False
        # Окно неактивно или свёрнуто — анимация стоит на текущем кадре.
        self._suspended = False
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

    def set_suspended(self, suspended):
        """Пауза, пока окно программы неактивно: на него не смотрят, и
        кадры декодировались бы впустую."""
        suspended = bool(suspended)
        if suspended == self._suspended:
            return
        self._suspended = suspended
        if self._movie is None:
            return
        if suspended:
            self._movie.setPaused(True)
        elif self.isVisible() and not self._still:
            self._resume_movie()

    def set_still(self, still):
        """Показывать первый кадр вместо анимации (пресет даёт картинку)."""
        still = bool(still)
        if still == self._still:
            return
        self._still = still
        if self._movie is None:
            return
        if still:
            self._movie.setPaused(True)
            self._movie.jumpToFrame(0)
            self._on_movie_frame(0)
        elif self.isVisible() and not self._suspended:
            self._resume_movie()
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

    def set_movie(self, path, first_frame=None, from_video=False):
        """Анимация (GIF, WEBP): проигрывается, пока предпросмотр на экране.

        from_video — копия сделана из видео: на статичном пресете она стоит
        на первом кадре с подписью «кадр из видео».
        """
        self._stop_movie()
        self._movie_from_video = bool(from_video)
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
        if self._still:
            movie.jumpToFrame(0)
            self._on_movie_frame(0)
        elif self.isVisible():
            movie.start()
            if self._suspended:
                movie.setPaused(True)

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
        if self._movie is None or self._still or self._suspended:
            return
        self._resume_movie()

    def _resume_movie(self):
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
            "kick": self._paint_kick,
            "youtube": self._paint_youtube,
        }.get(self.platform, self._paint_discord)
        paint(painter, rect, scene)

        if self._is_video or (self._still and self._movie_from_video):
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
        """Чат Twitch: две строки сообщений, поле ввода и строка баллов.

        Значки у ников нарисованы по умолчанию (алмаз у «twitch», галочка у
        «DJClancy»); пресет значка подписки ставит на их место картинку
        пользователя. Пресет баллов — в строку под полем ввода, туда, где
        Twitch показывает иконку баллов канала рядом с их числом.
        """
        code = self._code
        badge_preset = code == "twitch_badge_pack"
        points_preset = code == "twitch_points_pack"
        if badge_preset:
            inline, zoom = 0, 72
        elif points_preset:
            inline, zoom = 0, 112
        elif code == "seventv_emote":
            inline, zoom = 32, 128
        else:
            inline, zoom = 28, 112
        # Крупно 7TV показывается целиком в своих пропорциях, а не в квадрате.
        zoom_shape = SHAPE_STICKER if code == "seventv_emote" and not self._fill \
            else SHAPE_SQUARE
        right = self._zoom_tile(painter, rect, scene, zoom, zoom_shape)
        chat = QRectF(rect.left() + PADDING, rect.top() + PADDING,
                      right - rect.left() - PADDING, rect.height() - PADDING * 2)
        line_height = max(TWITCH_BADGE_SIZE + 6, inline)
        messages_height = line_height * 2 + 6
        bottom_height = TWITCH_INPUT_HEIGHT + 6 + TWITCH_BALANCE_HEIGHT
        # Когда окно невысокое, всё не помещается: остаётся то, ради чего
        # пресет, — строка баллов для иконки баллов, сообщения для остальных.
        fits_both = chat.height() >= messages_height + 8 + bottom_height
        if fits_both or not points_preset:
            self._twitch_messages(painter, chat, scene, line_height, inline, badge_preset)
        if fits_both or (points_preset and chat.height() >= bottom_height):
            self._twitch_bottom(painter, chat, scene, inline, points_preset)

    def _twitch_messages(self, painter, chat, scene, line_height, inline, badge_preset):
        name_font = self._font(13, bold=True)
        text_font = self._font(13)
        baseline_shift = (line_height + QFontMetrics(text_font).ascent()) / 2 - 2
        rows = (("twitch", TWITCH_NAME_COLORS[0], draw_twitch_gem_badge),
                ("DJClancy", TWITCH_NAME_COLORS[1], draw_twitch_verified_badge))
        y = chat.top()
        for row, (name, color, draw_badge) in enumerate(rows):
            if y + line_height > chat.bottom() + 1:
                break
            x = chat.left()
            badge_rect = QRectF(x, y + (line_height - TWITCH_BADGE_SIZE) / 2,
                                TWITCH_BADGE_SIZE, TWITCH_BADGE_SIZE)
            if badge_preset:
                # Значок, который делает пользователь, — на месте стандартного.
                painter.drawPixmap(badge_rect.topLeft().toPoint(),
                                   self._emote(TWITCH_BADGE_SIZE))
            else:
                draw_badge(painter, badge_rect)
            x += TWITCH_BADGE_SIZE + 4
            x = self._draw_text(painter, x, y + baseline_shift, name, color, name_font)
            x = self._draw_text(painter, x, y + baseline_shift, ": ", scene["text"], text_font)
            if row == 0 or not inline:
                x = self._draw_text(painter, x, y + baseline_shift,
                                    tr("preview_msg_twitch") + " ", scene["text"], text_font)
            emotes = 1 if row == 0 else 2
            shape = SHAPE_WIDE if self._code == "seventv_emote" else SHAPE_SQUARE
            for _ in range(emotes if inline else 0):
                pixmap = self._emote(inline, shape)
                width = pixmap.width() / (pixmap.devicePixelRatio() or 1)
                if x + width > chat.right():
                    break
                painter.drawPixmap(int(x), int(y + (line_height - inline) / 2), pixmap)
                x += width + 4
            y += line_height + 6

    def _twitch_bottom(self, painter, chat, scene, inline, points_preset):
        """Поле «Отправить сообщение» и строка баллов, как под чатом Twitch."""
        top = chat.bottom() - TWITCH_INPUT_HEIGHT - 6 - TWITCH_BALANCE_HEIGHT
        field = QRectF(chat.left(), top, chat.width(), TWITCH_INPUT_HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(scene["input"]))
        painter.drawRoundedRect(field, 6, 6)
        icon = 20
        icon_y = field.top() + (field.height() - icon) / 2
        x = field.left() + 6
        if inline:
            # Слева в поле Twitch показывает смайлик — пусть это будет свой.
            painter.drawPixmap(int(x), int(icon_y), self._emote(icon))
        else:
            draw_smiley_outline(painter, QRectF(x + 2, icon_y + 2, icon - 4, icon - 4),
                                QColor(scene["muted"]))
        x += icon + 8
        text_font = self._font(13)
        baseline = field.top() + (field.height() + QFontMetrics(text_font).ascent()) / 2 - 2
        self._draw_text(painter, x, baseline, tr("preview_send_message"), scene["muted"],
                        text_font)
        draw_smiley_outline(painter, QRectF(field.right() - 24, icon_y + 2, 16, 16),
                            QColor(scene["muted"]))

        row = QRectF(chat.left(), field.bottom() + 6, chat.width(), TWITCH_BALANCE_HEIGHT)
        small_font = self._font(12, bold=True)
        baseline = row.top() + (row.height() + QFontMetrics(small_font).ascent()) / 2 - 2
        x = row.left() + 2
        draw_twitch_bits(painter, QRectF(x, row.top() + 4, 14, 14))
        x = self._draw_text(painter, x + 18, baseline, "0", scene["text"], small_font) + 14
        points_rect = QRectF(x, row.top() + (row.height() - TWITCH_POINTS_SIZE) / 2,
                             TWITCH_POINTS_SIZE, TWITCH_POINTS_SIZE)
        if points_preset:
            # Иконка баллов пользователя — на месте стандартной.
            painter.drawPixmap(points_rect.topLeft().toPoint(), self._emote(TWITCH_POINTS_SIZE))
        else:
            draw_twitch_points(painter, points_rect, QColor(scene["text"]))
        self._draw_text(painter, x + TWITCH_POINTS_SIZE + 5, baseline,
                        tr("preview_points_balance"), scene["text"], small_font)

        button_font = self._font(12, bold=True)
        label = tr("preview_chat_button")
        width = QFontMetrics(button_font).horizontalAdvance(label) + 20
        button = QRectF(row.right() - width, row.top(), width, row.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(scene["accent"]))
        painter.drawRoundedRect(button, 4, 4)
        painter.setFont(button_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(button, int(Qt.AlignmentFlag.AlignCenter), label)
        draw_gear_outline(painter, QRectF(button.left() - 26, row.top() + 3, 16, 16),
                          QColor(scene["muted"]))

    def _paint_kick(self, painter, rect, scene):
        """Чат Kick: две строки сообщений и поле ввода под ними.

        Пресет значка подписки ставит картинку пользователя на место
        значка у ника, смайлики — в текст сообщений.
        """
        badge_preset = self._code == "kick_badge_pack"
        inline, zoom = (0, 72) if badge_preset else (28, 112)
        right = self._zoom_tile(painter, rect, scene, zoom)
        chat = QRectF(rect.left() + PADDING, rect.top() + PADDING,
                      right - rect.left() - PADDING, rect.height() - PADDING * 2)
        line_height = max(KICK_BADGE_SIZE + 6, inline)
        name_font = self._font(13, bold=True)
        text_font = self._font(13)
        baseline_shift = (line_height + QFontMetrics(text_font).ascent()) / 2 - 2
        y = chat.top()
        for row, (name, color) in enumerate((("streamer", KICK_NAME_COLORS[0]),
                                             ("Viewer42", KICK_NAME_COLORS[1]))):
            if y + line_height > chat.bottom() + 1:
                break
            x = chat.left()
            badge_rect = QRectF(x, y + (line_height - KICK_BADGE_SIZE) / 2,
                                KICK_BADGE_SIZE, KICK_BADGE_SIZE)
            if badge_preset:
                painter.drawPixmap(badge_rect.topLeft().toPoint(),
                                   self._emote(KICK_BADGE_SIZE))
            else:
                draw_star_badge(painter, badge_rect, QColor(scene["accent"]))
            x += KICK_BADGE_SIZE + 4
            x = self._draw_text(painter, x, y + baseline_shift, name, color, name_font)
            x = self._draw_text(painter, x, y + baseline_shift, ": ", scene["text"], text_font)
            if row == 0 or not inline:
                x = self._draw_text(painter, x, y + baseline_shift,
                                    tr("preview_msg_kick") + " ", scene["text"], text_font)
            for _ in range((1 if row == 0 else 2) if inline else 0):
                if x + inline > chat.right():
                    break
                painter.drawPixmap(int(x), int(y + (line_height - inline) / 2),
                                   self._emote(inline))
                x += inline + 4
            y += line_height + 6
        field_top = chat.bottom() - TWITCH_INPUT_HEIGHT
        if field_top >= y:
            field = QRectF(chat.left(), field_top, chat.width(), TWITCH_INPUT_HEIGHT)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(scene["input"]))
            painter.drawRoundedRect(field, 6, 6)
            baseline = field.top() + (field.height() + QFontMetrics(text_font).ascent()) / 2 - 2
            self._draw_text(painter, field.left() + 10, baseline, tr("preview_send_message"),
                            scene["muted"], text_font)
            draw_smiley_outline(painter, QRectF(field.right() - 24, field.top() + 7, 16, 16),
                                QColor(scene["muted"]))

    def _paint_youtube(self, painter, rect, scene):
        """Живой чат YouTube: аватар, имя, значок спонсора и сообщение.

        Пресет значка ставит картинку пользователя у имени спонсора,
        эмодзи — в текст сообщения, как YouTube показывает их в чате.
        """
        badge_preset = self._code == "youtube_badge"
        inline = 0 if badge_preset else YOUTUBE_INLINE_EMOJI
        right = self._zoom_tile(painter, rect, scene, 64 if badge_preset else 112)
        chat = QRectF(rect.left() + PADDING, rect.top() + PADDING,
                      right - rect.left() - PADDING, rect.height() - PADDING * 2)
        line_height = max(YOUTUBE_AVATAR_SIZE, inline) + 4
        name_font = self._font(13, bold=True)
        text_font = self._font(13)
        baseline_shift = (line_height + QFontMetrics(text_font).ascent()) / 2 - 2
        rows = (("Alex", scene["name"], True), ("Maria", scene["muted"], False))
        y = chat.top()
        for row, (name, color, member) in enumerate(rows):
            if y + line_height > chat.bottom() + 1:
                break
            x = chat.left()
            avatar = QRectF(x, y + (line_height - YOUTUBE_AVATAR_SIZE) / 2,
                            YOUTUBE_AVATAR_SIZE, YOUTUBE_AVATAR_SIZE)
            draw_letter_avatar(painter, avatar, QColor(YOUTUBE_AVATAR_COLORS[row]), name[0])
            x += YOUTUBE_AVATAR_SIZE + 8
            x = self._draw_text(painter, x, y + baseline_shift, name, color, name_font) + 4
            if member:
                badge_rect = QRectF(x, y + (line_height - YOUTUBE_BADGE_SIZE) / 2,
                                    YOUTUBE_BADGE_SIZE, YOUTUBE_BADGE_SIZE)
                if badge_preset:
                    painter.drawPixmap(badge_rect.topLeft().toPoint(),
                                       self._emote(YOUTUBE_BADGE_SIZE))
                else:
                    draw_star_badge(painter, badge_rect, QColor(scene["name"]))
                x += YOUTUBE_BADGE_SIZE + 6
            text = tr("preview_msg_youtube") if row == 0 else tr("preview_msg_youtube2")
            x = self._draw_text(painter, x, y + baseline_shift, text + " ",
                                scene["text"], text_font)
            if inline and x + inline <= chat.right():
                painter.drawPixmap(int(x), int(y + (line_height - inline) / 2),
                                   self._emote(inline))
            y += line_height + 6

    def _paint_discord(self, painter, rect, scene):
        sticker = self._code.startswith("discord_sticker")
        x0 = rect.left() + PADDING
        y = rect.top() + PADDING
        # Сообщение от «пользователя Discord» с логотипом вместо аватара.
        draw_discord_avatar(painter, QRectF(x0, y, 36, 36), QColor(scene["accent"]))
        x = x0 + 48
        name_font = self._font(13, bold=True)
        x_after = self._draw_text(painter, x, y + 13, "Discord", scene["name"], name_font)
        self._draw_text(painter, x_after + 8, y + 13, tr("preview_today", time=PREVIEW_TIME),
                        scene["muted"], self._font(CAPTION_PX))
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

    def _time_pill(self, painter, x, y, scene, background=None):
        """Время сообщения в «таблетке», правый нижний угол — в (x, y).

        На картинке (стикер) — полупрозрачная тёмная, как в самих
        мессенджерах; рядом с картинкой — цвета пузыря (background)."""
        font = self._font(CAPTION_PX)
        width = QFontMetrics(font).horizontalAdvance(PREVIEW_TIME) + 12
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background) if background else QColor(0, 0, 0, 120))
        painter.drawRoundedRect(QRectF(x - width, y - 18, width, 18), 9, 9)
        painter.setFont(font)
        painter.setPen(QColor(scene["text"]) if background else QColor("#ffffff"))
        painter.drawText(QRectF(x - width, y - 18, width, 18),
                         int(Qt.AlignmentFlag.AlignCenter), PREVIEW_TIME)

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
        # Эмодзи — как в Telegram: строкой в сообщении («оцени новый эмодзи»
        # с временем внутри пузыря) и следом крупным, отдельным сообщением
        # без пузыря, с временем в таблетке справа.
        text_font = self._font(13)
        time_font = self._font(CAPTION_PX)
        text = tr("preview_msg_telegram") + " "
        inline = 20
        text_width = QFontMetrics(text_font).horizontalAdvance(text)
        time_width = QFontMetrics(time_font).horizontalAdvance(PREVIEW_TIME)
        bubble = QRectF(rect.left() + PADDING, rect.top() + PADDING,
                        12 + text_width + inline + 10 + time_width + 10, 34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(scene["panel"]))
        painter.drawRoundedRect(bubble, 12, 12)
        end = self._draw_text(painter, bubble.left() + 12, bubble.top() + 22, text,
                              scene["text"], text_font)
        painter.drawPixmap(int(end), int(bubble.top() + 7), self._emote(inline))
        self._draw_text(painter, bubble.right() - 10 - time_width, bubble.top() + 24,
                        PREVIEW_TIME, scene["muted"], time_font)
        big = int(min(100, available - bubble.height() - 8))
        if big >= 32:
            x = bubble.left()
            y = bubble.bottom() + 8
            painter.drawPixmap(int(x), int(y), self._emote(big))
            self._time_pill(painter, x + big + 54, y + big, scene, background=scene["panel"])

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

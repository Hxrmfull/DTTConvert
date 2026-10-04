import csv
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass

from PyQt6.QtCore import (Qt, QEasingCurve, QEvent, QLocale, QPoint, QPropertyAnimation,
                          QSettings, QSize, QThread, QTimer, QUrl, pyqtSignal)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QImage,
    QImageReader,
    QKeySequence,
    QMovie,
    QPainter,
    QPen,
    QPixmap,
    QFont,
    QFontInfo,
    QFontMetrics,
    QShortcut,
    QStandardItem,
)
from PyQt6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QAbstractButton,
    QAbstractSpinBox,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QMessageBox,
    QSplitter,
    QSystemTrayIcon,
    QStackedWidget,
    QScrollArea,
    QFrame,
    QGraphicsOpacityEffect,
)

from animation_info import animated_image_info
from lottie_utils import is_tgs, representative_frame
from app_info import APP_NAME, ORGANIZATION, RELEASES_URL, version_string, window_title
from updater import (UpdateCheckWorker, UpdateDownloadWorker, installed_variant,
                     is_newer, launch_installer)
from i18n import (ENGLISH, LANGUAGE_NAMES, LANGUAGE_ORDER, current_language,
                  language_from_locale, number, plural, set_language, tr)
from discord_utils import (
    DISCORD_PRESET_COLUMNS,
    discord_hint,
    is_discord_format,
)
from errors import first_line, message_text
import media_motion
import url_import
from styles import (THEME_MAIN, build_stylesheet, palette, theme_for_tab)
from chat_preview import ChatPreview
from stream_platforms import (SQUARE_PLATFORMS, is_square_platform_format,
                              square_hint, square_platform, square_preset_label)
from whatsapp_utils import (
    WHATSAPP_PRESET_COLUMNS,
    WHATSAPP_STATIC,
    is_whatsapp_format,
    whatsapp_hint,
    whatsapp_preset_label,
)
from ffmpeg_utils import INDETERMINATE_PROGRESS, check_ffmpeg_available
from format_names import PLATFORM_LABEL_KEYS, format_label
from job_model import (
    AUDIO_KEEP,
    AUDIO_NONE,
    ConversionJob,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_QUALITY,
    JobSettings,
)
from telegram_utils import (
    MAX_VIDEO_DURATION_SEC,
    is_telegram_emoji_format,
    is_telegram_format,
    is_telegram_video_format,
    telegram_hint,
)
from widgets import (
    ButtonCursorFilter,
    ElidedLabel,
    round_combo_popup,
    GroupHeaderDelegate,
    ITEM_PARTS_ROLE,
    PopupMenu,
    StatusDotDelegate,
    ToggleSwitch,
    apply_button_cursor,
)
from worker import (
    ANIMATABLE_IMAGE_EXTS,
    ANIMATED_WEBP_EXT,
    TGS_EXT,
    GIF_EXT,
    IMAGE_EXTS,
    VIDEO_EXTS,
    ConversionWorker,
    get_category,
    is_static_target,
)
from twitch_utils import (
    TWITCH_MIN_SMOOTH_FPS,
    TWITCH_PRESET_COLUMNS,
    twitch_preset_label,
    is_twitch_animated_format,
    is_twitch_format,
    twitch_effective_fps,
    twitch_hint,
    twitch_smooth_duration_limit,
)

_log = logging.getLogger(__name__)

DATA_ROLE = Qt.ItemDataRole.UserRole

# Один список на всё: типы файлов знает обработчик, и окно принимает
# ровно то, что он умеет разобрать.
SUPPORTED_INPUT_EXTS = IMAGE_EXTS | VIDEO_EXTS | {GIF_EXT, ANIMATED_WEBP_EXT, TGS_EXT}

def supported_files_filter():
    """Фильтр диалога выбора файлов строится из списка поддерживаемых
    расширений. Раньше он был отдельной строкой и отставал от списка:
    AVIF и HEIC программа принимала перетаскиванием, но в диалоге они
    не показывались.
    """
    masks = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUT_EXTS))
    return f'{tr("dlg_media_filter")} ({masks});;{tr("dlg_all_files")} (*.*)'


# Список форматов разбит на группы: без них два десятка пунктов сливались
# в одну простыню, и звуковые форматы терялись между видео и стикерами.
FORMAT_GROUPS = [
    ("fmt_images", ["jpg", "png", "webp", "bmp", "avif"]),
    ("fmt_animation", ["gif", "apng"]),
    ("fmt_video", ["mp4", "webm", "avi"]),
    ("fmt_audio_only", ["mp3", "m4a", "wav"]),
    ("fmt_frames", ["frames"]),
]

# Подписи кнопок на вкладке Discord.
DISCORD_PRESET_LABEL_KEYS = {
    "discord_sticker_png": "preset_sticker_png",
    "discord_sticker_apng": "preset_sticker_apng",
    "discord_emoji_png": "preset_emoji_png",
    "discord_emoji_gif": "preset_emoji_gif",
}

# Пояснения к неочевидным пунктам списка — всплывают при наведении.
FORMAT_TOOLTIP_KEYS = {
    "frames": "tip_frames",
    "apng": "tip_apng",
    "gif": "tip_gif",
    "mp3": "tip_mp3",
    "m4a": "tip_mp3",
    "wav": "tip_wav",
    "avif": "tip_avif",
}


def format_tooltip(code):
    key = FORMAT_TOOLTIP_KEYS.get(code)
    return tr(key) if key else ""


def rotate_options():
    """Варианты поворота. Направление вынесено в подсказку: «90° по часовой»
    требовало такой ширины, что панель получала горизонтальную прокрутку."""
    return [(tr("rotate_none"), 0), ("90°", 90), ("180°", 180), ("270°", 270)]


def flip_options():
    """Отражение одним списком вместо пары тумблеров: так строка настроек
    занимает вдвое меньше высоты, а вариантов всего четыре."""
    return [
        (tr("flip_none"), (False, False)),
        (tr("flip_h"), (True, False)),
        (tr("flip_v"), (False, True)),
        (tr("flip_both"), (True, True)),
    ]

# Форматы без картинки: из видео достаётся только звуковая дорожка.
AUDIO_FORMAT_CODES = {"mp3", "m4a", "wav"}
VIDEO_FORMAT_CODES = {"mp4", "webm", "avi"}

# Форматы, у которых ползунок качества и «уложить в размер» действительно
# на что-то влияют: у JPG, WEBP и AVIF есть качество сжатия, у видео —
# битрейт. У PNG, BMP, GIF, APNG, звука и покадрового разбора крутить
# нечего, и оба поля молча ничего не делали — теперь они там гаснут.
TUNABLE_FORMATS = {"jpg", "webp", "avif", "mp4", "webm", "avi"}

# Битрейты звука для выпадающего списка, кбит/с.
AUDIO_BITRATES = (96, 128, 160, 192, 256, 320)

# Выше этого списку форматов разворачиваться незачем: он перестаёт
# помещаться в окно и уезжает за край экрана.
FORMAT_POPUP_MAX_HEIGHT = 420
# Ширина полей времени. Было 78 и 86 — короткое «0,00 сек» помещалось,
# а «1250,50 сек» у длинного ролика (или «3599,90» у Telegram) уже нет:
# кнопки счётчика съедали хвост. Строки с этими полями свободны по ширине.
TRIM_FIELD_WIDTH = 108
TG_FRAGMENT_FIELD_WIDTH = 90
# Строк в списке форматов без прокрутки (вместе с заголовками групп):
# столько, чтобы список целиком (со скруглённым низом) помещался в
# предел высоты выше — при 13 строках нижний край обрезался.
FORMAT_POPUP_VISIBLE_ITEMS = 12
# Панель настроек шире этого не растягивается: её поля имеют разумную
# ширину сами по себе, и лишнее место превращалось либо в пропасть между
# подписью и полем, либо в пустоту. Всё, что шире, достаётся очереди —
# списку файлов ширина нужна для длинных имён.
SETTINGS_PANEL_MAX_WIDTH = 660
# Поля по бокам кнопки-вкладки из таблицы стилей плюс рамка.
TAB_BUTTON_PADDING = 22

EXT_TO_DEFAULT_CODE = {
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".png": "png",
    ".apng": "apng",
    ".webp": "webp",
    ".awebp": "gif",
    # Стикер Telegram чаще всего переводят в GIF — его открывает что угодно.
    ".tgs": "gif",
    ".bmp": "bmp",
    ".avif": "avif",
    ".heic": "jpg",
    ".heif": "jpg",
    ".gif": "gif",
    ".mp4": "mp4",
    ".webm": "webm",
    ".avi": "avi",
    ".tif": "png",
    ".tiff": "png",
}
# Прочие видеоконтейнеры по умолчанию превращаются в MP4: он открывается
# везде, а сам исходный контейнер программа не пишет.
EXT_TO_DEFAULT_CODE.update({ext: "mp4" for ext in VIDEO_EXTS
                            if ext not in EXT_TO_DEFAULT_CODE})

STATUS_PENDING = "Ожидание"
STATUS_PROCESSING = "Обработка"
STATUS_DONE = "Готово"
STATUS_ERROR = "Ошибка"
# Файл, обработку которого прервали кнопкой «Остановить».
STATUS_STOPPED = "Остановлено"
# Состояния, при которых файл больше не в работе.
FINISHED_STATUSES = (STATUS_DONE, STATUS_ERROR, STATUS_STOPPED)

# Статусы в отчёте переводятся при записи: обработчик про язык не знает
# и пишет их этими же внутренними значениями.
REPORT_STATUS_KEYS = {
    STATUS_DONE: "status_done",
    STATUS_ERROR: "status_error",
    STATUS_STOPPED: "status_stopped",
    STATUS_PENDING: "status_pending",
    STATUS_PROCESSING: "status_processing",
}

TAB_MAIN, TAB_TELEGRAM, TAB_TWITCH, TAB_DISCORD, TAB_WHATSAPP = 0, 1, 2, 3, 4
# Kick и YouTube идут за WhatsApp в порядке SQUARE_PLATFORMS.
TAB_KICK, TAB_YOUTUBE = 5, 6

# .tgs тоже: миниатюру для него рисует rlottie (см. scaled_thumbnail).
THUMBNAIL_IMAGE_EXTS = IMAGE_EXTS | {GIF_EXT, TGS_EXT}

# Расширения, за которыми может прятаться анимация. Только для них имеет
# смысл звать get_category из потока интерфейса: она открывает файл, чтобы
# отличить анимированный WEBP/PNG/AVIF от статичного, а для всех остальных
# расширений ответ и так известен заранее.
MAYBE_ANIMATED_EXTS = ANIMATABLE_IMAGE_EXTS | {ANIMATED_WEBP_EXT, TGS_EXT}

THUMBNAIL_SIZE = 48
# Кадр для предпросмотра в чате: самый крупный его вариант — 160 px,
# с запасом под экраны с масштабом 200 %.
PREVIEW_FRAME_SIZE = 320
# Сколько готовых кадров предпросмотра держим про запас.
PREVIEW_CACHE_LIMIT = 24
# Настройки, которые «Сброс» сохраняет: они не про обработку файлов.
PRESERVED_ON_RESET = ("language", "check_updates", "animate_media")
# Сколько дней хранятся картинки, вставленные из буфера обмена.
PASTED_KEEP_DAYS = 7
# Адрес картинки во вставке из браузера («Копировать изображение»).
IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)""", re.IGNORECASE)
# Через сколько миллисекунд после прокрутки или изменения очереди
# пересчитывается, какие миниатюры анимировать.
QUEUE_MOTION_SYNC_MS = 120
# Больше этого числа миниатюр не строим — иначе добавление папки подвешивает окно.
THUMBNAIL_LIMIT = 300
# Сколько длится плавная смена цветов при переходе между вкладками площадок.
THEME_FADE_MS = 180
# Столько кадров при извлечении считаем поводом переспросить пользователя.
FRAME_COUNT_WARNING_THRESHOLD = 2000

def idle_status():
    """Надпись в простое. Функция, а не константа: константа считается при
    импорте, и после смены языка осталась бы на прежнем."""
    return tr("idle")

# Размер окна по умолчанию. Все параметры обработки помещаются на одной
# вкладке без прокрутки — запас около 20 px, так что новую строку настроек
# просто так не добавить: сначала прогоните тест вёрстки.
DEFAULT_WINDOW_SIZE = (1140, 790)

# Названия площадок для подписей: не переводятся.
PLATFORM_TITLES = {"telegram": "Telegram", "twitch": "Twitch",
                   "discord": "Discord", "whatsapp": "WhatsApp"}
PLATFORM_TITLES.update({platform.key: platform.title for platform in SQUARE_PLATFORMS})


@dataclass
class QueueEntry:
    """Строка очереди: файл, его настройки и текущее состояние обработки."""

    input_path: str
    settings: JobSettings
    status: str = STATUS_PENDING
    progress: int = 0
    message: str = ""
    # Галочка в очереди: обрабатываются только отмеченные файлы.
    enabled: bool = True

    def to_job(self, output_dir, overwrite):
        return ConversionJob(
            input_path=self.input_path,
            output_dir=output_dir,
            settings=self.settings.copy(),
            overwrite=overwrite,
            # Файл пользователя запоминаем отдельно: обработка может пойти
            # через временный промежуточный файл, а перезаписать оригинал
            # нельзя ни при каких настройках.
            source_path=self.input_path,
        )


def default_settings_for(path):
    ext = os.path.splitext(path)[1].lower()
    return JobSettings(output_format=EXT_TO_DEFAULT_CODE.get(ext, "mp4"))


def image_via_pillow(path):
    """Читает картинку через Pillow, когда Qt формат не понимает.

    Qt не умеет AVIF и HEIC, а именно в них приходят эмодзи с 7TV и фото
    с iPhone — без этого у них не было ни миниатюры, ни превью.
    """
    try:
        from PIL import Image
        from PIL.ImageQt import ImageQt

        with Image.open(path) as image:
            image.seek(0)
            # copy(): ImageQt держит ссылку на буфер Pillow, а он умрёт
            # вместе с картинкой на выходе из with.
            return QImage(ImageQt(image.convert("RGBA"))).copy()
    except Exception:
        _log.debug("Pillow не смог открыть %s для превью", path, exc_info=True)
        return None


def tgs_thumbnail(path, size):
    """Кадр стикера .tgs для миниатюры и предпросмотра (None — не вышло)."""
    try:
        from PIL.ImageQt import ImageQt

        return QImage(ImageQt(representative_frame(path, size))).copy()
    except Exception:
        _log.debug("Не удалось нарисовать стикер %s", path, exc_info=True)
        return None


def scaled_thumbnail(path, size):
    """Читает картинку сразу в размер миниатюры, а не целиком.

    QImageReader умеет отдать уменьшенное изображение, не распаковывая
    оригинал полностью: у JPEG это работает через масштабирование DCT
    и даёт выигрыш почти втрое.

    Отдаёт QImage, а не QPixmap: миниатюры готовятся в фоновом потоке,
    а QPixmap — устройство отрисовки, и работать с ним вне потока
    интерфейса Qt не разрешает. Перевод в QPixmap делает получатель.
    """
    if is_tgs(path):
        # Стикер Telegram: Qt его не читает, кадр из середины рисует rlottie.
        return tgs_thumbnail(path, size)
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    source_size = reader.size()
    if source_size.isValid() and (source_size.width() > size or source_size.height() > size):
        reader.setScaledSize(
            source_size.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio)
        )
    image = reader.read()
    if not image.isNull():
        return image
    # Qt не открывает AVIF и HEIC — читаем их через Pillow.
    return image_via_pillow(path)


def media_info(path, ffmpeg=None):
    """Разрешение, длительность и FPS для видео и анимированных картинок.

    У анимированных WebP/AVIF ffprobe длительность не отдаёт, поэтому для
    них тайминги считает animation_info.
    """
    info = {"width": None, "height": None, "duration": None, "fps": None}
    if get_category(path) == "animated_image":
        details = animated_image_info(path, getattr(ffmpeg, "ffprobe_path", None))
        if details:
            info.update(duration=details.get("duration"), fps=details.get("fps"))
        if is_tgs(path):
            if details:
                info.update(width=details.get("width"), height=details.get("height"))
            return info
        # Размер берём заголовком через QImageReader, а не QPixmap: функцию
        # зовут из фонового потока, а QPixmap работает только в потоке
        # интерфейса. Заодно не распаковывается сама картинка.
        size = QImageReader(path).size()
        if size.isValid():
            info.update(width=size.width(), height=size.height())
        return info
    if ffmpeg is not None:
        info.update(ffmpeg.get_media_info(path))
    return info


class QueueInfoWorker(QThread):
    """Опрашивает длительность файлов очереди по очереди в фоне."""

    info_ready = pyqtSignal(str, dict)

    def __init__(self, ffmpeg, paths, parent=None):
        super().__init__(parent)
        self.ffmpeg = ffmpeg
        self.paths = list(paths)

    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():
                return
            try:
                info = media_info(path, self.ffmpeg)
            except Exception:
                # Пустой ответ вместо молчания: по завершении опроса окно
                # перезапускает его для файлов, которых ещё нет в кэше,
                # и пропущенный файл крутил бы опрос по кругу без конца.
                info = {}
            self.info_ready.emit(path, info)


class ImageThumbnailWorker(QThread):
    """Готовит миниатюры картинок в фоне.

    Раньше это делалось прямо при добавлении файла в очередь: QPixmap
    распаковывал снимок целиком (до 160 мс на фотографию 4000x3000) ради
    значка в 48 px, и папка на две сотни фото подвешивала окно на полминуты.

    Здесь картинка декодируется сразу в нужный размер: у JPEG это ускоряет
    разбор почти втрое, а у остальных форматов окно просто не блокируется.

    Наружу уходит QImage: QPixmap — устройство отрисовки, и создавать его
    вне потока интерфейса Qt не разрешает.
    """

    thumbnail_ready = pyqtSignal(str, QImage)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = list(paths)

    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():
                return
            image = scaled_thumbnail(path, THUMBNAIL_SIZE)
            if image is not None and not image.isNull():
                self.thumbnail_ready.emit(path, image)


class VideoThumbnailWorker(QThread):
    """Достаёт первый кадр видео для миниатюры — по одному файлу за раз,
    чтобы добавление большой очереди не занимало процессор целиком."""

    thumbnail_ready = pyqtSignal(str, QImage)

    def __init__(self, ffmpeg, paths, parent=None):
        super().__init__(parent)
        self.ffmpeg = ffmpeg
        self.paths = list(paths)

    def run(self):
        import tempfile

        for path in self.paths:
            if self.isInterruptionRequested():
                return
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    frame_path = os.path.join(tmp_dir, "thumb.png")
                    self.ffmpeg.extract_single_frame(
                        path, frame_path, THUMBNAIL_SIZE * 2, 0, True
                    )
                    # QImage, а не QPixmap: поток не интерфейсный.
                    image = QImage(frame_path)
            except Exception:
                continue
            if not image.isNull():
                self.thumbnail_ready.emit(path, image)


def pasted_directory():
    """Куда сохраняются картинки из буфера обмена.

    Рядом с журналом, в профиле пользователя: папка с программой может
    быть закрыта на запись (Program Files).
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = os.path.join(base, ORGANIZATION, "pasted")
    os.makedirs(directory, exist_ok=True)
    return directory


def save_clipboard_image(image):
    """Сохраняет картинку из буфера в PNG и возвращает путь к файлу."""
    directory = pasted_directory()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(directory, f"clipboard_{stamp}.png")
    counter = 1
    while os.path.exists(path):
        path = os.path.join(directory, f"clipboard_{stamp}_{counter}.png")
        counter += 1
    if not image.save(path, "PNG"):
        raise OSError(path)
    return path


def cleanup_pasted_images(max_age_days=PASTED_KEEP_DAYS):
    """Удаляет старые вставки: они нужны, пока файл стоит в очереди."""
    try:
        directory = pasted_directory()
        limit = time.time() - max_age_days * 24 * 60 * 60
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if (name.startswith("clipboard_") and name.endswith(".png")
                    and os.path.getmtime(path) < limit):
                os.remove(path)
    except OSError:
        _log.debug("Не удалось почистить папку вставок", exc_info=True)


class PreviewFrameWorker(QThread):
    """Готовит кадр для предпросмотра в фоне.

    Фото на 4000 px или кадр из видео в потоке интерфейса подвешивали бы
    окно при каждом выборе строки. Кадр сразу уменьшается до размера,
    которого хватает самому крупному предпросмотру.
    """

    frame_ready = pyqtSignal(str, QImage)
    # Что проигрывать вместо кадра (media_motion.motion_source); пустая
    # строка — ничего: файл не анимирован или анимация длинная.
    animation_ready = pyqtSignal(str, str)

    def __init__(self, path, ffmpeg, parent=None):
        super().__init__(parent)
        self.path = path
        self.ffmpeg = ffmpeg

    def run(self):
        image = None
        try:
            if os.path.splitext(self.path)[1].lower() in VIDEO_EXTS:
                if self.ffmpeg is not None:
                    import tempfile

                    with tempfile.TemporaryDirectory() as tmp_dir:
                        frame_path = os.path.join(tmp_dir, "preview.png")
                        self.ffmpeg.extract_single_frame(
                            self.path, frame_path, PREVIEW_FRAME_SIZE, 0, True
                        )
                        image = QImage(frame_path)
            else:
                image = scaled_thumbnail(self.path, PREVIEW_FRAME_SIZE)
        except Exception:
            _log.debug("Не удалось подготовить предпросмотр %s", self.path, exc_info=True)
        # Кадр — сразу: копия для проигрывания готовится секунду-другую,
        # и всё это время предпросмотр не должен стоять пустым.
        self.frame_ready.emit(self.path, image if image is not None else QImage())
        # Окно закрывается — анимацию не начинаем: она идёт секунды.
        if self.isInterruptionRequested():
            return
        source = None
        try:
            source = media_motion.motion_source(self.path, self.ffmpeg)
        except Exception:
            _log.debug("Не удалось сделать анимацию предпросмотра %s", self.path,
                       exc_info=True)
        self.animation_ready.emit(self.path, source or "")


class QueueMotionWorker(QThread):
    """Готовит анимацию для миниатюр очереди — по одному файлу, в фоне.

    Свой объект FFmpeg, а не общий окна: копию видео он делает секундами,
    и при закрытии окна её надо остановить, не задев других.
    """

    ready = pyqtSignal(str, str)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = list(paths)
        self.ffmpeg = None

    def run(self):
        try:
            from ffmpeg_utils import FFmpegProcessor

            self.ffmpeg = FFmpegProcessor()
        except Exception:
            self.ffmpeg = None  # без FFmpeg анимируются картинки, но не видео
        for path in self.paths:
            if self.isInterruptionRequested():
                break
            source = None
            try:
                source = media_motion.motion_source(path, self.ffmpeg)
            except Exception:
                _log.debug("Не удалось подготовить анимацию %s", path, exc_info=True)
            self.ready.emit(path, source or "")


class FolderScanWorker(QThread):
    """Обходит папки в фоне, чтобы интерфейс не подвисал на больших деревьях."""

    finished_scan = pyqtSignal(list, list)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self):
        accepted = []
        skipped = []
        for path in self.paths:
            if self.isInterruptionRequested():
                break
            if os.path.isdir(path):
                for root, _dirs, files in os.walk(path):
                    if self.isInterruptionRequested():
                        break
                    for name in files:
                        full_path = os.path.join(root, name)
                        if os.path.splitext(name)[1].lower() in SUPPORTED_INPUT_EXTS:
                            accepted.append(full_path)
                        else:
                            skipped.append(full_path)
                continue
            if os.path.splitext(path)[1].lower() in SUPPORTED_INPUT_EXTS:
                accepted.append(path)
            else:
                skipped.append(path)
        self.finished_scan.emit(accepted, skipped)


class LinkDownloadWorker(QThread):
    """Скачивает файлы по ссылкам в фоне: сеть может отвечать секундами."""

    downloaded = pyqtSignal(str)
    # Ссылка и ошибка (LocalizedError или текст) — переводит окно при показе.
    failed = pyqtSignal(str, object)

    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.urls = list(urls)

    def run(self):
        for url in self.urls:
            if self.isInterruptionRequested():
                break
            try:
                path = url_import.download_url(
                    url, pasted_directory(), SUPPORTED_INPUT_EXTS,
                    cancelled=self.isInterruptionRequested,
                )
            except Exception as exc:
                _log.info("Не удалось скачать по ссылке %s: %s", url, exc)
                self.failed.emit(url, exc)
                continue
            self.downloaded.emit(path)


class FileQueueList(QListWidget):
    def __init__(self, on_files_dropped, on_empty_clicked=None, parent=None,
                 on_urls_dropped=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        # Перетаскивание внутри списка меняет порядок обработки.
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        # Без горизонтальной прокрутки: длинное имя сокращается посередине
        # (см. StatusDotDelegate), а формат и значок состояния всегда видны.
        # Adjust — строки перекладываются при изменении ширины окна.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.on_files_dropped = on_files_dropped
        self.on_empty_clicked = on_empty_clicked
        # Картинка или ссылка, перетащенная из браузера, приходит адресом
        # в сети, а не файлом на диске.
        self.on_urls_dropped = on_urls_dropped
        self._placeholder_visible = True
        self._drag_active = False
        self._update_cursor()

    def set_placeholder_visible(self, visible):
        if self._placeholder_visible != visible:
            self._placeholder_visible = visible
            self._update_cursor()
            self.viewport().update()

    def _update_cursor(self):
        """Пока очередь пуста, вся область работает как кнопка добавления."""
        if self._placeholder_visible and self.on_empty_clicked:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()

    def mouseReleaseEvent(self, event):
        clicked_empty_area = (
            event.button() == Qt.MouseButton.LeftButton
            and self._placeholder_visible
            and self.itemAt(event.pos()) is None
            and self.on_empty_clicked is not None
        )
        super().mouseReleaseEvent(event)
        if clicked_empty_area:
            self.on_empty_clicked()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._placeholder_visible:
            return
        # Подсказка рисуется прямо в пустой области — так сразу понятно,
        # что сюда можно перетаскивать файлы.
        painter = QPainter(self.viewport())
        rect = self.viewport().rect().adjusted(18, 18, -18, -18)
        colors = palette()
        accent = colors["accent"] if self._drag_active else colors["drop_border"]
        pen = QPen(QColor(accent))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

        painter.setPen(QColor(colors["drop_text_active"] if self._drag_active
                              else colors["drop_text"]))
        icon_font = painter.font()
        icon_font.setPointSize(30)
        painter.setFont(icon_font)
        icon_rect = rect.adjusted(0, 0, 0, -rect.height() // 2)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "⭳")

        text_font = painter.font()
        text_font.setPointSize(10)
        painter.setFont(text_font)
        text_rect = rect.adjusted(16, rect.height() // 2, -16, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            tr("drop_hint") + "\n\n" + tr("drop_hint_paste"),
        )
        painter.end()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self._drag_active = True
            self.viewport().update()
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self._drag_active = False
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._drag_active = False
        self.viewport().update()
        if event.mimeData().hasUrls():
            paths = []
            links = []
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path:
                    paths.append(local_path)
                elif url.scheme() in ("http", "https"):
                    links.append(url.toString())
            if paths:
                self.on_files_dropped(paths)
            if links and self.on_urls_dropped is not None:
                self.on_urls_dropped(links)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Язык выбираем до первой подписи: заголовок окна ставится сразу,
        # и на прежнем языке он остался бы до перезапуска.
        store = QSettings(ORGANIZATION, ORGANIZATION)
        saved_language = store.value("language", "", type=str)
        # При первом запуске берём язык системы: чаще всего он и нужен.
        set_language(saved_language or language_from_locale(QLocale.system().name()))
        self.setWindowTitle(window_title())
        self.resize(*DEFAULT_WINDOW_SIZE)
        # Ниже этого размера панели начинают наезжать друг на друга.
        # 1010 — очередь (около 430 px) и панель настроек с семью
        # вкладками (530 px) рядом, без обрезки карточки справа.
        self.setMinimumSize(1010, 680)

        self._loading_settings = False
        self._refreshing_items = False
        self._transient_status = None
        # Выбранный формат живёт отдельно от активной вкладки: иначе переход
        # на «Правки» ради кадрирования сбрасывал бы пресет площадки.
        self._rebuilding = False
        self._selected_format = "mp4"
        # В списке форматов временно показана строка пресета площадки.
        self._preset_row_shown = False
        # Пока панель собирается, currentChanged у QStackedWidget уже
        # срабатывает — а виджеты вкладки «Правки» ещё не созданы.
        self._ui_ready = False
        # Соответствие «номер задачи -> строка очереди»: обрабатываются
        # не все строки, поэтому индексы задач и строк не совпадают.
        self._job_rows = []
        self.worker = None
        self.scan_worker = None
        self._last_report = []
        self._ffmpeg_probe = None
        # Кадры для предпросмотра готовятся в фоне и кэшируются по пути.
        self._preview_frames = {}
        self._preview_worker = None
        self._pending_preview_path = None
        self._preview_shown_path = None
        self._thumb_worker = None
        self._queue_info_worker = None
        self._media_info_cache = {}
        self._thumbnail_cache = {}
        self._pending_video_thumbnails = []
        self._pending_image_thumbnails = []
        self._image_thumb_worker = None
        self.settings_store = QSettings(ORGANIZATION, ORGANIZATION)
        saved_dir = self.settings_store.value("output_dir", "", type=str)
        self.output_dir = saved_dir if os.path.isdir(saved_dir) else os.path.expanduser("~")
        self.log_path = None
        self._tray_icon = None
        self._run_started_at = None
        self._last_output_dir = None

        self._build_ui()
        self._install_button_affordances()
        self._install_shortcuts()
        self._update_queue_counter()
        self._restore_window_state()
        # Предупреждение показываем после отрисовки окна, иначе оно всплывает
        # раньше самого приложения.
        QTimer.singleShot(0, self._check_ffmpeg_status)
        self._update_worker = None
        self._update_url = None
        # Анимация файлов в интерфейсе: что проигрывать для каждого файла
        # (пустая строка — ничего), анимированные миниатюры очереди и поток,
        # который их готовит. Выключается в меню версии.
        self._animate_media = self.settings_store.value("animate_media", True, type=bool)
        self._motion_sources = {}
        self._queue_movies = {}
        self._queue_motion_items = {}
        self._queue_motion_worker = None
        self._queue_motion_pending = []
        # Загрузка по ссылкам: поток, ссылки в очереди за ним, итоги.
        self._link_worker = None
        self._pending_links = []
        self._link_errors = []
        self._link_added = 0
        # Загрузка установщика новой версии и её процент — переживают
        # пересборку окна при смене языка.
        self._update_download = None
        self._update_percent = 0
        # Сеть — не раньше, чем окно появилось: старт не должен её ждать.
        QTimer.singleShot(1500, self._start_update_check)
        cleanup_pasted_images()
        try:
            url_import.cleanup_links(pasted_directory(), PASTED_KEEP_DAYS)
        except OSError:
            _log.debug("Не удалось почистить загрузки по ссылкам", exc_info=True)
        media_motion.cleanup_preview_animations()

    def _restore_window_state(self):
        """Возвращает размер окна, вкладку и положение разделителя."""
        geometry = self.settings_store.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        splitter_state = self.settings_store.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)
        tab = self.settings_store.value("active_tab", TAB_MAIN, type=int)
        if 0 <= tab < self.settings_tabs.count():
            self.settings_tabs.setCurrentIndex(tab)
        self._sync_tab_buttons()
        self._apply_tab_theme()

    def _save_window_state(self):
        self.settings_store.setValue("window_geometry", self.saveGeometry())
        self.settings_store.setValue("splitter_state", self.splitter.saveState())
        self.settings_store.setValue("active_tab", self.settings_tabs.currentIndex())

    def _on_language_changed(self):
        """Смена языка: пересобираем начинку окна и возвращаем состояние.

        Пересборка вместо обхода всех подписей — так ничего не забудется:
        подписей под две сотни, и любая пропущенная осталась бы на старом
        языке до перезапуска.
        """
        if self._loading_settings or self._rebuilding:
            return
        code = self.language_combo.currentData()
        if not code or code == current_language():
            return
        self.settings_store.setValue("language", code)
        set_language(code)
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Собирает интерфейс заново, сохранив очередь и настройки."""
        self._stop_all_queue_movies()
        entries = [self._entry(self.file_list.item(row))
                   for row in range(self.file_list.count())]
        current_row = self.file_list.currentRow()
        # Выделение запоминаем целиком, а не одну текущую строку: иначе после
        # смены языка «Применить к выбранным» брало бы один файл вместо
        # отмеченных пользователем.
        selected_rows = [self.file_list.row(item)
                         for item in self.file_list.selectedItems()]
        selected_format = self._selected_format
        active_tab = self.settings_tabs.currentIndex()
        splitter_state = self.splitter.saveState()
        panel = self._current_panel_settings()

        self._rebuilding = True
        try:
            self.setWindowTitle(window_title())
            self._build_ui()
            self._install_button_affordances()
            self.splitter.restoreState(splitter_state)
            self.output_dir_edit.setText(self.output_dir)
            self.overwrite_checkbox.setChecked(
                self.settings_store.value("overwrite", False, type=bool)
            )
            for entry in entries:
                self._append_entry(entry)
            self.settings_tabs.setCurrentIndex(active_tab)
            if 0 <= current_row < self.file_list.count():
                self.file_list.setCurrentRow(current_row)
            for row in selected_rows:
                if 0 <= row < self.file_list.count():
                    self.file_list.item(row).setSelected(True)
            # Настройки панели ставим последними: возврат выделения выше
            # поднимает _on_selection_changed, а тот подставляет настройки
            # выбранной строки. Формат, выбранный при нескольких выделенных
            # файлах, в задачи ещё не записан — и молча терялся.
            self._selected_format = selected_format
            self._load_settings_into_panel(panel.copy(output_format=selected_format))
        finally:
            self._rebuilding = False
        self._update_queue_counter()
        self._set_settings_enabled(bool(self.file_list.selectedItems()))
        self._apply_tab_theme()
        self._check_ffmpeg_status(quiet=True)
        # Ссылка на обновление живёт на прежней нижней панели.
        if self._update_url:
            self._on_update_found(
                self.settings_store.value("known_update", "", type=str), self._update_url
            )
            if self._update_download is not None:
                self._show_update_progress(self._update_percent)

    def _build_ui(self):
        # Пока панель собирается, обработчики сигналов трогать нечего.
        self._ui_ready = False
        # Список форматов будет новый и пустой, а флаг остался от прежнего.
        # Без сброса _drop_preset_row снимал бы две первые строки свежей
        # модели — заголовок «Изображения» и JPG: после смены языка при
        # выбранном пресете площадки JPG пропадал из списка до перезапуска.
        self._preset_row_shown = False
        # Тема панели принадлежит прежним виджетам: новые ещё не перекрашены.
        self._current_theme = None
        # Предпросмотры будут новые и пустые.
        self._preview_shown_path = None
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # Заголовок не дублируем — он уже есть в шапке окна.
        self.ffmpeg_warning_label = QLabel("")
        self.ffmpeg_warning_label.setObjectName("WarningLabel")
        self.ffmpeg_warning_label.setVisible(False)
        root_layout.addWidget(self.ffmpeg_warning_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter
        root_layout.addWidget(splitter, stretch=1)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        splitter.setHandleWidth(14)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        bottom_panel = self._build_bottom_panel()
        bottom_panel.setObjectName("BottomPanel")
        # Дробная часть в полях — по языку интерфейса, а не по системе:
        # в английском окне на русской Windows стояло «0,00 s», а в
        # подписях рядом — «3.0 s».
        locale = QLocale(QLocale.Language.English if current_language() == ENGLISH
                         else QLocale.Language.Russian)
        for spin in central.findChildren(QAbstractSpinBox):
            spin.setLocale(locale)
        # Отбивка сверху: блок сохранения не должен липнуть к кнопкам очереди.
        root_layout.addSpacing(6)
        root_layout.addWidget(bottom_panel)

    def _build_left_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        queue_title = QLabel(tr("queue_title"))
        queue_title.setObjectName("SectionLabel")
        header_layout.addWidget(queue_title)
        header_layout.addStretch(1)
        self.queue_counter_label = QLabel(tr("queue_empty"))
        self.queue_counter_label.setObjectName("HintLabel")
        header_layout.addWidget(self.queue_counter_label)
        layout.addLayout(header_layout)

        # Поле для ссылки на виду: Ctrl+V и пункт меню очереди находят не все.
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        self.link_edit = QLineEdit()
        self.link_edit.setPlaceholderText(tr("link_placeholder"))
        self.link_edit.setAccessibleName(tr("link_placeholder"))
        self.link_edit.setToolTip(tr("dlg_link_text"))
        self.link_edit.setClearButtonEnabled(True)
        self.link_edit.returnPressed.connect(self._on_link_entered)
        self.link_add_button = QPushButton(tr("link_add"))
        self.link_add_button.setToolTip(tr("dlg_link_text"))
        self.link_add_button.clicked.connect(self._on_link_entered)
        link_row.addWidget(self.link_edit, stretch=1)
        link_row.addWidget(self.link_add_button)
        layout.addLayout(link_row)

        self.file_list = FileQueueList(
            self._add_files_from_paths, on_empty_clicked=self._on_add_files_clicked,
            on_urls_dropped=self._add_files_from_urls,
        )
        self.file_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.file_list.itemChanged.connect(self._on_item_check_changed)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_queue_context_menu)
        self.file_list.setItemDelegate(StatusDotDelegate(self._status_at_index, self.file_list))
        # Какие миниатюры анимировать, зависит от того, что видно.
        self.file_list.verticalScrollBar().valueChanged.connect(self._schedule_motion_sync)
        model = self.file_list.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.rowsMoved,
                       model.modelReset, model.layoutChanged):
            signal.connect(self._schedule_motion_sync)
        # Перестановка мышью и Alt+↑/↓ нигде больше не упоминалась.
        self.file_list.setToolTip(tr("queue_tip"))
        self.file_list.setAccessibleName(tr("queue_title"))
        self.file_list.setAccessibleDescription(tr("queue_tip"))
        layout.addWidget(self.file_list, stretch=1)

        # Обе строки кнопок — одна сетка, поэтому колонки совпадают по ширине.
        buttons_grid = QGridLayout()
        buttons_grid.setHorizontalSpacing(8)
        buttons_grid.setVerticalSpacing(8)

        add_button = QPushButton(tr("add_files"))
        add_button.setObjectName("PrimaryButton")
        add_button.setToolTip(tr("add_files_tip"))
        add_button.clicked.connect(self._on_add_files_clicked)

        remove_button = QPushButton(tr("remove_selected"))
        remove_button.setObjectName("QuietButton")
        remove_button.setToolTip(tr("remove_selected_tip"))
        remove_button.clicked.connect(self._on_remove_selected)

        clear_button = QPushButton(tr("clear_list"))
        clear_button.setObjectName("QuietButton")
        clear_button.setToolTip(tr("clear_list_tip"))
        clear_button.clicked.connect(self._on_clear_list)

        # Порядок обработки меняется перетаскиванием и клавишами Alt+↑/↓,
        # а на месте прежних кнопок — управление галочками: обрабатываются
        # только отмеченные файлы.
        check_all_button = QPushButton(tr("check_all"))
        check_all_button.setToolTip(tr("check_all_tip"))
        check_all_button.clicked.connect(lambda: self._set_all_checked(True))

        uncheck_all_button = QPushButton(tr("uncheck_all"))
        uncheck_all_button.setObjectName("QuietButton")
        uncheck_all_button.setToolTip(tr("uncheck_all_tip"))
        uncheck_all_button.clicked.connect(lambda: self._set_all_checked(False))
        # Гаснут, когда делать нечего: «Отметить все» при всех отмеченных.
        self.check_all_button = check_all_button
        self.uncheck_all_button = uncheck_all_button
        self.remove_button = remove_button
        self.clear_button = clear_button

        # Сетка из 6 колонок: первый ряд — три кнопки, второй — две,
        # так оба ряда получаются одинаковой ширины без «висящих» кнопок.
        for column, button in enumerate((add_button, remove_button, clear_button)):
            buttons_grid.addWidget(button, 0, column * 2, 1, 2)
        buttons_grid.addWidget(check_all_button, 1, 0, 1, 3)
        buttons_grid.addWidget(uncheck_all_button, 1, 3, 1, 3)
        layout.addLayout(buttons_grid)

        return container

    def _install_button_affordances(self):
        """Курсор показывает, можно ли нажать кнопку: «рука» у доступной,
        «запрещено» у недоступной. Фильтр следит за сменой состояния."""
        self._cursor_filter = ButtonCursorFilter(self)
        for button in self.findChildren(QAbstractButton):
            # Фокус кнопкам — только с клавиатуры. Рамку фокуса таблица стилей
            # рисует белой, и после щелчка мышью она оставалась бы на кнопке,
            # как будто это ещё одно состояние (в Qt нет :focus-visible).
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            if isinstance(button, ToggleSwitch):
                continue
            button.installEventFilter(self._cursor_filter)
            apply_button_cursor(button)
        # Выпадающие списки — без квадратного окна за скруглённой карточкой.
        for combo in self.findChildren(QComboBox):
            round_combo_popup(combo)

    def _install_shortcuts(self):
        bindings = [
            (QKeySequence.StandardKey.Open, self._on_add_files_clicked),
            (QKeySequence("Delete"), self._on_remove_selected),
            (QKeySequence("Alt+Up"), lambda: self._move_selected(-1)),
            (QKeySequence("Alt+Down"), lambda: self._move_selected(1)),
            (QKeySequence("Ctrl+Return"), self._on_start_clicked),
            # Поле ввода с фокусом перехватывает Ctrl+V раньше окна, поэтому
            # вставка текста в поля работает как обычно.
            (QKeySequence(QKeySequence.StandardKey.Paste), self._paste_from_clipboard),
            (QKeySequence("Esc"), self._on_stop_clicked),
        ]
        for sequence, handler in bindings:
            QShortcut(QKeySequence(sequence), self, activated=handler)

    def _make_preset_button(self, label, code, on_click):
        """Пресет — переключатель: активный вариант остаётся подсвеченным."""
        button = QPushButton(label)
        button.setObjectName("PresetButton")
        button.setCheckable(True)
        button.setAutoExclusive(False)
        button.clicked.connect(lambda _checked=False, fmt=code: on_click(fmt))
        return button

    def _build_telegram_tab(self):
        tab = QWidget()
        tab.setObjectName("SettingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(5)

        self.telegram_format_code = "tg_sticker_png"
        self.telegram_hint_label = QLabel()
        self.telegram_hint_label.setObjectName("HintCallout")
        self.telegram_hint_label.setWordWrap(True)
        # Минимум с запасом: подсказки разной длины иначе двигают кнопки,
        # а на узком окне переносятся в несколько строк.
        self.telegram_hint_label.setMinimumHeight(42)
        layout.addWidget(self.telegram_hint_label)

        # Стикеры и эмодзи — раздельными колонками: при построчной раскладке
        # "Стикер WEBM" оказывался в одной строке с "Эмодзи PNG".
        presets_layout = QGridLayout()
        presets_layout.setHorizontalSpacing(10)
        columns = [
            (tr("col_sticker", size=512), [
                (tr("preset_sticker_png"), "tg_sticker_png"),
                (tr("preset_sticker_webp"), "tg_sticker_webp"),
                (tr("preset_sticker_webm"), "tg_sticker_webm"),
            ]),
            (tr("col_emoji", size=100), [
                (tr("preset_emoji_png"), "tg_emoji_png"),
                (tr("preset_emoji_webp"), "tg_emoji_webp"),
                (tr("preset_emoji_webm"), "tg_emoji_webm"),
            ]),
        ]
        self.telegram_preset_buttons = {}
        for column, (caption, presets) in enumerate(columns):
            header = QLabel(caption)
            header.setObjectName("GroupCaption")
            presets_layout.addWidget(header, 0, column)
            for row, (label, code) in enumerate(presets, start=1):
                button = self._make_preset_button(label, code, self._apply_telegram_preset)
                self.telegram_preset_buttons[code] = button
                presets_layout.addWidget(button, row, column)
        layout.addLayout(presets_layout)

        # Компактная строка «Фрагмент: с N сек, длиной M сек» — два отдельных
        # подписанных поля не помещались в ширину панели.
        duration_layout = QHBoxLayout()
        duration_layout.setSpacing(6)
        self.tg_start_label = QLabel(tr("tg_fragment"))
        self.tg_start_spin = QDoubleSpinBox()
        self.tg_start_spin.setRange(0.0, 3600.0)
        self.tg_start_spin.setSingleStep(0.1)
        self.tg_start_spin.setFixedWidth(TG_FRAGMENT_FIELD_WIDTH)
        self.tg_start_spin.setToolTip(
            tr("tg_start_tip")
        )
        self.tg_start_spin.valueChanged.connect(self._on_tg_start_changed)
        duration_layout.addWidget(self.tg_start_label)
        duration_layout.addWidget(self.tg_start_spin)

        self.tg_duration_label = QLabel(tr("tg_fragment_len"))
        self.tg_duration_spin = QDoubleSpinBox()
        self.tg_duration_spin.setRange(0.1, MAX_VIDEO_DURATION_SEC)
        self.tg_duration_spin.setSingleStep(0.1)
        self.tg_duration_spin.setValue(MAX_VIDEO_DURATION_SEC)
        self.tg_duration_spin.setFixedWidth(TG_FRAGMENT_FIELD_WIDTH)
        self.tg_duration_spin.setToolTip(
            tr("tg_duration_tip")
        )
        self.tg_duration_spin.valueChanged.connect(self._on_settings_changed)
        self.tg_start_label.setBuddy(self.tg_start_spin)
        self.tg_duration_label.setBuddy(self.tg_duration_spin)
        duration_layout.addWidget(self.tg_duration_label)
        duration_layout.addWidget(self.tg_duration_spin)
        self.tg_units_label = QLabel(tr("seconds_suffix").strip())
        duration_layout.addWidget(self.tg_units_label)
        duration_layout.addStretch(1)
        layout.addLayout(duration_layout)

        self.tg_source_label = QLabel("")
        self.tg_source_label.setObjectName("HintLabel")
        layout.addWidget(self.tg_source_label)
        self._add_platform_footer(layout, "telegram")
        return tab

    def _build_twitch_tab(self):
        tab = QWidget()
        tab.setObjectName("SettingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(5)

        self.twitch_format_code = "twitch_static_112"
        self.twitch_hint_label = QLabel()
        self.twitch_hint_label.setObjectName("HintCallout")
        self.twitch_hint_label.setWordWrap(True)
        self.twitch_hint_label.setMinimumHeight(42)
        layout.addWidget(self.twitch_hint_label)

        # Две колонки, как у Telegram: смайлики Twitch отдельно от значков
        # и смайликов расширений чата.
        presets_layout = QGridLayout()
        presets_layout.setHorizontalSpacing(10)
        self.twitch_preset_buttons = {}
        for column, (caption_key, codes) in enumerate(TWITCH_PRESET_COLUMNS):
            header = QLabel(tr(caption_key))
            header.setObjectName("GroupCaption")
            presets_layout.addWidget(header, 0, column)
            for row, code in enumerate(codes, start=1):
                button = self._make_preset_button(
                    twitch_preset_label(code), code, self._apply_twitch_preset
                )
                self.twitch_preset_buttons[code] = button
                presets_layout.addWidget(button, row, column)
        layout.addLayout(presets_layout)
        self._add_platform_footer(layout, "twitch")
        return tab

    def _build_whatsapp_tab(self):
        tab = QWidget()
        tab.setObjectName("SettingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(5)

        self.whatsapp_format_code = WHATSAPP_STATIC
        self.whatsapp_hint_label = QLabel()
        self.whatsapp_hint_label.setObjectName("HintCallout")
        self.whatsapp_hint_label.setWordWrap(True)
        self.whatsapp_hint_label.setMinimumHeight(42)
        layout.addWidget(self.whatsapp_hint_label)

        presets_layout = QGridLayout()
        presets_layout.setHorizontalSpacing(10)
        self.whatsapp_preset_buttons = {}
        for column, (caption_key, codes) in enumerate(WHATSAPP_PRESET_COLUMNS):
            header = QLabel(tr(caption_key))
            header.setObjectName("GroupCaption")
            presets_layout.addWidget(header, 0, column)
            for row, code in enumerate(codes, start=1):
                button = self._make_preset_button(
                    whatsapp_preset_label(code), code, self._apply_whatsapp_preset
                )
                self.whatsapp_preset_buttons[code] = button
                presets_layout.addWidget(button, row, column)
        layout.addLayout(presets_layout)
        self._add_platform_footer(layout, "whatsapp")
        return tab

    def _build_square_platform_tab(self, platform):
        """Вкладка Kick или YouTube: выноска, колонки пресетов, предпросмотр.

        Собирается по описанию из stream_platforms — как вкладка WhatsApp,
        только без отдельного кода на каждую площадку.
        """
        tab = QWidget()
        tab.setObjectName("SettingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(5)

        self.square_format_codes[platform.key] = platform.default
        hint_label = QLabel()
        hint_label.setObjectName("HintCallout")
        hint_label.setWordWrap(True)
        hint_label.setMinimumHeight(42)
        layout.addWidget(hint_label)
        self.square_hint_labels[platform.key] = hint_label

        presets_layout = QGridLayout()
        presets_layout.setHorizontalSpacing(10)
        buttons = {}
        for column, (caption_key, codes) in enumerate(platform.columns):
            header = QLabel(tr(caption_key))
            header.setObjectName("GroupCaption")
            presets_layout.addWidget(header, 0, column)
            for row, code in enumerate(codes, start=1):
                button = self._make_preset_button(
                    square_preset_label(code), code, self._apply_square_preset
                )
                buttons[code] = button
                presets_layout.addWidget(button, row, column)
        # Одна колонка не должна растягиваться на всю ширину карточки.
        if len(platform.columns) == 1:
            presets_layout.setColumnStretch(1, 1)
        layout.addLayout(presets_layout)
        self.square_preset_buttons[platform.key] = buttons
        self._add_platform_footer(layout, platform.key)
        return tab

    def _add_platform_footer(self, layout, platform):
        """Низ вкладки площадки: тумблер «заполнить квадрат», примечание
        о том, к чему применяется пресет, и предпросмотр в макете чата.

        Предпросмотр занимает свободное место под настройками и тянется
        вместе с окном, но не выше своего предела.
        """
        fill_toggle = ToggleSwitch(tr("fill_square"))
        fill_toggle.setToolTip(tr("fill_square_tip"))
        fill_toggle.toggled.connect(self._on_fill_toggled)
        self.fill_toggles[platform] = fill_toggle
        layout.addWidget(fill_toggle)

        # Примечание «к выделенным, а без выделения — ко всем» живёт под
        # карточкой, на месте кнопок применения (см. _build_right_panel):
        # пресет применяется сразу, и кнопки на вкладках площадок были лишними.

        # Отдельной подписи у предпросмотра нет: макет чата узнаётся сам, а
        # строка заголовка не помещалась на вкладке Telegram с выбранным
        # видео — та и так самая тесная.
        preview = ChatPreview(platform)
        preview.setToolTip(tr("preview_title"))
        preview.setAccessibleName(tr("preview_title"))
        self.chat_previews[platform] = preview
        layout.addWidget(preview, 1)
        # Пустота — после предпросмотра: когда он дорос до предела,
        # лишняя высота уходит сюда, а не в зазоры между строками.
        layout.addStretch(0)

    def _confirm(self, title, text, action):
        """Вопрос с кнопками «<действие>» и «Отмена» вместо «Да/Нет».

        Стандартные кнопки Qt без его перевода выходили по-английски и в
        русском окне, а «Да/Нет» заставляет перечитывать вопрос. По
        умолчанию и по Esc — отмена: все вопросы здесь о рискованном шаге.
        """
        box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self)
        accept = box.addButton(action, QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() is accept

    def _on_reset_settings(self):
        if not self._confirm(tr("dlg_reset_title"), tr("dlg_reset_text"), tr("btn_reset")):
            return
        # Язык и проверка обновлений — не параметры обработки: сброс их не
        # трогает, иначе после перезапуска окно внезапно меняло бы язык.
        kept = {key: self.settings_store.value(key)
                for key in PRESERVED_ON_RESET if self.settings_store.contains(key)}
        self.settings_store.clear()
        for key, value in kept.items():
            self.settings_store.setValue(key, value)
        self.settings_store.sync()
        self.output_dir = os.path.expanduser("~")
        self.output_dir_edit.setText(self.output_dir)
        self.overwrite_checkbox.setChecked(False)
        self.telegram_format_code = "tg_sticker_png"
        self.twitch_format_code = "twitch_static_112"
        self.discord_format_code = "discord_sticker_png"
        self.whatsapp_format_code = WHATSAPP_STATIC
        self.square_format_codes = {platform.key: platform.default
                                    for platform in SQUARE_PLATFORMS}
        self.settings_tabs.setCurrentIndex(TAB_MAIN)
        self._load_settings_into_panel(JobSettings())
        self.current_file_label.setText(tr("reset_done"))

    def _build_corner_controls(self, row):
        """Номер версии с меню, ссылка на обновление и выбор языка."""
        # Номер версии — тихая кнопка с меню: обновления, анимация файлов,
        # журнал. Раньше меню открывалось только правым щелчком по подписи,
        # и о нём мало кто знал.
        self.version_button = QPushButton(f"v{version_string()}")
        self.version_button.setObjectName("VersionButton")
        self.version_button.setToolTip(
            tr("version_tip", app=APP_NAME, version=version_string()))
        self.version_button.setAccessibleName(
            tr("version_accessible", version=version_string()))
        version_menu = PopupMenu(self)
        version_menu.aboutToShow.connect(lambda: self._fill_version_menu(version_menu))
        self.version_button.setMenu(version_menu)

        # Ссылка на новую версию: появляется, только если она вышла, и
        # встаёт на место номера версии, а не рядом.
        self.update_button = QPushButton()
        self.update_button.setObjectName("UpdateButton")
        self.update_button.setVisible(False)
        self.update_button.clicked.connect(self._on_update_clicked)
        self.update_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.update_button.customContextMenuRequested.connect(
            lambda position: self._on_version_menu(position, self.update_button))

        self.language_combo = QComboBox()
        self.language_combo.setObjectName("CornerCombo")
        self.language_combo.setToolTip(tr("language_tip"))
        self.language_combo.setAccessibleName(tr("language_tip"))
        for code in LANGUAGE_ORDER:
            self.language_combo.addItem(LANGUAGE_NAMES[code], code)
        index = self.language_combo.findData(current_language())
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)

        row.addWidget(self.update_button)
        row.addWidget(self.version_button)
        row.addWidget(self.language_combo)

    def _build_right_panel(self):
        # Тумблеры «заполнить квадрат» на каждой вкладке площадки и
        # предпросмотры — по площадке; заполняются при сборке вкладок.
        self.fill_toggles = {}
        self.chat_previews = {}
        # Kick и YouTube: выбранный пресет, кнопки и выноска — по площадке.
        self.square_format_codes = {}
        self.square_preset_buttons = {}
        self.square_hint_labels = {}
        container = QWidget()
        # Панель целиком перекрашивается под вкладку площадки (см. _apply_tab_theme).
        self.right_panel = container
        # Ширина с запасом: вертикальная полоса прокрутки съедает 12 px, и без
        # запаса из-за неё появлялась ещё и горизонтальная.
        # 530 — чтобы строка из семи вкладок помещалась без наложения
        # (tests/test_layout_min.py, tab_bar_problems).
        container.setMinimumWidth(530)
        container.setMaximumWidth(SETTINGS_PANEL_MAX_WIDTH)
        layout = QVBoxLayout(container)
        # Небольшой отступ слева, иначе рамка вплотную примыкает к списку файлов.
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)

        # Заголовок отдельной строкой вместо QGroupBox: рамка группы дублировала
        # рамку вкладок, а её скруглённые углы почти сливались с фоном.
        settings_title = QLabel(tr("settings_title"))
        settings_title.setObjectName("SectionLabel")
        # Справа от заголовка — версия и язык: правый верхний угол окна был
        # пустым, а нижняя строка тесной.
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(settings_title)
        title_row.addStretch(1)
        self._build_corner_controls(title_row)
        layout.addLayout(title_row)

        # Вместо QTabWidget — кнопки-вкладки и QStackedWidget: Qt не рисует
        # дуги скруглённых углов у QTabWidget::pane, из-за чего рамка панели
        # выглядела разорванной. Обычный виджет скругляется корректно.
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(4)
        self.tab_buttons = []
        captions = (
            (tr("tab_main"), tr("tab_main_tip")),
            ("Telegram", tr("tab_telegram_tip")),
            ("Twitch", tr("tab_twitch_tip")),
            ("Discord", tr("tab_discord_tip")),
            ("WhatsApp", tr("tab_whatsapp_tip")),
        ) + tuple((platform.title, tr(f"tab_{platform.key}_tip"))
                  for platform in SQUARE_PLATFORMS)
        for index, (caption, tip) in enumerate(captions):
            button = QPushButton(caption)
            button.setObjectName("TabButton")
            button.setCheckable(True)
            button.setToolTip(tip)
            # Для диктора — «Вкладка Telegram», а не просто нажатая кнопка.
            button.setAccessibleName(tr("tab_accessible", name=caption))
            button.setAccessibleDescription(tip)
            # Выбранная вкладка рисуется жирнее, а sizeHint считается по
            # обычному начертанию — из-за этого «Дополнительно» обрезалось
            # ровно в тот момент, когда вкладка становилась активной.
            # ensurePolished обязателен: до него у кнопки шрифт по умолчанию,
            # а не заданный таблицей стилей, и мерка выходит заниженной.
            button.ensurePolished()
            bold = QFont(button.font())
            bold.setWeight(QFont.Weight.DemiBold)
            button.setMinimumWidth(
                QFontMetrics(bold).horizontalAdvance(caption) + TAB_BUTTON_PADDING
            )
            button.clicked.connect(
                lambda _checked=False, page=index: self.settings_tabs.setCurrentIndex(page)
            )
            tab_bar.addWidget(button)
            self.tab_buttons.append(button)
        tab_bar.addStretch(1)
        layout.addLayout(tab_bar)

        self.settings_tabs = QStackedWidget()
        self.settings_tabs.setObjectName("SettingsCard")
        self.settings_tabs.currentChanged.connect(self._on_tab_changed)
        self.settings_tabs.currentChanged.connect(self._sync_tab_buttons)

        # Прокрутка вместо сжатия: на маленьком окне метки с переносом слов
        # занижают свою минимальную высоту, и элементы наезжали друг на друга.
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setObjectName("SettingsScroll")
        # Сама область прокрутки — не элемент управления: без этого Tab
        # останавливался на ней, и фокус пропадал из виду на один шаг.
        settings_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Горизонтальная полоса как страховка: лучше прокрутка, чем обрезанный текст.
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        settings_scroll.setWidget(self.settings_tabs)

        # Фон и рамку рисует отдельный контейнер, а не сама область прокрутки:
        # Qt не закрашивает фон под полосой прокрутки, и в углах карточки
        # просвечивал фон окна, как только полоса появлялась.
        settings_card = QFrame()
        settings_card.setObjectName("SettingsCardFrame")
        card_layout = QVBoxLayout(settings_card)
        # Отступ, чтобы область прокрутки не доходила до скруглённых углов:
        # её фон непрозрачный, иначе под полосой прокрутки просвечивает окно.
        card_layout.setContentsMargins(7, 7, 7, 7)
        card_layout.addWidget(settings_scroll)
        settings_card.setMinimumHeight(240)
        layout.addWidget(settings_card, stretch=1)

        self.settings_tabs.addWidget(self._build_main_tab())
        self.settings_tabs.addWidget(self._build_telegram_tab())
        self.settings_tabs.addWidget(self._build_twitch_tab())
        self.settings_tabs.addWidget(self._build_discord_tab())
        self.settings_tabs.addWidget(self._build_whatsapp_tab())
        for platform in SQUARE_PLATFORMS:
            self.settings_tabs.addWidget(self._build_square_platform_tab(platform))
        self._ui_ready = True

        apply_layout = QHBoxLayout()
        self.apply_selected_button = QPushButton(tr("apply_selected"))
        self.apply_selected_button.clicked.connect(self._apply_to_selected)
        self.apply_all_button = QPushButton(tr("apply_all"))
        self.apply_all_button.clicked.connect(self._apply_to_all)
        # На вкладках площадок пресет применяется сразу по щелчку, поэтому
        # вместо кнопок применения там примечание о том, к чему он применён.
        # Стопка, а не скрытие: высота строки одна на всех вкладках, и
        # вёрстка карточки при переключении не прыгает.
        apply_buttons = QWidget()
        apply_buttons_layout = QHBoxLayout(apply_buttons)
        apply_buttons_layout.setContentsMargins(0, 0, 0, 0)
        apply_buttons_layout.addWidget(self.apply_selected_button, stretch=1)
        apply_buttons_layout.addWidget(self.apply_all_button, stretch=1)
        # Одна строка с многоточием, а не перенос: скрытая страница стопки
        # с переносом считала себе высоту в две строки, и строка кнопок на
        # «Основной» вырастала на 10 px — ровно из запаса по высоте.
        self.platform_note_label = ElidedLabel(tr("platform_note"))
        self.platform_note_label.setObjectName("ApplyNote")
        self.platform_note_label.setAlignment(Qt.AlignmentFlag.AlignVCenter
                                              | Qt.AlignmentFlag.AlignLeft)
        self.apply_stack = QStackedWidget()
        self.apply_stack.addWidget(apply_buttons)
        self.apply_stack.addWidget(self.platform_note_label)
        self.reset_settings_button = QPushButton(tr("reset"))
        self.reset_settings_button.setObjectName("QuietButton")
        self.reset_settings_button.setToolTip(
            tr("reset_tip")
        )
        self.reset_settings_button.clicked.connect(self._on_reset_settings)
        apply_layout.addWidget(self.apply_stack, stretch=1)
        apply_layout.addWidget(self.reset_settings_button)
        # Отступ, чтобы кнопки не липли к нижней рамке карточки настроек.
        layout.addSpacing(4)
        layout.addLayout(apply_layout)
        # Распорки в конце нет намеренно: она делила бы свободное место
        # с областью настроек, и карточка получала лишь половину высоты —
        # из-за этого нижние строки настроек уезжали под прокрутку.
        self._set_settings_enabled(False)
        self._update_enabled_states()
        self._update_hints()
        self._sync_tab_buttons()
        return container

    def _build_main_tab(self):
        """Вкладка «Основная»: формат, размер, частота кадров, длительность."""
        main_tab = QWidget()
        main_tab.setObjectName("SettingsPage")
        grid = QGridLayout(main_tab)
        grid.setContentsMargins(4, 6, 4, 4)
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(10)
        format_label = QLabel(tr("output_format"))
        grid.addWidget(format_label, 0, 0)
        self.format_combo = QComboBox()
        # Подпись — «приятель» поля: так её читает экранный диктор.
        format_label.setBuddy(self.format_combo)
        self._fill_format_combo()
        self.format_combo.currentIndexChanged.connect(self._on_format_combo_changed)
        grid.addWidget(self.format_combo, 0, 1, 1, 3)

        size_caption = QLabel(tr("group_size"))
        size_caption.setObjectName("GroupCaption")
        grid.addWidget(size_caption, 1, 0, 1, 4)

        self.resize_checkbox = ToggleSwitch(tr("resize"))
        self.resize_checkbox.stateChanged.connect(self._on_resize_toggle)
        grid.addWidget(self.resize_checkbox, 2, 0, 1, 2)
        self.width_label = QLabel(tr("width"))
        grid.addWidget(self.width_label, 3, 0)
        self.width_spin = QSpinBox()
        self.width_label.setBuddy(self.width_spin)
        self.width_spin.setRange(0, 10000)
        self.width_spin.setSpecialValueText(tr("auto"))
        self.width_spin.valueChanged.connect(self._on_settings_changed)
        grid.addWidget(self.width_spin, 3, 1)
        self.height_label = QLabel(tr("height"))
        grid.addWidget(self.height_label, 3, 2)
        self.height_spin = QSpinBox()
        self.height_label.setBuddy(self.height_spin)
        self.height_spin.setRange(0, 10000)
        self.height_spin.setSpecialValueText(tr("auto"))
        self.height_spin.valueChanged.connect(self._on_settings_changed)
        grid.addWidget(self.height_spin, 3, 3)
        self.keep_aspect_checkbox = ToggleSwitch(tr("keep_aspect"))
        self.keep_aspect_checkbox.setChecked(True)
        self.keep_aspect_checkbox.stateChanged.connect(self._on_settings_changed)
        # Рядом с тумблером размера, а не отдельной строкой: настроек на
        # вкладке много, и каждая лишняя строка приближает прокрутку.
        grid.addWidget(self.keep_aspect_checkbox, 2, 2, 1, 2)
        self.fps_checkbox = ToggleSwitch(tr("change_fps"))
        self.fps_checkbox.stateChanged.connect(self._on_fps_toggle)
        grid.addWidget(self.fps_checkbox, 4, 0, 1, 2)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        self.fps_spin.setAccessibleName(tr("change_fps"))
        self.fps_spin.valueChanged.connect(self._on_settings_changed)
        grid.addWidget(self.fps_spin, 4, 2, 1, 2)
        # Обрезка по времени для видео и GIF — тем же тумблером, что размер и FPS.
        self.trim_checkbox = ToggleSwitch(tr("change_trim"))
        self.trim_checkbox.setToolTip(
            tr("trim_tip")
        )
        self.trim_checkbox.stateChanged.connect(self._on_trim_toggle)
        grid.addWidget(self.trim_checkbox, 5, 0, 1, 4)

        # Начало и конец фрагмента, а не начало и длина: «с 5 сек, длиной
        # 3 сек» приходилось считать в уме, «с 5 по 8 сек» — нет.
        # Наружу всё равно уходит длительность, её требует FFmpeg.
        trim_row = QHBoxLayout()
        trim_row.setSpacing(6)
        self.trim_start_label = QLabel(tr("trim_start"))
        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0.0, 86400.0)
        self.trim_start_spin.setSingleStep(0.5)
        self.trim_start_spin.setFixedWidth(TRIM_FIELD_WIDTH)
        self.trim_start_spin.setSuffix(tr("seconds_suffix"))
        self.trim_start_spin.valueChanged.connect(self._on_trim_changed)
        self.trim_end_label = QLabel(tr("trim_end"))
        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0.1, 86400.0)
        self.trim_end_spin.setSingleStep(0.5)
        self.trim_end_spin.setFixedWidth(TRIM_FIELD_WIDTH)
        self.trim_end_spin.setSuffix(tr("seconds_suffix"))
        self.trim_end_spin.valueChanged.connect(self._on_trim_changed)
        self.trim_start_label.setBuddy(self.trim_start_spin)
        self.trim_end_label.setBuddy(self.trim_end_spin)
        for widget in (self.trim_start_label, self.trim_start_spin,
                       self.trim_end_label, self.trim_end_spin):
            trim_row.addWidget(widget)
        trim_row.addStretch(1)
        grid.addLayout(trim_row, 6, 0, 1, 4)

        turn_caption = QLabel(tr("group_turn"))
        turn_caption.setObjectName("GroupCaption")
        grid.addWidget(turn_caption, 7, 0, 1, 4)

        # Поворот и отражение — одной строкой: двумя отдельными тумблерами
        # страница переставала помещаться в карточку без прокрутки.
        self.rotate_label = QLabel(tr("rotate"))
        grid.addWidget(self.rotate_label, 8, 0)
        self.rotate_combo = QComboBox()
        self.rotate_combo.setToolTip(tr("rotate_tip"))
        for caption, _degrees in rotate_options():
            self.rotate_combo.addItem(caption)
        self.rotate_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.rotate_label.setBuddy(self.rotate_combo)
        grid.addWidget(self.rotate_combo, 8, 1)

        self.flip_label = QLabel(tr("flip"))
        grid.addWidget(self.flip_label, 8, 2)
        self.flip_combo = QComboBox()
        for caption, _flags in flip_options():
            self.flip_combo.addItem(caption)
        self.flip_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.flip_label.setBuddy(self.flip_combo)
        grid.addWidget(self.flip_combo, 8, 3)

        quality_caption = QLabel(tr("group_quality"))
        quality_caption.setObjectName("GroupCaption")
        grid.addWidget(quality_caption, 9, 0, 1, 4)

        self.quality_checkbox = ToggleSwitch(tr("set_quality"))
        self.quality_checkbox.setToolTip(
            tr("set_quality_tip")
        )
        self.quality_checkbox.stateChanged.connect(self._on_quality_toggle)
        grid.addWidget(self.quality_checkbox, 10, 0, 1, 2)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(DEFAULT_QUALITY)
        self.quality_spin.setAccessibleName(tr("set_quality"))
        self.quality_spin.valueChanged.connect(self._on_settings_changed)
        grid.addWidget(self.quality_spin, 10, 2, 1, 2)

        self.target_size_checkbox = ToggleSwitch(tr("target_size"))
        self.target_size_checkbox.setToolTip(
            tr("target_size_tip")
        )
        self.target_size_checkbox.stateChanged.connect(self._on_target_size_toggle)
        grid.addWidget(self.target_size_checkbox, 11, 0, 1, 2)
        self.target_size_spin = QDoubleSpinBox()
        self.target_size_spin.setRange(0.1, 4096.0)
        self.target_size_spin.setSingleStep(0.5)
        self.target_size_spin.setValue(10.0)
        self.target_size_spin.setSuffix(tr("megabytes_suffix"))
        self.target_size_spin.setAccessibleName(tr("target_size"))
        self.target_size_spin.valueChanged.connect(self._on_settings_changed)
        grid.addWidget(self.target_size_spin, 11, 2, 1, 2)

        self.audio_label = QLabel(tr("audio_track"))
        grid.addWidget(self.audio_label, 12, 0)
        self.audio_combo = QComboBox()
        self.audio_combo.addItems([tr("audio_keep"), tr("audio_drop")])
        self.audio_combo.setToolTip(
            tr("audio_tip")
        )
        self.audio_combo.currentIndexChanged.connect(self._on_audio_changed)
        self.audio_label.setBuddy(self.audio_combo)
        grid.addWidget(self.audio_combo, 12, 1)
        self.audio_bitrate_label = QLabel(tr("audio_bitrate"))
        grid.addWidget(self.audio_bitrate_label, 12, 2)
        self.audio_bitrate_combo = QComboBox()
        for value in AUDIO_BITRATES:
            self.audio_bitrate_combo.addItem(tr("kbps", value=value))
        self.audio_bitrate_combo.setCurrentIndex(AUDIO_BITRATES.index(DEFAULT_AUDIO_BITRATE))
        self.audio_bitrate_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.audio_bitrate_label.setBuddy(self.audio_bitrate_combo)
        grid.addWidget(self.audio_bitrate_combo, 12, 3)

        grid.setRowStretch(13, 1)
        return main_tab

    def _make_group_header(self, caption):
        """Заголовок группы в списке форматов.

        Начертание задаётся элементу, а приглушённый цвет подставляет
        GroupHeaderDelegate: и правило QSS, и setForeground у элемента
        таблица стилей списка перебивает.
        """
        header = QStandardItem(caption)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont(self.format_combo.font())
        font.setBold(True)
        # Через QFontInfo, а не pointSize: таблица стилей задаёт размер в
        # пикселях, и pointSize у такого шрифта равен -1 — заголовок тогда
        # получал случайный размер вместо «на ступень мельче пунктов».
        font.setPixelSize(max(9, QFontInfo(font).pixelSize() - 2))
        header.setFont(font)
        return header

    def _fill_format_combo(self):
        """Наполняет список форматов группами с невыбираемыми заголовками.

        Пресеты площадок сюда не попадают — у них свои вкладки, а список
        из тридцати с лишним строк читать неудобно.
        """
        model = self.format_combo.model()
        for caption_key, codes in FORMAT_GROUPS:
            model.appendRow(self._make_group_header(tr(caption_key)))
            for code in codes:
                entry = QStandardItem(format_label(code))
                # Код держим в данных пункта: подписи переводятся, и искать
                # формат по тексту после смены языка стало бы нечем.
                entry.setData(code, DATA_ROLE)
                tooltip = format_tooltip(code)
                if tooltip:
                    entry.setToolTip(tooltip)
                model.appendRow(entry)

        # Список открывается в обычном режиме (combobox-popup: 0 в таблице
        # стилей), и Qt учитывает число видимых строк — по умолчанию их 10,
        # для двадцати с лишним форматов с заголовками групп это тесно.
        # Предел высоты — страховка поверх него: размер задаёт рамка-
        # контейнер, а не сам список, ограничение списка окно игнорирует.
        self.format_combo.setMaxVisibleItems(FORMAT_POPUP_VISIBLE_ITEMS)
        # Заголовки групп рисует делегат: цвет, заданный элементу или
        # правилом QSS, таблица стилей списка всё равно перебивает.
        # Ставим его самому списку, а не его виду: QComboBox подменяет
        # делегат вида своим, и назначенный напрямую до отрисовки не доживает.
        self.format_combo.setItemDelegate(
            # Подпись группы заметно приглушённее названий форматов,
            # чтобы заголовок не читался как ещё один пункт.
            GroupHeaderDelegate(palette()["format_header"], self.format_combo)
        )
        view = self.format_combo.view()
        view.setMaximumHeight(FORMAT_POPUP_MAX_HEIGHT)
        container = view.parentWidget()
        if container is not None:
            container.setMaximumHeight(FORMAT_POPUP_MAX_HEIGHT)
        self._select_format_in_combo(self._selected_format)

    def _select_format_in_combo(self, code):
        """Показывает в поле формата выбранный формат.

        Пресета площадки в списке нет, поэтому под него временно добавляется
        отдельная строка: иначе поле показывало бы прежний обычный формат,
        то есть попросту врало о том, что получится на выходе.
        """
        self._drop_preset_row()
        if code in PLATFORM_LABEL_KEYS:
            model = self.format_combo.model()
            entry = QStandardItem(format_label(code))
            entry.setData(code, DATA_ROLE)
            model.insertRow(0, entry)
            model.insertRow(0, self._make_group_header(tr("fmt_preset_group")))
            self._preset_row_shown = True
            self.format_combo.setCurrentIndex(1)
            return
        index = self.format_combo.findData(code, DATA_ROLE)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)

    def _drop_preset_row(self):
        """Убирает временную строку пресета из списка форматов."""
        if not self._preset_row_shown:
            return
        self._preset_row_shown = False
        model = self.format_combo.model()
        model.removeRow(0)
        model.removeRow(0)

    def _build_discord_tab(self):
        tab = QWidget()
        tab.setObjectName("SettingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(5)

        self.discord_format_code = "discord_sticker_png"
        self.discord_hint_label = QLabel()
        self.discord_hint_label.setObjectName("HintCallout")
        self.discord_hint_label.setWordWrap(True)
        self.discord_hint_label.setMinimumHeight(42)
        layout.addWidget(self.discord_hint_label)

        presets_layout = QGridLayout()
        presets_layout.setHorizontalSpacing(10)
        self.discord_preset_buttons = {}
        for column, (size, codes) in enumerate(DISCORD_PRESET_COLUMNS):
            caption = tr("col_emoji" if size == 128 else "col_sticker", size=size)
            header = QLabel(caption)
            header.setObjectName("GroupCaption")
            presets_layout.addWidget(header, 0, column)
            for row, code in enumerate(codes, start=1):
                label = tr(DISCORD_PRESET_LABEL_KEYS[code])
                button = self._make_preset_button(label, code, self._apply_discord_preset)
                self.discord_preset_buttons[code] = button
                presets_layout.addWidget(button, row, column)
        layout.addLayout(presets_layout)
        self._add_platform_footer(layout, "discord")
        return tab

    def _build_bottom_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        output_layout = QHBoxLayout()
        output_label = QLabel(tr("output_dir"))
        output_layout.addWidget(output_label)
        self.output_dir_edit = QLineEdit(self.output_dir)
        output_label.setBuddy(self.output_dir_edit)
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setObjectName("ReadOnlyPath")
        self.output_dir_edit.setToolTip(tr("output_dir_tip"))
        output_layout.addWidget(self.output_dir_edit, stretch=1)
        browse_button = QPushButton(tr("browse"))
        browse_button.clicked.connect(self._on_browse_output_dir)
        output_layout.addWidget(browse_button)
        layout.addLayout(output_layout)

        self.overwrite_checkbox = ToggleSwitch(tr("overwrite"))
        self.overwrite_checkbox.setChecked(
            self.settings_store.value("overwrite", False, type=bool)
        )
        self.overwrite_checkbox.setToolTip(
            tr("overwrite_tip")
        )

        # Сокращается многоточием, а не распирает строку: итог обработки
        # рядом с кнопками «Открыть папку» и «Отчёт» в неё не помещался.
        self.current_file_label = ElidedLabel(idle_status())
        self.current_file_label.setObjectName("HintLabel")

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        # В простое полоса не нужна — показывается только во время работы.
        self.overall_progress_bar.setVisible(False)

        self.report_button = QPushButton(tr("report_csv"))
        self.report_button.clicked.connect(self._on_save_report)
        self.report_button.setVisible(False)

        self.start_button = QPushButton(tr("start"))
        self.start_button.setObjectName("StartButton")
        self.start_button.setToolTip(tr("start_tip"))
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button = QPushButton(tr("stop"))
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setToolTip(tr("stop_off"))
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)

        # Настройка и статус слева, кнопки запуска справа в одной строке:
        # так низ окна не растягивается на четыре отдельных яруса.
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setSpacing(4)
        left_column.addWidget(self.overwrite_checkbox)
        left_column.addWidget(self.current_file_label)
        left_column.addWidget(self.overall_progress_bar)
        action_row.addLayout(left_column, stretch=1)

        self.open_folder_button = QPushButton(tr("open_folder"))
        self.open_folder_button.setToolTip(tr("open_folder_tip"))
        self.open_folder_button.clicked.connect(self._on_open_output_folder)
        self.open_folder_button.setVisible(False)

        action_row.addWidget(self.open_folder_button, alignment=Qt.AlignmentFlag.AlignBottom)
        action_row.addWidget(self.report_button, alignment=Qt.AlignmentFlag.AlignBottom)
        action_row.addWidget(self.stop_button, alignment=Qt.AlignmentFlag.AlignBottom)
        action_row.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(action_row)

        return container

    def _check_ffmpeg_status(self, quiet=False):
        available, ffmpeg_path, ffprobe_path = check_ffmpeg_available()
        if available:
            try:
                from ffmpeg_utils import FFmpegProcessor

                self._ffmpeg_probe = FFmpegProcessor()
            except Exception:
                self._ffmpeg_probe = None
        if not available:
            self.ffmpeg_warning_label.setText(
                tr("ffmpeg_warning")
            )
            self.ffmpeg_warning_label.setVisible(True)
            if quiet:
                # При смене языка окно пересобирается, и предупреждение
                # всплывало бы заново — а пользователь его уже видел.
                return
            QMessageBox.warning(
                self,
                tr("dlg_ffmpeg_title"),
                tr("dlg_ffmpeg_text"),
            )

    def _on_add_files_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("dlg_choose_files"), "", supported_files_filter()
        )
        if paths:
            self._add_files_from_paths(paths)

    def _add_files_from_paths(self, paths):
        needs_scan = any(os.path.isdir(path) for path in paths)
        if not needs_scan:
            # Один проход вместо проверки вхождения в список: на нескольких
            # тысячах выбранных файлов квадратичный перебор заметно тормозил.
            accepted, skipped = [], []
            for path in paths:
                target = accepted if os.path.splitext(path)[1].lower() in SUPPORTED_INPUT_EXTS \
                    else skipped
                target.append(path)
            self._on_scan_finished(accepted, skipped)
            return

        if self.scan_worker is not None and self.scan_worker.isRunning():
            QMessageBox.information(
                self, tr("dlg_scanning_title"), tr("dlg_scanning_text")
            )
            return
        self.current_file_label.setText(tr("scanning"))
        self.scan_worker = FolderScanWorker(list(paths))
        self.scan_worker.finished_scan.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_finished(self, accepted, skipped):
        self.current_file_label.setText(idle_status())
        # Сравниваем нормализованные пути: на Windows C:\Foo\a.png и
        # c:\foo\a.png — один и тот же файл, а строки разные.
        existing = {
            self._normalized(self._entry(self.file_list.item(i)).input_path)
            for i in range(self.file_list.count())
        }
        duplicates = []
        added_any = False
        for path in accepted:
            key = self._normalized(path)
            if key in existing:
                duplicates.append(path)
                continue
            if self._try_add_single_file(path):
                existing.add(key)
                added_any = True
            else:
                skipped.append(path)

        notes = []
        if skipped:
            notes.append(
                tr("dlg_skipped_format") + "\n" + "\n".join(skipped[:15])
                + ("\n" + tr("dlg_and_more", count=len(skipped) - 15)
                   if len(skipped) > 15 else "")
            )
        if duplicates:
            notes.append(
                tr("dlg_skipped_dupes") + "\n" + "\n".join(duplicates[:15])
                + ("\n" + tr("dlg_and_more", count=len(duplicates) - 15)
                   if len(duplicates) > 15 else "")
            )
        if notes:
            QMessageBox.information(self, tr("dlg_skipped_title"), "\n\n".join(notes))
        self._update_queue_counter()
        self._start_image_thumbnails()
        self._start_video_thumbnails()
        self._queue_durations_ready(
            [self._entry(self.file_list.item(i)).input_path
             for i in range(self.file_list.count())]
        )
        if added_any and self.file_list.count() > 0 and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)

    def _append_entry(self, entry):
        item = QListWidgetItem()
        item.setData(DATA_ROLE, entry)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if entry.enabled else Qt.CheckState.Unchecked
        )
        self._set_item_thumbnail(item, entry.input_path)
        self._refresh_item_text(item)
        self.file_list.addItem(item)
        return item

    def _try_add_single_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_INPUT_EXTS:
            return False
        if not os.path.isfile(path):
            return False
        self._append_entry(
            QueueEntry(input_path=path, settings=default_settings_for(path))
        )
        return True

    def _set_all_checked(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.file_list.count()):
            self.file_list.item(row).setCheckState(state)
        self._update_queue_counter()

    def _on_item_check_changed(self, item):
        """Галочка строки сохраняется в её данных."""
        if self._refreshing_items:
            return
        entry = self._entry(item)
        if entry is None:
            return
        entry.enabled = item.checkState() == Qt.CheckState.Checked
        item.setData(DATA_ROLE, entry)
        self._update_queue_counter()

    def _checked_rows(self):
        return [
            row for row in range(self.file_list.count())
            if self.file_list.item(row).checkState() == Qt.CheckState.Checked
        ]

    def _update_queue_counter(self):
        total = self.file_list.count()
        if not total:
            self.queue_counter_label.setText(tr("queue_empty"))
            # Сообщение о применённом пресете относится к файлам, которых
            # больше нет, — иначе оно висит и путает.
            if self.worker is None:
                self.current_file_label.setText(idle_status())
        else:
            checked = len(self._checked_rows())
            if checked == total:
                self.queue_counter_label.setText(tr("queue_count", total=total))
            else:
                self.queue_counter_label.setText(tr("queue_checked", checked=checked, total=total))
        self.file_list.set_placeholder_visible(total == 0)
        checked = len(self._checked_rows()) if total else 0
        self.check_all_button.setEnabled(checked < total)
        self.uncheck_all_button.setEnabled(checked > 0)
        self.clear_button.setEnabled(total > 0)
        self.remove_button.setEnabled(bool(self.file_list.selectedItems()))

    def _set_item_thumbnail(self, item, path):
        """Ставит миниатюру из кэша или ставит файл в очередь на разбор.

        Ни картинки, ни видео здесь не читаются: декодирование фотографии
        ради значка 48 px занимало до 160 мс, и добавление папки на две
        сотни снимков подвешивало окно на полминуты. Теперь этим заняты
        фоновые потоки, а окно остаётся отзывчивым.
        """
        # На больших очередях отрисовка тысяч миниатюр подвешивает окно.
        if self.file_list.count() >= THUMBNAIL_LIMIT:
            return
        cached = self._thumbnail_cache.get(path)
        if cached is not None:
            item.setIcon(QIcon(cached))
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in THUMBNAIL_IMAGE_EXTS:
            self._pending_image_thumbnails.append(path)
            return
        # По расширению, а не через get_category: видео от анимации она
        # отличает открытием файла, а здесь поток интерфейса.
        if ext in VIDEO_EXTS:
            self._pending_video_thumbnails.append(path)

    def _start_image_thumbnails(self):
        """Разбирает накопленные картинки в фоне, порциями."""
        if not self._pending_image_thumbnails:
            return
        if self._image_thumb_worker is not None and self._image_thumb_worker.isRunning():
            return
        paths = self._pending_image_thumbnails[:]
        self._pending_image_thumbnails.clear()
        self._image_thumb_worker = ImageThumbnailWorker(paths, self)
        self._image_thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._image_thumb_worker.finished.connect(self._on_image_thumb_worker_finished)
        self._image_thumb_worker.finished.connect(self._image_thumb_worker.deleteLater)
        self._image_thumb_worker.start()

    def _on_image_thumb_worker_finished(self):
        self._image_thumb_worker = None
        self._start_image_thumbnails()

    def _start_video_thumbnails(self):
        if not self._pending_video_thumbnails or self._ffmpeg_probe is None:
            self._pending_video_thumbnails.clear()
            return
        if self._thumb_worker is not None and self._thumb_worker.isRunning():
            # Не бросаем накопленное: воркер занят, но по его завершении
            # очередь разбирается дальше. Раньше файлы, добавленные во время
            # предыдущего разбора, оставались без миниатюр навсегда.
            return
        paths = self._pending_video_thumbnails[:]
        self._pending_video_thumbnails.clear()
        # Родитель обязателен: ссылку на воркер мы снимаем по его завершении,
        # и без владельца объект QThread удалил бы сборщик мусора Python.
        self._thumb_worker = VideoThumbnailWorker(self._ffmpeg_probe, paths, self)
        self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_worker.finished.connect(self._on_thumb_worker_finished)
        self._thumb_worker.finished.connect(self._thumb_worker.deleteLater)
        self._thumb_worker.start()

    def _on_thumb_worker_finished(self):
        """Ссылку снимаем до повтора: сразу после сигнала finished поток
        ещё может числиться работающим, и проверка отбросила бы остаток."""
        self._thumb_worker = None
        self._start_video_thumbnails()

    def _on_thumbnail_ready(self, path, image):
        """Готовая миниатюра из фонового потока — и для картинок, и для видео.

        Из потока приходит QImage; в QPixmap он переводится здесь, в потоке
        интерфейса — только там Qt разрешает работать с устройствами отрисовки.
        """
        scaled = QPixmap.fromImage(image).scaled(
            THUMBNAIL_SIZE, THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_cache[path] = scaled
        icon = QIcon(scaled)
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if self._entry(item).input_path == path:
                if item.icon().isNull():
                    item.setIcon(icon)
                # Дубликаты в очередь не попадают, поэтому дальше не ищем.
                break

    def _move_selected(self, offset):
        rows = sorted(self.file_list.row(item) for item in self.file_list.selectedItems())
        if not rows:
            return
        if offset < 0 and rows[0] == 0:
            return
        if offset > 0 and rows[-1] == self.file_list.count() - 1:
            return
        for row in (rows if offset < 0 else reversed(rows)):
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row + offset, item)
            item.setSelected(True)

    def _on_remove_selected(self):
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
        self._set_settings_enabled(
            self.file_list.count() > 0 and len(self.file_list.selectedItems()) > 0
        )
        self._update_queue_counter()

    def _on_clear_list(self):
        self.file_list.clear()
        self._set_settings_enabled(False)
        self._update_queue_counter()

    @staticmethod
    def _entry(item):
        return item.data(DATA_ROLE)

    @staticmethod
    def _normalized(path):
        """Путь в сравнимом виде: без учёта регистра и формы записи."""
        try:
            return os.path.normcase(os.path.abspath(path))
        except (OSError, ValueError):
            return path

    def _duration_of(self, path):
        """Длительность для подписи в очереди. Для анимированных картинок
        считается сразу (это чтение заголовка), для видео берётся из кэша,
        который наполняет фоновый опрос ffprobe."""
        cached = self._media_info_cache.get(path)
        if cached is not None:
            return cached.get("duration")
        # Строка очереди перерисовывается на каждом обновлении процента,
        # поэтому сначала отсекаем по расширению: get_category ради ответа
        # про анимацию открывает файл.
        if os.path.splitext(path)[1].lower() not in MAYBE_ANIMATED_EXTS:
            return None
        if get_category(path) == "animated_image":
            details = animated_image_info(
                path, getattr(self._ffmpeg_probe, "ffprobe_path", None)
            )
            if details:
                self._media_info_cache[path] = {
                    "duration": details.get("duration"),
                    "fps": details.get("fps"),
                    "width": None, "height": None,
                }
                return details.get("duration")
        return None

    def _queue_durations_ready(self, paths=None):
        """Опрашивает длительность видео в очереди, чтобы подписи появились
        без выделения каждого файла вручную.

        Список берётся из самой очереди, а не из аргумента: пока шёл прошлый
        опрос, могли добавиться новые файлы, и раньше они оставались
        без длительности до тех пор, пока их не выделят мышью.
        """
        if paths is None:
            paths = [
                self._entry(self.file_list.item(i)).input_path
                for i in range(self.file_list.count())
            ]
        # Отбор по расширению: get_category открывала бы каждый файл очереди
        # прямо в потоке интерфейса, а видео от всего прочего расширение
        # отличает однозначно.
        pending = [
            path for path in paths
            if path not in self._media_info_cache
            and os.path.splitext(path)[1].lower() in VIDEO_EXTS
        ]
        if not pending or self._ffmpeg_probe is None:
            return
        if self._queue_info_worker is not None and self._queue_info_worker.isRunning():
            return
        self._queue_info_worker = QueueInfoWorker(self._ffmpeg_probe, pending, self)
        self._queue_info_worker.info_ready.connect(self._on_queue_info_ready)
        self._queue_info_worker.finished.connect(self._on_queue_info_worker_finished)
        self._queue_info_worker.finished.connect(self._queue_info_worker.deleteLater)
        self._queue_info_worker.start()

    def _on_queue_info_worker_finished(self):
        self._queue_info_worker = None
        self._queue_durations_ready()

    def _on_queue_info_ready(self, path, info):
        self._media_info_cache[path] = info
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if self._entry(item).input_path == path:
                self._refresh_item_text(item)
                break
        # Параметры приходят из фонового опроса уже после того, как файл
        # выбран, поэтому подписи о длительности и размере кадра надо
        # пересчитать — иначе они остаются пустыми до повторного выбора.
        selected = self.file_list.selectedItems()
        if selected and self._entry(selected[-1]).input_path == path:
            self._clamp_tg_duration()

    def _refresh_item_text(self, item):
        entry = self._entry(item)
        # setText/setToolTip тоже поднимают itemChanged — глушим обработчик,
        # иначе он принял бы это за смену галочки.
        self._refreshing_items = True
        name = os.path.basename(entry.input_path)
        status = entry.status
        if status == STATUS_PROCESSING:
            suffix = f"   ·   {entry.progress}%"
        elif status == STATUS_ERROR:
            suffix = f"   ·   {first_line(entry.message)}"
        else:
            suffix = ""
        code = entry.settings.output_format
        format_display = format_label(code)
        duration = self._duration_of(entry.input_path)
        tail = f"  →  {format_display}"
        if duration:
            tail = f"  ({self._format_duration(duration)})" + tail
        # Само состояние показывает значок справа, в тексте оно остаётся
        # только когда несёт подробности (процент или ошибка).
        item.setText(f"{name}{tail}{suffix}")
        # Части подписи — для делегата: он сокращает имя, а не формат.
        item.setData(ITEM_PARTS_ROLE, (name, tail, suffix))
        # Состояние словами — первой строкой подсказки: значок различается
        # цветом и формой, но словами надёжнее.
        status_line = tr(REPORT_STATUS_KEYS.get(status, "status_pending"))
        if status == STATUS_ERROR and entry.message:
            details = tr("error_tooltip", message=message_text(entry.message))
        else:
            details = entry.input_path
        item.setToolTip(f"{status_line}\n{details}")
        self._refreshing_items = False

    def _status_at_index(self, index):
        """Статус строки для делегата, рисующего цветную точку."""
        entry = index.data(DATA_ROLE)
        return entry.status if isinstance(entry, QueueEntry) else None

    def _on_queue_context_menu(self, position):
        item = self.file_list.itemAt(position)
        paste_action = QAction(tr("menu_paste"), self)
        paste_action.triggered.connect(self._paste_from_clipboard)
        link_action = QAction(tr("menu_add_link"), self)
        link_action.triggered.connect(self._on_add_link)
        if item is None:
            # По пустому месту — только добавление: остальным пунктам нужен файл.
            menu = PopupMenu(self)
            menu.addAction(paste_action)
            menu.addAction(link_action)
            menu.exec(self.file_list.viewport().mapToGlobal(position))
            return
        entry = self._entry(item)
        menu = PopupMenu(self)

        open_action = QAction(tr("menu_open"), self)
        open_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(entry.input_path))
        )
        menu.addAction(open_action)

        reveal_action = QAction(tr("menu_reveal"), self)
        reveal_action.triggered.connect(lambda: self._reveal_in_explorer(entry.input_path))
        menu.addAction(reveal_action)

        if entry.status == STATUS_ERROR and entry.message:
            details_action = QAction(tr("menu_error"), self)
            details_action.triggered.connect(
                lambda: QMessageBox.critical(self, tr("dlg_error_details"),
                                             message_text(entry.message))
            )
            menu.addAction(details_action)

        menu.addSeparator()
        menu.addAction(paste_action)
        menu.addAction(link_action)
        remove_action = QAction(tr("menu_remove"), self)
        remove_action.triggered.connect(self._on_remove_selected)
        menu.addAction(remove_action)

        menu.exec(self.file_list.viewport().mapToGlobal(position))

    def _paste_from_clipboard(self):
        """Ctrl+V: файлы, путь или картинка из буфера обмена — в очередь.

        Картинку, скопированную в браузере или снятую «Ножницами», файлом
        не передать, поэтому она сохраняется в папку программы и в очередь
        встаёт уже как обычный PNG.
        """
        if self.worker is not None:
            return
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return
        paths = []
        if mime.hasUrls():
            paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        if not paths and mime.hasText():
            candidates = [line.strip().strip('"') for line in mime.text().splitlines()]
            paths = [path for path in candidates if path and os.path.exists(path)]
        if paths:
            self._add_files_from_paths(paths)
            return
        # Ссылка на картинку лучше самой картинки: «Копировать изображение»
        # в браузере кладёт в буфер только первый кадр GIF, а по адресу из
        # той же вставки (<img src>) скачивается вся анимация.
        links = []
        if mime.hasHtml():
            links = [url for url in IMG_SRC_RE.findall(mime.html())
                     if url.lower().startswith(("http://", "https://"))][:1]
        if not links and mime.hasUrls():
            links = [url.toString() for url in mime.urls()
                     if url.scheme() in ("http", "https")]
        if not links and mime.hasText():
            links = url_import.extract_urls(mime.text())
        if links:
            self._add_files_from_urls(links)
            return
        if mime.hasImage():
            image = QImage(mime.imageData())
            if not image.isNull():
                try:
                    path = save_clipboard_image(image)
                except OSError as exc:
                    self.current_file_label.setText(tr("paste_failed", error=exc))
                    return
                self._add_files_from_paths([path])
                self.current_file_label.setText(tr("paste_added", count=1))
                return
        self.current_file_label.setText(tr("paste_nothing"))

    def _on_add_link(self):
        """Диалог «Добавить по ссылке»: одна ссылка или несколько, по строкам."""
        if self.worker is not None:
            return
        text, accepted = QInputDialog.getMultiLineText(
            self, tr("dlg_link_title"), tr("dlg_link_text"))
        if not accepted:
            return
        links = url_import.extract_urls(text)
        if not links:
            self.current_file_label.setText(tr("link_none"))
            return
        self._add_files_from_urls(links)

    def _on_link_entered(self):
        """Ссылка из поля над очередью: Enter или кнопка «Добавить»."""
        if self.worker is not None:
            self.current_file_label.setText(tr("link_busy"))
            return
        links = url_import.extract_urls(self.link_edit.text())
        if not links:
            self.current_file_label.setText(tr("link_none"))
            return
        self.link_edit.clear()
        self._add_files_from_urls(links)

    def _add_files_from_urls(self, urls):
        """Скачивает файлы по ссылкам и ставит их в очередь по мере загрузки."""
        if self.worker is not None or not urls:
            return
        if self._link_worker is not None:
            # Предыдущая загрузка ещё идёт — новые ссылки встанут за ней.
            self._pending_links.extend(urls)
            return
        self._link_errors = []
        self._link_added = 0
        self._start_link_download(list(urls))

    def _start_link_download(self, urls):
        self._link_total = len(urls)
        self._link_done = 0
        self.current_file_label.setText(tr("link_downloading", done=0, total=self._link_total))
        self._link_worker = LinkDownloadWorker(urls, self)
        self._link_worker.downloaded.connect(self._on_link_downloaded)
        self._link_worker.failed.connect(self._on_link_failed)
        self._link_worker.finished.connect(self._on_link_worker_finished)
        self._link_worker.finished.connect(self._link_worker.deleteLater)
        self._link_worker.start()

    def _link_progress(self):
        self._link_done += 1
        self.current_file_label.setText(
            tr("link_downloading", done=self._link_done, total=self._link_total))

    def _on_link_downloaded(self, path):
        self._link_progress()
        self._link_added += 1
        self._add_files_from_paths([path])

    def _on_link_failed(self, url, error):
        self._link_progress()
        self._link_errors.append(f"{url}\n{message_text(error)}")

    def _on_link_worker_finished(self):
        self._link_worker = None
        if self._pending_links:
            pending, self._pending_links = self._pending_links, []
            self._start_link_download(pending)
            return
        if self._link_errors:
            self.current_file_label.setText(
                tr("link_result", added=self._link_added, failed=len(self._link_errors)))
            QMessageBox.warning(self, tr("dlg_link_failed_title"),
                                "\n\n".join(self._link_errors[:10]))
        else:
            self.current_file_label.setText(tr("link_added", count=self._link_added))

    def _reveal_in_explorer(self, path):
        """Открывает проводник с выделенным файлом."""
        if not os.path.exists(path):
            QMessageBox.information(self, tr("dlg_file_missing_title"),
                                    tr("dlg_file_missing_text", path=path))
            return
        if os.name == "nt":
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                return
            except OSError:
                _log.debug("Не удалось открыть проводник", exc_info=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _on_item_double_clicked(self, item):
        entry = self._entry(item)
        if entry.status == STATUS_ERROR and entry.message:
            QMessageBox.critical(self, tr("dlg_error_details"), message_text(entry.message))

    def _on_selection_changed(self):
        selected_items = self.file_list.selectedItems()
        self.remove_button.setEnabled(bool(selected_items))
        # «Пресет применён к выделенным файлам: 1» относится к прежнему
        # выделению — с новым оно только путает.
        if (self._transient_status is not None and self.worker is None
                and self.current_file_label.text() == self._transient_status):
            self._set_status(idle_status())
        self._set_settings_enabled(len(selected_items) > 0)
        if not selected_items:
            self._refresh_previews()
            return
        self._load_settings_into_panel(self._entry(selected_items[-1]).settings)

    # --- предпросмотр в макете чата ---

    def _preview_path(self):
        """Файл для предпросмотра: последний выделенный в очереди."""
        selected = self.file_list.selectedItems()
        if not selected:
            return None
        return self._entry(selected[-1]).input_path

    def _refresh_previews(self):
        """Обновляет предпросмотры всех площадок по выбранному файлу и пресету."""
        previews = getattr(self, "chat_previews", None)
        if not previews or not self._ui_ready:
            return
        codes = {
            "telegram": self.telegram_format_code,
            "twitch": self.twitch_format_code,
            "discord": self.discord_format_code,
            "whatsapp": self.whatsapp_format_code,
        }
        codes.update(self.square_format_codes)
        degrees = [value for _caption, value in rotate_options()]
        rotate = degrees[self.rotate_combo.currentIndex()]
        flip_h, flip_v = flip_options()[self.flip_combo.currentIndex()][1]
        fill = self._fill_square_checked()
        for platform, preview in previews.items():
            preview.set_preset(codes[platform], fill)
            preview.set_transform(rotate, flip_h, flip_v)
            # Без выбранного пресета предпросмотр приглушён: на выходе будет
            # обычный формат, а не стикер или смайлик.
            active = codes[platform] == self._selected_format
            preview.set_active(active)
            # Статичный пресет даёт одну картинку — анимация стоит на ней.
            preview.set_still(active and is_static_target(codes[platform]))
            preview.setToolTip(tr("preview_title") if active
                               else tr("preset_none_hint", platform=PLATFORM_TITLES[platform]))

        path = self._preview_path()
        if path == self._preview_shown_path:
            return
        self._preview_shown_path = path
        if path is None:
            for preview in previews.values():
                preview.set_image(None)
            return
        frame = self._preview_frames.get(path)
        if frame is not None:
            self._show_preview_frame(path, frame)
            # Кадр уже был, а что проигрывать — ещё не известно (поток
            # предпросмотра прервали): спрашиваем у потока очереди.
            if path not in self._motion_sources and media_motion.may_move(path):
                self._request_queue_motion([path])
            return
        # Пока кадр готовится в фоне, прежний файл не показываем — это
        # выглядело бы как предпросмотр не того файла.
        for preview in previews.values():
            preview.set_image(None)
        self._pending_preview_path = path
        self._start_preview_worker()

    def _start_preview_worker(self):
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return
        path = self._pending_preview_path
        if path is None:
            return
        self._pending_preview_path = None
        self._preview_worker = PreviewFrameWorker(path, self._ffmpeg_probe, self)
        self._preview_worker.frame_ready.connect(self._on_preview_frame_ready)
        self._preview_worker.animation_ready.connect(self._on_preview_animation_ready)
        self._preview_worker.finished.connect(self._on_preview_worker_finished)
        self._preview_worker.finished.connect(self._preview_worker.deleteLater)
        self._preview_worker.start()

    def _on_preview_worker_finished(self):
        self._preview_worker = None
        self._start_preview_worker()

    def _on_preview_frame_ready(self, path, image):
        # Пустой кадр не кэшируем: видео без FFmpeg покажется, как только
        # FFmpeg найдётся, а не останется пустым до перезапуска.
        if not image.isNull():
            if len(self._preview_frames) >= PREVIEW_CACHE_LIMIT:
                self._preview_frames.pop(next(iter(self._preview_frames)))
            self._preview_frames[path] = image
        if path == self._preview_shown_path:
            self._show_preview_frame(path, image)

    def _on_preview_animation_ready(self, path, source):
        self._on_motion_ready(path, source)

    def _on_motion_ready(self, path, source):
        """Известно, что проигрывать для файла (или что ничего)."""
        self._motion_sources[path] = source
        if path == self._preview_shown_path:
            self._show_preview_frame(path, self._preview_frames.get(path, QImage()))
        self._schedule_motion_sync()

    def _show_preview_frame(self, path, image):
        """Кадр или анимация файла во всех предпросмотрах.

        Проигрывается только короткая анимация (media_motion) и только если
        анимация файлов не выключена; иначе — неподвижный кадр.
        """
        is_video = os.path.splitext(path)[1].lower() in VIDEO_EXTS
        source = self._motion_sources.get(path) if self._animate_media else None
        for preview in self.chat_previews.values():
            if source:
                preview.set_movie(source, image if not image.isNull() else None,
                                  from_video=is_video)
            else:
                preview.set_image(image if not image.isNull() else None, is_video)

    # --- анимированные миниатюры очереди ---

    def _schedule_motion_sync(self, *_args):
        """Пересчитать анимированные миниатюры — чуть позже и один раз:
        прокрутка и добавление сотни файлов шлют сигналы пачками."""
        timer = getattr(self, "_motion_sync_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(QUEUE_MOTION_SYNC_MS)
            timer.timeout.connect(self._sync_queue_motion)
            self._motion_sync_timer = timer
        timer.start()

    def _visible_queue_items(self):
        """Строки очереди, которые сейчас видны, — {путь: строка}."""
        visible = {}
        view = self.file_list
        count = view.count()
        if not count:
            return visible
        height = view.viewport().height()
        first = view.indexAt(QPoint(4, 2)).row()
        last = view.indexAt(QPoint(4, max(2, height - 2))).row()
        first = 0 if first < 0 else first
        last = count - 1 if last < 0 else last
        for row in range(first, min(last, count - 1) + 1):
            item = view.item(row)
            path = self._entry(item).input_path
            if media_motion.may_move(path):
                visible[path] = item
        return visible

    def _sync_queue_motion(self):
        """Анимирует миниатюры видимых строк, остальные останавливает.

        Только видимые: анимация сотни миниатюр, которых никто не видит,
        тратила бы процессор впустую. В свёрнутом окне и при выключенной
        анимации стоят все.
        """
        if not getattr(self, "_ui_ready", False):
            return
        wanted = self._animate_media and self.isVisible() and not self.isMinimized()
        visible = self._visible_queue_items() if wanted else {}
        self._queue_motion_items = visible
        for path in list(self._queue_movies):
            if path not in visible or not self._motion_sources.get(path):
                self._stop_queue_movie(path)
        unknown = []
        for path in visible:
            source = self._motion_sources.get(path)
            if source is None:
                unknown.append(path)
            elif source and path not in self._queue_movies:
                self._start_queue_movie(path, source)
        if unknown:
            self._request_queue_motion(unknown)

    def _request_queue_motion(self, paths):
        for path in paths:
            if path not in self._queue_motion_pending:
                self._queue_motion_pending.append(path)
        if self._queue_motion_worker is not None or not self._queue_motion_pending:
            return
        batch, self._queue_motion_pending = self._queue_motion_pending, []
        worker = QueueMotionWorker(batch, self)
        worker.ready.connect(self._on_motion_ready)
        worker.finished.connect(self._on_queue_motion_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._queue_motion_worker = worker
        worker.start()

    def _on_queue_motion_worker_finished(self):
        self._queue_motion_worker = None
        # Пока поток работал, могли прокрутить к другим строкам.
        pending = [path for path in self._queue_motion_pending
                   if path not in self._motion_sources]
        self._queue_motion_pending = []
        if pending:
            self._request_queue_motion(pending)

    def _start_queue_movie(self, path, source):
        movie = QMovie(source, parent=self)
        if not movie.isValid() or movie.frameCount() == 1:
            movie.deleteLater()
            return
        movie.setCacheMode(QMovie.CacheMode.CacheNone)
        movie.frameChanged.connect(lambda _frame, key=path: self._on_queue_movie_frame(key))
        self._queue_movies[path] = movie
        movie.start()

    def _on_queue_movie_frame(self, path):
        movie = self._queue_movies.get(path)
        item = self._queue_motion_items.get(path)
        if movie is None or item is None:
            return
        image = movie.currentImage()
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image).scaled(
            THUMBNAIL_SIZE, THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._set_queue_icon(item, QIcon(pixmap))

    def _set_queue_icon(self, item, icon):
        # setIcon поднимает itemChanged — глушим обработчик галочек.
        self._refreshing_items = True
        try:
            item.setIcon(icon)
        except RuntimeError:
            pass  # строка уже удалена из очереди
        finally:
            self._refreshing_items = False

    def _stop_queue_movie(self, path):
        """Останавливает анимацию миниатюры и возвращает неподвижный кадр."""
        movie = self._queue_movies.pop(path, None)
        if movie is None:
            return
        movie.stop()
        movie.deleteLater()
        static = self._thumbnail_cache.get(path)
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if self._entry(item).input_path == path:
                self._set_queue_icon(item, QIcon(static) if static is not None else QIcon())
                break

    def _stop_all_queue_movies(self):
        for path in list(self._queue_movies):
            self._stop_queue_movie(path)

    def _set_media_animation(self, enabled):
        """Переключатель «Анимация файлов» из меню версии."""
        self._animate_media = bool(enabled)
        self.settings_store.setValue("animate_media", self._animate_media)
        self._sync_queue_motion()
        if self._preview_shown_path:
            self._show_preview_frame(self._preview_shown_path,
                                     self._preview_frames.get(self._preview_shown_path,
                                                              QImage()))

    def changeEvent(self, event):
        super().changeEvent(event)
        # Свернули или развернули окно — анимации останавливаются или идут.
        if event.type() == QEvent.Type.WindowStateChange:
            self._schedule_motion_sync()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_motion_sync()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_motion_sync()

    def _on_save_report(self):
        if not self._last_report:
            QMessageBox.information(self, tr("dlg_no_data_title"), tr("dlg_no_data_text"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_save_report"), "report.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow([tr("csv_file"), tr("csv_format"), tr("csv_status"),
                                 tr("csv_seconds"), tr("csv_message")])
                for row in self._last_report:
                    writer.writerow([
                        row["input_path"], format_label(row["output_format"]),
                        tr(REPORT_STATUS_KEYS[row["status"]])
                        if row["status"] in REPORT_STATUS_KEYS else row["status"],
                        row["elapsed_sec"], first_line(row["message"]),
                    ])
        except OSError as exc:
            QMessageBox.warning(self, tr("dlg_save_failed"), str(exc))
            return
        QMessageBox.information(self, tr("dlg_saved"), tr("dlg_report_saved", path=path))

    def _on_tg_start_changed(self):
        self._clamp_tg_duration()
        self._on_settings_changed()

    def _selected_source_duration(self):
        """Длительность выбранного файла, если она известна."""
        selected = self.file_list.selectedItems()
        if not selected:
            return None
        return self._duration_of(self._entry(selected[-1]).input_path)

    def _clamp_tg_duration(self):
        """Не даём выбрать фрагмент за пределами исходника и растягивать
        короткий файл: длительность ограничена остатком после «Начала»."""
        source = self._selected_source_duration()
        if not source:
            self.tg_start_spin.setMaximum(3600.0)
            self.tg_duration_spin.setMaximum(MAX_VIDEO_DURATION_SEC)
            self.tg_source_label.setText("")
            return

        max_start = max(0.0, source - 0.1)
        self.tg_start_spin.setMaximum(max_start)
        remaining = max(0.1, source - self.tg_start_spin.value())
        limit = min(MAX_VIDEO_DURATION_SEC, remaining)
        was_loading = self._loading_settings
        self._loading_settings = True
        try:
            self.tg_duration_spin.setMaximum(limit)
            if self.tg_duration_spin.value() > limit:
                self.tg_duration_spin.setValue(limit)
        finally:
            self._loading_settings = was_loading

        if source <= MAX_VIDEO_DURATION_SEC:
            self.tg_source_label.setText(
                tr("tg_source_short", duration=self._format_duration(source))
            )
        else:
            self.tg_source_label.setText(
                tr("tg_source_long", duration=self._format_duration(source),
                   length=number(round(self.tg_duration_spin.value(), 1)),
                   start=number(round(self.tg_start_spin.value(), 1)))
            )

    def _autofill_tg_duration(self, settings):
        """Подставляет длительность исходника, пока пользователь её не менял:
        раньше короткий файл всё равно растягивался до трёх секунд."""
        source = self._selected_source_duration()
        if not source:
            return
        if settings.tg_start or settings.tg_duration != MAX_VIDEO_DURATION_SEC:
            return
        was_loading = self._loading_settings
        self._loading_settings = True
        try:
            self.tg_duration_spin.setValue(min(source, MAX_VIDEO_DURATION_SEC))
        finally:
            self._loading_settings = was_loading

    def _update_telegram_hint(self):
        self._set_platform_hint("telegram", self.telegram_hint_label,
                                telegram_hint(self.telegram_format_code),
                                self.telegram_format_code, "Telegram")
        # У стикера Telegram одна сторона 512, другая — по пропорциям:
        # заполнять нечего, тумблер действует только на эмодзи.
        emoji = is_telegram_emoji_format(self.telegram_format_code)
        toggle = self.fill_toggles.get("telegram")
        if toggle is not None:
            toggle.setEnabled(emoji)
            toggle.setToolTip(tr("fill_square_tip") if emoji
                              else tr("fill_square_sticker_tip"))
        # Поле длительности остаётся на месте и просто гаснет для статичных
        # форматов, иначе кнопки подпрыгивают при переключении пресета.
        is_video = is_telegram_video_format(self.telegram_format_code)
        self.tg_duration_label.setEnabled(is_video)
        self.tg_duration_spin.setEnabled(is_video)
        self.tg_start_label.setEnabled(is_video)
        self.tg_start_spin.setEnabled(is_video)
        self.tg_units_label.setEnabled(is_video)
        self.tg_source_label.setVisible(is_video)
        self._sync_preset_buttons()

    def _update_twitch_hint(self):
        self._set_platform_hint("twitch", self.twitch_hint_label,
                                twitch_hint(self.twitch_format_code),
                                self.twitch_format_code, "Twitch")
        self._sync_preset_buttons()

    def _update_discord_hint(self):
        self._set_platform_hint("discord", self.discord_hint_label,
                                discord_hint(self.discord_format_code),
                                self.discord_format_code, "Discord")
        self._sync_preset_buttons()

    def _update_whatsapp_hint(self):
        self._set_platform_hint("whatsapp", self.whatsapp_hint_label,
                                whatsapp_hint(self.whatsapp_format_code),
                                self.whatsapp_format_code, "WhatsApp")
        self._sync_preset_buttons()

    def _update_square_hints(self):
        for platform in SQUARE_PLATFORMS:
            code = self.square_format_codes[platform.key]
            self._set_platform_hint(platform.key, self.square_hint_labels[platform.key],
                                    square_hint(code), code, platform.title)
        self._sync_preset_buttons()

    def _set_platform_hint(self, platform, label, hint, code, title):
        """Выноска вкладки площадки.

        Пока выбран обычный формат, выноска говорит, что пресет не выбран:
        раньше она описывала пресет, который к файлу не применялся.
        """
        active = code == self._selected_format
        text = hint if active else tr("preset_none_hint", platform=title)
        label.setText(text)
        preview = self.chat_previews.get(platform) if hasattr(self, "chat_previews") else None
        if preview is not None:
            preview.setAccessibleDescription(text)

    def _update_hints(self):
        self._update_telegram_hint()
        self._update_twitch_hint()
        self._update_discord_hint()
        self._update_whatsapp_hint()
        self._update_square_hints()
        self._refresh_previews()

    def _sync_tab_buttons(self, index=None):
        current = self.settings_tabs.currentIndex() if index is None else index
        for position, button in enumerate(self.tab_buttons):
            button.setChecked(position == current)

    def _sync_preset_buttons(self):
        """Подсвечивает кнопку пресета, который выбран сейчас.

        Подсветка привязана к выбранному формату, а не к последней нажатой
        кнопке: иначе после переключения на обычный формат на вкладке
        площадки продолжал гореть пресет, который уже не применяется.
        """
        groups = (
            (self.telegram_preset_buttons, self.telegram_format_code),
            (self.twitch_preset_buttons, self.twitch_format_code),
            (self.discord_preset_buttons, self.discord_format_code),
            (self.whatsapp_preset_buttons, self.whatsapp_format_code),
        ) + tuple((self.square_preset_buttons.get(platform.key, {}),
                   self.square_format_codes.get(platform.key))
                  for platform in SQUARE_PLATFORMS)
        for buttons, active_code in groups:
            for code, button in buttons.items():
                button.setChecked(
                    code == active_code and code == self._selected_format
                )

    def _on_tab_changed(self, _index):
        """Переключение вкладки — только смена вида.

        Настройки к ней больше не привязаны: формат хранится отдельно,
        поэтому заглянуть в «Дополнительно» при выбранном пресете Telegram
        уже не значит потерять этот пресет.
        """
        if not self._ui_ready:
            return
        self._sync_apply_row()
        self._update_enabled_states()
        self._apply_tab_theme(animate=self.isVisible() and not self._rebuilding)

    def _sync_apply_row(self):
        """Кнопки применения — на «Основной», примечание — на площадках."""
        on_main = self.settings_tabs.currentIndex() == TAB_MAIN
        self.apply_stack.setCurrentIndex(0 if on_main else 1)

    def _apply_tab_theme(self, animate=False):
        """Красит панель настроек в цвета площадки открытой вкладки.

        Таблица стилей ставится самой панели, а не приложению: очередь и
        нижняя панель остаются в основной теме, и окно не «прыгает»
        целиком при каждом переключении. Темы меняют только цвета —
        отступы и шрифты у них общие, поэтому вёрстка не сдвигается.
        """
        theme = theme_for_tab(self.settings_tabs.currentIndex())
        if theme == self._current_theme:
            return
        snapshot = self.right_panel.grab() if animate else None
        # Пустая строка — основная тема: панель берёт стили приложения.
        self.right_panel.setStyleSheet(
            "" if theme == THEME_MAIN else build_stylesheet(theme)
        )
        colors = palette(theme)
        for toggle in self.right_panel.findChildren(ToggleSwitch):
            toggle.set_palette(colors)
        self._current_theme = theme
        if snapshot is not None and not snapshot.isNull():
            self._fade_out_snapshot(snapshot)

    def _fade_out_snapshot(self, snapshot):
        """Плавный переход: снимок панели в прежних цветах тает поверх новой.

        QSS не умеет анимировать цвета, а пересобирать таблицу стилей на
        каждом кадре дорого. Снимок с прозрачностью — дёшево и гладко.
        """
        cover = QLabel(self.right_panel)
        cover.setPixmap(snapshot)
        cover.setGeometry(self.right_panel.rect())
        # Клики проходят сквозь снимок: переход не должен мешать работе.
        cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        effect = QGraphicsOpacityEffect(cover)
        effect.setOpacity(1.0)
        cover.setGraphicsEffect(effect)
        cover.show()
        cover.raise_()
        animation = QPropertyAnimation(effect, b"opacity", cover)
        animation.setDuration(THEME_FADE_MS)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(cover.deleteLater)
        animation.start()

    def _is_platform_format(self, output_format=None):
        fmt = output_format or self._selected_format
        return (is_telegram_format(fmt) or is_twitch_format(fmt)
                or is_discord_format(fmt) or is_whatsapp_format(fmt)
                or is_square_platform_format(fmt))

    def _load_settings_into_panel(self, settings):
        self._loading_settings = True
        try:
            # Вкладку здесь не переключаем: добавление или выбор файла
            # выбрасывало пользователя обратно на «Основную» посреди работы.
            # Формат виден в списке форматов и в подсветке кнопок пресетов.
            output_format = settings.output_format
            self._selected_format = output_format
            if is_telegram_format(output_format):
                self.telegram_format_code = output_format
            elif is_twitch_format(output_format):
                self.twitch_format_code = output_format
            elif is_discord_format(output_format):
                self.discord_format_code = output_format
            elif is_whatsapp_format(output_format):
                self.whatsapp_format_code = output_format
            elif square_platform(output_format):
                self.square_format_codes[square_platform(output_format).key] = output_format
            self._select_format_in_combo(output_format)
            for toggle in self.fill_toggles.values():
                toggle.setChecked(settings.fill_square)
            self.resize_checkbox.setChecked(settings.resize_enabled)
            self.width_spin.setValue(settings.width)
            self.height_spin.setValue(settings.height)
            self.keep_aspect_checkbox.setChecked(settings.keep_aspect)
            self.fps_checkbox.setChecked(settings.fps_enabled)
            self.fps_spin.setValue(settings.fps)
            # Пределы сбрасываем до присвоения: иначе максимум, оставшийся
            # от прошлого файла, урезал бы длительность нового.
            self.tg_start_spin.setMaximum(3600.0)
            self.tg_duration_spin.setMaximum(MAX_VIDEO_DURATION_SEC)
            self.tg_duration_spin.setValue(settings.tg_duration)
            self.tg_start_spin.setValue(settings.tg_start)
            self.trim_checkbox.setChecked(settings.trim_enabled)
            self.trim_start_spin.setMaximum(86400.0)
            self.trim_end_spin.setMaximum(86400.0)
            self.trim_start_spin.setValue(settings.trim_start)
            source = self._selected_source_duration()
            # В настройках хранится длительность, в панели — момент конца.
            duration = settings.trim_duration or min(source or 5.0, 5.0)
            self.trim_end_spin.setValue(settings.trim_start + duration)
            degrees = [value for _caption, value in rotate_options()]
            self.rotate_combo.setCurrentIndex(
                degrees.index(settings.effective_rotate)
                if settings.effective_rotate in degrees else 0
            )
            flags = (settings.flip_horizontal, settings.flip_vertical)
            self.flip_combo.setCurrentIndex(
                next((i for i, (_c, f) in enumerate(flip_options()) if f == flags), 0)
            )
            self.quality_checkbox.setChecked(settings.quality_enabled)
            self.quality_spin.setValue(settings.quality)
            self.target_size_checkbox.setChecked(settings.target_size_enabled)
            if settings.target_size_mb > 0:
                self.target_size_spin.setValue(settings.target_size_mb)
            self.audio_combo.setCurrentIndex(1 if settings.drops_audio else 0)
            if settings.audio_bitrate in AUDIO_BITRATES:
                self.audio_bitrate_combo.setCurrentIndex(
                    AUDIO_BITRATES.index(settings.audio_bitrate)
                )
        finally:
            self._loading_settings = False
        self._update_enabled_states()
        self._autofill_tg_duration(settings)
        self._clamp_tg_duration()
        self._update_hints()

    def _current_panel_settings(self):
        """Настройки по состоянию всех вкладок сразу.

        Формат берётся из _selected_format, а не из активной вкладки:
        правки на соседней вкладке не должны сбрасывать выбранный пресет.
        """
        fmt = self._selected_format
        degrees = [value for _caption, value in rotate_options()]
        flip_h, flip_v = flip_options()[self.flip_combo.currentIndex()][1]
        settings = JobSettings(
            output_format=fmt,
            resize_enabled=self.resize_checkbox.isChecked(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            keep_aspect=self.keep_aspect_checkbox.isChecked(),
            fps_enabled=self.fps_checkbox.isChecked(),
            fps=self.fps_spin.value(),
            tg_duration=self.tg_duration_spin.value(),
            tg_start=self.tg_start_spin.value(),
            trim_enabled=self.trim_checkbox.isChecked(),
            trim_start=self.trim_start_spin.value(),
            # FFmpeg берёт длительность, а не момент конца.
            trim_duration=max(0.1, self.trim_end_spin.value()
                              - self.trim_start_spin.value()),
            rotate=degrees[self.rotate_combo.currentIndex()],
            flip_horizontal=flip_h,
            flip_vertical=flip_v,
            quality_enabled=self.quality_checkbox.isChecked(),
            quality=self.quality_spin.value(),
            target_size_enabled=self.target_size_checkbox.isChecked(),
            target_size_mb=self.target_size_spin.value(),
            audio_mode=AUDIO_NONE if self.audio_combo.currentIndex() == 1 else AUDIO_KEEP,
            audio_bitrate=AUDIO_BITRATES[self.audio_bitrate_combo.currentIndex()],
            fill_square=self._fill_square_checked(),
        )
        if self._is_platform_format(fmt):
            # Размер и частота кадров у пресетов заданы спецификацией
            # площадки — значения с «Основной» к ним не применяются.
            settings = settings.copy(
                resize_enabled=False,
                fps_enabled=is_telegram_video_format(fmt),
                fps=30 if is_telegram_video_format(fmt) else settings.fps,
                quality_enabled=False,
                target_size_enabled=False,
            )
        return settings

    def _store_panel_settings(self, items):
        panel = self._current_panel_settings()
        for item in items:
            entry = self._entry(item)
            entry.settings = panel.copy()
            item.setData(DATA_ROLE, entry)
            self._refresh_item_text(item)
        return len(items)

    def _preset_targets(self):
        return self.file_list.selectedItems() or [
            self.file_list.item(i) for i in range(self.file_list.count())
        ]

    def _report_preset_applied(self, count):
        """Короткая обратная связь: пресет применяется молча, и без неё
        непонятно, затронул ли он что-нибудь."""
        if not count:
            self._set_status(tr("preset_applied_none"), transient=True)
            return
        selected = bool(self.file_list.selectedItems())
        key = "preset_applied_selected" if selected else "preset_applied_all"
        self._set_status(tr(key, count=count), transient=True)

    def _set_status(self, text, transient=False):
        """Строка состояния внизу. Временное сообщение (о применённом
        пресете) снимается при смене выделения, а итог обработки — нет."""
        # Запоминается сам текст: если строку с тех пор переписал кто-то
        # другой (ход обработки, итог), снимать её при смене выделения нельзя.
        self._transient_status = text if transient else None
        self.current_file_label.setText(text)

    def _apply_telegram_preset(self, format_code):
        self._set_selected_format(format_code)
        self._report_preset_applied(self._store_panel_settings(self._preset_targets()))

    def _apply_twitch_preset(self, format_code):
        self._set_selected_format(format_code)
        self._report_preset_applied(self._store_panel_settings(self._preset_targets()))

    def _apply_discord_preset(self, format_code):
        self._set_selected_format(format_code)
        self._report_preset_applied(self._store_panel_settings(self._preset_targets()))

    def _apply_whatsapp_preset(self, format_code):
        self._set_selected_format(format_code)
        self._report_preset_applied(self._store_panel_settings(self._preset_targets()))

    def _apply_square_preset(self, format_code):
        self._set_selected_format(format_code)
        self._report_preset_applied(self._store_panel_settings(self._preset_targets()))

    def _fill_square_checked(self):
        toggle = next(iter(self.fill_toggles.values()), None)
        return bool(toggle and toggle.isChecked())

    def _on_fill_toggled(self, checked):
        """Тумблер «заполнить квадрат» один на все вкладки площадок.

        Значение общее — это свойство файла, а не вкладки, — поэтому
        соседние тумблеры повторяют нажатый.
        """
        for toggle in self.fill_toggles.values():
            if toggle.isChecked() != checked:
                toggle.blockSignals(True)
                toggle.setChecked(checked)
                toggle.blockSignals(False)
        self._refresh_previews()
        self._on_settings_changed()

    def _on_format_combo_changed(self):
        """Формат выбран списком. Пресеты площадок в нём тоже есть."""
        if self._loading_settings:
            return
        code = self.format_combo.currentData(DATA_ROLE)
        if code is None:
            return
        self._set_selected_format(code)
        self._on_settings_changed()

    def _set_selected_format(self, code):
        """Общая точка смены формата: и для списка, и для кнопок пресетов."""
        self._selected_format = code
        if is_telegram_format(code):
            self.telegram_format_code = code
        elif is_twitch_format(code):
            self.twitch_format_code = code
        elif is_discord_format(code):
            self.discord_format_code = code
        elif is_whatsapp_format(code):
            self.whatsapp_format_code = code
        elif square_platform(code):
            self.square_format_codes[square_platform(code).key] = code
        was_loading = self._loading_settings
        self._loading_settings = True
        try:
            self._select_format_in_combo(code)
        finally:
            self._loading_settings = was_loading
        self._update_enabled_states()
        self._update_hints()

    def _on_settings_changed(self):
        # Поворот и отражение видны в предпросмотре сразу, ещё до записи
        # настроек в очередь.
        if not self._loading_settings:
            self._refresh_previews()
        if self._loading_settings or len(self.file_list.selectedItems()) != 1:
            return
        self._store_panel_settings(self.file_list.selectedItems())

    def _on_resize_toggle(self):
        self._update_enabled_states()
        self._on_settings_changed()

    def _on_trim_toggle(self):
        self._update_enabled_states()
        self._on_settings_changed()

    def _on_trim_changed(self):
        self._clamp_trim_range()
        self._on_settings_changed()

    def _on_quality_toggle(self):
        # Качество и целевой размер спорят друг с другом: размером управляет
        # битрейт, и заданное качество к нему уже не применяется.
        if self.quality_checkbox.isChecked() and self.target_size_checkbox.isChecked():
            self.target_size_checkbox.setChecked(False)
        self._update_enabled_states()
        self._on_settings_changed()

    def _on_target_size_toggle(self):
        if self.target_size_checkbox.isChecked() and self.quality_checkbox.isChecked():
            self.quality_checkbox.setChecked(False)
        self._update_enabled_states()
        self._on_settings_changed()

    def _on_audio_changed(self):
        self._update_enabled_states()
        self._on_settings_changed()

    def _clamp_trim_range(self):
        """Держит конец фрагмента позже начала и в пределах файла."""
        source = self._selected_source_duration()
        was_loading = self._loading_settings
        self._loading_settings = True
        try:
            start = self.trim_start_spin.value()
            if source:
                self.trim_start_spin.setMaximum(max(0.0, source - 0.1))
                start = min(start, self.trim_start_spin.maximum())
                self.trim_end_spin.setMaximum(source)
            else:
                self.trim_end_spin.setMaximum(86400.0)
            # Конец всегда позже начала: иначе получился бы пустой фрагмент.
            self.trim_end_spin.setMinimum(start + 0.1)
            if self.trim_end_spin.value() < start + 0.1:
                self.trim_end_spin.setValue(min(self.trim_end_spin.maximum(),
                                                start + 0.1))
        finally:
            self._loading_settings = was_loading

    def _on_fps_toggle(self):
        self._update_enabled_states()
        self._on_settings_changed()

    def _update_enabled_states(self):
        """Гасит поля, которые при выбранном формате ни на что не влияют.

        Доступность зависит от самого формата, а не от открытой вкладки:
        пресет площадки диктует размер, частоту кадров и вес, а кадрирование
        с поворотом применяются поверх него и остаются доступными.
        """
        platform = self._is_platform_format()
        audio_only = self._selected_format in AUDIO_FORMAT_CODES
        has_picture = not audio_only

        # Размер и пропорции: у пресетов площадок они продиктованы спецификацией.
        resize = has_picture and not platform and self.resize_checkbox.isChecked()
        self.resize_checkbox.setEnabled(has_picture and not platform)
        self.width_spin.setEnabled(resize)
        self.height_spin.setEnabled(resize)
        self.width_label.setEnabled(resize)
        self.height_label.setEnabled(resize)
        self.keep_aspect_checkbox.setEnabled(resize)

        # Частота кадров: у Twitch и Discord её подбирает сам обработчик
        # под лимит веса, поэтому вручную она не задаётся.
        self.fps_checkbox.setEnabled(has_picture and not platform)
        self.fps_spin.setEnabled(
            has_picture and not platform and self.fps_checkbox.isChecked()
        )

        # Обрезка по времени: у Telegram для этого своя пара полей на его
        # вкладке. Звуковым форматам она тоже доступна — extract_audio
        # принимает trim, а поле было заперто, и обещанная в описании
        # обрезка звука до кода просто не доходила.
        trim_allowed = not is_telegram_format(self._selected_format)
        self.trim_checkbox.setEnabled(trim_allowed)
        trim_on = trim_allowed and self.trim_checkbox.isChecked()
        for widget in (self.trim_start_label, self.trim_start_spin,
                       self.trim_end_label, self.trim_end_spin):
            widget.setEnabled(trim_on)

        # Поворот и отражение применяются и поверх пресетов площадок.
        self.rotate_label.setEnabled(has_picture)
        self.rotate_combo.setEnabled(has_picture)
        self.flip_label.setEnabled(has_picture)
        self.flip_combo.setEnabled(has_picture)

        # Качество и целевой размер: у площадок вес диктует лимит, а у
        # остальных форматов оба поля работают только там, где есть чему
        # подчиняться — качество кодека или битрейт (см. TUNABLE_FORMATS).
        tunable = not platform and self._selected_format in TUNABLE_FORMATS
        self.quality_checkbox.setEnabled(tunable)
        self.quality_spin.setEnabled(tunable and self.quality_checkbox.isChecked())
        self.target_size_checkbox.setEnabled(tunable)
        self.target_size_spin.setEnabled(
            tunable and self.target_size_checkbox.isChecked()
        )

        # Звук есть только у видео и у самих звуковых форматов.
        audio_allowed = self._selected_format in VIDEO_FORMAT_CODES or audio_only
        self.audio_label.setEnabled(audio_allowed)
        self.audio_combo.setEnabled(audio_allowed and not audio_only)
        keeps_audio = audio_only or self.audio_combo.currentIndex() == 0
        self.audio_bitrate_label.setEnabled(audio_allowed and keeps_audio)
        self.audio_bitrate_combo.setEnabled(audio_allowed and keeps_audio)


    def _set_settings_enabled(self, has_selection):
        """Панель настроек остаётся доступной всегда, чтобы можно было
        изучить вкладки и параметры до добавления файлов. Блокируются
        только действия, которым нужен выбранный файл."""
        self.tg_duration_spin.setEnabled(is_telegram_video_format(self.telegram_format_code))
        self.apply_selected_button.setEnabled(has_selection)
        self.apply_all_button.setEnabled(self.file_list.count() > 0)
        self.apply_selected_button.setToolTip(
            tr("apply_selected_tip") if has_selection else tr("apply_selected_off")
        )
        self.apply_all_button.setToolTip(
            tr("apply_all_tip") if self.file_list.count() else tr("apply_all_off")
        )
        self._update_enabled_states()

    def _apply_to_selected(self):
        selected = self.file_list.selectedItems()
        if not selected:
            QMessageBox.information(self, tr("dlg_no_selection_title"), tr("dlg_no_selection_text"))
            return
        self._store_panel_settings(selected)

    def _apply_to_all(self):
        if not self.file_list.count():
            QMessageBox.information(self, tr("dlg_empty_list_title"), tr("dlg_empty_list_text"))
            return
        self._store_panel_settings([self.file_list.item(i) for i in range(self.file_list.count())])

    def _on_browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, tr("dlg_choose_output"), self.output_dir)
        if directory:
            self.output_dir = directory
            self.output_dir_edit.setText(directory)
            self.settings_store.setValue("output_dir", directory)

    def _on_start_clicked(self):
        if self.file_list.count() == 0:
            QMessageBox.information(self, tr("dlg_empty_queue_title"), tr("dlg_empty_queue_text"))
            return
        if not os.path.isdir(self.output_dir):
            QMessageBox.warning(self, tr("dlg_bad_dir_title"),
                                tr("dlg_bad_dir_text", path=self.output_dir))
            return
        if not self._output_dir_writable():
            QMessageBox.warning(
                self,
                tr("dlg_no_access_title"),
                tr("dlg_no_access_text", path=self.output_dir),
            )
            return

        # Обрабатываются только отмеченные галочкой файлы.
        rows = self._checked_rows()
        if not rows:
            QMessageBox.information(
                self,
                tr("dlg_nothing_checked_title"),
                tr("dlg_nothing_checked_text"),
            )
            return

        overwrite = self.overwrite_checkbox.isChecked()
        jobs = []
        self._job_rows = rows
        for row in rows:
            item = self.file_list.item(row)
            entry = self._entry(item)
            jobs.append(entry.to_job(self.output_dir, overwrite))
            entry.status = STATUS_PENDING
            entry.progress = 0
            entry.message = ""
            item.setData(DATA_ROLE, entry)
            self._refresh_item_text(item)

        if not self._confirm_frame_extraction(jobs):
            return
        if not self._confirm_twitch_animation_length(jobs):
            return

        self.settings_store.setValue("overwrite", overwrite)
        self._run_started_at = time.monotonic()
        self._last_output_dir = self.output_dir
        self._set_ui_running(True)
        self._set_progress_determinate(True)
        self.overall_progress_bar.setValue(0)
        self.current_file_label.setText(tr("preparing"))

        # Родитель обязателен: all_finished приходит из ещё работающего
        # потока, и окно снимает свою ссылку до того, как run() вернётся.
        # Без владельца объект QThread уничтожался бы на живом потоке.
        self.worker = ConversionWorker(jobs, self)
        # Удаление — только после настоящего конца потока, иначе воркеры
        # копились бы у окна от запуска к запуску.
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.file_started.connect(self._on_file_started)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.file_finished.connect(self._on_file_finished)
        self.worker.file_cancelled.connect(self._on_file_cancelled)
        self.worker.all_finished.connect(self._on_all_finished)
        self.worker.start()

    def _confirm_frame_extraction(self, jobs):
        """Предупреждает, если извлечение кадров создаст очень много файлов."""
        if self._ffmpeg_probe is None:
            return True
        total = 0
        for job in jobs:
            if job.output_format != "frames":
                continue
            # Обрезку учитываем: без неё предупреждение считало кадры по всей
            # длине файла, хотя брать из него собирались пару секунд.
            estimated = self._ffmpeg_probe.estimate_frame_count(
                job.input_path, job.settings.effective_fps,
                job.settings.effective_trim,
            )
            if estimated:
                total += estimated
        if total <= FRAME_COUNT_WARNING_THRESHOLD:
            return True
        return self._confirm(tr("dlg_many_frames_title"),
                             tr("dlg_many_frames_text", count=total),
                             tr("btn_create_frames"))

    def _confirm_twitch_animation_length(self, jobs):
        """Предупреждает, если анимированный смайлик Twitch выйдет рваным.

        У Twitch не больше 60 кадров на всю анимацию. Из длинного ролика
        подбор частоты кадров честно укладывался в лимит, опускаясь до
        двух-трёх кадров в секунду, — и обработка рапортовала «Готово»
        о смайлике, который больше похож на слайд-шоу.
        """
        long_files = []
        for job in jobs:
            if not is_twitch_animated_format(job.output_format):
                continue
            duration = self._job_duration(job)
            if duration and twitch_effective_fps(duration) < TWITCH_MIN_SMOOTH_FPS:
                long_files.append(
                    f"{os.path.basename(job.input_path)} — {self._format_duration(duration)}"
                )
        if not long_files:
            return True
        return self._confirm(
            tr("dlg_twitch_long_title"),
            tr("dlg_twitch_long_text", files="\n".join(long_files[:10]),
               seconds=number(twitch_smooth_duration_limit())),
            tr("btn_continue_anyway"))

    def _job_duration(self, job):
        """Сколько секунд исходника пойдёт в работу с учётом обрезки."""
        duration = self._duration_of(job.input_path)
        if duration is None and self._ffmpeg_probe is not None \
                and os.path.splitext(job.input_path)[1].lower() in VIDEO_EXTS | {".gif"}:
            duration = self._ffmpeg_probe.get_duration(job.input_path)
        trim = job.settings.effective_trim
        if duration and trim:
            start, length = trim
            duration = max(0.0, duration - start)
            if length:
                duration = min(duration, length)
        return duration

    def _set_progress_determinate(self, determinate):
        """Переключает полосу между процентами и «бегущим» режимом."""
        if determinate:
            self.overall_progress_bar.setRange(0, 100)
        else:
            self.overall_progress_bar.setRange(0, 0)

    def _on_stop_clicked(self):
        if self.worker is not None:
            self.worker.request_stop()
            self.current_file_label.setText(tr("stopping"))

    def _set_ui_running(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.start_button.setToolTip(
            tr("start_running") if running else tr("start_tip")
        )
        self.stop_button.setToolTip(
            tr("stop_tip") if running else tr("stop_off")
        )
        self.file_list.setEnabled(not running)
        # Пересобирать окно посреди обработки нельзя, поэтому
        # переключатель языка на это время запирается.
        self.language_combo.setEnabled(not running)
        self.overall_progress_bar.setVisible(running)

    def _item_for_job(self, index):
        if 0 <= index < len(self._job_rows):
            return self.file_list.item(self._job_rows[index])
        return None

    def _on_file_started(self, index):
        item = self._item_for_job(index)
        if item is None:
            return
        entry = self._entry(item)
        entry.status = STATUS_PROCESSING
        entry.progress = 0
        item.setData(DATA_ROLE, entry)
        self._refresh_item_text(item)
        self._update_running_label()

    def _update_running_label(self):
        """При параллельной обработке «файл N из M» врёт, поэтому считаем
        реально выполняющиеся и уже завершённые."""
        rows = self._job_rows or list(range(self.file_list.count()))
        running = []
        finished = 0
        for row in rows:
            entry = self._entry(self.file_list.item(row))
            if entry.status == STATUS_PROCESSING:
                running.append(os.path.basename(entry.input_path))
            elif entry.status in FINISHED_STATUSES:
                finished += 1
        total = len(rows)
        if not running:
            return
        if len(running) == 1:
            current = tr("progress_current", name=running[0])
        else:
            current = tr("progress_parallel", count=len(running),
                         files=plural("word_files", len(running)))
        parts = [tr("progress_done_of", done=finished, total=total), current]
        remaining = self._estimate_remaining(finished, total)
        if remaining:
            parts.append(tr("progress_left", time=remaining))
        self.current_file_label.setText("   ·   ".join(parts))

    def _estimate_remaining(self, finished, total):
        """Оценка оставшегося времени по среднему на уже готовые файлы."""
        if not self._run_started_at or finished <= 0 or finished >= total:
            return ""
        elapsed = time.monotonic() - self._run_started_at
        seconds = elapsed / finished * (total - finished)
        return self._format_duration(seconds)

    @staticmethod
    def _format_duration(seconds):
        seconds = max(0.0, float(seconds))
        if seconds < 10:
            # Короткие ролики и эмодзи: без дробной части «0.75 сек» стало бы «0 сек».
            return tr("sec", value=number(round(seconds, 1)))
        seconds = int(seconds)
        if seconds < 60:
            return tr("sec", value=seconds)
        minutes, rest = divmod(seconds, 60)
        if minutes < 60:
            return (tr("min_sec", minutes=minutes, seconds=rest) if rest
                    else tr("min", value=minutes))
        hours, minutes = divmod(minutes, 60)
        return tr("hour_min", hours=hours, minutes=minutes)

    def _on_progress_updated(self, index, percent):
        item = self._item_for_job(index)
        if item is None:
            return
        if percent == INDETERMINATE_PROGRESS:
            # Длительность файла неизвестна — показываем «бегущую» полосу.
            self._set_progress_determinate(False)
            return
        self._set_progress_determinate(True)
        entry = self._entry(item)
        entry.progress = percent
        item.setData(DATA_ROLE, entry)
        self._refresh_item_text(item)
        self._refresh_overall_progress()

    def _refresh_overall_progress(self):
        """Средний прогресс по обрабатываемым файлам — при параллельной
        обработке порядковый номер файла не отражает общий ход."""
        rows = self._job_rows or list(range(self.file_list.count()))
        total = len(rows)
        if not total:
            return
        accumulated = 0
        for row in rows:
            entry = self._entry(self.file_list.item(row))
            if entry.status in FINISHED_STATUSES:
                accumulated += 100
            else:
                accumulated += entry.progress
        self.overall_progress_bar.setValue(int(accumulated / total))

    def _on_file_finished(self, index, success, message):
        item = self._item_for_job(index)
        if item is None:
            return
        entry = self._entry(item)
        entry.status = STATUS_DONE if success else STATUS_ERROR
        entry.progress = 100 if success else entry.progress
        entry.message = "" if success else message
        item.setData(DATA_ROLE, entry)
        self._refresh_item_text(item)
        self._refresh_overall_progress()
        self._update_running_label()

    def _on_file_cancelled(self, index):
        """Прерванный файл получает своё состояние.

        Раньше обработчик отмены не сообщал об этом окну, и строка навсегда
        оставалась в состоянии «Обработка» с зависшим процентом.
        """
        item = self._item_for_job(index)
        if item is None:
            return
        entry = self._entry(item)
        entry.status = STATUS_STOPPED
        entry.message = ""
        item.setData(DATA_ROLE, entry)
        self._refresh_item_text(item)
        self._refresh_overall_progress()

    def _on_all_finished(self, stopped):
        self._set_ui_running(False)
        self._set_progress_determinate(True)
        if self.worker is not None:
            self._last_report = list(self.worker.report)
        self.report_button.setVisible(bool(self._last_report))
        self.report_button.setEnabled(bool(self._last_report))

        rows = self._job_rows or list(range(self.file_list.count()))
        statuses = [self._entry(self.file_list.item(row)).status for row in rows]
        done = statuses.count(STATUS_DONE)
        failed = statuses.count(STATUS_ERROR)
        cancelled = statuses.count(STATUS_STOPPED)
        total = max(1, len(statuses))
        self.overall_progress_bar.setValue(int(done * 100 / total))

        elapsed = ""
        if self._run_started_at:
            elapsed = "   ·   " + tr(
                "summary_elapsed",
                time=self._format_duration(time.monotonic() - self._run_started_at))
        prefix = tr("summary_stopped") if stopped else tr("summary_done")
        summary = prefix + " — " + tr("summary_counts", done=done, failed=failed)
        if cancelled:
            summary += tr("summary_cancelled", count=cancelled)
        summary += elapsed
        self.current_file_label.setText(summary)

        self.open_folder_button.setVisible(done > 0)
        self._notify_finished(summary, done > 0)
        self._run_started_at = None
        self.worker = None

    def _notify_finished(self, summary, success):
        """Подсказка, когда окно свёрнуто или не в фокусе: длинная пачка
        видео обрабатывается долго, и за ней никто не сидит."""
        if self.isActiveWindow():
            return
        QApplication.alert(self, 3000)
        icon = self.windowIcon()
        if icon.isNull() or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        try:
            if self._tray_icon is None:
                self._tray_icon = QSystemTrayIcon(icon, self)
                self._tray_icon.activated.connect(lambda _reason: self._raise_window())
            self._tray_icon.show()
            self._tray_icon.showMessage(
                APP_NAME,
                summary,
                QSystemTrayIcon.MessageIcon.Information if success
                else QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
            # Значок нужен только на время всплывающего сообщения.
            QTimer.singleShot(8000, self._hide_tray_icon)
        except Exception:
            _log.debug("Не удалось показать уведомление", exc_info=True)

    def _hide_tray_icon(self):
        if self._tray_icon is not None:
            self._tray_icon.hide()

    def _raise_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _output_dir_writable(self):
        """Проверяем запись заранее: иначе ошибка вылезет на каждом файле."""
        probe = os.path.join(self.output_dir, ".mcs_write_test")
        try:
            with open(probe, "w", encoding="utf-8"):
                pass
            os.remove(probe)
            return True
        except OSError:
            return False

    def _on_version_menu(self, position, anchor=None):
        """То же меню по правому щелчку на ссылке обновления."""
        menu = PopupMenu(self)
        self._fill_version_menu(menu)
        menu.exec((anchor or self.version_button).mapToGlobal(position))

    def _fill_version_menu(self, menu):
        """Пункты меню версии — заново при каждом открытии: галочки и пункт
        о новой версии зависят от того, что происходило с прошлого раза."""
        menu.clear()
        title = QAction(f"{APP_NAME} {version_string()}", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()

        updates = QAction(tr("update_check_toggle"), menu)
        updates.setCheckable(True)
        updates.setChecked(self.settings_store.value("check_updates", True, type=bool))
        updates.toggled.connect(
            lambda checked: self.settings_store.setValue("check_updates", checked))
        menu.addAction(updates)

        animation = QAction(tr("menu_animate_media"), menu)
        animation.setToolTip(tr("menu_animate_media_tip"))
        animation.setCheckable(True)
        animation.setChecked(self._animate_media)
        animation.toggled.connect(self._set_media_animation)
        menu.addAction(animation)
        menu.addSeparator()

        if self._update_url:
            # Обновление ставится щелчком по ссылке; прочитать, что нового,
            # можно отсюда — не скачивая.
            page_action = QAction(tr("menu_release_page"), menu)
            page_action.triggered.connect(self._open_update_page)
            menu.addAction(page_action)
        log_action = QAction(tr("menu_open_log"), menu)
        log_action.triggered.connect(self._open_log_folder)
        menu.addAction(log_action)

    def _start_update_check(self):
        """При каждом запуске спрашивает GitHub о новой версии — в фоне и молча.

        Раньше проверка шла не чаще раза в сутки, и вышедший выпуск мог
        оставаться незамеченным почти сутки. Запрос один на запуск — до
        лимита GitHub (60 в час без входа) так не дойти.
        """
        if not self.settings_store.value("check_updates", True, type=bool):
            return
        # Пока GitHub отвечает, показываем найденное в прошлый раз: без сети
        # ссылка на новую версию не пропадает.
        known = self.settings_store.value("known_update", "", type=str)
        url = self.settings_store.value("known_update_url", "", type=str)
        if known and url and is_newer(known):
            self._on_update_found(known, url)
        # Время прошлой проверки больше не нужно.
        self.settings_store.remove("last_update_check")
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.update_found.connect(self._on_update_found)
        # Ссылку снимаем до удаления объекта: иначе закрытие окна обратилось
        # бы к уже удалённому потоку, и PyQt уронил бы процесс целиком.
        self._update_worker.finished.connect(self._on_update_worker_finished)
        self._update_worker.finished.connect(self._update_worker.deleteLater)
        self._update_worker.start()

    def _on_update_worker_finished(self):
        self._update_worker = None

    def _on_update_found(self, version, url):
        self._update_url = url
        self.settings_store.setValue("known_update", version)
        self.settings_store.setValue("known_update_url", url)
        self.update_button.setText(tr("update_available", version=version))
        tip = "update_tip_install" if installed_variant() else "update_tip"
        self.update_button.setToolTip(tr(tip, current=version_string(), version=version))
        self.update_button.setVisible(True)
        self.version_button.setVisible(False)

    def _open_update_page(self):
        QDesktopServices.openUrl(QUrl(self._update_url or RELEASES_URL))

    def _on_update_clicked(self):
        """Обновление в один щелчок: скачать установщик, проверить, поставить.

        Копию из архива и запуск из исходников установщиком не обновить —
        для них щелчок открывает страницу выпуска, как раньше.
        """
        variant = installed_variant()
        if variant is None:
            self._open_update_page()
            return
        if self._update_download is not None:
            return
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, tr("dlg_update_title"), tr("dlg_update_busy"))
            return
        version = self.settings_store.value("known_update", "", type=str)
        if not self._confirm(tr("dlg_update_title"),
                             tr("dlg_update_text", version=version),
                             tr("btn_update_install")):
            return
        self._update_download = UpdateDownloadWorker(variant, self)
        self._update_download.progress.connect(self._show_update_progress)
        self._update_download.downloaded.connect(self._on_update_downloaded)
        self._update_download.failed.connect(self._on_update_failed)
        self._update_download.finished.connect(self._on_update_download_finished)
        self._update_download.finished.connect(self._update_download.deleteLater)
        self._show_update_progress(0)
        self._update_download.start()

    def _show_update_progress(self, percent):
        self._update_percent = percent
        self.update_button.setText(tr("update_downloading", percent=percent))
        self.update_button.setEnabled(False)

    def _on_update_download_finished(self):
        self._update_download = None

    def _restore_update_button(self):
        self._update_percent = 0
        self.update_button.setEnabled(True)
        self._on_update_found(
            self.settings_store.value("known_update", "", type=str), self._update_url
        )

    def _on_update_downloaded(self, path):
        try:
            launch_installer(path)
        except OSError as exc:
            # Например, пользователь отказал в правах администратора.
            self._on_update_failed(exc)
            return
        # Установщик заменит файлы программы — ей пора закрыться.
        self.close()

    def _on_update_failed(self, error):
        self._restore_update_button()
        if self._confirm(tr("dlg_update_failed_title"),
                         tr("dlg_update_failed_text", error=message_text(error)),
                         tr("btn_open_release_page")):
            self._open_update_page()

    def _open_log_folder(self):
        from logging_setup import log_directory

        QDesktopServices.openUrl(QUrl.fromLocalFile(log_directory()))

    def _on_open_output_folder(self):
        directory = self._last_output_dir or self.output_dir
        if not os.path.isdir(directory):
            QMessageBox.information(self, tr("dlg_folder_missing_title"), tr("dlg_folder_missing_text"))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            if not self.worker.wait(5000):
                self.worker.terminate()
                self.worker.wait(1000)
        # Копия видео для предпросмотра делается секундами — её FFmpeg
        # останавливаем, иначе окно не дождалось бы потока и Qt уронил бы
        # процесс, уничтожив работающий поток (0xC0000409). Останавливаем
        # через FFmpeg самого потока: после пересборки окна (смена языка)
        # у окна уже другой объект FFmpeg, и его отмена до процесса не дойдёт.
        for media_worker in (self.findChildren(PreviewFrameWorker)
                             + self.findChildren(QueueMotionWorker)):
            if media_worker.isRunning():
                media_worker.requestInterruption()
                if media_worker.ffmpeg is not None:
                    media_worker.ffmpeg.cancel()
        self._stop_all_queue_movies()
        for background in (self.scan_worker, self._thumb_worker,
                           self._image_thumb_worker, self._queue_info_worker,
                           self._preview_worker, self._update_worker,
                           self._update_download, self._link_worker,
                           self._queue_motion_worker):
            try:
                running = background is not None and background.isRunning()
            except RuntimeError:
                # Объект потока уже удалён Qt: ждать нечего. Исключение из
                # closeEvent PyQt превратил бы в падение всей программы.
                continue
            if running:
                background.requestInterruption()
                background.wait(2000)
        self._hide_tray_icon()
        self.settings_store.setValue("output_dir", self.output_dir)
        self.settings_store.setValue("overwrite", self.overwrite_checkbox.isChecked())
        self._save_window_state()
        event.accept()

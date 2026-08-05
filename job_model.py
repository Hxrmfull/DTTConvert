"""Типизированные структуры очереди конвертации.

Раньше настройки передавались обычными словарями, и опечатка в ключе
всплывала только во время выполнения. Здесь те же данные описаны
через dataclass, поэтому имена полей проверяются на этапе разбора кода.
"""

from dataclasses import dataclass, field, replace

from telegram_utils import MAX_VIDEO_DURATION_SEC

DEFAULT_FPS = 15

# Шкала качества интерфейса: 1 — самый маленький файл, 100 — лучшая картинка.
QUALITY_MIN = 1
QUALITY_MAX = 100
DEFAULT_QUALITY = 75

AUDIO_KEEP = "keep"
AUDIO_NONE = "none"
DEFAULT_AUDIO_BITRATE = 160

ROTATE_VALUES = (0, 90, 180, 270)


@dataclass
class JobSettings:
    """Параметры конвертации одного файла, задаваемые пользователем."""

    output_format: str = "mp4"
    resize_enabled: bool = False
    width: int = 0
    height: int = 0
    keep_aspect: bool = True
    fps_enabled: bool = False
    fps: int = DEFAULT_FPS
    tg_duration: float = MAX_VIDEO_DURATION_SEC
    # С какой секунды исходника брать фрагмент для Telegram-видео.
    tg_start: float = 0.0
    # Обрезка по времени для обычных конвертаций (видео, GIF, кадры).
    trim_enabled: bool = False
    trim_start: float = 0.0
    trim_duration: float = 0.0
    # Поворот по часовой стрелке и отражение.
    rotate: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    # Качество и целевой размер результата.
    quality_enabled: bool = False
    quality: int = DEFAULT_QUALITY
    target_size_enabled: bool = False
    target_size_mb: float = 0.0
    # Звук: оставить как есть или убрать совсем.
    audio_mode: str = AUDIO_KEEP
    audio_bitrate: int = DEFAULT_AUDIO_BITRATE

    @property
    def effective_width(self):
        return self.width if self.resize_enabled else 0

    @property
    def effective_height(self):
        return self.height if self.resize_enabled else 0

    @property
    def effective_fps(self):
        return self.fps if self.fps_enabled else None

    @property
    def effective_trim(self):
        """(начало, длительность) или None, если обрезка выключена."""
        if not self.trim_enabled:
            return None
        return (max(0.0, self.trim_start), max(0.0, self.trim_duration))

    @property
    def effective_rotate(self):
        value = int(self.rotate) % 360
        return value if value in ROTATE_VALUES else 0

    @property
    def has_transform(self):
        """Есть ли правки геометрии — поворот или отражение."""
        return bool(
            self.effective_rotate or self.flip_horizontal or self.flip_vertical
        )

    @property
    def effective_quality(self):
        """Качество 1..100 или None, если пользователь его не задавал."""
        if not self.quality_enabled:
            return None
        return max(QUALITY_MIN, min(QUALITY_MAX, int(self.quality)))

    @property
    def effective_target_bytes(self):
        """Целевой размер файла в байтах или None."""
        if not self.target_size_enabled or self.target_size_mb <= 0:
            return None
        return int(float(self.target_size_mb) * 1024 * 1024)

    @property
    def drops_audio(self):
        return self.audio_mode == AUDIO_NONE

    def copy(self, **changes):
        return replace(self, **changes)


@dataclass
class ConversionJob:
    """Одна задача для обработчика: что, куда и с какими параметрами."""

    input_path: str
    output_dir: str
    settings: JobSettings = field(default_factory=JobSettings)
    overwrite: bool = False
    output_base_name: str = ""
    # Путь к файлу, который выбрал пользователь. Отличается от input_path,
    # когда задача идёт через временный промежуточный файл: результат нельзя
    # писать поверх настоящего исходника, а input_path к этому моменту
    # указывает уже на временную копию.
    source_path: str = ""

    @property
    def output_format(self):
        return self.settings.output_format.lower()

    @property
    def protect_path(self):
        """Файл, который обработчик не имеет права перезаписать."""
        return self.source_path or self.input_path

    def copy(self, **changes):
        return replace(self, **changes)

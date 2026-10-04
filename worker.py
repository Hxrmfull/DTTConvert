import os
import tempfile
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QThread, pyqtSignal

from ffmpeg_utils import (
    ConversionCancelled,
    FFmpegProcessor,
    Transform,
    scaled_progress,
)
from PIL import Image

from discord_utils import (
    DISCORD_ALL_FORMATS,
    MAX_ANIMATION_FPS as DISCORD_MAX_FPS,
    MAX_STICKER_DURATION_SEC,
    discord_byte_limit,
    discord_extension,
    discord_size,
    discord_suffix,
    is_discord_animated_format,
    is_discord_format,
)
from errors import (
    LocalizedFileNotFoundError,
    LocalizedRuntimeError,
    LocalizedValueError,
    as_message,
)
from format_names import FormatLabel
from image_utils import ImageProcessor
from telegram_utils import (
    TG_ALL_FORMATS,
    is_telegram_emoji_format,
    is_telegram_video_format,
    static_image_extension,
)
from twitch_utils import (
    KIND_AUTO_WEBP,
    KIND_GIF,
    KIND_STATIC,
    is_twitch_animated_format,
    is_twitch_auto_format,
    is_twitch_format,
    twitch_preset,
)
from stream_platforms import is_square_platform_format, square_preset
from whatsapp_utils import (
    MAX_ANIMATION_FPS as WHATSAPP_MAX_FPS,
    MAX_ANIMATION_SEC as WHATSAPP_MAX_SEC,
    WHATSAPP_ALL_FORMATS,
    is_whatsapp_animated_format,
    is_whatsapp_format,
    whatsapp_byte_limit,
    whatsapp_extension,
    whatsapp_size,
    whatsapp_suffix,
)

IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp", "avif"}
VIDEO_FORMATS = {"mp4", "webm", "avi"}
AUDIO_FORMATS = {"mp3", "m4a", "wav"}
# Анимация одним файлом: GIF и APNG. У APNG полная прозрачность
# и все цвета, но и вес заметно больше.
ANIMATION_FORMATS = {"gif", "apng"}
FRAMES_FORMAT = {"frames"}
TELEGRAM_FORMATS = TG_ALL_FORMATS
DISCORD_FORMATS = DISCORD_ALL_FORMATS
WHATSAPP_FORMATS = WHATSAPP_ALL_FORMATS

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".apng", ".webp", ".bmp", ".avif",
              ".heic", ".heif", ".tif", ".tiff"}
# Видео на входе: FFmpeg читает все эти контейнеры. .mov пишут iPhone и
# заодно им пользуется сама программа как промежуточным файлом без потерь
# (см. _process_animated_image_job), .mkv — запись OBS.
VIDEO_EXTS = {".mp4", ".webm", ".avi", ".mov", ".mkv", ".m4v", ".wmv",
              ".flv", ".mpg", ".mpeg", ".3gp", ".ogv"}
GIF_EXT = ".gif"
ANIMATED_WEBP_EXT = ".awebp"
# Анимированный стикер Telegram (Lottie) — кадры рисует rlottie.
TGS_EXT = ".tgs"
# Форматы, которые бывают и статичными, и анимированными: тип определяется
# по содержимому файла, а не по расширению.
ANIMATABLE_IMAGE_EXTS = {".webp", ".png", ".apng", ".avif"}

# Форматы, которые обрабатываются целиком в Python и хорошо параллелятся.
LIGHTWEIGHT_FORMATS = IMAGE_FORMATS

# Сколько ответов «анимация или нет» держим про запас.
ANIMATION_CACHE_LIMIT = 512

_log = logging.getLogger(__name__)

_path_lock = threading.Lock()
_animation_lock = threading.Lock()
_animation_cache = OrderedDict()
_reserved_paths = set()


def is_animated_image(path):
    """Определяет анимацию по содержимому файла, а не по расширению.

    Анимированные WebP (эмодзи с 7TV и т.п.) и APNG сохраняются
    с обычными расширениями .webp и .png. Раньше программа считала их
    статичными картинками и отказывалась делать из них видео-стикеры.
    """
    try:
        key = (os.path.normcase(os.path.abspath(path)), os.path.getmtime(path),
               os.path.getsize(path))
    except OSError:
        return False
    with _animation_lock:
        cached = _animation_cache.get(key)
    if cached is not None:
        return cached

    animated = False
    try:
        with Image.open(path) as image:
            animated = getattr(image, "n_frames", 1) > 1
    except Exception:
        _log.debug("Не удалось прочитать %s для проверки анимации", path, exc_info=True)

    with _animation_lock:
        # Кэш нужен, чтобы список файлов не перечитывал их при каждой отрисовке.
        # Лишнее выбрасываем по одному, начиная со старого: полная очистка на
        # очереди длиннее лимита сбрасывала кэш почти на каждом обращении,
        # и файлы открывались заново при каждой отрисовке строки.
        while len(_animation_cache) >= ANIMATION_CACHE_LIMIT:
            _animation_cache.popitem(last=False)
        _animation_cache[key] = animated
    return animated


def get_category(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == GIF_EXT:
        return "gif"
    if ext in (ANIMATED_WEBP_EXT, TGS_EXT):
        return "animated_image"
    if ext in ANIMATABLE_IMAGE_EXTS and is_animated_image(path):
        return "animated_image"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "unknown"


def transform_for(settings):
    """Поворот и отражение из настроек или None, если их не задавали.

    Применяются в том числе поверх пресетов площадок: пресет отвечает за
    размер и лимиты, поворот — за ориентацию кадра.
    """
    if not settings.has_transform:
        return None
    return Transform(
        rotate=settings.effective_rotate,
        flip_horizontal=settings.flip_horizontal,
        flip_vertical=settings.flip_vertical,
    )


def is_static_target(output_format):
    """Даёт ли выбранный формат неподвижную картинку."""
    fmt = output_format.lower()
    if fmt in IMAGE_FORMATS:
        return True
    if fmt in TELEGRAM_FORMATS:
        return not is_telegram_video_format(fmt)
    if is_twitch_format(fmt):
        # 7TV анимирует то, что анимировано в исходнике, поэтому
        # анимированной картинке нужна вся анимация, а не один кадр.
        return not (is_twitch_animated_format(fmt) or is_twitch_auto_format(fmt))
    if is_discord_format(fmt):
        return not is_discord_animated_format(fmt)
    if is_whatsapp_format(fmt):
        return not is_whatsapp_animated_format(fmt)
    if is_square_platform_format(fmt):
        return square_preset(fmt).kind == KIND_STATIC
    return False


def _same_file(first, second):
    """Сравнение путей с учётом регистра и разных форм записи (Windows)."""
    try:
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(
            os.path.abspath(second)
        )
    except (OSError, ValueError):
        return False


def resolve_output_path(output_dir, base_name, extension, overwrite=False,
                        protect_path=None):
    """Путь для результата: перезапись или уникальное имя с суффиксом _1, _2...

    Имя резервируется под блокировкой, иначе при параллельной обработке два
    потока могут выбрать один и тот же путь и перезаписать чужой результат.

    protect_path — исходный файл задачи. Даже при включённой перезаписи
    результат никогда не пишется поверх него: иначе конвертация в ту же
    папку в том же формате уничтожала оригинал без возможности вернуть.
    """
    with _path_lock:
        candidate = os.path.join(output_dir, f"{base_name}.{extension}")
        collides_with_source = protect_path is not None and _same_file(candidate, protect_path)
        if overwrite and not collides_with_source:
            _reserved_paths.add(candidate)
            return candidate
        counter = 0
        while (
            os.path.exists(candidate)
            or candidate in _reserved_paths
            or (protect_path is not None and _same_file(candidate, protect_path))
        ):
            counter += 1
            candidate = os.path.join(output_dir, f"{base_name}_{counter}.{extension}")
        _reserved_paths.add(candidate)
        return candidate


def resolve_frames_dir(output_dir, base_name, overwrite=False):
    """Папка для покадрового разбора — по тем же правилам, что и файлы.

    Раньше имя собиралось напрямую, без резервирования: два файла с
    одинаковым именем из разных папок писали кадры в одну и ту же папку,
    а extract_frames чистит её перед работой — кадры первого пропадали.
    При параллельной обработке они вдобавок писались вперемешку.
    """
    with _path_lock:
        candidate = os.path.join(output_dir, f"{base_name}_frames")
        if overwrite and candidate not in _reserved_paths:
            _reserved_paths.add(candidate)
            return candidate
        counter = 0
        while os.path.exists(candidate) or candidate in _reserved_paths:
            counter += 1
            candidate = os.path.join(output_dir, f"{base_name}_frames_{counter}")
        _reserved_paths.add(candidate)
        return candidate


def release_reserved_paths():
    with _path_lock:
        _reserved_paths.clear()


def default_worker_count(jobs):
    """Сколько файлов обрабатывать одновременно.

    FFmpeg сам занимает все ядра, поэтому видео параллелим осторожно,
    а лёгкие картинки — шире.

    Тип определяется по расширению, а не через get_category: та открывает
    каждый файл, чтобы отличить анимацию от статики, а вызывают эту функцию
    в потоке интерфейса — на очереди из сотен картинок окно подвисало
    ещё до старта обработки.
    """
    if len(jobs) <= 1:
        return 1
    cpu_count = os.cpu_count() or 2
    heavy = any(
        job.output_format not in LIGHTWEIGHT_FORMATS
        or os.path.splitext(job.input_path)[1].lower() not in IMAGE_EXTS
        for job in jobs
    )
    limit = 2 if heavy else 4
    return max(1, min(limit, cpu_count, len(jobs)))


class ConversionWorker(QThread):
    file_started = pyqtSignal(int)
    progress_updated = pyqtSignal(int, int)
    # Сообщение — строка или errors.LocalizedError: текст ошибки переводится
    # в момент показа, а не здесь, в потоке обработки.
    file_finished = pyqtSignal(int, bool, object)
    # Файл, который прервали на середине. Отдельный сигнал, а не ошибка:
    # без него строка навсегда оставалась в состоянии «Обработка».
    file_cancelled = pyqtSignal(int)
    all_finished = pyqtSignal(bool)

    def __init__(self, jobs, parent=None, max_workers=None):
        super().__init__(parent)
        self.jobs = list(jobs)
        self.max_workers = max_workers or default_worker_count(self.jobs)
        self._stop_requested = False
        self._processors = {}
        self._processor_lock = threading.Lock()
        self._report_lock = threading.Lock()
        self.report = []

    def request_stop(self):
        """Прерывает очередь и убивает все запущенные процессы FFmpeg."""
        self._stop_requested = True
        with self._processor_lock:
            processors = list(self._processors.values())
        for processor in processors:
            processor.cancel()

    @property
    def stopped(self):
        return self._stop_requested

    def _processor_for_current_thread(self):
        """Отдельный FFmpegProcessor на поток: он хранит текущий процесс,
        и общий экземпляр при параллельной работе путал бы задачи."""
        key = threading.get_ident()
        with self._processor_lock:
            processor = self._processors.get(key)
            if processor is not None:
                return processor
        try:
            processor = FFmpegProcessor()
        except Exception:
            processor = None
        with self._processor_lock:
            if processor is not None:
                self._processors[key] = processor
                if self._stop_requested:
                    processor.cancel()
        return processor

    def run(self):
        release_reserved_paths()
        try:
            if self.max_workers <= 1:
                for index, job in enumerate(self.jobs):
                    if self._stop_requested:
                        break
                    self._run_single(index, job)
            else:
                with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                    for index, job in enumerate(self.jobs):
                        pool.submit(self._run_single, index, job)
        finally:
            release_reserved_paths()
            self.report.sort(key=lambda row: row["index"])
            self.all_finished.emit(self._stop_requested)

    def _run_single(self, index, job):
        if self._stop_requested:
            return
        self.file_started.emit(index)
        started_at = time.monotonic()
        try:
            self._process_job(index, job)
        except ConversionCancelled:
            self._record(index, job, "Остановлено", time.monotonic() - started_at, "")
            self.file_cancelled.emit(index)
        except Exception as exc:
            _log.exception("Ошибка обработки %s", job.input_path)
            message = as_message(exc)
            self._record(index, job, "Ошибка", time.monotonic() - started_at, message)
            self.file_finished.emit(index, False, message)
        else:
            self._record(index, job, "Готово", time.monotonic() - started_at, "")
            self.file_finished.emit(index, True, "Готово")

    def _record(self, index, job, status, elapsed, message):
        with self._report_lock:
            self.report.append({
                "index": index,
                "input_path": job.protect_path,
                "output_format": job.settings.output_format,
                "status": status,
                "elapsed_sec": round(elapsed, 2),
                # Ошибку храним целиком: отчёт переводится при записи в CSV.
                "message": message,
            })

    def _emit_progress(self, index, percent):
        self.progress_updated.emit(index, percent)

    def _check_cancelled(self):
        if self._stop_requested:
            raise ConversionCancelled("Обработка остановлена пользователем.")

    def _process_job(self, index, job):
        self._check_cancelled()
        settings = job.settings
        input_path = job.input_path
        output_dir = job.output_dir
        output_format = job.output_format
        width = settings.effective_width
        height = settings.effective_height
        keep_aspect = settings.keep_aspect
        fps = settings.effective_fps
        trim = settings.effective_trim
        overwrite = job.overwrite
        # Результат никогда не пишется поверх файла, выбранного пользователем,
        # даже когда обработка идёт через временный промежуточный файл.
        protect = job.protect_path
        transform = transform_for(settings)

        base_name = job.output_base_name or os.path.splitext(os.path.basename(input_path))[0]
        category = get_category(input_path)

        if not os.path.isfile(input_path):
            raise LocalizedFileNotFoundError(
                "err_source_missing", name=os.path.basename(job.protect_path)
            )

        os.makedirs(output_dir, exist_ok=True)
        ffmpeg = self._processor_for_current_thread()

        # Проверку звука делаем до распаковки анимации: иначе анимированная
        # картинка сначала раскладывалась на кадры и собиралась в
        # промежуточный файл, и только потом FFmpeg падал с невнятной
        # простынёй о том, что дорожки нет.
        if output_format in AUDIO_FORMATS and category != "video":
            raise LocalizedValueError("err_audio_from_non_video")

        if category == "animated_image":
            self._process_animated_image_job(index, job, base_name, ffmpeg)
            return

        if output_format in TELEGRAM_FORMATS:
            self._process_telegram_job(
                index, job, base_name, category, output_format, ffmpeg
            )
            return

        if is_twitch_format(output_format) or is_square_platform_format(output_format):
            preset = twitch_preset(output_format) or square_preset(output_format)
            self._process_square_job(
                index, job, base_name, category, output_format, preset, ffmpeg
            )
            return

        if is_discord_format(output_format):
            self._process_discord_job(
                index, job, base_name, category, output_format, ffmpeg
            )
            return

        if is_whatsapp_format(output_format):
            self._process_whatsapp_job(
                index, job, base_name, category, output_format, ffmpeg
            )
            return

        if output_format in AUDIO_FORMATS:
            if ffmpeg is None:
                raise LocalizedRuntimeError("err_no_ffmpeg")
            output_path = resolve_output_path(
                output_dir, base_name, output_format, overwrite, protect
            )
            ffmpeg.extract_audio(
                input_path, output_path, settings.audio_bitrate, trim,
                progress_callback=lambda p: self._emit_progress(index, p),
            )
            return

        if output_format in FRAMES_FORMAT:
            if category not in ("video", "gif", "animated_image"):
                raise LocalizedValueError("err_frames_need_motion")
            if ffmpeg is None:
                raise LocalizedRuntimeError("err_no_ffmpeg")
            frames_dir = resolve_frames_dir(output_dir, base_name, overwrite)
            ffmpeg.extract_frames(
                input_path, frames_dir, width, height, keep_aspect, fps, trim,
                progress_callback=lambda p: self._emit_progress(index, p),
                transform=transform,
            )
            return

        if category == "image":
            if output_format not in IMAGE_FORMATS:
                raise LocalizedValueError("err_static_image_target")
            output_path = resolve_output_path(output_dir, base_name, output_format, overwrite, protect)
            self._emit_progress(index, 10)
            ImageProcessor.convert_image(
                input_path, output_path, output_format, width, height, keep_aspect,
                transform=transform, quality=settings.effective_quality,
                target_bytes=settings.effective_target_bytes,
            )
            self._emit_progress(index, 100)
            return

        if ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        if category in ("gif", "animated_image"):
            if output_format in ANIMATION_FORMATS:
                self._process_animation_job(
                    index, job, base_name, output_format, ffmpeg, transform
                )
            elif output_format in VIDEO_FORMATS:
                output_path = resolve_output_path(output_dir, base_name, output_format, overwrite, protect)
                ffmpeg.gif_to_video(
                    input_path, output_path, width, height, keep_aspect, fps, trim,
                    progress_callback=lambda p: self._emit_progress(index, p),
                    transform=transform, quality=settings.effective_quality,
                    target_bytes=settings.effective_target_bytes,
                )
            elif output_format in IMAGE_FORMATS:
                output_path = resolve_output_path(output_dir, base_name, output_format, overwrite, protect)
                ffmpeg.extract_single_frame(
                    input_path, output_path, width, height, keep_aspect,
                    progress_callback=lambda p: self._emit_progress(index, p),
                    trim=trim, transform=transform,
                )
            else:
                raise LocalizedValueError("err_unknown_format", fmt=output_format)
            return

        if category == "video":
            if output_format in VIDEO_FORMATS:
                output_path = resolve_output_path(output_dir, base_name, output_format, overwrite, protect)
                ffmpeg.convert_video(
                    input_path, output_path, width, height, keep_aspect, fps, trim,
                    progress_callback=lambda p: self._emit_progress(index, p),
                    transform=transform, quality=settings.effective_quality,
                    target_bytes=settings.effective_target_bytes,
                    drop_audio=settings.drops_audio,
                    audio_bitrate=settings.audio_bitrate,
                )
            elif output_format in ANIMATION_FORMATS:
                self._process_animation_job(
                    index, job, base_name, output_format, ffmpeg, transform
                )
            elif output_format in IMAGE_FORMATS:
                output_path = resolve_output_path(output_dir, base_name, output_format, overwrite, protect)
                ffmpeg.extract_single_frame(
                    input_path, output_path, width, height, keep_aspect,
                    progress_callback=lambda p: self._emit_progress(index, p),
                    trim=trim, transform=transform,
                )
            else:
                raise LocalizedValueError("err_unknown_format", fmt=output_format)
            return

        raise LocalizedValueError(
            "err_unsupported_input", name=os.path.basename(job.protect_path)
        )

    def _process_animation_job(self, index, job, base_name, output_format,
                               ffmpeg, transform):
        """GIF или APNG из видео, GIF или анимированной картинки."""
        settings = job.settings
        extension = "png" if output_format == "apng" else "gif"
        output_path = resolve_output_path(
            job.output_dir, base_name, extension, job.overwrite, job.protect_path
        )
        report = lambda percent: self._emit_progress(index, percent)
        arguments = (job.input_path, output_path, settings.effective_width,
                     settings.effective_height, settings.keep_aspect,
                     settings.effective_fps, settings.effective_trim)
        if output_format == "apng":
            ffmpeg.convert_apng(*arguments, progress_callback=report,
                                transform=transform)
        else:
            ffmpeg.video_to_gif(*arguments, progress_callback=report,
                                transform=transform)

    def _process_animated_image_job(self, index, job, base_name, ffmpeg):
        """Готовит анимированную картинку к общему конвейеру обработки.

        Для неподвижного результата достаточно одного кадра. Для анимации
        кадры раскладываются в PNG и собираются в промежуточный файл без
        потерь: FFmpeg не декодирует анимированный WebP сам, а прежний
        промежуточный GIF съедал полупрозрачность.
        """
        settings = job.settings
        ffprobe_path = getattr(ffmpeg, "ffprobe_path", None)
        # Момент, с которого берётся кадр.
        start = settings.trim_start if settings.trim_enabled else 0.0

        if is_static_target(job.output_format):
            with tempfile.TemporaryDirectory() as tmp_dir:
                frame_path = os.path.join(tmp_dir, "frame.png")
                ImageProcessor.save_frame_at(
                    job.input_path, frame_path, start, ffprobe_path
                )
                self._emit_progress(index, 30)
                self._process_job(index, job.copy(
                    input_path=frame_path,
                    output_base_name=base_name,
                    source_path=job.protect_path,
                ))
            return

        if ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        with tempfile.TemporaryDirectory() as tmp_dir:
            frames_dir = os.path.join(tmp_dir, "frames")
            list_path = ImageProcessor.dump_animation_frames(
                job.input_path, frames_dir, ffprobe_path
            )
            intermediate = os.path.join(tmp_dir, "source.mov")
            ffmpeg.build_lossless_intermediate(
                list_path, intermediate,
                progress_callback=scaled_progress(
                    lambda p: self._emit_progress(index, p), 0, 0.15
                ),
            )
            self._process_job(index, job.copy(
                input_path=intermediate,
                output_base_name=base_name,
                source_path=job.protect_path,
            ))

    def _process_telegram_job(self, index, job, base_name, category, output_format, ffmpeg):
        settings = job.settings
        input_path = job.input_path
        output_dir = job.output_dir
        overwrite = job.overwrite
        protect = job.protect_path
        transform = transform_for(settings)

        if is_telegram_video_format(output_format):
            if category not in ("video", "gif", "animated_image"):
                raise LocalizedValueError(
                    "err_needs_motion", target=FormatLabel(output_format)
                )
            if ffmpeg is None:
                raise LocalizedRuntimeError("err_no_ffmpeg")
            target = "emoji" if is_telegram_emoji_format(output_format) else "sticker"
            suffix = "_tg_emoji" if target == "emoji" else "_tg_sticker"
            output_path = resolve_output_path(
                output_dir, f"{base_name}{suffix}", "webm", overwrite, protect
            )
            ffmpeg.convert_telegram_webm(
                input_path,
                output_path,
                target,
                max_duration=settings.tg_duration,
                start_time=settings.tg_start,
                progress_callback=lambda p: self._emit_progress(index, p),
                transform=transform,
                fill=settings.fill_square,
            )
            return

        if category not in ("image", "video", "gif", "animated_image"):
            raise LocalizedValueError(
                "err_unsupported_input", name=os.path.basename(job.protect_path)
            )

        ext = static_image_extension(output_format)
        suffix = "_tg_emoji" if is_telegram_emoji_format(output_format) else "_tg_sticker"
        output_path = resolve_output_path(
            output_dir, f"{base_name}{suffix}", ext, overwrite, protect
        )

        if category == "image":
            self._emit_progress(index, 10)
            ImageProcessor.convert_telegram_static(
                input_path, output_path, output_format, transform,
                fill=settings.fill_square,
            )
            self._emit_progress(index, 100)
            return

        if ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_path = os.path.join(tmp_dir, "frame.png")
            ffmpeg.extract_single_frame(
                input_path,
                frame_path,
                0,
                0,
                True,
                progress_callback=scaled_progress(
                    lambda p: self._emit_progress(index, p), 0, 0.5
                ),
                trim=(settings.tg_start, 0) if settings.tg_start else None,
            )
            ImageProcessor.convert_telegram_static(
                frame_path, output_path, output_format, transform,
                fill=settings.fill_square,
            )
        self._emit_progress(index, 100)

    def _process_square_job(self, index, job, base_name, category, output_format, preset,
                            ffmpeg):
        """Вкладки Twitch, Kick и YouTube: смайлики, значки, иконки баллов,
        7TV.

        Всё это квадраты одного или нескольких размеров под лимит веса;
        отличаются размеры, лимиты и то, анимирован ли результат.
        """
        settings = job.settings
        input_path = job.input_path
        transform = transform_for(settings)
        trim = settings.effective_trim
        fill = settings.fill_square
        moving = category in ("video", "gif", "animated_image")

        if preset.kind == KIND_GIF:
            animation = "gif"
        elif preset.kind == KIND_AUTO_WEBP:
            animation = "webp" if moving else None
        else:
            animation = None

        if preset.kind == KIND_GIF and not moving:
            raise LocalizedValueError("err_needs_motion", target=FormatLabel(output_format))
        if (animation or moving) and ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        report = lambda percent: self._emit_progress(index, percent)
        # Старший размер — первым: частота кадров, подобранная для него,
        # подходит и младшим (ролик тот же, файл легче), и вместо полного
        # подбора на каждый размер хватает одной попытки. Заодно все файлы
        # комплекта анимируются одинаково.
        sizes = sorted(preset.sizes, reverse=True)
        # Прогресс делим между размерами комплекта, иначе полоса откатывается назад.
        share = 100.0 / len(sizes)
        fps_hint = None
        frame_path = None
        with tempfile.TemporaryDirectory() as tmp_dir:
            for position, size in enumerate(sizes):
                self._check_cancelled()
                offset = int(position * share)
                part = scaled_progress(report, offset, share / 100.0)
                name = f"{base_name}{preset.suffix.format(size=size)}"
                extension = {"gif": "gif", "webp": "webp"}.get(animation, "png")
                output_path = resolve_output_path(
                    job.output_dir, name, extension, job.overwrite, job.protect_path
                )
                if animation == "gif":
                    fps_hint = ffmpeg.convert_square_gif(
                        input_path, output_path, size, preset.max_bytes,
                        max_frames=preset.max_frames, fps_cap=preset.fps_cap,
                        trim=trim, transform=transform, fill=fill,
                        fps_hint=fps_hint, progress_callback=part,
                    )
                    continue
                if animation == "webp":
                    ffmpeg.convert_animated_webp(
                        input_path, output_path, size, preset.max_bytes,
                        fps_cap=preset.fps_cap, max_frames=preset.max_frames,
                        trim=trim, transform=transform, fill=fill,
                        progress_callback=part,
                    )
                    continue

                source = input_path
                if category != "image":
                    # Кадр из видео достаём один раз на весь комплект.
                    if frame_path is None:
                        frame_path = os.path.join(tmp_dir, "frame.png")
                        ffmpeg.extract_single_frame(
                            input_path, frame_path, 0, 0, True, trim=trim
                        )
                    source = frame_path
                ImageProcessor.convert_twitch_static(
                    source, output_path, size, transform, fill=fill,
                    limit_bytes=preset.max_bytes,
                )
                self._emit_progress(index, offset + int(share))
        self._emit_progress(index, 100)

    def _process_whatsapp_job(self, index, job, base_name, category, output_format,
                              ffmpeg):
        """Стикер WhatsApp (статичный или анимированный) и иконка набора."""
        settings = job.settings
        transform = transform_for(settings)
        trim = settings.effective_trim
        fill = settings.fill_square
        size = whatsapp_size(output_format)
        limit = whatsapp_byte_limit(output_format)
        animated = is_whatsapp_animated_format(output_format)
        moving = category in ("video", "gif", "animated_image")

        if animated and not moving:
            raise LocalizedValueError("err_needs_motion", target=FormatLabel(output_format))
        if moving and ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        output_path = resolve_output_path(
            job.output_dir, f"{base_name}{whatsapp_suffix(output_format)}",
            whatsapp_extension(output_format), job.overwrite, job.protect_path,
        )
        report = lambda percent: self._emit_progress(index, percent)

        if animated:
            ffmpeg.convert_animated_webp(
                job.input_path, output_path, size, limit,
                fps_cap=WHATSAPP_MAX_FPS, max_duration=WHATSAPP_MAX_SEC,
                trim=trim, transform=transform, fill=fill, progress_callback=report,
            )
            return

        pil_format = "PNG" if whatsapp_extension(output_format) == "png" else "WEBP"
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = job.input_path
            if category != "image":
                source = os.path.join(tmp_dir, "frame.png")
                ffmpeg.extract_single_frame(
                    job.input_path, source, 0, 0, True,
                    progress_callback=scaled_progress(report, 0, 0.5), trim=trim,
                )
            self._emit_progress(index, 60)
            ImageProcessor.convert_square_static(
                source, output_path, size, limit, transform, fill, pil_format
            )
        self._emit_progress(index, 100)

    def _process_discord_job(self, index, job, base_name, category, output_format, ffmpeg):
        settings = job.settings
        input_path = job.input_path
        output_dir = job.output_dir
        overwrite = job.overwrite
        protect = job.protect_path
        transform = transform_for(settings)
        trim = settings.effective_trim

        size = discord_size(output_format)
        limit = discord_byte_limit(output_format)
        suffix = discord_suffix(output_format)
        extension = discord_extension(output_format)
        animated = is_discord_animated_format(output_format)

        if animated and category not in ("video", "gif", "animated_image"):
            raise LocalizedValueError(
                "err_needs_motion", target=FormatLabel(output_format)
            )
        if animated and ffmpeg is None:
            raise LocalizedRuntimeError("err_no_ffmpeg")

        output_path = resolve_output_path(
            output_dir, f"{base_name}{suffix}", extension, overwrite, protect
        )
        report = lambda percent: self._emit_progress(index, percent)

        if not animated:
            if category == "image":
                self._emit_progress(index, 10)
                ImageProcessor.convert_discord_static(
                    input_path, output_path, size, limit, transform,
                    fill=settings.fill_square,
                )
                self._emit_progress(index, 100)
                return
            if ffmpeg is None:
                raise LocalizedRuntimeError("err_no_ffmpeg")
            with tempfile.TemporaryDirectory() as tmp_dir:
                frame_path = os.path.join(tmp_dir, "frame.png")
                ffmpeg.extract_single_frame(
                    input_path, frame_path, 0, 0, True,
                    progress_callback=scaled_progress(report, 0, 0.5),
                    trim=trim,
                )
                ImageProcessor.convert_discord_static(
                    frame_path, output_path, size, limit, transform,
                    fill=settings.fill_square,
                )
            self._emit_progress(index, 100)
            return

        if output_format == "discord_sticker_apng":
            ffmpeg.convert_discord_apng(
                input_path, output_path, size, limit,
                max_duration=MAX_STICKER_DURATION_SEC, fps_cap=DISCORD_MAX_FPS,
                trim=trim, transform=transform, progress_callback=report,
                fill=settings.fill_square,
            )
            return

        ffmpeg.convert_discord_gif(
            input_path, output_path, size, limit, fps_cap=DISCORD_MAX_FPS,
            trim=trim, transform=transform, progress_callback=report,
            fill=settings.fill_square,
        )

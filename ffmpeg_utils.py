import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

from telegram_utils import (
    MAX_VIDEO_DURATION_SEC,
    MAX_VIDEO_FPS,
    MAX_WEBM_SIZE_BYTES,
    build_telegram_video_filter,
    validate_webm_file,
)
from twitch_utils import TWITCH_MAX_FRAMES, TWITCH_MAX_GIF_BYTES

# Если FFmpeg не выдал ни строки вывода за это время, считаем его зависшим.
FFMPEG_STALL_TIMEOUT_SEC = 300

# Прогресс неизвестен (не удалось определить длительность) — UI показывает "бегущую" полосу.
INDETERMINATE_PROGRESS = -1

# Шкала качества интерфейса (1..100) в параметры кодеков. Пары — значение
# при качестве 1 и при качестве 100; у всех трёх кодеков меньше значит лучше.
# Середина шкалы примерно соответствует прежним зашитым значениям.
QUALITY_SCALE = {
    ".mp4": (34, 16),    # -crf для libx264
    ".webm": (50, 24),   # -crf для libvpx-vp9
    ".avi": (12, 2),     # -qscale:v для mpeg4
}

# Кодеки звуковой дорожки по расширению выходного файла.
AUDIO_CODECS = {
    ".mp4": "aac",
    ".webm": "libopus",
    ".avi": "libmp3lame",
    ".mp3": "libmp3lame",
    ".m4a": "aac",
    ".wav": "pcm_s16le",
}

# Ниже этого битрейта видео превращается в кашу — целевой размер недостижим.
MIN_VIDEO_BITRATE = 32_000


class FFmpegNotFoundError(Exception):
    pass


class ConversionCancelled(Exception):
    """Пользователь остановил обработку."""


def _bundled_binary(name):
    """Возвращает FFmpeg рядом с приложением или внутри PyInstaller-сборки.

    Внешняя копия рядом с exe имеет приоритет над вшитой, чтобы FFmpeg
    можно было обновить без пересборки приложения.
    """
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    source_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = getattr(sys, "_MEIPASS", None)
    directories = [executable_dir, source_dir]
    if bundle_dir:
        directories.append(bundle_dir)

    for directory in directories:
        for relative_path in (name, os.path.join("ffmpeg", name)):
            candidate = os.path.join(directory, relative_path)
            if os.path.isfile(candidate):
                return candidate
    return None


def check_ffmpeg_available():
    suffix = ".exe" if os.name == "nt" else ""
    ffmpeg_path = _bundled_binary(f"ffmpeg{suffix}") or shutil.which("ffmpeg")
    ffprobe_path = _bundled_binary(f"ffprobe{suffix}") or shutil.which("ffprobe")
    if ffmpeg_path is None or ffprobe_path is None:
        return False, ffmpeg_path, ffprobe_path
    return True, ffmpeg_path, ffprobe_path


def _run_hidden_kwargs():
    kwargs = {}
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def scaled_progress(callback, offset=0, factor=1.0):
    """Оборачивает колбэк прогресса, сжимая его в диапазон [offset, offset+factor*100].

    Значение INDETERMINATE_PROGRESS пробрасывается без изменений.
    """
    if callback is None:
        return None

    def _wrapped(percent):
        if percent == INDETERMINATE_PROGRESS:
            callback(INDETERMINATE_PROGRESS)
        else:
            callback(offset + int(percent * factor))

    return _wrapped


def _expected_search_steps(low, high):
    """Сколько шагов займёт бинарный поиск по диапазону — для расчёта прогресса."""
    steps = 0
    span = max(1, high - low + 1)
    while span > 0:
        steps += 1
        span //= 2
    return max(1, steps)


def _search_step_progress(callback, attempt, expected_attempts):
    """Прогресс одной попытки подбора занимает свою долю общей полосы,
    чтобы она не откатывалась назад при каждой новой попытке."""
    if callback is None:
        return None
    share = 100.0 / expected_attempts
    offset = min(99, int(attempt * share))
    return scaled_progress(callback, offset, min(share, 100 - offset) / 100.0)


@dataclass(frozen=True)
class Transform:
    """Правки геометрии кадра: поворот и отражение.

    Собирается из настроек задачи и применяется до масштабирования —
    иначе пресеты площадок разворачивали бы уже подогнанный под размер кадр.
    """

    rotate: int = 0               # градусы по часовой стрелке: 0, 90, 180, 270
    flip_horizontal: bool = False
    flip_vertical: bool = False

    def __bool__(self):
        return bool(self.rotate or self.flip_horizontal or self.flip_vertical)

    def filters(self):
        """Фильтры FFmpeg в порядке применения."""
        parts = []
        rotate = int(self.rotate) % 360
        if rotate == 90:
            parts.append("transpose=1")
        elif rotate == 180:
            # Отдельного фильтра на 180° нет, две четверти оборота дешевле
            # обращения к rotate= с интерполяцией.
            parts.append("transpose=1,transpose=1")
        elif rotate == 270:
            parts.append("transpose=2")
        if self.flip_horizontal:
            parts.append("hflip")
        if self.flip_vertical:
            parts.append("vflip")
        return parts


def quality_to_codec_value(ext, quality):
    """Переводит качество 1..100 в -crf (или -qscale) для расширения."""
    scale = QUALITY_SCALE.get(ext)
    if scale is None or not quality:
        return None
    worst, best = scale
    quality = max(1, min(100, int(quality)))
    return int(round(worst + (best - worst) * (quality - 1) / 99.0))


def _terminate_process(process):
    """Мягко завершает процесс, через 3 секунды — принудительно."""
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass


class FFmpegProcessor:
    def __init__(self):
        available, ffmpeg_path, ffprobe_path = check_ffmpeg_available()
        if not available:
            raise FFmpegNotFoundError(
                "FFmpeg или FFprobe не найдены в системе. "
                "Установите FFmpeg и убедитесь, что он добавлен в PATH."
            )
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._process_lock = threading.Lock()
        self._current_process = None
        self._cancelled = False

    def cancel(self):
        """Останавливает текущий и все последующие запуски FFmpeg."""
        with self._process_lock:
            self._cancelled = True
            process = self._current_process
        if process is not None and process.poll() is None:
            _terminate_process(process)

    @property
    def cancelled(self):
        with self._process_lock:
            return self._cancelled

    def get_duration(self, path):
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                **_run_hidden_kwargs(),
            )
            value = result.stdout.strip()
            duration = float(value)
            if duration <= 0:
                return None
            return duration
        except Exception:
            return None

    def get_frame_count(self, path):
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-count_frames",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                **_run_hidden_kwargs(),
            )
            value = result.stdout.strip()
            return int(value)
        except Exception:
            return None

    @staticmethod
    def build_scale_filter(width, height, keep_aspect):
        width = int(width) if width else 0
        height = int(height) if height else 0
        if width <= 0 and height <= 0:
            return None
        if width > 0 and height > 0:
            if keep_aspect:
                return (
                    f"scale={width}:{height}:"
                    f"force_original_aspect_ratio=decrease:force_divisible_by=2"
                )
            return f"scale={width}:{height}"
        if width > 0 and height <= 0:
            return f"scale={width}:-2"
        return f"scale=-2:{height}"

    @classmethod
    def build_filter_string(cls, width, height, keep_aspect, fps, transform=None):
        """Цепочка фильтров: сначала поворот кадра, потом частота и размер."""
        parts = list(transform.filters()) if transform else []
        if fps:
            parts.append(f"fps={int(fps)}")
        scale = cls.build_scale_filter(width, height, keep_aspect)
        if scale:
            parts.append(scale)
        if not parts:
            return None
        return ",".join(parts)

    TIME_MS_PATTERN = re.compile(r"out_time_ms=(\d+)")
    TIME_CLOCK_PATTERN = re.compile(r"out_time=(\d+):(\d+):(\d+\.\d+)")

    @classmethod
    def _parse_progress_seconds(cls, line):
        """Извлекает из строки прогресса FFmpeg текущую позицию в секундах."""
        match = cls.TIME_MS_PATTERN.search(line)
        if match:
            return int(match.group(1)) / 1_000_000.0
        match = cls.TIME_CLOCK_PATTERN.search(line)
        if match:
            return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
        return None

    def _run_with_progress(self, cmd, total_duration, progress_callback):
        if self.cancelled:
            raise ConversionCancelled("Обработка остановлена пользователем.")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            **_run_hidden_kwargs(),
        )
        with self._process_lock:
            if self._cancelled:
                cancelled_before_start = True
            else:
                cancelled_before_start = False
                self._current_process = process
        if cancelled_before_start:
            _terminate_process(process)
            raise ConversionCancelled("Обработка остановлена пользователем.")

        # FFmpeg пишет вывод построчно; читаем его в отдельном потоке,
        # чтобы основной цикл мог засечь зависание (отсутствие вывода).
        lines_queue = queue.Queue()

        def _pump_output():
            try:
                for line in process.stdout:
                    lines_queue.put(line)
            except (ValueError, OSError):
                pass
            finally:
                lines_queue.put(None)

        reader = threading.Thread(target=_pump_output, daemon=True)
        reader.start()

        has_duration = bool(total_duration and total_duration > 0)
        if not has_duration and progress_callback:
            progress_callback(INDETERMINATE_PROGRESS)

        last_percent = 0
        output_lines = []
        stalled = False
        try:
            while True:
                try:
                    line = lines_queue.get(timeout=FFMPEG_STALL_TIMEOUT_SEC)
                except queue.Empty:
                    stalled = True
                    break
                if line is None:
                    break
                output_lines.append(line)
                if has_duration:
                    current_seconds = self._parse_progress_seconds(line)
                    if current_seconds is not None:
                        percent = int(min(99, (current_seconds / total_duration) * 100))
                        if percent > last_percent:
                            last_percent = percent
                            if progress_callback:
                                progress_callback(percent)
                if "progress=end" in line and progress_callback:
                    progress_callback(100)
        finally:
            if stalled or self.cancelled:
                _terminate_process(process)
            return_code = process.wait()
            reader.join(timeout=1)
            with self._process_lock:
                if self._current_process is process:
                    self._current_process = None

        if self.cancelled:
            raise ConversionCancelled("Обработка остановлена пользователем.")
        if stalled:
            raise RuntimeError(
                f"FFmpeg не отвечает более {FFMPEG_STALL_TIMEOUT_SEC // 60} мин и был остановлен. "
                "Возможно, файл повреждён или использует неподдерживаемый кодек."
            )
        if return_code != 0:
            tail = "".join(output_lines[-40:])
            raise RuntimeError(f"FFmpeg завершился с ошибкой (код {return_code}):\n{tail}")

    def _base_cmd(self, input_path, trim=None):
        """Начало команды FFmpeg. trim — пара (начало, длительность) в секундах.

        Здесь задаётся только начало (-ss перед -i, чтобы перемотка была
        быстрой). Длительность добавляется отдельно, у выходного файла:
        в командах с двумя входами (генерация GIF через палитру) -t между
        входами применился бы к палитре, а не к результату.
        """
        cmd = [self.ffmpeg_path, "-y"]
        start = (trim or (0, 0))[0]
        if start:
            cmd += ["-ss", f"{float(start):.3f}"]
        cmd += ["-i", input_path]
        return cmd

    @staticmethod
    def _trim_output_args(trim):
        """Ограничение длительности — параметр выходного файла."""
        duration = (trim or (0, 0))[1]
        return ["-t", f"{float(duration):.3f}"] if duration else []

    @staticmethod
    def _trimmed_duration(total, trim):
        """Сколько секунд реально обработаем — для расчёта прогресса."""
        if not trim:
            return total
        start, duration = trim
        if total:
            available = max(0.0, total - float(start or 0))
            return min(available, float(duration)) if duration else available
        return float(duration) or total

    @staticmethod
    def _video_codec_args(ext, quality=None, bitrate=None):
        """Аргументы видеокодека для расширения выходного файла.

        quality — шкала интерфейса 1..100, bitrate — режим целевого размера
        (тогда качество не задаётся, размером управляет битрейт).
        """
        codecs = {
            ".mp4": ["-c:v", "libx264", "-preset", "medium"],
            ".webm": ["-c:v", "libvpx-vp9"],
            ".avi": ["-c:v", "mpeg4"],
        }
        args = codecs.get(ext)
        if args is None:
            raise ValueError(f"Неподдерживаемый видео формат: {ext}")
        args = list(args)

        if bitrate:
            bitrate = int(bitrate)
            args += ["-b:v", str(bitrate)]
            if ext == ".mp4":
                # Потолок и буфер держат битрейт в рамках на резких сценах,
                # иначе файл вылезает за целевой размер.
                args += ["-maxrate", str(int(bitrate * 1.45)),
                         "-bufsize", str(bitrate * 2)]
            return args

        value = quality_to_codec_value(ext, quality)
        if ext == ".avi":
            args += ["-qscale:v", str(value if value is not None else 3)]
        elif ext == ".webm":
            args += ["-b:v", "0", "-crf", str(value if value is not None else 32)]
        else:
            args += ["-crf", str(value if value is not None else 20)]
        return args

    @staticmethod
    def _audio_codec_args(ext, drop_audio=False, bitrate=None):
        """Аргументы звуковой дорожки. drop_audio убирает её совсем."""
        if drop_audio:
            return ["-an"]
        codec = AUDIO_CODECS.get(ext)
        if codec is None:
            return []
        args = ["-c:a", codec]
        if codec == "pcm_s16le":
            # У несжатого PCM битрейта нет — его задаёт частота дискретизации.
            return args
        default_bitrate = 128 if ext == ".webm" else 160
        args += ["-b:a", f"{int(bitrate or default_bitrate)}k"]
        return args

    def _generate_gif_via_palette(
        self, input_path, output_path, vf, duration, palette_filter, paletteuse_filter,
        progress_callback=None, trim=None
    ):
        """Двухпроходная генерация GIF: сначала строится палитра цветов, затем сам GIF."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            palette_path = os.path.join(tmp_dir, "palette.png")
            palette_cmd = self._base_cmd(input_path, trim)
            palette_cmd += ["-vf", f"{vf},{palette_filter}"]
            palette_cmd += self._trim_output_args(trim)
            palette_cmd += ["-progress", "pipe:1", "-nostats", palette_path]
            self._run_with_progress(
                palette_cmd, duration, scaled_progress(progress_callback, 0, 0.5)
            )

            gif_cmd = self._base_cmd(input_path, trim)
            gif_cmd += ["-i", palette_path]
            gif_cmd += ["-lavfi", f"{vf}[x];[x][1:v]{paletteuse_filter}"]
            gif_cmd += self._trim_output_args(trim)
            gif_cmd += ["-progress", "pipe:1", "-nostats", output_path]
            self._run_with_progress(
                gif_cmd, duration, scaled_progress(progress_callback, 50, 0.5)
            )

    @staticmethod
    def _target_video_bitrate(target_bytes, duration, audio_bitrate_kbps):
        """Битрейт видео, при котором файл уложится в целевой размер."""
        if not target_bytes or not duration or duration <= 0:
            return None
        audio_bits = float(audio_bitrate_kbps or 0) * 1000.0 * duration
        # 3 % отдаём заголовкам контейнера — без запаса файл стабильно
        # вылезал за границу на пару десятков килобайт.
        video_bits = (target_bytes * 8 - audio_bits) * 0.97
        if video_bits <= 0:
            return None
        bitrate = int(video_bits / duration)
        return bitrate if bitrate >= MIN_VIDEO_BITRATE else None

    def convert_video(self, input_path, output_path, width, height, keep_aspect, fps,
                      trim=None, progress_callback=None, transform=None,
                      quality=None, target_bytes=None, drop_audio=False,
                      audio_bitrate=None):
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        ext = os.path.splitext(output_path)[1].lower()
        filter_string = self.build_filter_string(width, height, keep_aspect, fps, transform)

        bitrate = None
        if target_bytes:
            bitrate = self._target_video_bitrate(
                target_bytes, total_duration,
                0 if drop_audio else (audio_bitrate or 160),
            )
            if bitrate is None:
                raise ValueError(
                    f"Целевой размер {target_bytes // 1024} КБ слишком мал для "
                    "этого файла. Увеличьте размер, обрежьте по времени или "
                    "уменьшите разрешение."
                )

        # Битрейт — оценка сверху, и на сложном материале файл выходит крупнее.
        # Одна повторная попытка с поправкой надёжнее, чем обещать точный размер.
        attempts = 2 if bitrate else 1
        for attempt in range(attempts):
            cmd = self._base_cmd(input_path, trim)
            if filter_string:
                cmd += ["-vf", filter_string]
            cmd += self._video_codec_args(ext, quality, bitrate)
            cmd += self._audio_codec_args(ext, drop_audio, audio_bitrate)
            if ext == ".mp4":
                cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
            cmd += self._trim_output_args(trim)
            cmd += ["-progress", "pipe:1", "-nostats", output_path]
            step = scaled_progress(
                progress_callback, int(attempt * 100 / attempts), 1.0 / attempts
            ) if attempts > 1 else progress_callback
            self._run_with_progress(cmd, total_duration, step)

            if not bitrate or attempt == attempts - 1:
                break
            actual = os.path.getsize(output_path)
            if actual <= target_bytes:
                break
            corrected = int(bitrate * (target_bytes / actual) * 0.95)
            if corrected < MIN_VIDEO_BITRATE:
                break
            bitrate = corrected
        if progress_callback:
            progress_callback(100)

    def video_to_gif(self, input_path, output_path, width, height, keep_aspect, fps,
                     trim=None, progress_callback=None, transform=None):
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        effective_fps = fps if fps else 10
        filter_string = self.build_filter_string(
            width, height, keep_aspect, effective_fps, transform
        )
        if not filter_string:
            filter_string = f"fps={effective_fps}"
        self._generate_gif_via_palette(
            input_path, output_path, filter_string, total_duration,
            "palettegen=stats_mode=diff", "paletteuse=dither=bayer:bayer_scale=3",
            progress_callback, trim,
        )
        if progress_callback:
            progress_callback(100)

    def gif_to_video(self, input_path, output_path, width, height, keep_aspect, fps,
                     trim=None, progress_callback=None, transform=None,
                     quality=None, target_bytes=None, drop_audio=False,
                     audio_bitrate=None):
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        ext = os.path.splitext(output_path)[1].lower()
        bitrate = None
        if target_bytes:
            # У GIF звука нет, поэтому весь бюджет достаётся видео.
            bitrate = self._target_video_bitrate(target_bytes, total_duration, 0)
            if bitrate is None:
                raise ValueError(
                    f"Целевой размер {target_bytes // 1024} КБ слишком мал для "
                    "этого файла. Увеличьте размер или обрежьте по времени."
                )
        cmd = self._base_cmd(input_path, trim)
        filter_parts = []
        filter_string = self.build_filter_string(width, height, keep_aspect, fps, transform)
        if filter_string:
            filter_parts.append(filter_string)
        filter_parts.append("format=yuv420p")
        cmd += ["-vf", ",".join(filter_parts)]
        cmd += self._video_codec_args(ext, quality, bitrate)
        if ext == ".mp4":
            cmd += ["-movflags", "+faststart"]
        cmd += self._trim_output_args(trim)
        cmd += ["-progress", "pipe:1", "-nostats", output_path]
        self._run_with_progress(cmd, total_duration, progress_callback)

    def extract_audio(self, input_path, output_path, bitrate=None, trim=None,
                      progress_callback=None):
        """Достаёт звуковую дорожку в отдельный файл (MP3, M4A или WAV)."""
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        ext = os.path.splitext(output_path)[1].lower()
        if ext not in (".mp3", ".m4a", ".wav"):
            raise ValueError(f"Неподдерживаемый формат звука: {ext}")
        cmd = self._base_cmd(input_path, trim)
        cmd += ["-vn"]
        cmd += self._audio_codec_args(ext, False, bitrate)
        cmd += self._trim_output_args(trim)
        cmd += ["-progress", "pipe:1", "-nostats", output_path]
        self._run_with_progress(cmd, total_duration, progress_callback)
        if progress_callback:
            progress_callback(100)

    @staticmethod
    def _square_filter(size, transform=None):
        """Вписывает кадр в квадрат, добирая пустоту прозрачным фоном."""
        parts = list(transform.filters()) if transform else []
        parts.append(
            f"scale={size}:{size}:force_original_aspect_ratio=decrease,"
            f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
        )
        return ",".join(parts)

    def _search_fps_within_limit(self, duration, max_frames, fps_cap, encode,
                                 fits, progress_callback, limit_error, suffix=".gif"):
        """Подбирает максимальный FPS, при котором результат влезает в лимиты.

        Бинарный поиск вместо перебора: попыток выходит около пяти вместо
        полутора десятков, а каждая — это полная перекодировка.
        """
        if max_frames and duration:
            fps_cap = min(fps_cap, max(1, int(max_frames / duration)))
        low, high = 1, max(1, int(fps_cap))
        attempt = 0
        expected_attempts = _expected_search_steps(low, high)
        best_result = None
        last_error = None

        with tempfile.TemporaryDirectory() as attempts_dir:
            # Расширение обязательно: без него FFmpeg не выбирает мультиплексор
            # и отказывается открывать выходной файл.
            candidate_path = os.path.join(attempts_dir, f"candidate{suffix}")
            while low <= high:
                fps = (low + high) // 2
                attempt_progress = _search_step_progress(
                    progress_callback, attempt, expected_attempts
                )
                attempt += 1
                try:
                    encode(fps, candidate_path, attempt_progress)
                except ConversionCancelled:
                    raise
                except RuntimeError as exc:
                    last_error = exc
                    high = fps - 1
                    continue

                problem = fits(candidate_path)
                if problem is not None:
                    last_error = RuntimeError(problem)
                    high = fps - 1
                    continue

                best_result = f"{candidate_path}.best"
                shutil.copyfile(candidate_path, best_result)
                low = fps + 1

            if best_result is None:
                raise last_error or RuntimeError(limit_error)
            with open(best_result, "rb") as handle:
                return handle.read()

    def _convert_sized_gif(self, input_path, output_path, size, max_bytes,
                           max_frames=None, fps_cap=15, trim=None, transform=None,
                           progress_callback=None):
        """Квадратный GIF под лимиты площадки: размер файла и число кадров."""
        duration = self._trimmed_duration(self.get_duration(input_path), trim)
        vf_base = self._square_filter(size, transform)
        limit_kb = max_bytes // 1024

        def encode(fps, destination, attempt_progress):
            self._generate_gif_via_palette(
                input_path, destination, f"fps={fps},{vf_base}", duration,
                "palettegen=reserve_transparent=1", "paletteuse",
                attempt_progress, trim,
            )

        def fits(path):
            if max_frames is not None:
                frames = self.get_frame_count(path)
                if frames is not None and frames > max_frames:
                    return f"В GIF больше {max_frames} кадров."
            if os.path.getsize(path) > max_bytes:
                return f"GIF не удалось уложить в лимит {limit_kb} КБ."
            return None

        blob = self._search_fps_within_limit(
            duration, max_frames, fps_cap, encode, fits, progress_callback,
            f"Не удалось создать GIF в пределах {limit_kb} КБ.",
        )
        with open(output_path, "wb") as handle:
            handle.write(blob)
        if progress_callback:
            progress_callback(100)

    def convert_twitch_gif(self, input_path, output_path, size, progress_callback=None,
                           trim=None, transform=None):
        """Создаёт квадратный GIF для Twitch: максимум 60 кадров и 1 МБ."""
        self._convert_sized_gif(
            input_path, output_path, size, TWITCH_MAX_GIF_BYTES,
            max_frames=TWITCH_MAX_FRAMES, fps_cap=15, trim=trim,
            transform=transform, progress_callback=progress_callback,
        )

    def convert_discord_gif(self, input_path, output_path, size, max_bytes,
                            fps_cap=30, trim=None, transform=None,
                            progress_callback=None):
        """Анимированный эмодзи Discord: у него ограничен только размер файла."""
        self._convert_sized_gif(
            input_path, output_path, size, max_bytes, max_frames=None,
            fps_cap=fps_cap, trim=trim, transform=transform,
            progress_callback=progress_callback,
        )

    def convert_apng(self, input_path, output_path, width, height, keep_aspect,
                     fps, trim=None, progress_callback=None, transform=None):
        """Анимированный PNG: одна картинка со всеми кадрами внутри.

        В отличие от GIF, APNG хранит полноценную 8-битную прозрачность и
        все цвета, поэтому мягкие края и градиенты не огрубляются. Расплата —
        размер файла: APNG заметно тяжелее GIF.
        """
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        cmd = self._base_cmd(input_path, trim)
        filter_string = self.build_filter_string(width, height, keep_aspect, fps, transform)
        if filter_string:
            cmd += ["-vf", filter_string]
        cmd += ["-an", "-c:v", "apng", "-pix_fmt", "rgba", "-plays", "0"]
        cmd += self._trim_output_args(trim)
        # Расширение у файла .png, поэтому мультиплексор задаём явно —
        # иначе FFmpeg запишет одиночную картинку вместо анимации.
        cmd += ["-f", "apng", "-progress", "pipe:1", "-nostats", output_path]
        self._run_with_progress(cmd, total_duration, progress_callback)
        if progress_callback:
            progress_callback(100)

    def convert_discord_apng(self, input_path, output_path, size, max_bytes,
                             max_duration=None, fps_cap=30, trim=None,
                             transform=None, progress_callback=None):
        """Анимированный стикер Discord: APNG с полноценной полупрозрачностью.

        В отличие от GIF, APNG хранит 8-битную альфу — мягкие края эмодзи
        не превращаются в рваную кайму. Размер регулируется частотой кадров:
        у APNG нет ни квантования цветов, ни параметра качества.
        """
        duration = self._trimmed_duration(self.get_duration(input_path), trim)
        if max_duration:
            duration = min(duration, float(max_duration)) if duration else float(max_duration)
        vf_base = self._square_filter(size, transform)
        limit_kb = max_bytes // 1024

        def encode(fps, destination, attempt_progress):
            cmd = self._base_cmd(input_path, trim)
            cmd += ["-vf", f"fps={fps},{vf_base}"]
            cmd += ["-an", "-c:v", "apng", "-pix_fmt", "rgba", "-plays", "0"]
            if max_duration:
                cmd += ["-t", f"{float(max_duration):.3f}"]
            else:
                cmd += self._trim_output_args(trim)
            # Расширение у файла .png, поэтому мультиплексор задаём явно —
            # иначе FFmpeg запишет одиночную картинку вместо анимации.
            cmd += ["-f", "apng", "-progress", "pipe:1", "-nostats", destination]
            self._run_with_progress(cmd, duration, attempt_progress)

        def fits(path):
            if os.path.getsize(path) > max_bytes:
                return f"APNG не удалось уложить в лимит {limit_kb} КБ."
            return None

        blob = self._search_fps_within_limit(
            duration, None, fps_cap, encode, fits, progress_callback,
            f"Не удалось создать APNG в пределах {limit_kb} КБ. "
            "Сократите длительность или упростите анимацию.",
            suffix=".png",
        )
        with open(output_path, "wb") as handle:
            handle.write(blob)
        if progress_callback:
            progress_callback(100)

    def build_lossless_intermediate(self, list_path, output_path, progress_callback=None):
        """Собирает кадры по списку concat в промежуточный файл без потерь.

        Кодек qtrle хранит RGBA как есть: полупрозрачность и покадровые
        задержки доходят до итоговой конвертации нетронутыми. Раньше здесь
        был GIF, а он схлопывает альфу до одного бита.
        """
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:v", "qtrle", "-pix_fmt", "argb",
            "-progress", "pipe:1", "-nostats", output_path,
        ]
        self._run_with_progress(cmd, None, progress_callback)

    def estimate_frame_count(self, input_path, fps=None, trim=None):
        """Примерное число кадров, которое даст извлечение (для предупреждения)."""
        info = self.get_media_info(input_path)
        duration = self._trimmed_duration(info.get("duration"), trim)
        if not duration:
            return None
        return int(duration * (fps or info.get("fps") or 25))

    def get_media_info(self, path):
        """Разрешение, длительность и FPS одним вызовом ffprobe."""
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate:format=duration",
            "-of", "default=noprint_wrappers=1",
            path,
        ]
        info = {"width": None, "height": None, "duration": None, "fps": None}
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                **_run_hidden_kwargs(),
            )
        except Exception:
            return info

        for line in result.stdout.splitlines():
            key, _, value = line.partition("=")
            value = value.strip()
            if not value or value == "N/A":
                continue
            try:
                if key == "width":
                    info["width"] = int(value)
                elif key == "height":
                    info["height"] = int(value)
                elif key == "duration":
                    duration = float(value)
                    info["duration"] = duration if duration > 0 else None
                elif key == "avg_frame_rate":
                    numerator, _, denominator = value.partition("/")
                    fps = float(numerator) / float(denominator or 1)
                    info["fps"] = fps if fps > 0 else None
            except (ValueError, ZeroDivisionError):
                continue
        return info

    def extract_frames(self, input_path, output_dir, width, height, keep_aspect, fps,
                       trim=None, progress_callback=None, transform=None):
        # Старые кадры от прошлого запуска удаляем, иначе они смешаются с новыми.
        if os.path.isdir(output_dir):
            for name in os.listdir(output_dir):
                if re.fullmatch(r"frame_\d+\.png", name):
                    try:
                        os.remove(os.path.join(output_dir, name))
                    except OSError:
                        pass
        os.makedirs(output_dir, exist_ok=True)
        total_duration = self._trimmed_duration(self.get_duration(input_path), trim)
        cmd = self._base_cmd(input_path, trim)
        filter_string = self.build_filter_string(width, height, keep_aspect, fps, transform)
        if filter_string:
            cmd += ["-vf", filter_string]
        output_pattern = os.path.join(output_dir, "frame_%05d.png")
        cmd += self._trim_output_args(trim)
        cmd += ["-progress", "pipe:1", "-nostats", output_pattern]
        self._run_with_progress(cmd, total_duration, progress_callback)

    def extract_single_frame(self, input_path, output_path, width, height, keep_aspect,
                             progress_callback=None, trim=None, transform=None):
        """Один кадр в картинку. trim выбирает момент, с которого его брать."""
        # Длительность фрагмента здесь не нужна — кадр всё равно один,
        # поэтому от trim берём только начало.
        start_only = (trim[0], 0) if trim else None
        cmd = self._base_cmd(input_path, start_only)
        parts = list(transform.filters()) if transform else []
        scale = self.build_scale_filter(width, height, keep_aspect)
        if scale:
            parts.append(scale)
        cmd += ["-frames:v", "1"]
        if parts:
            cmd += ["-vf", ",".join(parts)]
        cmd += ["-progress", "pipe:1", "-nostats", output_path]
        self._run_with_progress(cmd, None, progress_callback)
        if progress_callback:
            progress_callback(100)

    def convert_telegram_webm(
        self,
        input_path,
        output_path,
        target,
        max_duration=None,
        start_time=0.0,
        progress_callback=None,
        transform=None,
    ):
        """Конвертация видео/GIF в WEBM VP9 для Telegram (стикер или emoji).

        start_time — с какой секунды исходника брать фрагмент: длинное видео
        обрезается по выбранному месту, а не всегда с начала.
        """
        if target not in ("sticker", "emoji"):
            raise ValueError(f"Неизвестный тип Telegram-видео: {target}")

        max_duration = min(
            float(max_duration) if max_duration else MAX_VIDEO_DURATION_SEC,
            MAX_VIDEO_DURATION_SEC,
        )
        if max_duration <= 0:
            raise ValueError("Длительность Telegram-видео должна быть больше 0 секунд.")

        vf = build_telegram_video_filter(
            target, max_duration, transform.filters() if transform else None
        )
        input_duration = self.get_duration(input_path)
        is_gif = input_path.lower().endswith(".gif")

        start_time = max(0.0, float(start_time or 0.0))
        if input_duration:
            # Не выходим за конец файла: иначе получился бы пустой результат.
            start_time = min(start_time, max(0.0, input_duration - 0.05))
            available = input_duration - start_time
        else:
            available = max_duration
        # Короткий файл больше не растягивается зацикливанием до трёх секунд —
        # берём его собственную длину.
        effective_duration = max(0.05, min(available, max_duration))

        def encode_with_crf(crf, destination, attempt_callback):
            cmd = [self.ffmpeg_path, "-y"]
            if is_gif:
                cmd += ["-ignore_loop", "0"]
            if start_time > 0:
                cmd += ["-ss", f"{start_time:.3f}"]
            cmd += [
                "-i", input_path,
                "-t", f"{effective_duration:.3f}",
                "-an",
                "-r", str(MAX_VIDEO_FPS),
                "-vf", vf,
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-crf", str(crf),
                "-b:v", "0",
                "-row-mt", "1",
                "-deadline", "good",
                "-cpu-used", "2",
                "-progress", "pipe:1",
                "-nostats",
                destination,
            ]
            self._run_with_progress(cmd, effective_duration, attempt_callback)

        # Меньший CRF = лучше качество и больший файл. Бинарным поиском находим
        # минимальный (самый качественный) CRF, укладывающийся в лимит 256 KB.
        low, high = 28, 60
        best_blob = None
        last_error = None
        last_size = None
        attempt = 0
        expected_attempts = _expected_search_steps(low, high)

        with tempfile.TemporaryDirectory() as attempts_dir:
            candidate_path = os.path.join(attempts_dir, "candidate.webm")
            best_path = os.path.join(attempts_dir, "best.webm")
            while low <= high:
                crf = (low + high) // 2
                attempt_callback = _search_step_progress(
                    progress_callback, attempt, expected_attempts
                )
                attempt += 1
                try:
                    encode_with_crf(crf, candidate_path, attempt_callback)
                except ConversionCancelled:
                    raise
                except RuntimeError as exc:
                    last_error = exc
                    low = crf + 1
                    continue

                size = os.path.getsize(candidate_path)
                output_duration = self.get_duration(candidate_path)
                if output_duration and output_duration > max_duration + 0.05:
                    last_error = RuntimeError(
                        f"Длительность {output_duration:.2f} сек превышает лимит "
                        f"{MAX_VIDEO_DURATION_SEC:.0f} сек."
                    )
                    raise last_error

                last_size = size
                if size <= MAX_WEBM_SIZE_BYTES:
                    shutil.copyfile(candidate_path, best_path)
                    best_blob = best_path
                    high = crf - 1
                else:
                    low = crf + 1

            if best_blob is None:
                if last_error:
                    raise last_error
                size_kb = (last_size or 0) // 1024
                raise RuntimeError(
                    f"Не удалось уложиться в лимит 256 KB (получено {size_kb} KB). "
                    "Упростите анимацию, сократите длительность или уменьшите детализацию."
                )
            shutil.copyfile(best_blob, output_path)

        issues = validate_webm_file(output_path, self.get_duration(output_path))
        if issues:
            raise RuntimeError(issues[0])
        if progress_callback:
            progress_callback(100)

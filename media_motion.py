"""Анимация файлов в интерфейсе: в предпросмотре чата и миниатюрах очереди.

Проигрываются только короткие анимации — не длиннее SHORT_ANIMATION_SEC:
смайлики, стикеры, GIF и короткие ролики. Длинное видео в очереди и в
предпросмотре стоит одним кадром: декодировать его ради миниатюры значит
тратить процессор впустую, а смайлик или стикер дольше 10 секунд и так не
бывает.

Что проигрывать (motion_source):
- GIF и анимированный WEBP — сам файл, его умеет QMovie;
- видео, APNG, анимированный AVIF и стикер .tgs — копия в WEBP на
  PREVIEW_ANIMATION_SIZE px (QMovie их не проигрывает): видео режет
  FFmpeg, кадры APNG/AVIF собирает Pillow, стикер рисует rlottie.

Копии лежат во временной папке (lottie_utils.preview_animation_path) и
удаляются через несколько дней (cleanup_preview_animations).
"""

import os
import time

from animation_info import animated_image_info
from lottie_utils import is_tgs, preview_animation_path, write_preview_animation

# Не длиннее — анимация проигрывается, длиннее — стоит одним кадром.
SHORT_ANIMATION_SEC = 10.0

VIDEO_MOTION_EXTS = {".mp4", ".webm", ".avi", ".mov", ".mkv", ".m4v", ".wmv",
                     ".flv", ".mpg", ".mpeg", ".3gp", ".ogv"}
# Проигрывает сам QMovie.
MOVIE_EXTS = {".gif", ".webp"}
# Бывают анимированными, но QMovie их не проигрывает — нужна копия.
PILLOW_MOTION_EXTS = {".png", ".apng", ".avif"}
# Что вообще может оказаться анимацией — остальное не открываем.
MAYBE_MOTION_EXTS = VIDEO_MOTION_EXTS | MOVIE_EXTS | PILLOW_MOTION_EXTS | {".tgs", ".awebp"}

PREVIEW_ANIMATION_SIZE = 200
PREVIEW_VIDEO_FPS = 15
PREVIEW_ANIMATION_MAX_FRAMES = 150
COPY_KEEP_DAYS = 7


def may_move(path):
    return os.path.splitext(path)[1].lower() in MAYBE_MOTION_EXTS


def animation_duration(path, ffmpeg=None):
    """Длительность анимации в секундах или None, если файл не анимирован.

    Видео меряет ffprobe (нужен FFmpeg), анимированные картинки и .tgs —
    чтение заголовков (animation_info).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_MOTION_EXTS:
        if ffmpeg is None:
            return None
        duration = ffmpeg.get_duration(path)
        return duration if duration and duration > 0 else None
    if ext not in MAYBE_MOTION_EXTS:
        return None
    info = animated_image_info(path, getattr(ffmpeg, "ffprobe_path", None))
    if not info:
        return None
    return info.get("duration") or None


def is_short(duration):
    return bool(duration) and duration <= SHORT_ANIMATION_SEC


def motion_source(path, ffmpeg=None):
    """Что проигрывать вместо неподвижного кадра, или None.

    None — файл не анимирован, анимация длинная или копию сделать не вышло.
    Долгие шаги (копия видео) идут здесь же, поэтому зовётся из фонового
    потока.
    """
    if not may_move(path):
        return None
    duration = animation_duration(path, ffmpeg)
    if not is_short(duration):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext in MOVIE_EXTS:
        return path
    if is_tgs(path):
        return write_preview_animation(path)
    target = preview_animation_path(path)
    if os.path.isfile(target):
        return target
    if ext in VIDEO_MOTION_EXTS:
        if ffmpeg is None:
            return None
        return _write_copy(target, lambda partial: ffmpeg.make_preview_animation(
            path, partial, PREVIEW_ANIMATION_SIZE, SHORT_ANIMATION_SEC, PREVIEW_VIDEO_FPS))
    return _write_copy(target, lambda partial: _pillow_copy(path, partial))


def _write_copy(target, write):
    """Пишет копию во временный файл и переименовывает целиком: недописанную
    копию другой поток принял бы за готовую."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    partial = f"{target}.{os.getpid()}.{id(write)}.part.webp"
    try:
        if write(partial) is False:
            return None
        os.replace(partial, target)
        return target
    finally:
        if os.path.exists(partial):
            os.remove(partial)


def _pillow_copy(path, partial):
    from PIL import Image

    with Image.open(path) as source:
        count = getattr(source, "n_frames", 1)
        if count < 2:
            return False
        frames, durations = [], []
        for index in range(min(count, PREVIEW_ANIMATION_MAX_FRAMES)):
            source.seek(index)
            frame = source.convert("RGBA")
            frame.thumbnail((PREVIEW_ANIMATION_SIZE, PREVIEW_ANIMATION_SIZE))
            frames.append(frame)
            durations.append(source.info.get("duration") or 100)
    frames[0].save(partial, "WEBP", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, quality=70)
    return True


def cleanup_preview_animations(max_age_days=COPY_KEEP_DAYS):
    """Удаляет старые проигрываемые копии из временной папки."""
    folder = os.path.dirname(preview_animation_path(""))
    try:
        limit = time.time() - max_age_days * 24 * 60 * 60
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.path.getmtime(path) < limit:
                os.remove(path)
    except OSError:
        pass

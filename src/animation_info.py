"""Длительность и частота кадров анимированных изображений.

Pillow надёжно считает число кадров у WEBP/AVIF/APNG, но у многих таких
файлов не отдаёт длительность кадра, а FFmpeg не умеет декодировать
анимированный WebP вовсе. Поэтому тайминги берутся из нескольких
источников по очереди — иначе анимация конвертируется с выдуманной
скоростью (раньше подставлялось 100 мс на кадр, и эмодзи на 33 fps
проигрывался втрое медленнее оригинала).
"""

import json
import logging
import os
import struct
import subprocess

from PIL import Image

_log = logging.getLogger(__name__)

# Если скорость определить не удалось — 10 кадров в секунду как в GIF.
FALLBACK_FRAME_MS = 100


def _pillow_frame_durations(path):
    """Длительности кадров, если формат их отдаёт (GIF, часть APNG)."""
    try:
        with Image.open(path) as image:
            frames = getattr(image, "n_frames", 1)
            if frames <= 1:
                return []
            durations = []
            for index in range(frames):
                image.seek(index)
                durations.append(image.info.get("duration"))
            if all(value for value in durations):
                return [float(value) for value in durations]
            return []
    except Exception:
        _log.debug("Pillow не дал длительности кадров для %s", path, exc_info=True)
        return []


def _webp_frame_durations(path):
    """Длительности из чанков ANMF анимированного WebP.

    Разбор контейнера — единственный надёжный способ: Pillow эти поля
    не показывает, а FFmpeg такой файл не открывает.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return []
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return []

    durations = []
    position = 12
    while position + 8 <= len(data):
        fourcc = data[position:position + 4]
        try:
            size = struct.unpack("<I", data[position + 4:position + 8])[0]
        except struct.error:
            break
        payload = position + 8
        if fourcc == b"ANMF" and payload + 16 <= len(data):
            # Заголовок ANMF: x, y, ширина, высота по 3 байта, затем
            # длительность кадра — тоже 3 байта, в миллисекундах.
            durations.append(float(int.from_bytes(data[payload + 12:payload + 15], "little")))
        position = payload + size + (size & 1)
    return durations if all(durations) else []


def _ffprobe_animation(path, ffprobe_path):
    """Длительность и FPS у форматов, которые FFmpeg читает (AVIF).

    У AVIF несколько видеодорожек: миниатюра-картинка, альфа и сама
    анимация. Берём дорожку с наибольшим числом кадров.
    """
    if not ffprobe_path:
        return None
    command = [
        ffprobe_path, "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=nb_frames,avg_frame_rate,duration",
        "-of", "json", path,
    ]
    try:
        from ffmpeg_utils import _run_hidden_kwargs

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=20,
            **_run_hidden_kwargs(),
        )
        streams = json.loads(result.stdout or "{}").get("streams", [])
    except Exception:
        _log.debug("ffprobe не смог прочитать %s", path, exc_info=True)
        return None

    best = None
    for stream in streams:
        try:
            frames = int(stream.get("nb_frames") or 0)
        except (TypeError, ValueError):
            frames = 0
        if frames <= 1:
            continue
        try:
            duration = float(stream.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            continue
        if best is None or frames > best[0]:
            best = (frames, duration)
    if best is None:
        return None
    frames, duration = best
    return {"frames": frames, "duration": duration, "fps": frames / duration}


def animated_image_info(path, ffprobe_path=None):
    """Сведения об анимации: кадры, длительности кадров, общая длина, FPS.

    Возвращает None, если файл не анимированный.
    """
    if os.path.splitext(path)[1].lower() == ".tgs":
        # Стикер Telegram: Pillow его не открывает, сведения даёт rlottie.
        from lottie_utils import tgs_info

        try:
            return tgs_info(path)
        except Exception:
            _log.debug("Не удалось прочитать стикер %s", path, exc_info=True)
            return None
    try:
        with Image.open(path) as image:
            frames = getattr(image, "n_frames", 1)
            loop = image.info.get("loop", 0)
    except Exception:
        return None
    if frames <= 1:
        return None

    durations = _pillow_frame_durations(path)
    if not durations and os.path.splitext(path)[1].lower() == ".webp":
        durations = _webp_frame_durations(path)

    if durations:
        total_ms = sum(durations)
        return {
            "frames": len(durations),
            "durations": durations,
            "duration": total_ms / 1000.0,
            "fps": (len(durations) / (total_ms / 1000.0)) if total_ms else None,
            "loop": loop,
        }

    probed = _ffprobe_animation(path, ffprobe_path)
    if probed:
        per_frame = probed["duration"] * 1000.0 / probed["frames"]
        return {
            "frames": probed["frames"],
            "durations": [per_frame] * probed["frames"],
            "duration": probed["duration"],
            "fps": probed["fps"],
            "loop": loop,
        }

    # Скорость неизвестна — берём стандартные для GIF 10 кадров в секунду.
    return {
        "frames": frames,
        "durations": [float(FALLBACK_FRAME_MS)] * frames,
        "duration": frames * FALLBACK_FRAME_MS / 1000.0,
        "fps": 1000.0 / FALLBACK_FRAME_MS,
        "loop": loop,
        "estimated": True,
    }

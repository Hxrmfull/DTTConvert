"""Анимированные стикеры Telegram (.tgs).

TGS — это анимация Lottie: векторный JSON, сжатый gzip, обычно 512×512,
до трёх секунд, 30 или 60 кадров в секунду. FFmpeg и Pillow такой файл не
читают, поэтому кадры рисует rlottie — та же библиотека, которой стикеры
рисует сам Telegram (пакет rlottie-python, LGPL; DLL лежит отдельным
файлом рядом с программой).

Дальше .tgs идёт тем же путём, что анимированный WEBP: кадры раскладываются
в PNG со списком задержек, и общий конвейер собирает из них GIF, WEBP,
видео и пресеты площадок. Обратно, в .tgs, конвертировать нельзя: из
растровой картинки векторную анимацию не получить.
"""

import gzip
import logging
import os

from errors import LocalizedRuntimeError, LocalizedValueError

_log = logging.getLogger(__name__)

TGS_EXT = ".tgs"
# Если в файле не указана частота кадров — стандартная для стикеров.
FALLBACK_FPS = 30.0


def is_tgs(path):
    return os.path.splitext(path)[1].lower() == TGS_EXT


def rlottie_available():
    try:
        import rlottie_python  # noqa: F401
    except Exception:
        return False
    return True


class _Animation:
    """Открытая анимация: rlottie-объект, его размер, кадры и частота.

    Закрывается явно (with): объект rlottie держит разобранную сцену в
    памяти библиотеки, и сборщик мусора освобождал бы её когда придётся.
    """

    def __init__(self, path):
        try:
            from rlottie_python import LottieAnimation
            from rlottie_python import rlottie_wrapper
        except Exception:
            raise LocalizedRuntimeError("err_no_rlottie")
        # Пакет есть, а DLL не загрузилась (например, её не положили в
        # сборку): from_tgs бросил бы тот же OSError, что и на битом
        # архиве, и пользователь увидел бы «файл повреждён».
        if getattr(rlottie_wrapper, "RLOTTIE_LIB", None) is None:
            raise LocalizedRuntimeError("err_no_rlottie")
        try:
            # gzip.open внутри from_tgs: не-gzip и битый архив — исключение.
            animation = LottieAnimation.from_tgs(path)
        except (OSError, EOFError, UnicodeDecodeError, gzip.BadGzipFile):
            raise LocalizedValueError("err_bad_tgs", name=os.path.basename(path))
        # На неверном JSON rlottie не бросает исключение, а молча оставляет
        # пустой указатель — следующий вызов в библиотеку уронил бы процесс.
        if not getattr(animation, "animation_p", None):
            raise LocalizedValueError("err_bad_tgs", name=os.path.basename(path))
        self._animation = animation
        width, height = animation.lottie_animation_get_size()
        self.width = int(width) or 512
        self.height = int(height) or 512
        fps = float(animation.lottie_animation_get_framerate() or 0)
        self.fps = fps if fps > 0 else FALLBACK_FPS
        # rlottie считает кадры включительно с последним (op − ip + 1): у
        # стикера на 3 секунды при 60 fps это 181 кадр и 3,017 с, а
        # последний кадр совпадает с первым следующего круга. Число кадров
        # берётся из длительности (op − ip) / fps — тогда анимация
        # зацикливается без кадра-дубля и укладывается в лимит Telegram.
        duration = float(animation.lottie_animation_get_duration() or 0)
        total = int(animation.lottie_animation_get_totalframe())
        frames = round(duration * self.fps) if duration > 0 else total
        self.frames = max(1, min(frames, total) if total > 0 else frames)

    def render(self, index, width=None, height=None):
        """Кадр как RGBA-картинка Pillow. Вектор рисуется сразу в нужном
        размере — без потери чёткости при увеличении."""
        index = max(0, min(int(index), self.frames - 1))
        image = self._animation.render_pillow_frame(
            frame_num=index, width=int(width or self.width), height=int(height or self.height)
        )
        return image.convert("RGBA")

    def frame_at(self, seconds):
        return max(0, min(int((seconds or 0) * self.fps), self.frames - 1))

    def close(self):
        if self._animation is not None:
            self._animation.lottie_animation_destroy()
            self._animation = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def open_tgs(path):
    return _Animation(path)


def tgs_info(path):
    """Сведения в том же виде, что animation_info.animated_image_info."""
    with open_tgs(path) as animation:
        per_frame = 1000.0 / animation.fps
        return {
            "frames": animation.frames,
            "durations": [per_frame] * animation.frames,
            "duration": animation.frames / animation.fps,
            "fps": animation.fps,
            "loop": 0,
            "width": animation.width,
            "height": animation.height,
        }


def tgs_size(path):
    with open_tgs(path) as animation:
        return animation.width, animation.height


def representative_frame(path, size=None):
    """Кадр для миниатюры и предпросмотра — из середины анимации.

    Первый кадр у многих стикеров пустой или почти пустой: рисунок только
    появляется. Середина почти всегда показывает стикер целиком.
    """
    with open_tgs(path) as animation:
        width, height = animation.width, animation.height
        if size:
            scale = min(size / width, size / height, 1.0)
            width, height = max(1, round(width * scale)), max(1, round(height * scale))
        return animation.render(animation.frames // 2, width, height)


# Предпросмотр в чате: стикер проигрывается, как GIF и WEBP. Кадры рисуются
# мелко и не чаще 30 в секунду — для предпросмотра этого хватает, а файл
# получается в сотню килобайт и пишется за доли секунды.
PREVIEW_SIZE = 160
PREVIEW_MAX_FPS = 30.0


def preview_animation_path(path):
    """Где лежит проигрываемая копия стикера для предпросмотра.

    Имя зависит от пути, размера и времени изменения: правка стикера даёт
    новую копию, а не показывает старую.
    """
    import hashlib
    import tempfile

    try:
        stat = os.stat(path)
        key = f"{os.path.abspath(path)}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        key = os.path.abspath(path)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    folder = os.path.join(tempfile.gettempdir(), "dttconvert_preview")
    return os.path.join(folder, f"{digest}.webp")


def write_preview_animation(path):
    """Пишет анимированный WEBP для предпросмотра (если его ещё нет)."""
    target = preview_animation_path(path)
    if os.path.isfile(target):
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open_tgs(path) as animation:
        step = max(1, round(animation.fps / PREVIEW_MAX_FPS))
        scale = min(PREVIEW_SIZE / animation.width, PREVIEW_SIZE / animation.height, 1.0)
        width = max(1, round(animation.width * scale))
        height = max(1, round(animation.height * scale))
        frames = [animation.render(index, width, height)
                  for index in range(0, animation.frames, step)]
        frame_ms = 1000.0 * step / animation.fps
    # Сначала во временное имя: проигрыватель не должен открыть
    # недописанный файл, если предпросмотр попросят дважды подряд.
    partial = target + ".part"
    frames[0].save(partial, format="WEBP", save_all=True, append_images=frames[1:],
                   duration=round(frame_ms), loop=0, quality=80, method=0)
    os.replace(partial, target)
    return target


import os

from PIL import Image, ImageOps

from animation_info import animated_image_info
from errors import LocalizedRuntimeError, LocalizedValueError

from telegram_utils import (
    EMOJI_SIZE,
    MAX_STATIC_SIZE_BYTES,
    compute_sticker_size,
    static_image_extension,
)
from twitch_utils import TWITCH_MAX_STATIC_BYTES

try:  # HEIC/HEIF с iPhone читается через дополнительный плагин.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    # Без плагина не читаются только HEIC/HEIF, остальные форматы работают.
    pass

FORMAT_TO_PIL = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "avif": "AVIF",
}

FORMATS_WITHOUT_ALPHA = {"jpg", "jpeg", "bmp"}

# Форматы с параметром качества: только для них имеет смысл подбор под
# целевой размер файла. У PNG и BMP качества нет, там работает палитра.
LOSSY_PIL_FORMATS = {"JPEG", "WEBP", "AVIF"}

DEFAULT_IMAGE_QUALITY = 92

# Сжатие временных PNG-кадров: они живут секунды, и скорость важнее веса.
TEMP_PNG_COMPRESSION = 1

# Имя списка кадров для concat-демультиплексора FFmpeg.
FRAME_LIST_NAME = "frames.txt"


def save_within_limit(image, output_path, pil_format, limit_bytes):
    """Сохраняет картинку, укладываясь в лимит площадки.

    PNG без потерь: если он не влезает, уменьшаем палитру, а не размер —
    стикер обязан остаться 512 px по стороне. WEBP сжимаем качеством.
    Раньше лимита не было вовсе, и шумная картинка давала файл вдвое
    больше допустимого, который Telegram просто не принимал.
    """
    limit_kb = limit_bytes // 1024
    if pil_format in LOSSY_PIL_FORMATS:
        for quality in (92, 80, 65, 50, 35, 20):
            image.save(output_path, format=pil_format, quality=quality,
                       **({"method": 6} if pil_format == "WEBP" else {}))
            if os.path.getsize(output_path) <= limit_bytes:
                return
        # Раньше здесь был молчаливый выход, и наружу уходил файл больше
        # лимита — площадка отвергала его уже при загрузке.
        raise LocalizedRuntimeError(
            "err_image_over_limit", limit=limit_kb,
            got=os.path.getsize(output_path) // 1024,
        )

    image.save(output_path, format=pil_format, optimize=True)
    if os.path.getsize(output_path) <= limit_bytes:
        return

    has_alpha = image.mode in ("RGBA", "LA")
    for colors in (256, 128, 64, 32):
        try:
            quantized = image.quantize(
                colors=colors, method=Image.Quantize.FASTOCTREE
            )
        except (ValueError, OSError):
            break
        quantized.save(output_path, format=pil_format, optimize=True)
        if os.path.getsize(output_path) <= limit_bytes:
            return

    raise LocalizedRuntimeError(
        "err_image_over_limit_alpha" if has_alpha else "err_image_over_limit",
        limit=limit_kb, got=os.path.getsize(output_path) // 1024,
    )


def _ensure_valid_size(width, height):
    if width <= 0 or height <= 0:
        raise LocalizedValueError("err_zero_size")


def apply_transform(image, rotate=0, flip_horizontal=False, flip_vertical=False):
    """Поворот и отражение — в том же порядке, что у FFmpeg."""
    rotate = int(rotate) % 360
    if rotate:
        # У Pillow поворот против часовой стрелки, у нас — по часовой.
        clockwise = {
            90: Image.Transpose.ROTATE_270,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }.get(rotate)
        if clockwise is not None:
            image = image.transpose(clockwise)

    if flip_horizontal:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_vertical:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return image


class ImageProcessor:
    @staticmethod
    def compute_target_size(original_width, original_height, width, height, keep_aspect):
        _ensure_valid_size(original_width, original_height)
        width = int(width) if width else 0
        height = int(height) if height else 0
        if width <= 0 and height <= 0:
            return original_width, original_height
        if width > 0 and height <= 0:
            ratio = width / float(original_width)
            new_height = max(1, round(original_height * ratio))
            return width, new_height
        if height > 0 and width <= 0:
            ratio = height / float(original_height)
            new_width = max(1, round(original_width * ratio))
            return new_width, height
        if keep_aspect:
            width_ratio = width / float(original_width)
            height_ratio = height / float(original_height)
            ratio = min(width_ratio, height_ratio)
            new_width = max(1, round(original_width * ratio))
            new_height = max(1, round(original_height * ratio))
            return new_width, new_height
        return width, height

    @classmethod
    def convert_image(cls, input_path, output_path, output_format, width, height,
                      keep_aspect, transform=None, quality=None, target_bytes=None):
        output_format = output_format.lower()
        pil_format = FORMAT_TO_PIL.get(output_format)
        if pil_format is None:
            raise LocalizedValueError("err_unknown_format", fmt=output_format)

        with Image.open(input_path) as source_image:
            source_image.load()
            working = source_image.copy()
            if transform:
                working = apply_transform(
                    working, transform.rotate,
                    transform.flip_horizontal, transform.flip_vertical,
                )
            original_width, original_height = working.size
            target_width, target_height = cls.compute_target_size(
                original_width, original_height, width, height, keep_aspect
            )

            if (target_width, target_height) != (original_width, original_height):
                resized_image = working.resize(
                    (target_width, target_height), Image.LANCZOS
                )
            else:
                resized_image = working

            if output_format in FORMATS_WITHOUT_ALPHA:
                if resized_image.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", resized_image.size, (255, 255, 255))
                    converted = resized_image.convert("RGBA")
                    background.paste(converted, mask=converted.split()[-1])
                    resized_image = background
                elif resized_image.mode != "RGB":
                    resized_image = resized_image.convert("RGB")
            else:
                if pil_format == "PNG" and resized_image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                    resized_image = resized_image.convert("RGBA")
                if pil_format == "WEBP" and resized_image.mode not in ("RGB", "RGBA"):
                    resized_image = resized_image.convert("RGBA")

            # Целевой размер имеет смысл только там, где есть качество:
            # у PNG и BMP его подбирать нечем.
            if target_bytes and pil_format in LOSSY_PIL_FORMATS:
                save_within_limit(resized_image, output_path, pil_format, target_bytes)
                return

            save_kwargs = {}
            if pil_format == "JPEG":
                save_kwargs["quality"] = quality or DEFAULT_IMAGE_QUALITY
                save_kwargs["optimize"] = True
            elif pil_format == "WEBP":
                save_kwargs["quality"] = quality or DEFAULT_IMAGE_QUALITY
                save_kwargs["method"] = 6
            elif pil_format == "PNG":
                save_kwargs["optimize"] = True
            elif pil_format == "AVIF":
                save_kwargs["quality"] = quality or 80

            resized_image.save(output_path, format=pil_format, **save_kwargs)

    @classmethod
    def convert_telegram_static(cls, input_path, output_path, output_format,
                                transform=None, fill=False):
        """Конвертация в статичный TG-стикер или emoji (PNG/WEBP)."""
        fmt = output_format.lower()
        image_ext = static_image_extension(fmt)
        if image_ext is None:
            raise LocalizedValueError("err_unknown_format", fmt=output_format)

        pil_format = FORMAT_TO_PIL[image_ext]
        is_emoji = fmt.startswith("tg_emoji")

        with Image.open(input_path) as source_image:
            source_image.load()
            working = source_image.convert("RGBA")
            if transform:
                working = apply_transform(
                    working, transform.rotate,
                    transform.flip_horizontal, transform.flip_vertical,
                )
            original_width, original_height = working.size
            _ensure_valid_size(original_width, original_height)

            if is_emoji:
                result = cls._fit_into_square(working, EMOJI_SIZE, fill)
            else:
                target_width, target_height = compute_sticker_size(
                    original_width, original_height
                )
                result = working.resize((target_width, target_height), Image.LANCZOS)

            save_within_limit(result, output_path, pil_format, MAX_STATIC_SIZE_BYTES)

    @staticmethod
    def _fit_into_square(image, size, fill=False):
        """Приводит картинку к квадрату.

        fill=False — вписывает целиком, оставляя поля прозрачными;
        fill=True — заполняет квадрат, обрезая лишнее по краям от центра.
        """
        width, height = image.size
        _ensure_valid_size(width, height)
        if fill:
            return ImageOps.fit(image, (size, size), Image.LANCZOS,
                                centering=(0.5, 0.5))
        ratio = min(size / width, size / height)
        new_width = max(1, round(width * ratio))
        new_height = max(1, round(height * ratio))
        resized = image.resize((new_width, new_height), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(resized, ((size - new_width) // 2, (size - new_height) // 2), resized)
        return canvas

    @classmethod
    def convert_square_static(cls, input_path, output_path, size, limit_bytes,
                              transform=None, fill=False, pil_format="PNG"):
        """Квадратная статичная картинка с прозрачным фоном под лимит площадки."""
        with Image.open(input_path) as source_image:
            source_image.load()
            working = source_image.convert("RGBA")
            if transform:
                working = apply_transform(
                    working, transform.rotate,
                    transform.flip_horizontal, transform.flip_vertical,
                )
            canvas = cls._fit_into_square(working, size, fill)
            save_within_limit(canvas, output_path, pil_format, limit_bytes)

    @classmethod
    def convert_twitch_static(cls, input_path, output_path, size, transform=None,
                              fill=False, limit_bytes=TWITCH_MAX_STATIC_BYTES):
        """Квадратный PNG для смайлика, значка или иконки баллов Twitch."""
        cls.convert_square_static(
            input_path, output_path, size, limit_bytes, transform, fill
        )

    @classmethod
    def convert_discord_static(cls, input_path, output_path, size, limit_bytes,
                               transform=None, fill=False):
        """Создаёт квадратный PNG для стикера или эмодзи Discord."""
        cls.convert_square_static(input_path, output_path, size, limit_bytes,
                                  transform, fill)

    @staticmethod
    def save_frame_at(input_path, output_path, seconds=0.0, ffprobe_path=None):
        """Сохраняет кадр анимации, приходящийся на указанную секунду.

        Нужен, когда из анимированной картинки делают статичный результат:
        раскладывать всю анимацию ради одного кадра незачем.
        """
        frame_index = 0
        if seconds and seconds > 0:
            info = animated_image_info(input_path, ffprobe_path) or {}
            elapsed = 0.0
            for index, duration_ms in enumerate(info.get("durations") or []):
                elapsed += float(duration_ms) / 1000.0
                frame_index = index
                if elapsed > seconds:
                    break

        with Image.open(input_path) as source_image:
            frame_count = getattr(source_image, "n_frames", 1)
            source_image.seek(max(0, min(frame_index, frame_count - 1)))
            source_image.convert("RGBA").save(
                output_path, format="PNG", compress_level=TEMP_PNG_COMPRESSION
            )

    @staticmethod
    def dump_animation_frames(input_path, frames_dir, ffprobe_path=None):
        """Раскладывает анимацию в PNG-кадры и список для concat-демультиплексора.

        Через список FFmpeg получает и полноценную 8-битную полупрозрачность,
        и точные покадровые задержки. Промежуточный GIF, который стоял здесь
        раньше, схлопывал альфу до одного бита и рвал мягкие края эмодзи.

        Кадры пишутся на диск по одному: держать распакованную анимацию
        целиком в памяти слишком дорого.
        """
        info = animated_image_info(input_path, ffprobe_path) or {}
        os.makedirs(frames_dir, exist_ok=True)

        with Image.open(input_path) as source_image:
            frame_count = getattr(source_image, "n_frames", 1)
            durations = list(info.get("durations") or [])
            if len(durations) < frame_count:
                fallback = durations[-1] if durations else source_image.info.get("duration", 100)
                durations += [float(fallback or 100)] * (frame_count - len(durations))

            names = []
            for index in range(frame_count):
                source_image.seek(index)
                name = f"frame_{index:05d}.png"
                # Кадры временные и живут секунды, поэтому сжимаются слабо:
                # на уровне по умолчанию PNG сжимается в разы дольше, а
                # выигрыш в весе тут никому не нужен.
                source_image.convert("RGBA").save(
                    os.path.join(frames_dir, name), format="PNG",
                    compress_level=TEMP_PNG_COMPRESSION,
                )
                names.append(name)

        list_path = os.path.join(frames_dir, FRAME_LIST_NAME)
        with open(list_path, "w", encoding="utf-8") as handle:
            handle.write("ffconcat version 1.0\n")
            for index, name in enumerate(names):
                seconds = max(0.001, float(durations[index]) / 1000.0)
                handle.write(f"file '{name}'\nduration {seconds:.4f}\n")
            if names:
                # Последний кадр повторяется без duration — иначе concat
                # отбрасывает его задержку и анимация теряет один кадр.
                handle.write(f"file '{names[-1]}'\n")
        return list_path

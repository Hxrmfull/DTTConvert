"""Утилиты для подготовки стикеров и emoji по спецификации Telegram.

Документация: https://core.telegram.org/stickers
"""

from i18n import tr

STICKER_MAX_SIDE = 512
EMOJI_SIZE = 100
MAX_VIDEO_DURATION_SEC = 3.0
MAX_VIDEO_FPS = 30
MAX_WEBM_SIZE_BYTES = 256 * 1024
# Лимит Telegram на статичный стикер/emoji (PNG или WEBP).
MAX_STATIC_SIZE_BYTES = 512 * 1024

TG_STICKER_FORMATS = {"tg_sticker_png", "tg_sticker_webp", "tg_sticker_webm"}
TG_EMOJI_FORMATS = {"tg_emoji_png", "tg_emoji_webp", "tg_emoji_webm"}
TG_ALL_FORMATS = TG_STICKER_FORMATS | TG_EMOJI_FORMATS

TG_FORMAT_LABELS = {
    "tg_sticker_png": "TG Стикер (PNG)",
    "tg_sticker_webp": "TG Стикер (WEBP)",
    "tg_sticker_webm": "TG Стикер (WEBM)",
    "tg_emoji_png": "TG Emoji (PNG)",
    "tg_emoji_webp": "TG Emoji (WEBP)",
    "tg_emoji_webm": "TG Emoji (WEBM)",
}


def is_telegram_format(output_format):
    return output_format.lower() in TG_ALL_FORMATS


def is_telegram_video_format(output_format):
    fmt = output_format.lower()
    return fmt in ("tg_sticker_webm", "tg_emoji_webm")


def is_telegram_emoji_format(output_format):
    return output_format.lower() in TG_EMOJI_FORMATS


def compute_sticker_size(original_width, original_height):
    """Одна сторона ровно 512 px, другая — 512 или меньше."""
    if original_width <= 0 or original_height <= 0:
        return STICKER_MAX_SIDE, STICKER_MAX_SIDE
    if original_width >= original_height:
        new_width = STICKER_MAX_SIDE
        new_height = max(1, round(original_height * STICKER_MAX_SIDE / original_width))
    else:
        new_height = STICKER_MAX_SIDE
        new_width = max(1, round(original_width * STICKER_MAX_SIDE / original_height))
    return new_width, new_height


def sticker_scale_filter():
    """FFmpeg-фильтр: одна сторона ровно 512 px, пропорции сохранены."""
    return (
        "scale="
        "'if(eq(a,1),512,if(gt(a,1),512,-2))':"
        "'if(eq(a,1),512,if(gt(a,1),-2,512))'"
    )


def emoji_scale_filter():
    """FFmpeg-фильтр: ровно 100x100 с прозрачным фоном."""
    return (
        "scale=100:100:force_original_aspect_ratio=decrease,"
        "pad=100:100:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    )


def build_telegram_video_filter(target, max_duration=MAX_VIDEO_DURATION_SEC,
                                extra_filters=None):
    """Цепочка фильтров: обрезка по длительности + правки кадра + масштаб.

    extra_filters — ручные правки геометрии (кадрирование, поворот). Они
    идут до масштабирования: обрезать нужно исходный кадр, а не уже
    подогнанный под 512 px.
    """
    scale = sticker_scale_filter() if target == "sticker" else emoji_scale_filter()
    parts = [f"trim=duration={max_duration}", "setpts=PTS-STARTPTS"]
    parts.extend(extra_filters or [])
    parts.append(scale)
    return ",".join(parts)


def static_image_extension(output_format):
    fmt = output_format.lower()
    if fmt.endswith("_png"):
        return "png"
    if fmt.endswith("_webp"):
        return "webp"
    return None


def validate_webm_file(path, duration_sec=None):
    """Проверка выходного WEBM на соответствие лимитам Telegram."""
    import os

    issues = []
    size = os.path.getsize(path)
    if size > MAX_WEBM_SIZE_BYTES:
        issues.append(
            f"Размер файла {size // 1024} KB превышает лимит 256 KB. "
            "Попробуйте упростить анимацию или уменьшить длительность."
        )
    if duration_sec is not None and duration_sec > MAX_VIDEO_DURATION_SEC + 0.05:
        issues.append(
            f"Длительность {duration_sec:.2f} сек превышает лимит {MAX_VIDEO_DURATION_SEC:.0f} сек."
        )
    return issues


def telegram_hint(output_format):
    fmt = output_format.lower()
    if fmt in ("tg_sticker_png", "tg_sticker_webp"):
        return tr("hint_tg_sticker_static", fmt=static_image_extension(fmt).upper())
    if fmt in ("tg_emoji_png", "tg_emoji_webp"):
        return tr("hint_tg_emoji_static", fmt=static_image_extension(fmt).upper())
    # Подсказки намеренно короткие: на вкладке Telegram и без них тесно,
    # а третья строка выталкивала содержимое за пределы карточки.
    if fmt == "tg_sticker_webm":
        return tr("hint_tg_sticker_webm")
    if fmt == "tg_emoji_webm":
        return tr("hint_tg_emoji_webm")
    return ""

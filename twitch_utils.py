"""Параметры выходных файлов для смайликов Twitch."""

from i18n import tr

TWITCH_STATIC_FORMATS = {"twitch_static_112", "twitch_static_pack"}
TWITCH_ANIMATED_FORMATS = {"twitch_animated_112", "twitch_animated_pack"}
TWITCH_ALL_FORMATS = TWITCH_STATIC_FORMATS | TWITCH_ANIMATED_FORMATS

TWITCH_FORMAT_LABELS = {
    "twitch_static_112": "Twitch PNG (112×112)",
    "twitch_static_pack": "Twitch PNG комплект (28/56/112)",
    "twitch_animated_112": "Twitch GIF (112×112)",
    "twitch_animated_pack": "Twitch GIF комплект (28/56/112)",
}

# Короткие подписи для кнопок-пресетов на вкладке Twitch.
TWITCH_PRESET_CODES = [
    "twitch_static_112", "twitch_static_pack",
    "twitch_animated_112", "twitch_animated_pack",
]

_PRESET_LABEL_KEYS = {
    "twitch_static_112": "preset_twitch_png",
    "twitch_static_pack": "preset_twitch_png_pack",
    "twitch_animated_112": "preset_twitch_gif",
    "twitch_animated_pack": "preset_twitch_gif_pack",
}


def twitch_preset_buttons():
    """Пары «подпись, код» на текущем языке."""
    return [(tr(_PRESET_LABEL_KEYS[code]), code) for code in TWITCH_PRESET_CODES]

TWITCH_EMOTE_SIZES = (28, 56, 112)

# Лимиты Twitch для анимированных смайликов.
TWITCH_MAX_FRAMES = 60
TWITCH_MAX_GIF_BYTES = 1024 * 1024
# Лимит Twitch на статичный смайлик PNG.
TWITCH_MAX_STATIC_BYTES = 1024 * 1024


def is_twitch_format(output_format):
    return output_format.lower() in TWITCH_ALL_FORMATS


def is_twitch_animated_format(output_format):
    return output_format.lower() in TWITCH_ANIMATED_FORMATS


def twitch_sizes(output_format):
    return TWITCH_EMOTE_SIZES if output_format.endswith("_pack") else (112,)


def twitch_hint(output_format):
    """Пояснение к выбранному пресету Twitch, включая проверяемые лимиты."""
    fmt = output_format.lower()
    sizes = tr("twitch_sizes_pack") if fmt.endswith("_pack") else tr("twitch_sizes_one")
    if is_twitch_animated_format(fmt):
        limit_mb = TWITCH_MAX_GIF_BYTES / (1024 * 1024)
        limit = (tr("mb", value=f"{limit_mb:g}") if limit_mb >= 1
                 else tr("kb", value=TWITCH_MAX_GIF_BYTES // 1024))
        return tr("hint_twitch_animated", sizes=sizes,
                  frames=TWITCH_MAX_FRAMES, limit=limit)
    return tr("hint_twitch_static", sizes=sizes)

"""Параметры выходных файлов для вкладки Twitch.

Кроме смайликов самого Twitch здесь значки подписки, иконки наград за
баллы канала и смайлики сторонних расширений чата — 7TV и BTTV: все они
живут в чате Twitch, и пользователю их удобнее искать на одной вкладке.

Требования площадок:
- смайлики Twitch — PNG или GIF, 28/56/112 px, до 1 МБ, GIF до 60 кадров;
- значки подписки — PNG 18/36/72 px, до 25 КБ каждый
  (https://help.twitch.tv/s/article/subscriber-badge-guide);
- иконки наград за баллы канала — PNG 28/56/112 px, до 25 КБ каждая;
- 7TV — до 128×128, WEBP/GIF/PNG, до 150 кадров анимации;
- BTTV — 112×112, PNG или GIF, до 1 МБ.
"""

from dataclasses import dataclass

from i18n import tr

# Лимиты Twitch для смайликов.
TWITCH_MAX_FRAMES = 60
TWITCH_MAX_GIF_BYTES = 1024 * 1024
TWITCH_MAX_STATIC_BYTES = 1024 * 1024
TWITCH_EMOTE_SIZES = (28, 56, 112)

TWITCH_BADGE_SIZES = (18, 36, 72)
TWITCH_POINTS_SIZES = (28, 56, 112)
TWITCH_SMALL_ICON_BYTES = 25 * 1024

SEVENTV_SIZE = 128
SEVENTV_MAX_BYTES = 1024 * 1024
SEVENTV_MAX_FRAMES = 150
SEVENTV_FPS_CAP = 30

BTTV_SIZE = 112
BTTV_MAX_BYTES = 1024 * 1024
BTTV_FPS_CAP = 25

# Частота кадров анимированного смайлика Twitch: не выше этой, даже если
# лимит кадров позволяет больше, — так GIF укладывается в вес.
TWITCH_FPS_CAP = 15
# Ниже этой частоты анимация смотрится слайд-шоу: стоит переспросить.
TWITCH_MIN_SMOOTH_FPS = 8

# Вид результата: всегда статичный PNG, всегда GIF или «по исходнику» —
# анимация из видео и анимированных картинок, PNG из обычных.
KIND_STATIC = "static"
KIND_GIF = "gif"
KIND_AUTO_WEBP = "auto_webp"
KIND_AUTO_GIF = "auto_gif"


@dataclass(frozen=True)
class SquarePreset:
    """Квадратная картинка одного или нескольких размеров под лимит веса."""

    sizes: tuple
    max_bytes: int
    kind: str
    # Суффикс имени файла; {size} подставляется для комплектов.
    suffix: str
    max_frames: int = None
    fps_cap: int = TWITCH_FPS_CAP

    @property
    def is_pack(self):
        return len(self.sizes) > 1


TWITCH_PRESETS = {
    "twitch_static_112": SquarePreset((112,), TWITCH_MAX_STATIC_BYTES, KIND_STATIC,
                                      "_twitch_{size}"),
    "twitch_static_pack": SquarePreset(TWITCH_EMOTE_SIZES, TWITCH_MAX_STATIC_BYTES,
                                       KIND_STATIC, "_twitch_{size}"),
    "twitch_animated_112": SquarePreset((112,), TWITCH_MAX_GIF_BYTES, KIND_GIF,
                                        "_twitch_{size}", TWITCH_MAX_FRAMES),
    "twitch_animated_pack": SquarePreset(TWITCH_EMOTE_SIZES, TWITCH_MAX_GIF_BYTES,
                                         KIND_GIF, "_twitch_{size}", TWITCH_MAX_FRAMES),
    "twitch_badge_pack": SquarePreset(TWITCH_BADGE_SIZES, TWITCH_SMALL_ICON_BYTES,
                                      KIND_STATIC, "_twitch_badge_{size}"),
    "twitch_points_pack": SquarePreset(TWITCH_POINTS_SIZES, TWITCH_SMALL_ICON_BYTES,
                                       KIND_STATIC, "_twitch_points_{size}"),
    "seventv_emote": SquarePreset((SEVENTV_SIZE,), SEVENTV_MAX_BYTES, KIND_AUTO_WEBP,
                                  "_7tv", SEVENTV_MAX_FRAMES, SEVENTV_FPS_CAP),
    "bttv_emote": SquarePreset((BTTV_SIZE,), BTTV_MAX_BYTES, KIND_AUTO_GIF,
                               "_bttv", None, BTTV_FPS_CAP),
}

TWITCH_STATIC_FORMATS = {code for code, preset in TWITCH_PRESETS.items()
                         if preset.kind == KIND_STATIC}
TWITCH_ANIMATED_FORMATS = {code for code, preset in TWITCH_PRESETS.items()
                           if preset.kind == KIND_GIF}
# Анимированы или нет — решает исходник.
TWITCH_AUTO_FORMATS = {code for code, preset in TWITCH_PRESETS.items()
                       if preset.kind in (KIND_AUTO_WEBP, KIND_AUTO_GIF)}
TWITCH_ALL_FORMATS = set(TWITCH_PRESETS)

# Колонки кнопок на вкладке Twitch: смайлики Twitch отдельно от значков
# и смайликов расширений.
TWITCH_PRESET_COLUMNS = [
    ("col_twitch_emotes", ["twitch_static_112", "twitch_static_pack",
                           "twitch_animated_112", "twitch_animated_pack"]),
    ("col_twitch_more", ["twitch_badge_pack", "twitch_points_pack",
                         "seventv_emote", "bttv_emote"]),
]
# Плоский список — для тестов и старого кода.
TWITCH_PRESET_CODES = [code for _caption, codes in TWITCH_PRESET_COLUMNS
                       for code in codes]

_PRESET_LABEL_KEYS = {
    "twitch_static_112": "preset_twitch_png",
    "twitch_static_pack": "preset_twitch_png_pack",
    "twitch_animated_112": "preset_twitch_gif",
    "twitch_animated_pack": "preset_twitch_gif_pack",
    "twitch_badge_pack": "preset_twitch_badge",
    "twitch_points_pack": "preset_twitch_points",
    "seventv_emote": "preset_7tv",
    "bttv_emote": "preset_bttv",
}


def twitch_preset_label(code):
    return tr(_PRESET_LABEL_KEYS[code])


def twitch_preset_buttons():
    """Пары «подпись, код» на текущем языке."""
    return [(twitch_preset_label(code), code) for code in TWITCH_PRESET_CODES]


def twitch_preset(output_format):
    return TWITCH_PRESETS.get(output_format.lower())


def twitch_effective_fps(duration):
    """Какую частоту кадров даст лимит в 60 кадров на такой длительности."""
    if not duration or duration <= 0:
        return TWITCH_FPS_CAP
    return min(TWITCH_FPS_CAP, TWITCH_MAX_FRAMES / float(duration))


def twitch_smooth_duration_limit():
    """Самая длинная анимация, которая ещё остаётся плавной."""
    return TWITCH_MAX_FRAMES / float(TWITCH_MIN_SMOOTH_FPS)


def is_twitch_format(output_format):
    return output_format.lower() in TWITCH_ALL_FORMATS


def is_twitch_animated_format(output_format):
    """Всегда анимированный результат (GIF-смайлик Twitch)."""
    return output_format.lower() in TWITCH_ANIMATED_FORMATS


def is_twitch_auto_format(output_format):
    """Анимация или статика — по исходнику (7TV, BTTV)."""
    return output_format.lower() in TWITCH_AUTO_FORMATS


def twitch_sizes(output_format):
    preset = twitch_preset(output_format)
    return preset.sizes if preset else (112,)


def _limit_text(limit_bytes):
    if limit_bytes >= 1024 * 1024:
        return tr("mb", value=f"{limit_bytes / (1024 * 1024):g}")
    return tr("kb", value=limit_bytes // 1024)


def _sizes_text(sizes):
    if len(sizes) == 1:
        return tr("twitch_sizes_one_n", size=sizes[0])
    return tr("twitch_sizes_set", sizes="/".join(str(size) for size in sizes),
              count=len(sizes))


def twitch_hint(output_format):
    """Пояснение к выбранному пресету, включая проверяемые лимиты."""
    fmt = output_format.lower()
    preset = twitch_preset(fmt)
    if preset is None:
        return ""
    sizes = _sizes_text(preset.sizes)
    limit = _limit_text(preset.max_bytes)
    if fmt == "twitch_badge_pack":
        return tr("hint_twitch_badge", sizes=sizes, limit=limit)
    if fmt == "twitch_points_pack":
        return tr("hint_twitch_points", sizes=sizes, limit=limit)
    if fmt == "seventv_emote":
        return tr("hint_7tv", size=preset.sizes[0], limit=limit,
                  frames=preset.max_frames)
    if fmt == "bttv_emote":
        return tr("hint_bttv", size=preset.sizes[0], limit=limit)
    if preset.kind == KIND_GIF:
        return tr("hint_twitch_animated", sizes=sizes,
                  frames=preset.max_frames, limit=limit)
    return tr("hint_twitch_static", sizes=sizes)

"""Kick и YouTube: смайлики и значки под требования площадок.

Устроены как пресеты Twitch — квадрат одного или нескольких размеров
под лимит веса (SquarePreset), и обрабатываются тем же кодом. Здесь
только числа, подписи и подсказки; вкладки в окне собираются по этим
описаниям общим кодом, а не отдельным на каждую площадку.

Требования площадок:
- Kick, смайлик: PNG или GIF, до 500×500, меньше 1 МБ; в чате показывается
  в 28, 56 и 112 px (https://help.kick.com/en/articles/7113467). GIF
  делается 256 px: 500 px анимации почти никогда не укладывается в 1 МБ,
  а крупнее 112 px смайлик в чате не бывает;
- Kick, значок подписки: PNG с прозрачным фоном
  (https://help.kick.com/en/articles/11390623); размер Kick не называет,
  обычно загружают 36×36, поэтому комплект 36 и 72 px — для чётких экранов;
- YouTube, эмодзи канала: от 48×48 до 480×480, меньше 1 МБ; GIF YouTube
  показывает неподвижным (https://support.google.com/youtube/answer/7544492);
- YouTube, значок спонсора: PNG или JPEG не меньше 32×32, меньше 1 МБ,
  в чате — 16 px (там же).

«Меньше 1 МБ» — это 1 000 000 байт: в какой системе счёт у площадок,
не сказано, а так файл подходит при любом прочтении.
"""

from dataclasses import dataclass

from i18n import tr
from twitch_utils import KIND_GIF, KIND_STATIC, SquarePreset

ONE_MB = 1_000_000

KICK_EMOTE_SIZE = 500
KICK_ANIMATED_SIZE = 256
KICK_BADGE_SIZES = (36, 72)
KICK_MAX_BYTES = ONE_MB
KICK_FPS_CAP = 20

YOUTUBE_EMOJI_SIZE = 480
YOUTUBE_BADGE_SIZE = 128
YOUTUBE_MAX_BYTES = ONE_MB

KICK_PRESETS = {
    "kick_emote": SquarePreset((KICK_EMOTE_SIZE,), KICK_MAX_BYTES, KIND_STATIC, "_kick"),
    "kick_emote_gif": SquarePreset((KICK_ANIMATED_SIZE,), KICK_MAX_BYTES, KIND_GIF,
                                   "_kick", None, KICK_FPS_CAP),
    "kick_badge_pack": SquarePreset(KICK_BADGE_SIZES, KICK_MAX_BYTES, KIND_STATIC,
                                    "_kick_badge_{size}"),
}

YOUTUBE_PRESETS = {
    "youtube_emoji": SquarePreset((YOUTUBE_EMOJI_SIZE,), YOUTUBE_MAX_BYTES, KIND_STATIC,
                                  "_yt_emoji"),
    "youtube_badge": SquarePreset((YOUTUBE_BADGE_SIZE,), YOUTUBE_MAX_BYTES, KIND_STATIC,
                                  "_yt_badge"),
}


@dataclass(frozen=True)
class SquarePlatform:
    """Площадка, у которой все пресеты — квадраты под лимит веса."""

    key: str
    title: str
    presets: dict
    # Колонки кнопок: (ключ подписи колонки, [коды пресетов]).
    columns: tuple
    default: str

    def is_format(self, output_format):
        return (output_format or "").lower() in self.presets

    def preset(self, output_format):
        return self.presets.get((output_format or "").lower())


KICK = SquarePlatform(
    "kick", "Kick", KICK_PRESETS,
    (("col_kick_emotes", ("kick_emote", "kick_emote_gif")),
     ("col_kick_more", ("kick_badge_pack",))),
    "kick_emote",
)
YOUTUBE = SquarePlatform(
    "youtube", "YouTube", YOUTUBE_PRESETS,
    (("col_yt_members", ("youtube_emoji", "youtube_badge")),),
    "youtube_emoji",
)
# Порядок — порядок вкладок после WhatsApp.
SQUARE_PLATFORMS = (KICK, YOUTUBE)


def square_platform(output_format):
    """Площадка Kick или YouTube, к которой относится формат, или None."""
    for platform in SQUARE_PLATFORMS:
        if platform.is_format(output_format):
            return platform
    return None


def square_preset(output_format):
    platform = square_platform(output_format)
    return platform.preset(output_format) if platform else None


def is_square_platform_format(output_format):
    return square_platform(output_format) is not None


# Подписи кнопок (preset_*) и строк списка форматов (lbl_*).
PRESET_LABEL_KEYS = {code: f"preset_{code}" for platform in SQUARE_PLATFORMS
                     for code in platform.presets}
FORMAT_LABEL_KEYS = {code: f"lbl_{code}" for platform in SQUARE_PLATFORMS
                     for code in platform.presets}


def square_preset_label(code):
    return tr(PRESET_LABEL_KEYS[code])


def _limit_text(limit_bytes):
    return tr("mb", value=f"{limit_bytes / ONE_MB:g}")


def square_hint(output_format):
    """Пояснение к выбранному пресету Kick или YouTube."""
    code = (output_format or "").lower()
    preset = square_preset(code)
    if preset is None:
        return ""
    sizes = "/".join(str(size) for size in preset.sizes)
    return tr(f"hint_{code}", size=preset.sizes[0], sizes=sizes,
              limit=_limit_text(preset.max_bytes))

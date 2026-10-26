"""Параметры стикеров и эмодзи Discord.

Документация: https://support.discord.com/hc/articles/4402687377815 (стикеры)
и https://support.discord.com/hc/articles/360036479811 (эмодзи).

Устроено так же, как telegram_utils и twitch_utils: коды форматов, лимиты
и подсказки в одном месте, чтобы интерфейс и обработчик не разъезжались.
"""

from i18n import tr

STICKER_SIZE = 320
EMOJI_SIZE = 128

MAX_STICKER_BYTES = 512 * 1024
MAX_EMOJI_BYTES = 256 * 1024

# Анимированный стикер Discord: не длиннее 5 секунд и не больше 60 кадров
# в секунду. Кадры сверх лимита приложение срезает подбором FPS.
MAX_STICKER_DURATION_SEC = 5.0
MAX_ANIMATION_FPS = 30

DISCORD_STICKER_FORMATS = {"discord_sticker_png", "discord_sticker_apng"}
DISCORD_EMOJI_FORMATS = {"discord_emoji_png", "discord_emoji_gif"}
DISCORD_ALL_FORMATS = DISCORD_STICKER_FORMATS | DISCORD_EMOJI_FORMATS

# Анимированные варианты: им нужен исходник с несколькими кадрами.
DISCORD_ANIMATED_FORMATS = {"discord_sticker_apng", "discord_emoji_gif"}

DISCORD_FORMAT_LABELS = {
    "discord_sticker_png": "DC Стикер (PNG)",
    "discord_sticker_apng": "DC Стикер (APNG)",
    "discord_emoji_png": "DC Эмодзи (PNG)",
    "discord_emoji_gif": "DC Эмодзи (GIF)",
}

# Колонки кнопок-пресетов на вкладке Discord: стикеры отдельно от эмодзи,
# иначе «Стикер APNG» оказывается в одной строке с «Эмодзи PNG».
DISCORD_PRESET_COLUMNS = [
    (STICKER_SIZE, ["discord_sticker_png", "discord_sticker_apng"]),
    (EMOJI_SIZE, ["discord_emoji_png", "discord_emoji_gif"]),
]


def is_discord_format(output_format):
    return output_format.lower() in DISCORD_ALL_FORMATS


def is_discord_animated_format(output_format):
    return output_format.lower() in DISCORD_ANIMATED_FORMATS


def is_discord_emoji_format(output_format):
    return output_format.lower() in DISCORD_EMOJI_FORMATS


def discord_size(output_format):
    """Сторона квадрата в пикселях для выбранного пресета."""
    return EMOJI_SIZE if is_discord_emoji_format(output_format) else STICKER_SIZE


def discord_byte_limit(output_format):
    """Предельный размер готового файла в байтах."""
    return MAX_EMOJI_BYTES if is_discord_emoji_format(output_format) else MAX_STICKER_BYTES


def discord_extension(output_format):
    fmt = output_format.lower()
    if fmt.endswith("_apng"):
        return "png"
    if fmt.endswith("_gif"):
        return "gif"
    if fmt.endswith("_png"):
        return "png"
    return None


def discord_suffix(output_format):
    """Суффикс имени файла, чтобы результат не путался с исходником."""
    return "_dc_emoji" if is_discord_emoji_format(output_format) else "_dc_sticker"


def _limit_text(limit_bytes):
    return tr("kb", value=limit_bytes // 1024)


def discord_hint(output_format):
    """Пояснение к выбранному пресету — те же лимиты, что проверяет обработчик."""
    fmt = output_format.lower()
    if fmt == "discord_sticker_png":
        return tr("hint_dc_sticker_png", size=STICKER_SIZE,
                  limit=_limit_text(MAX_STICKER_BYTES))
    if fmt == "discord_sticker_apng":
        return tr("hint_dc_sticker_apng", size=STICKER_SIZE,
                  duration=MAX_STICKER_DURATION_SEC,
                  limit=_limit_text(MAX_STICKER_BYTES))
    if fmt == "discord_emoji_png":
        return tr("hint_dc_emoji_png", size=EMOJI_SIZE,
                  limit=_limit_text(MAX_EMOJI_BYTES))
    if fmt == "discord_emoji_gif":
        return tr("hint_dc_emoji_gif", size=EMOJI_SIZE,
                  limit=_limit_text(MAX_EMOJI_BYTES))
    return ""

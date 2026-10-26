"""Параметры стикеров WhatsApp.

Документация: https://github.com/WhatsApp/stickers/blob/main/Android/README.md

- стикер — WEBP ровно 512×512, статичный до 100 КБ;
- анимированный стикер — до 500 КБ и не длиннее 10 секунд, кадр не
  короче 8 мс (при наших частотах это выполняется само собой);
- иконка набора — статичная 96×96, до 50 КБ.

Устроено так же, как telegram_utils и discord_utils: коды форматов,
лимиты и подсказки в одном месте.
"""

from i18n import tr

STICKER_SIZE = 512
TRAY_SIZE = 96

MAX_STATIC_BYTES = 100 * 1024
MAX_ANIMATED_BYTES = 500 * 1024
MAX_TRAY_BYTES = 50 * 1024
MAX_ANIMATION_SEC = 10.0
# Выше этой частоты анимированный WEBP 512×512 почти никогда не влезает
# в 500 КБ, а глазу хватает и её.
MAX_ANIMATION_FPS = 20

WHATSAPP_STATIC = "whatsapp_static"
WHATSAPP_ANIMATED = "whatsapp_animated"
WHATSAPP_TRAY = "whatsapp_tray"
WHATSAPP_ALL_FORMATS = {WHATSAPP_STATIC, WHATSAPP_ANIMATED, WHATSAPP_TRAY}

WHATSAPP_PRESET_COLUMNS = [
    ("col_wa_sticker", [WHATSAPP_STATIC, WHATSAPP_ANIMATED]),
    ("col_wa_pack", [WHATSAPP_TRAY]),
]

_PRESET_LABEL_KEYS = {
    WHATSAPP_STATIC: "preset_wa_static",
    WHATSAPP_ANIMATED: "preset_wa_animated",
    WHATSAPP_TRAY: "preset_wa_tray",
}


def whatsapp_preset_label(code):
    return tr(_PRESET_LABEL_KEYS[code])


def is_whatsapp_format(output_format):
    return output_format.lower() in WHATSAPP_ALL_FORMATS


def is_whatsapp_animated_format(output_format):
    return output_format.lower() == WHATSAPP_ANIMATED


def whatsapp_size(output_format):
    return TRAY_SIZE if output_format.lower() == WHATSAPP_TRAY else STICKER_SIZE


def whatsapp_byte_limit(output_format):
    fmt = output_format.lower()
    if fmt == WHATSAPP_TRAY:
        return MAX_TRAY_BYTES
    if fmt == WHATSAPP_ANIMATED:
        return MAX_ANIMATED_BYTES
    return MAX_STATIC_BYTES


def whatsapp_extension(output_format):
    return "png" if output_format.lower() == WHATSAPP_TRAY else "webp"


def whatsapp_suffix(output_format):
    return "_wa_tray" if output_format.lower() == WHATSAPP_TRAY else "_wa_sticker"


def whatsapp_hint(output_format):
    fmt = output_format.lower()
    if fmt == WHATSAPP_STATIC:
        return tr("hint_wa_static", size=STICKER_SIZE, limit=MAX_STATIC_BYTES // 1024)
    if fmt == WHATSAPP_ANIMATED:
        return tr("hint_wa_animated", size=STICKER_SIZE,
                  limit=MAX_ANIMATED_BYTES // 1024, duration=f"{MAX_ANIMATION_SEC:g}")
    if fmt == WHATSAPP_TRAY:
        return tr("hint_wa_tray", size=TRAY_SIZE, limit=MAX_TRAY_BYTES // 1024)
    return ""

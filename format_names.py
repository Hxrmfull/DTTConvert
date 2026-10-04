"""Подписи форматов на текущем языке.

Лежат отдельно от окна: подпись нужна и обработчику — в тексте ошибки
«такой-то пресет делается только из видео», — а тянуть ради этого
главное окно в поток обработки нельзя.
"""

from i18n import tr
from stream_platforms import FORMAT_LABEL_KEYS as SQUARE_FORMAT_LABEL_KEYS

# Названия обычных форматов от языка не зависят.
PLAIN_FORMAT_NAMES = {
    "jpg": "JPG", "png": "PNG", "webp": "WEBP", "bmp": "BMP", "avif": "AVIF",
    "gif": "GIF", "apng": "APNG",
    "mp4": "MP4", "webm": "WEBM", "avi": "AVI",
    "mp3": "MP3", "m4a": "M4A · AAC", "wav": "WAV",
}

# Пресеты площадок: ключи перевода подписей.
PLATFORM_LABEL_KEYS = {
    "tg_sticker_png": "lbl_tg_sticker_png",
    "tg_sticker_webp": "lbl_tg_sticker_webp",
    "tg_sticker_webm": "lbl_tg_sticker_webm",
    "tg_emoji_png": "lbl_tg_emoji_png",
    "tg_emoji_webp": "lbl_tg_emoji_webp",
    "tg_emoji_webm": "lbl_tg_emoji_webm",
    "twitch_static_112": "lbl_twitch_static_112",
    "twitch_static_pack": "lbl_twitch_static_pack",
    "twitch_animated_112": "lbl_twitch_animated_112",
    "twitch_animated_pack": "lbl_twitch_animated_pack",
    "twitch_badge_pack": "lbl_twitch_badge_pack",
    "twitch_points_pack": "lbl_twitch_points_pack",
    "discord_sticker_png": "lbl_dc_sticker_png",
    "discord_sticker_apng": "lbl_dc_sticker_apng",
    "discord_emoji_png": "lbl_dc_emoji_png",
    "discord_emoji_gif": "lbl_dc_emoji_gif",
    "seventv_emote": "lbl_7tv",
    "bttv_emote": "lbl_bttv",
    "whatsapp_static": "lbl_wa_static",
    "whatsapp_animated": "lbl_wa_animated",
    "whatsapp_tray": "lbl_wa_tray",
}
# Kick и YouTube: ключи подписей строятся по кодам (lbl_<код>).
PLATFORM_LABEL_KEYS.update(SQUARE_FORMAT_LABEL_KEYS)


def format_label(code):
    """Подпись формата на текущем языке."""
    if code in PLAIN_FORMAT_NAMES:
        return PLAIN_FORMAT_NAMES[code]
    if code == "frames":
        return tr("frames_label")
    key = PLATFORM_LABEL_KEYS.get(code)
    return tr(key) if key else code


class FormatLabel:
    """Подпись формата, которая переводится в момент вывода.

    Нужна полям ошибок: текст ошибки собирается при показе, и подпись
    внутри него должна быть на том же языке, что и само сообщение.
    """

    def __init__(self, code):
        self.code = code

    def __format__(self, spec):
        return format(format_label(self.code), spec)

    def __str__(self):
        return format_label(self.code)

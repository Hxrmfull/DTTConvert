"""Собирает icon.ico из icon.png.

Все размеры делаются из самой картинки. Раньше для мелких (16-32 px)
рисовался упрощённый силуэт — кольцо со стрелками и треугольник, — потому
что тонкие линии оригинала на таком размере расплываются. Но значок
получался просто другим, и это сбивало с толку: в проводнике одна
картинка, в заголовке окна другая.

Чтобы мелкие размеры не превращались в пятно, картинка уменьшается
постепенно (вдвое за шаг) и слегка подчёркивается нерезкой маской —
одиночный прыжок с 1024 до 16 px размывает линии сильнее.

Крупные кадры записываются первыми: часть просмотрщиков показывает
первый кадр контейнера, а не подходящий по размеру, и файл выглядел
как размытые 16 px. Windows выбирает кадр по размеру, ей порядок неважен.

Запуск после замены icon.png:  python make_icon.py
"""
import io
import os
import struct

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "icon.png")

# Набор размеров, которые Windows использует в проводнике, на панели задач
# и в заголовке окна.
SIZES = [256, 128, 64, 48, 32, 24, 20, 16]

# Ниже этого размера линии выигрывают от лёгкого подчёркивания контуров.
SHARPEN_BELOW = 48


def downscale(source, size):
    """Уменьшает картинку постепенно: так тонкие линии меньше размываются."""
    image = source
    while image.width >= size * 2:
        image = image.resize(
            (max(size, image.width // 2), max(size, image.height // 2)),
            Image.LANCZOS,
        )
    if image.size != (size, size):
        image = image.resize((size, size), Image.LANCZOS)

    if size < SHARPEN_BELOW:
        # Нерезкая маска по цветовым каналам: применённая к альфе, она даёт
        # рваные полупрозрачные края вокруг скруглённого квадрата.
        alpha = image.getchannel("A")
        sharpened = image.convert("RGB").filter(
            ImageFilter.UnsharpMask(radius=1.0, percent=90, threshold=0)
        )
        image = sharpened.convert("RGBA")
        image.putalpha(alpha)
    return image


def write_ico(frames, path):
    """Пишет .ico вручную: Pillow кладёт в контейнер одну картинку, а нам
    нужны все размеры сразу.

    Каждый кадр хранится как PNG — Windows Vista и новее это поддерживает.
    """
    blobs = []
    for frame in frames:
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        blobs.append(buffer.getvalue())

    header = struct.pack("<HHH", 0, 1, len(frames))  # reserved, type=icon, count
    entry_size = 16
    offset = len(header) + entry_size * len(frames)

    entries = b""
    for frame, blob in zip(frames, blobs):
        # 256 записывается как 0 — в байт больше не помещается.
        width = 0 if frame.width >= 256 else frame.width
        height = 0 if frame.height >= 256 else frame.height
        entries += struct.pack(
            "<BBBBHHII",
            width, height,
            0,      # палитра не используется
            0,      # зарезервировано
            1,      # плоскости
            32,     # бит на пиксель
            len(blob),
            offset,
        )
        offset += len(blob)

    with open(path, "wb") as handle:
        handle.write(header)
        handle.write(entries)
        for blob in blobs:
            handle.write(blob)


def main():
    source = Image.open(SRC).convert("RGBA")
    frames = [downscale(source, size) for size in SIZES]

    ico_path = os.path.join(HERE, "icon.ico")
    write_ico(frames, ico_path)
    print("создан:", ico_path, os.path.getsize(ico_path), "байт")
    print("размеры (первым идёт крупный):", [f.width for f in frames])


if __name__ == "__main__":
    main()

# DTTConvert

[English](README.md) · **Русский**

Конвертер картинок, GIF, видео и стикеров для **D**iscord, **T**elegram и
**T**witch, а также WhatsApp, 7TV и BTTV. Пресеты сами подбирают размер,
частоту кадров и вес, чтобы площадка приняла файл с первой попытки.

Интерфейс на русском и английском, язык переключается в правом нижнем углу.

![Окно DTTConvert](docs/screenshot.png)

## Скачать

Windows 10/11, 64 бита — страница [релизов](../../releases).

| Файл | Что это |
|---|---|
| `…-with-ffmpeg-setup.exe` | Установщик с FFmpeg — проще всего, прав администратора не нужно |
| `…-without-ffmpeg-setup.exe` | Установщик без FFmpeg — если FFmpeg уже есть |
| `…-with-ffmpeg.zip` | Без установки, с FFmpeg: распаковать и запустить |
| `…-without-ffmpeg.zip` | Без установки и без FFmpeg — самый лёгкий |

Из архива программа запускается сразу; переносить нужно **всю папку**
(рядом с exe лежит `_internal`).

**SmartScreen** («Система Windows защитила ваш компьютер»): программа
без цифровой подписи. Нажмите «Подробнее» → «Выполнить в любом случае».

**Без FFmpeg** работают только картинки (JPG, PNG, WEBP, BMP, AVIF).
Для видео, GIF, стикеров и звука положите `ffmpeg.exe` и `ffprobe.exe`
рядом с `DTTConvert.exe` или установите FFmpeg в `PATH`
([сборки для Windows](https://www.gyan.dev/ffmpeg/builds/)).

## Что умеет

- **На входе:** JPG, PNG, APNG, WEBP, BMP, AVIF, HEIC, TIFF, GIF, видео
  (MP4, WebM, AVI, MOV, MKV и др.) и анимированные стикеры Telegram `.tgs`.
  Анимированные WEBP, AVIF и APNG узнаются по содержимому.
- **На выходе:** JPG, PNG, WEBP, BMP, AVIF, GIF, APNG, MP4, WebM, AVI,
  звук (MP3, M4A, WAV) и покадровый разбор в PNG.
- **Пресеты площадок** — см. таблицу ниже. Предпросмотр показывает
  результат прямо в макете чата Telegram, Twitch, Discord и WhatsApp.
- **Правка:** размер, частота кадров, обрезка по времени, поворот,
  отражение, качество, ограничение веса файла, звук оставить или убрать.
  «Заполнить квадрат» обрезает края вместо прозрачных полей.
- **Очередь:** перетаскивание файлов и папок, вставка из буфера (`Ctrl+V`),
  свои настройки у каждого файла, параллельная обработка, отчёт в CSV.
  Исходник никогда не перезаписывается.
- **Клавиши:** `Ctrl+O` — добавить, `Delete` — убрать, `Alt+↑/↓` — порядок,
  `Ctrl+Enter` — старт, `Esc` — стоп. Всё окно проходится через `Tab`.

## Требования площадок

| Площадка | Пресет | Формат и лимиты |
|---|---|---|
| Telegram | Стикер | PNG/WEBP, сторона 512 px; видео — WEBM/VP9, ≤ 3 с, ≤ 30 FPS, ≤ 256 КБ, без звука |
| Telegram | Эмодзи | PNG/WEBP 100×100; видео — WEBM, те же лимиты |
| Discord | Стикер | PNG или APNG 320×320, ≤ 512 КБ, анимация ≤ 5 с |
| Discord | Эмодзи | PNG или GIF 128×128, ≤ 256 КБ |
| Twitch | Смайлик | PNG/GIF 112×112 или комплект 28/56/112, ≤ 1 МБ, GIF ≤ 60 кадров |
| Twitch | Значок подписки, баллы | PNG, комплекты 18/36/72 и 28/56/112, каждый ≤ 25 КБ |
| 7TV / BTTV | Смайлик | WEBP/GIF или PNG, 128 / 112 px, ≤ 1 МБ |
| WhatsApp | Стикер | WEBP 512×512, ≤ 100 КБ; анимация ≤ 10 с, ≤ 500 КБ; иконка набора PNG 96×96 |

Стикер `.tgs` переводится в любой из этих форматов, в GIF и видео; обратно
в `.tgs` перевести нельзя — это векторный формат.

## Запуск из исходников

Python 3.9+:

```bash
pip install -r requirements.txt
python main.py
```

`pillow-heif` нужен только для HEIC, `rlottie-python` — только для `.tgs`.

Тесты (для `test_core` нужен FFmpeg; окна на экран не выводятся):

```bash
python tests/run_all.py
```

Сборка для Windows (нужен [PyInstaller](https://pyinstaller.org/); для
установщиков — [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```powershell
powershell -File build_windows.ps1              # архивы с FFmpeg и без в release\
powershell -File build_windows.ps1 -Installer   # плюс установщики
```

Ключи: `-Variant with-ffmpeg|without-ffmpeg`, `-FfmpegDir <папка>`, `-NoZip`.
Вшиваемый FFmpeg сверяется с `ffmpeg_checksums.txt`.

## Прочее

- **Журнал:** `%LOCALAPPDATA%\DTTConvert\logs\app.log` — двойной щелчок
  по номеру версии открывает папку.
- **Обновления:** при каждом запуске программа спрашивает GitHub о новой
  версии и показывает ссылку вместо номера версии; сама ничего не скачивает.
  Отключается в меню номера версии (правый щелчок).
- **История изменений** — в [CHANGELOG.ru.md](CHANGELOG.ru.md).

## Лицензии

Код — [MIT](LICENSE). FFmpeg во вшитой сборке — LGPL/GPL, его лицензия
лежит рядом с exe (`FFmpeg-LICENSE`). Стикеры `.tgs` рисует
[rlottie-python](https://github.com/laggykiller/rlottie-python) (LGPL 2.1):
его `rlottie.dll` — отдельный заменяемый файл в `_internal\rlottie_python`,
лицензия — `rlottie-python-LICENSE.txt` рядом с exe.

"""Перевод интерфейса. Русский и английский.

Строки лежат здесь одной таблицей, а не разбросаны по коду: так видно,
что переведено, а что забыли. Ключ — короткий идентификатор, значение —
пара «русский, английский».

Язык переключается на лету: главное окно пересобирает свою начинку
целиком, поэтому отдельного «обновить все подписи» не нужно.
"""

RUSSIAN = "ru"
ENGLISH = "en"

LANGUAGE_NAMES = {RUSSIAN: "Русский", ENGLISH: "English"}
LANGUAGE_ORDER = (RUSSIAN, ENGLISH)

_current = RUSSIAN

# Ключ: (русский, английский)
STRINGS = {
    # --- окно и заголовки ---
    # Подзаголовка у окна нет: в шапке только название и версия.
    "queue_title": ("Очередь обработки", "Processing queue"),
    "settings_title": ("Параметры обработки", "Processing options"),
    "queue_empty": ("Очередь пуста", "Queue is empty"),
    "queue_count": ("Файлов в очереди: {total}", "Files in queue: {total}"),
    "queue_checked": ("Отмечено {checked} из {total}", "Checked {checked} of {total}"),
    "drop_hint": ("Перетащите файлы или папки сюда\n"
                  "или нажмите здесь, чтобы выбрать их на диске",
                  "Drop files or folders here\n"
                  "or click to pick them from disk"),

    # --- кнопки очереди ---
    "add_files": ("Добавить файлы", "Add files"),
    "add_files_tip": ("Добавить файлы в очередь (Ctrl+O)", "Add files to the queue (Ctrl+O)"),
    "remove_selected": ("Удалить выбранное", "Remove selected"),
    "remove_selected_tip": ("Убрать выделенные файлы из очереди (Delete)",
                           "Remove the selected files from the queue (Delete)"),
    "clear_list": ("Очистить список", "Clear list"),
    "clear_list_tip": ("Убрать из очереди все файлы", "Remove every file from the queue"),
    "check_all": ("Отметить все", "Check all"),
    "check_all_tip": ("Обрабатывать все файлы очереди", "Process every file in the queue"),
    "uncheck_all": ("Снять отметки", "Uncheck all"),
    "uncheck_all_tip": ("Снять отметки со всех файлов", "Uncheck every file"),

    # --- вкладки ---
    "tab_main": ("Основная", "General"),
    "tab_main_tip": ("Формат, размер, частота кадров, длительность, поворот, качество и звук",
                     "Format, size, frame rate, duration, rotation, quality and audio"),
    "tab_telegram_tip": ("Готовые пресеты стикеров и эмодзи Telegram",
                         "Ready-made Telegram sticker and emoji presets"),
    "tab_twitch_tip": ("Готовые пресеты смайликов Twitch",
                       "Ready-made Twitch emote presets"),
    "tab_discord_tip": ("Готовые пресеты стикеров и эмодзи Discord",
                        "Ready-made Discord sticker and emoji presets"),

    # --- вкладка «Основная» ---
    "output_format": ("Выходной формат:", "Output format:"),
    "group_size": ("РАЗМЕР, ЧАСТОТА КАДРОВ И ДЛИТЕЛЬНОСТЬ",
                   "SIZE, FRAME RATE AND DURATION"),
    "group_turn": ("ПОВОРОТ И ОТРАЖЕНИЕ", "ROTATION AND FLIP"),
    "group_quality": ("КАЧЕСТВО, РАЗМЕР ФАЙЛА И ЗВУК",
                      "QUALITY, FILE SIZE AND AUDIO"),
    "resize": ("Изменить размер", "Resize"),
    "keep_aspect": ("Сохранять пропорции", "Keep aspect ratio"),
    "width": ("Ширина (px):", "Width (px):"),
    "height": ("Высота (px):", "Height (px):"),
    "auto": ("Авто", "Auto"),
    "change_fps": ("Изменить FPS (видео и GIF)", "Change FPS (video and GIF)"),
    "change_trim": ("Изменить длительность (видео, GIF и звук)",
                    "Change duration (video, GIF and audio)"),
    "trim_tip": ("Вырезать фрагмент: с какой секунды начать и на какой закончить.",
                 "Cut a fragment: which second to start at and which to end at."),
    "trim_start": ("Начало", "From"),
    "trim_end": ("Конец", "To"),
    "seconds_suffix": (" сек", " s"),
    "rotate": ("Поворот", "Rotation"),
    "rotate_tip": ("Поворот по часовой стрелке.", "Clockwise rotation."),
    "flip": ("Отражение", "Flip"),
    "rotate_none": ("Нет", "None"),
    "flip_none": ("Нет", "None"),
    "flip_h": ("Слева направо", "Horizontal"),
    "flip_v": ("Сверху вниз", "Vertical"),
    "flip_both": ("Обе стороны", "Both"),
    "set_quality": ("Задать качество", "Set quality"),
    "set_quality_tip": ("1 — самый маленький файл, 100 — лучшая картинка. "
                        "Без этого используются встроенные значения кодеков.",
                        "1 is the smallest file, 100 the best picture. "
                        "Left off, the codec defaults are used."),
    "target_size": ("Уложить в размер", "Fit into size"),
    "target_size_tip": ("Битрейт подбирается под указанный размер. Качество при этом "
                        "не задаётся: размером управляет битрейт.",
                        "The bitrate is chosen to hit the given size. Quality is not "
                        "set in this mode: the bitrate drives the size."),
    "megabytes_suffix": (" МБ", " MB"),
    "audio_track": ("Дорожка", "Audio"),
    "audio_keep": ("Оставить", "Keep"),
    "audio_drop": ("Убрать", "Remove"),
    "audio_tip": ("«Убрать» выдаёт видео без звука — так же, как требуют стикеры.",
                  "“Remove” produces silent video, the way stickers require."),
    "audio_bitrate": ("Битрейт", "Bitrate"),
    "kbps": ("{value} кбит/с", "{value} kbps"),

    # --- группы форматов ---
    "fmt_images": ("ИЗОБРАЖЕНИЯ", "IMAGES"),
    "fmt_animation": ("АНИМАЦИЯ", "ANIMATION"),
    "fmt_video": ("ВИДЕО", "VIDEO"),
    "fmt_audio_only": ("ТОЛЬКО ЗВУК", "AUDIO ONLY"),
    "fmt_frames": ("ПОКАДРОВЫЙ РАЗБОР", "FRAME-BY-FRAME"),
    "fmt_preset_group": ("ВЫБРАННЫЙ ПРЕСЕТ", "SELECTED PRESET"),
    "frames_label": ("PNG-кадры (папка)", "PNG frames (folder)"),
    "tip_frames": ("Не один файл, а папка: каждый кадр сохраняется отдельной "
                   "картинкой frame_00001.png, frame_00002.png… в «<имя файла>_frames». "
                   "Из минуты видео получаются тысячи файлов.",
                   "Not one file but a folder: every frame is saved separately as "
                   "frame_00001.png, frame_00002.png… into “<file name>_frames”. "
                   "A minute of video yields thousands of files."),
    "tip_apng": ("Анимированный PNG: одна картинка со всеми кадрами внутри. "
                 "В отличие от GIF сохраняет полупрозрачность и все цвета, "
                 "но весит заметно больше. Файл получает расширение .png.",
                 "Animated PNG: a single picture holding every frame. Unlike GIF "
                 "it keeps semi-transparency and all colours, but weighs far more. "
                 "The file gets a .png extension."),
    "tip_gif": ("Анимация одним файлом. Прозрачность однобитная, цветов не больше "
                "256 — мягкие края огрубляются. Зато открывается везде.",
                "Animation in one file. Transparency is one-bit and colours are "
                "capped at 256, so soft edges get rough. But it opens anywhere."),
    "tip_mp3": ("Из видео берётся только звуковая дорожка, картинка отбрасывается.",
                "Only the audio track is taken from the video, the picture is dropped."),
    "tip_wav": ("Звук без сжатия: качество исходника, но файл крупный.",
                "Uncompressed audio: source quality, but a large file."),
    "tip_avif": ("Сжимает лучше JPEG при том же качестве, но открывается не везде.",
                 "Compresses better than JPEG at the same quality, but is not "
                 "supported everywhere."),

    # --- применение настроек ---
    "apply_selected": ("Применить к выделенным", "Apply to selected"),
    "apply_selected_tip": ("Применить настройки к выделенным (подсвеченным) файлам",
                           "Apply the settings to the selected (highlighted) files"),
    "apply_selected_off": ("Недоступно: сначала выделите файлы в очереди мышью",
                           "Unavailable: select files in the queue first"),
    "apply_all": ("Применить ко всем", "Apply to all"),
    "apply_all_tip": ("Применить настройки ко всем файлам очереди",
                      "Apply the settings to every file in the queue"),
    "apply_all_off": ("Недоступно: очередь пуста", "Unavailable: the queue is empty"),
    "reset": ("Сброс", "Reset"),
    "reset_tip": ("Вернуть настройки обработки и папку сохранения к исходным",
                  "Restore the processing options and output folder to defaults"),

    # --- нижняя панель ---
    "output_dir": ("Папка сохранения:", "Output folder:"),
    "output_dir_tip": ("Изменить можно кнопкой «Обзор…»",
                       "Change it with the “Browse…” button"),
    "browse": ("Обзор...", "Browse..."),
    "overwrite": ("Перезаписывать существующие файлы", "Overwrite existing files"),
    "overwrite_tip": ("Выключено — рядом создаётся копия с суффиксом _1, _2 и т.д.",
                      "When off, a copy with the suffix _1, _2 and so on is created."),
    "language": ("Язык", "Language"),
    "language_tip": ("Язык интерфейса", "Interface language"),
    "report_csv": ("Отчёт (CSV)", "Report (CSV)"),
    "open_folder": ("Открыть папку", "Open folder"),
    "open_folder_tip": ("Показать папку с результатами в проводнике",
                        "Show the output folder in the file manager"),
    "start": ("Старт", "Start"),
    "start_tip": ("Начать обработку очереди (Ctrl+Enter)",
                  "Start processing the queue (Ctrl+Enter)"),
    "start_running": ("Идёт обработка", "Processing"),
    "stop": ("Остановить", "Stop"),
    "stop_tip": ("Прервать обработку (Esc)", "Interrupt processing (Esc)"),
    "stop_off": ("Недоступно: обработка не запущена",
                 "Unavailable: processing is not running"),
    "version_tip": ("{app} {version}\nДвойной клик — открыть папку с журналом",
                    "{app} {version}\nDouble-click to open the log folder"),

    # --- состояния очереди ---
    "status_pending": ("Ожидание", "Waiting"),
    "status_processing": ("Обработка", "Processing"),
    "status_done": ("Готово", "Done"),
    "status_error": ("Ошибка", "Error"),
    "status_stopped": ("Остановлено", "Stopped"),
    "idle": ("Готово к запуску", "Ready to start"),
    "scanning": ("Сканирование папки...", "Scanning folder..."),
    "preparing": ("Подготовка к обработке...", "Preparing..."),
    "stopping": ("Остановка после завершения текущего файла...",
                 "Stopping after the current file finishes..."),

    # --- ход обработки ---
    "progress_done_of": ("Обработано {done} из {total}", "Processed {done} of {total}"),
    "progress_current": ("Сейчас: {name}", "Now: {name}"),
    "progress_parallel": ("Параллельно: {count} файла(ов)", "In parallel: {count} file(s)"),
    "progress_left": ("осталось ~{time}", "~{time} left"),
    "summary_done": ("Обработка завершена", "Processing finished"),
    "summary_stopped": ("Остановлено пользователем", "Stopped by the user"),
    "summary_counts": ("успешно: {done}, с ошибкой: {failed}",
                       "succeeded: {done}, failed: {failed}"),
    "summary_cancelled": (", прервано: {count}", ", interrupted: {count}"),
    "summary_elapsed": ("заняло {time}", "took {time}"),

    # --- единицы времени ---
    "sec": ("{value} сек", "{value} s"),
    "min": ("{value} мин", "{value} min"),
    "min_sec": ("{minutes} мин {seconds:02d} сек", "{minutes} min {seconds:02d} s"),
    "hour_min": ("{hours} ч {minutes:02d} мин", "{hours} h {minutes:02d} min"),

    # --- диалоги ---
    "dlg_choose_files": ("Выберите файлы", "Choose files"),
    "dlg_media_filter": ("Медиафайлы", "Media files"),
    "dlg_all_files": ("Все файлы", "All files"),
    "dlg_choose_output": ("Выберите папку сохранения", "Choose the output folder"),
    "dlg_scanning_title": ("Идёт сканирование", "Scanning"),
    "dlg_scanning_text": ("Дождитесь окончания предыдущего сканирования папки.",
                          "Wait until the previous folder scan finishes."),
    "dlg_skipped_title": ("Часть файлов пропущена", "Some files were skipped"),
    "dlg_skipped_format": ("Неподдерживаемый формат (пропущены):",
                           "Unsupported format (skipped):"),
    "dlg_skipped_dupes": ("Уже есть в очереди (пропущены):",
                          "Already in the queue (skipped):"),
    "dlg_and_more": ("... и ещё {count}", "... and {count} more"),
    "dlg_empty_queue_title": ("Очередь пуста", "The queue is empty"),
    "dlg_empty_queue_text": ("Добавьте файлы для конвертации.", "Add files to convert."),
    "dlg_no_selection_title": ("Нет выбора", "Nothing selected"),
    "dlg_no_selection_text": ("Выберите хотя бы один файл в очереди.",
                              "Select at least one file in the queue."),
    "dlg_empty_list_title": ("Список пуст", "The list is empty"),
    "dlg_empty_list_text": ("Добавьте файлы в очередь.", "Add files to the queue."),
    "dlg_bad_dir_title": ("Некорректная папка", "Invalid folder"),
    "dlg_bad_dir_text": ("Выберите корректную папку сохранения.",
                         "Choose a valid output folder."),
    "dlg_no_access_title": ("Нет доступа к папке", "No access to the folder"),
    "dlg_no_access_text": ("В выбранную папку нельзя записывать файлы:\n{path}\n\n"
                           "Выберите другую папку сохранения.",
                           "Files cannot be written to the chosen folder:\n{path}\n\n"
                           "Pick a different output folder."),
    "dlg_nothing_checked_title": ("Ничего не отмечено", "Nothing is checked"),
    "dlg_nothing_checked_text": ("Отметьте галочками файлы, которые нужно обработать.",
                                 "Tick the files you want to process."),
    "dlg_many_frames_title": ("Очень много кадров", "A great many frames"),
    "dlg_many_frames_text": ("Будет создано примерно {count} PNG-файлов. "
                             "Это может занять много места на диске и времени.\n\n"
                             "Продолжить?",
                             "About {count} PNG files will be created. That may take "
                             "a lot of disk space and time.\n\nContinue?"),
    "dlg_reset_title": ("Сбросить настройки", "Reset the settings"),
    "dlg_reset_text": ("Вернуть настройки обработки и папку сохранения "
                       "к исходному состоянию?\n\nОчередь файлов не пострадает.",
                       "Restore the processing options and output folder to their "
                       "defaults?\n\nThe file queue will not be touched."),
    "reset_done": ("Настройки сброшены", "Settings have been reset"),
    "dlg_no_data_title": ("Нет данных", "No data"),
    "dlg_no_data_text": ("Сначала выполните конвертацию.", "Run a conversion first."),
    "dlg_save_report": ("Сохранить отчёт", "Save the report"),
    "dlg_save_failed": ("Не удалось сохранить", "Could not save"),
    "dlg_saved": ("Сохранено", "Saved"),
    "dlg_report_saved": ("Отчёт сохранён: {path}", "Report saved: {path}"),
    "dlg_file_missing_title": ("Файл не найден", "File not found"),
    "dlg_file_missing_text": ("Файла больше нет:\n{path}", "The file is gone:\n{path}"),
    "dlg_folder_missing_title": ("Папка недоступна", "Folder unavailable"),
    "dlg_folder_missing_text": ("Папка сохранения не найдена.", "The output folder was not found."),
    "dlg_error_details": ("Подробности ошибки", "Error details"),
    "dlg_ffmpeg_title": ("FFmpeg не найден", "FFmpeg not found"),
    # Подсказка начинается с копии рядом с программой: в сборке без FFmpeg
    # это самый короткий путь, а возня с PATH нужна далеко не всем.
    "dlg_ffmpeg_text": ("FFmpeg или FFprobe не найдены.\n\n"
                        "Видео, GIF, стикеры и звук будут недоступны, пока "
                        "не появится FFmpeg. Достаточно одного из двух:\n\n"
                        "1. Положить ffmpeg.exe и ffprobe.exe рядом "
                        "с программой, в её папку.\n"
                        "2. Или установить FFmpeg и добавить его в PATH.\n\n"
                        "Сборки для Windows: https://www.gyan.dev/ffmpeg/builds/\n\n"
                        "Обработка изображений (JPG, PNG, WEBP, BMP, AVIF) "
                        "работает и без него.",
                        "Neither FFmpeg nor FFprobe was found.\n\n"
                        "Video, GIF, stickers and audio stay unavailable until "
                        "FFmpeg shows up. Either one will do:\n\n"
                        "1. Put ffmpeg.exe and ffprobe.exe next to the "
                        "application, in its own folder.\n"
                        "2. Or install FFmpeg and add it to PATH.\n\n"
                        "Windows builds: https://www.gyan.dev/ffmpeg/builds/\n\n"
                        "Image conversion (JPG, PNG, WEBP, BMP, AVIF) works "
                        "without it."),
    # Строка над очередью, поэтому короткая: подробности — в окне при запуске.
    "ffmpeg_warning": ("FFmpeg не найден: доступны только изображения. "
                       "Положите ffmpeg.exe рядом с программой или добавьте "
                       "FFmpeg в PATH.",
                       "FFmpeg not found: images only. Put ffmpeg.exe next to "
                       "the application or add FFmpeg to PATH."),

    # --- контекстное меню очереди ---
    "menu_open": ("Открыть файл", "Open file"),
    "menu_reveal": ("Показать в проводнике", "Show in file manager"),
    "menu_error": ("Подробности ошибки", "Error details"),
    "menu_remove": ("Убрать из очереди", "Remove from the queue"),
    "error_tooltip": ("{message}\n\n(двойной клик — открыть полный текст ошибки)",
                      "{message}\n\n(double-click to see the full error text)"),

    # --- отчёт CSV ---
    "csv_file": ("Файл", "File"),
    "csv_format": ("Формат", "Format"),
    "csv_status": ("Статус", "Status"),
    "csv_seconds": ("Время, сек", "Time, s"),
    "csv_message": ("Сообщение", "Message"),

    # --- примечания на вкладках площадок ---
    "platform_note": ("Применяется к выделенным файлам, а без выделения — ко всем.",
                      "Applied to the selected files, or to all of them if nothing "
                      "is selected."),
    "preset_applied_selected": ("Пресет применён к выбранным ({count} шт.)",
                                "Preset applied to the selected files ({count})"),
    "preset_applied_all": ("Пресет применён ко всем файлам ({count} шт.)",
                           "Preset applied to every file ({count})"),
    "preset_applied_none": ("Пресет выбран. Добавьте файлы — он применится к ним.",
                            "Preset selected. Add files and it will be applied."),
    "tg_fragment": ("Фрагмент: с", "Fragment: from"),
    "tg_fragment_len": ("сек, длиной", "s, lasting"),
    "tg_start_tip": ("С какой секунды исходника брать фрагмент. Для файлов длиннее "
                     "трёх секунд так выбирается нужный момент.",
                     "Which second of the source the fragment starts at. This is how "
                     "you pick the moment in files longer than three seconds."),
    "tg_duration_tip": ("Длина фрагмента, не больше трёх секунд по спецификации "
                        "Telegram. Короткий файл не растягивается — берётся его "
                        "собственная длина.",
                        "Fragment length, at most three seconds per the Telegram "
                        "spec. A short file is not stretched — its own length is used."),
    "tg_source_short": ("Файл длится {duration} — короче лимита, берётся целиком.",
                        "The file lasts {duration} — under the limit, taken whole."),
    "tg_source_long": ("Файл длится {duration} — будет обрезан до {length:.1f} сек "
                       "с {start:.1f} сек.",
                       "The file lasts {duration} — it will be cut to {length:.1f} s "
                       "starting at {start:.1f} s."),
    "col_sticker": ("СТИКЕР · {size} PX", "STICKER · {size} PX"),
    "col_emoji": ("ЭМОДЗИ · {size} PX", "EMOJI · {size} PX"),
    "preset_sticker_png": ("Стикер PNG", "Sticker PNG"),
    "preset_sticker_webp": ("Стикер WEBP", "Sticker WEBP"),
    "preset_sticker_webm": ("Стикер WEBM", "Sticker WEBM"),
    "preset_sticker_apng": ("Стикер APNG", "Sticker APNG"),
    "preset_emoji_png": ("Эмодзи PNG", "Emoji PNG"),
    "preset_emoji_webp": ("Эмодзи WEBP", "Emoji WEBP"),
    "preset_emoji_webm": ("Эмодзи WEBM", "Emoji WEBM"),
    "preset_emoji_gif": ("Эмодзи GIF", "Emoji GIF"),
    "preset_twitch_png": ("PNG 112×112", "PNG 112×112"),
    "preset_twitch_png_pack": ("PNG комплект (3 файла)", "PNG set (3 files)"),
    "preset_twitch_gif": ("GIF 112×112", "GIF 112×112"),
    "preset_twitch_gif_pack": ("GIF комплект (3 файла)", "GIF set (3 files)"),

    # --- подсказки к пресетам площадок ---
    "hint_tg_sticker_static": (
        "Статичный стикер Telegram: одна сторона 512 px, формат {fmt}, "
        "прозрачный фон рекомендуется.",
        "Telegram static sticker: one side 512 px, {fmt} format, "
        "a transparent background is recommended."),
    "hint_tg_emoji_static": (
        "Статичный emoji Telegram: 100×100 px, формат {fmt}.",
        "Telegram static emoji: 100×100 px, {fmt} format."),
    "hint_tg_sticker_webm": (
        "Видео-стикер Telegram: WEBM/VP9 без звука, одна сторона 512 px, "
        "до 30 FPS, до 3 сек, ≤ 256 КБ.",
        "Telegram video sticker: WEBM/VP9 without audio, one side 512 px, "
        "up to 30 FPS, up to 3 s, ≤ 256 KB."),
    "hint_tg_emoji_webm": (
        "Видео-emoji Telegram: WEBM/VP9 без звука, 100×100 px, "
        "до 30 FPS, до 3 сек, ≤ 256 КБ.",
        "Telegram video emoji: WEBM/VP9 without audio, 100×100 px, "
        "up to 30 FPS, up to 3 s, ≤ 256 KB."),
    "hint_twitch_static": (
        "Статичный смайлик Twitch: PNG, {sizes}, квадрат с прозрачным фоном. "
        "Изображение вписывается целиком, пустое место остаётся прозрачным.",
        "Twitch static emote: PNG, {sizes}, a square with a transparent "
        "background. The image fits whole, the spare room stays transparent."),
    "hint_twitch_animated": (
        "Анимированный смайлик Twitch: GIF, {sizes}, квадрат с прозрачным фоном. "
        "Лимиты: не более {frames} кадров и {limit} — FPS подбирается автоматически.",
        "Twitch animated emote: GIF, {sizes}, a square with a transparent "
        "background. Limits: at most {frames} frames and {limit} — the FPS is "
        "chosen automatically."),
    "twitch_sizes_pack": ("28, 56 и 112 px (3 файла)", "28, 56 and 112 px (3 files)"),
    "twitch_sizes_one": ("112×112 px", "112×112 px"),
    "hint_dc_sticker_png": (
        "Статичный стикер Discord: PNG, ровно {size}×{size} px, квадрат "
        "с прозрачным фоном, не больше {limit}.",
        "Discord static sticker: PNG, exactly {size}×{size} px, a square with "
        "a transparent background, no larger than {limit}."),
    "hint_dc_sticker_apng": (
        "Анимированный стикер Discord: APNG, {size}×{size} px, до {duration:g} сек, "
        "не больше {limit} — FPS подбирается автоматически. "
        "Полупрозрачность сохраняется.",
        "Discord animated sticker: APNG, {size}×{size} px, up to {duration:g} s, "
        "no larger than {limit} — the FPS is chosen automatically. "
        "Semi-transparency is preserved."),
    "hint_dc_emoji_png": (
        "Статичный эмодзи Discord: PNG, {size}×{size} px, не больше {limit}.",
        "Discord static emoji: PNG, {size}×{size} px, no larger than {limit}."),
    "hint_dc_emoji_gif": (
        "Анимированный эмодзи Discord: GIF, {size}×{size} px, не больше {limit} — "
        "FPS подбирается автоматически. У GIF прозрачность однобитная, "
        "мягкие края огрубляются.",
        "Discord animated emoji: GIF, {size}×{size} px, no larger than {limit} — "
        "the FPS is chosen automatically. GIF transparency is one-bit, so soft "
        "edges get rough."),
    # --- подписи форматов площадок ---
    "lbl_tg_sticker_png": ("TG Стикер (PNG)", "TG Sticker (PNG)"),
    "lbl_tg_sticker_webp": ("TG Стикер (WEBP)", "TG Sticker (WEBP)"),
    "lbl_tg_sticker_webm": ("TG Стикер (WEBM)", "TG Sticker (WEBM)"),
    "lbl_tg_emoji_png": ("TG Эмодзи (PNG)", "TG Emoji (PNG)"),
    "lbl_tg_emoji_webp": ("TG Эмодзи (WEBP)", "TG Emoji (WEBP)"),
    "lbl_tg_emoji_webm": ("TG Эмодзи (WEBM)", "TG Emoji (WEBM)"),
    "lbl_twitch_static_112": ("Twitch PNG (112×112)", "Twitch PNG (112×112)"),
    "lbl_twitch_static_pack": ("Twitch PNG комплект (28/56/112)",
                               "Twitch PNG set (28/56/112)"),
    "lbl_twitch_animated_112": ("Twitch GIF (112×112)", "Twitch GIF (112×112)"),
    "lbl_twitch_animated_pack": ("Twitch GIF комплект (28/56/112)",
                                 "Twitch GIF set (28/56/112)"),
    "lbl_dc_sticker_png": ("DC Стикер (PNG)", "DC Sticker (PNG)"),
    "lbl_dc_sticker_apng": ("DC Стикер (APNG)", "DC Sticker (APNG)"),
    "lbl_dc_emoji_png": ("DC Эмодзи (PNG)", "DC Emoji (PNG)"),
    "lbl_dc_emoji_gif": ("DC Эмодзи (GIF)", "DC Emoji (GIF)"),

    "kb": ("{value} КБ", "{value} KB"),
    "mb": ("{value} МБ", "{value} MB"),
}


def language_from_locale(locale_name):
    """Язык по имени системной локали вроде «ru_RU» или «en-US».

    Всё, что не русское, показываем по-английски: своего перевода для
    остальных языков нет, а английский понятнее русского для иностранца.
    """
    code = (locale_name or "").replace("-", "_").split("_")[0].lower()
    return RUSSIAN if code == "ru" else ENGLISH


def set_language(code):
    """Переключает язык. Неизвестный код игнорируется."""
    global _current
    if code in LANGUAGE_NAMES:
        _current = code


def current_language():
    return _current


def tr(key, **fields):
    """Строка на текущем языке. Незнакомый ключ возвращается как есть —
    так пропущенный перевод виден сразу, а не роняет программу."""
    pair = STRINGS.get(key)
    if pair is None:
        return key
    text = pair[0] if _current == RUSSIAN else pair[1]
    return text.format(**fields) if fields else text


def missing_translations():
    """Ключи, у которых нет пары из двух строк. Нужна тестам."""
    broken = []
    for key, pair in STRINGS.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            broken.append(key)
        elif not all(isinstance(value, str) and value.strip() for value in pair):
            broken.append(key)
    return broken

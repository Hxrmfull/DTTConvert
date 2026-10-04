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
    # «Убрать», а не «Удалить»: «удалить» читалось как удаление с диска.
    "remove_selected": ("Убрать выделенные", "Remove selected"),
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
    # Подписи полей — без двоеточий, как у «Поворот» и «Начало».
    # «Размер» на вкладке значил три разные вещи: пиксели кадра, вес файла
    # и заголовок группы. Теперь пиксели — «разрешение», мегабайты — «вес».
    "output_format": ("Выходной формат", "Output format"),
    "group_size": ("РАЗРЕШЕНИЕ, ЧАСТОТА КАДРОВ И ДЛИТЕЛЬНОСТЬ",
                   "RESOLUTION, FRAME RATE AND DURATION"),
    "group_turn": ("ПОВОРОТ И ОТРАЖЕНИЕ", "ROTATION AND FLIP"),
    "group_quality": ("КАЧЕСТВО, ВЕС ФАЙЛА И ЗВУК",
                      "QUALITY, FILE SIZE AND AUDIO"),
    "resize": ("Изменить разрешение", "Resize"),
    "keep_aspect": ("Сохранять пропорции", "Keep aspect ratio"),
    "width": ("Ширина (px)", "Width (px)"),
    "height": ("Высота (px)", "Height (px)"),
    "auto": ("Авто", "Auto"),
    "change_fps": ("Изменить FPS (видео и GIF)", "Change FPS (video and GIF)"),
    "change_trim": ("Обрезать по времени (видео, GIF и звук)",
                    "Trim (video, GIF and audio)"),
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
    "flip_h": ("По горизонтали", "Horizontal"),
    "flip_v": ("По вертикали", "Vertical"),
    "flip_both": ("По обеим осям", "Both"),
    "set_quality": ("Задать качество", "Set quality"),
    "set_quality_tip": ("1 — самый маленький файл, 100 — лучшая картинка. "
                        "Без этого используются встроенные значения кодеков.",
                        "1 is the smallest file, 100 the best picture. "
                        "Left off, the codec defaults are used."),
    "target_size": ("Ограничить вес файла", "Limit file size"),
    "target_size_tip": ("Битрейт подбирается так, чтобы файл весил не больше "
                        "указанного. Качество при этом не задаётся: весом управляет "
                        "битрейт.",
                        "The bitrate is chosen so the file is no larger than the given "
                        "size. Quality is not set in this mode: the bitrate drives the "
                        "size."),
    "megabytes_suffix": (" МБ", " MB"),
    "audio_track": ("Звук", "Audio"),
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
    "apply_selected_off": ("Недоступно: сначала выделите файлы в очереди",
                           "Unavailable: select files in the queue first"),
    "apply_all": ("Применить ко всем", "Apply to all"),
    "apply_all_tip": ("Применить настройки ко всем файлам очереди",
                      "Apply the settings to every file in the queue"),
    "apply_all_off": ("Недоступно: очередь пуста", "Unavailable: the queue is empty"),
    "reset": ("Сброс", "Reset"),
    "reset_tip": ("Вернуть настройки обработки и папку сохранения к исходным",
                  "Restore the processing options and output folder to defaults"),

    # --- нижняя панель ---
    "output_dir": ("Папка сохранения", "Output folder"),
    "output_dir_tip": ("Изменить можно кнопкой «Обзор…»",
                       "Change it with the “Browse…” button"),
    "browse": ("Обзор…", "Browse…"),
    # Коротко: строка внизу окна тесная. Что значит «выключено» — в подсказке.
    "overwrite": ("Перезаписывать файлы", "Overwrite files"),
    "overwrite_tip": ("Включено — файл с тем же именем в папке сохранения заменяется. "
                      "Выключено — рядом создаётся копия с суффиксом _1, _2 и т. д.",
                      "On — a file with the same name in the output folder is replaced. "
                      "Off — a copy with the suffix _1, _2 and so on is created."),
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
    "version_tip": ("{app} {version}\nДвойной щелчок — открыть папку журнала.\n"
                    "Правый щелчок или Enter — меню.",
                    "{app} {version}\nDouble-click to open the log folder.\n"
                    "Right-click or Enter opens the menu."),
    "tab_accessible": ("Вкладка {name}", "{name} tab"),
    "queue_tip": ("Порядок обработки меняется перетаскиванием или Alt+↑ / Alt+↓. "
                  "Обрабатываются только отмеченные галочкой файлы.",
                  "Drag files or press Alt+↑ / Alt+↓ to change the processing order. "
                  "Only checked files are processed."),
    # Кнопки подтверждений называют действие, а не «Да/Нет»: стандартные
    # кнопки Qt без его перевода выходили по-английски и в русском окне.
    "btn_cancel": ("Отмена", "Cancel"),
    "btn_reset": ("Сбросить", "Reset"),
    "btn_create_frames": ("Создать кадры", "Create frames"),
    "btn_continue_anyway": ("Всё равно продолжить", "Continue anyway"),

    # --- состояния очереди ---
    "status_pending": ("Ожидание", "Waiting"),
    "status_processing": ("Обработка", "Processing"),
    "status_done": ("Готово", "Done"),
    "status_error": ("Ошибка", "Error"),
    "status_stopped": ("Остановлено", "Stopped"),
    "idle": ("Готово к запуску", "Ready to start"),
    "scanning": ("Сканирование папки…", "Scanning folder…"),
    "preparing": ("Подготовка к обработке…", "Preparing…"),
    "stopping": ("Остановка после завершения текущего файла…",
                 "Stopping after the current file finishes…"),

    # --- ход обработки ---
    "progress_done_of": ("Обработано {done} из {total}", "Processed {done} of {total}"),
    "progress_current": ("Сейчас: {name}", "Now: {name}"),
    "progress_parallel": ("Параллельно: {count} {files}", "In parallel: {count} {files}"),
    # Формы слова для plural(): одна, две-четыре, пять и больше.
    "word_files": ("файл|файла|файлов", "file|files"),
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
    "dlg_and_more": ("…и ещё {count}", "…and {count} more"),
    "dlg_empty_queue_title": ("Очередь пуста", "The queue is empty"),
    "dlg_empty_queue_text": ("Добавьте файлы для обработки.", "Add files to process."),
    "dlg_no_selection_title": ("Нет выбора", "Nothing selected"),
    "dlg_no_selection_text": ("Выберите хотя бы один файл в очереди.",
                              "Select at least one file in the queue."),
    "dlg_empty_list_title": ("Список пуст", "The list is empty"),
    "dlg_empty_list_text": ("Добавьте файлы в очередь.", "Add files to the queue."),
    "dlg_bad_dir_title": ("Некорректная папка", "Invalid folder"),
    "dlg_bad_dir_text": ("Папки сохранения больше нет:\n{path}\n\n"
                         "Возможно, её переименовали, удалили или отключили диск. "
                         "Выберите другую кнопкой «Обзор…».",
                         "The output folder no longer exists:\n{path}\n\n"
                         "It may have been renamed, deleted or its drive disconnected. "
                         "Pick another one with the “Browse…” button."),
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
    "dlg_twitch_long_title": ("Слишком длинная анимация", "Animation too long"),
    "dlg_twitch_long_text": ("В анимированном смайлике Twitch не больше 60 кадров, "
                             "поэтому из длинного ролика выйдет рваное слайд-шоу:\n\n"
                             "{files}\n\nПлавно получается до ~{seconds} сек. Лучше "
                             "обрезать фрагмент на вкладке «Основная».\n\n"
                             "Всё равно продолжить?",
                             "A Twitch animated emote holds at most 60 frames, so a "
                             "long clip turns into a choppy slideshow:\n\n{files}\n\n"
                             "It stays smooth up to ~{seconds} s. Better trim a "
                             "fragment on the General tab.\n\nContinue anyway?"),
    "dlg_reset_title":("Сбросить настройки", "Reset the settings"),
    "dlg_reset_text": ("Вернуть настройки обработки и папку сохранения "
                       "к исходному состоянию?\n\nОчередь файлов не пострадает.",
                       "Restore the processing options and output folder to their "
                       "defaults?\n\nThe file queue will not be touched."),
    "reset_done": ("Настройки сброшены", "Settings have been reset"),
    "dlg_no_data_title": ("Нет данных", "No data"),
    "dlg_no_data_text": ("Отчёт появится после обработки.",
                         "The report appears after processing."),
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
    # Выноска, пока пресет площадки не выбран: раньше она описывала пресет,
    # который не применялся, и вводила в заблуждение.
    "preset_none_hint": ("Пресет {platform} не выбран — файл сохранится в обычном "
                         "формате. Нажмите кнопку ниже, чтобы выбрать пресет.",
                         "No {platform} preset is selected — the file is saved in a "
                         "regular format. Click a button below to pick one."),
    "platform_note": ("Применяется к выделенным файлам, а без выделения — ко всем.",
                      "Applied to the selected files, or to all of them if nothing "
                      "is selected."),
    # «Выделенные» — подсвеченные строки, «отмеченные» — с галочкой;
    # слово «выбранные» не используется, чтобы их не путать.
    "preset_applied_selected": ("Пресет применён к выделенным файлам: {count}",
                                "Preset applied to the selected files: {count}"),
    "preset_applied_all": ("Пресет применён ко всем файлам: {count}",
                           "Preset applied to every file: {count}"),
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
    "tg_source_long": ("Файл длится {duration} — будет обрезан до {length} сек "
                       "с {start} сек.",
                       "The file lasts {duration} — it will be cut to {length} s "
                       "starting at {start} s."),
    "col_sticker": ("СТИКЕР · {size} PX", "STICKER · {size} PX"),
    "col_emoji": ("ЭМОДЗИ · {size} PX", "EMOJI · {size} PX"),
    "preset_sticker_png": ("Стикер PNG", "PNG sticker"),
    "preset_sticker_webp": ("Стикер WEBP", "WEBP sticker"),
    "preset_sticker_webm": ("Стикер WEBM", "WEBM sticker"),
    "preset_sticker_apng": ("Стикер APNG", "APNG sticker"),
    "preset_emoji_png": ("Эмодзи PNG", "PNG emoji"),
    "preset_emoji_webp": ("Эмодзи WEBP", "WEBP emoji"),
    "preset_emoji_webm": ("Эмодзи WEBM", "WEBM emoji"),
    "preset_emoji_gif": ("Эмодзи GIF", "GIF emoji"),
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
        "Статичный эмодзи Telegram: 100×100 px, формат {fmt}.",
        "Telegram static emoji: 100×100 px, {fmt} format."),
    "hint_tg_sticker_webm": (
        "Видео-стикер Telegram: WEBM/VP9 без звука, одна сторона 512 px, "
        "до 30 FPS, до 3 сек, ≤ 256 КБ.",
        "Telegram video sticker: WEBM/VP9 without audio, one side 512 px, "
        "up to 30 FPS, up to 3 s, ≤ 256 KB."),
    "hint_tg_emoji_webm": (
        "Видеоэмодзи Telegram: WEBM/VP9 без звука, 100×100 px, "
        "до 30 FPS, до 3 сек, ≤ 256 КБ.",
        "Telegram video emoji: WEBM/VP9 without audio, 100×100 px, "
        "up to 30 FPS, up to 3 s, ≤ 256 KB."),
    "hint_twitch_static": (
        "Статичный смайлик Twitch: PNG, {sizes}, квадрат с прозрачным фоном, "
        "не больше 1 МБ.",
        "Twitch static emote: PNG, {sizes}, a square with a transparent "
        "background, no larger than 1 MB."),
    "hint_twitch_animated": (
        "Анимированный смайлик Twitch: GIF, {sizes}, квадрат с прозрачным фоном. "
        "Лимиты: не более {frames} кадров и {limit} — FPS подбирается автоматически.",
        "Twitch animated emote: GIF, {sizes}, a square with a transparent "
        "background. Limits: at most {frames} frames and {limit} — the FPS is "
        "chosen automatically."),
    "twitch_sizes_set": ("{sizes} px — {count} файла", "{sizes} px — {count} files"),
    "twitch_sizes_one_n": ("{size}×{size} px", "{size}×{size} px"),
    "hint_twitch_badge": (
        "Значок подписки Twitch: PNG, {sizes}, прозрачный фон, каждый не больше "
        "{limit}. Рисунок должен читаться даже в 18 px.",
        "Twitch subscriber badge: PNG, {sizes}, transparent background, each "
        "no larger than {limit}. The picture must read even at 18 px."),
    "hint_twitch_points": (
        "Иконка награды за баллы канала: PNG, {sizes}, прозрачный фон, каждая "
        "не больше {limit}.",
        "Channel Points reward icon: PNG, {sizes}, transparent background, "
        "each no larger than {limit}."),
    "hint_7tv": (
        "Смайлик 7TV: {size}×{size} px. Из видео и анимации — анимированный "
        "WEBP (до {frames} кадров), из картинки — PNG. Не больше {limit}.",
        "7TV emote: {size}×{size} px. Video and animations become an animated "
        "WEBP (up to {frames} frames), still pictures a PNG. No larger than {limit}."),
    "hint_bttv": (
        "Смайлик BTTV: {size}×{size} px. Из видео и анимации — GIF, из картинки "
        "— PNG. Не больше {limit}.",
        "BTTV emote: {size}×{size} px. Video and animations become a GIF, still "
        "pictures a PNG. No larger than {limit}."),
    "col_twitch_emotes": ("СМАЙЛИКИ TWITCH", "TWITCH EMOTES"),
    "col_twitch_more": ("ЗНАЧКИ И РАСШИРЕНИЯ", "BADGES AND EXTENSIONS"),
    "preset_twitch_badge": ("Значок подписки (3 файла)", "Sub badge (3 files)"),
    "preset_twitch_points": ("Значок баллов (3 файла)", "Points icon (3 files)"),
    "preset_7tv": ("Смайлик 7TV", "7TV emote"),
    "preset_bttv": ("Смайлик BTTV", "BTTV emote"),
    # Подписи форматов площадок — одна схема «Площадка: что и в чём»:
    # раньше рядом стояли «TG Стикер», «DC Эмодзи», «WA Стикер» и «Twitch PNG».
    "lbl_twitch_badge_pack": ("Twitch: значок 18/36/72", "Twitch: badge 18/36/72"),
    "lbl_twitch_points_pack": ("Twitch: баллы 28/56/112", "Twitch: points 28/56/112"),
    "lbl_7tv": ("7TV: смайлик 128×128", "7TV: emote 128×128"),
    "lbl_bttv": ("BTTV: смайлик 112×112", "BTTV: emote 112×112"),

    # --- WhatsApp ---
    "tab_whatsapp_tip": ("Готовые пресеты стикеров WhatsApp",
                         "Ready-made WhatsApp sticker presets"),
    "col_wa_sticker": ("СТИКЕР · 512 PX", "STICKER · 512 PX"),
    "col_wa_pack": ("НАБОР", "PACK"),
    "preset_wa_static": ("Стикер WEBP", "WEBP sticker"),
    "preset_wa_animated": ("Анимированный WEBP", "Animated WEBP"),
    "preset_wa_tray": ("Иконка набора 96 px", "Pack icon 96 px"),
    "lbl_wa_static": ("WhatsApp: стикер WEBP", "WhatsApp: WEBP sticker"),
    "lbl_wa_animated": ("WhatsApp: анимированный стикер", "WhatsApp: animated sticker"),
    "lbl_wa_tray": ("WhatsApp: иконка набора 96", "WhatsApp: pack icon 96"),
    "hint_wa_static": (
        "Стикер WhatsApp: WEBP ровно {size}×{size} px, прозрачный фон, "
        "не больше {limit} КБ.",
        "WhatsApp sticker: WEBP of exactly {size}×{size} px, transparent "
        "background, no larger than {limit} KB."),
    "hint_wa_animated": (
        "Анимированный стикер WhatsApp: WEBP {size}×{size} px, до {duration} сек, "
        "не больше {limit} КБ — FPS подбирается автоматически.",
        "WhatsApp animated sticker: WEBP {size}×{size} px, up to {duration} s, "
        "no larger than {limit} KB — the FPS is chosen automatically."),
    "hint_wa_tray": (
        "Иконка набора WhatsApp: PNG {size}×{size} px, не больше {limit} КБ. "
        "Нужна одна на весь набор.",
        "WhatsApp pack icon: PNG {size}×{size} px, no larger than {limit} KB. "
        "One is needed per pack."),

    # --- режим вписывания в квадрат ---
    "fill_square": ("Заполнить квадрат (обрезать края)", "Fill the square (crop edges)"),
    "fill_square_tip": ("Включено — картинка заполняет квадрат целиком, лишнее по "
                        "краям обрезается по центру. Выключено — вписывается целиком, "
                        "а пустое место остаётся прозрачным.",
                        "On — the picture fills the whole square and the overflow "
                        "is cropped around the centre. Off — it fits whole and the "
                        "spare room stays transparent."),
    "fill_square_sticker_tip": ("Стикер Telegram не квадратный: одна его сторона "
                                "512 px, другая — по пропорциям. Режим действует "
                                "только на эмодзи.",
                                "A Telegram sticker is not square: one side is "
                                "512 px and the other follows the proportions. "
                                "This mode only affects emoji."),

    # --- вставка из буфера обмена ---
    "menu_paste": ("Вставить из буфера (Ctrl+V)", "Paste from clipboard (Ctrl+V)"),
    "paste_nothing": ("В буфере обмена нет картинки или файлов",
                      "The clipboard holds no picture or files"),
    "paste_added": ("Из буфера добавлено: {count}", "Added from the clipboard: {count}"),
    "paste_failed": ("Не удалось сохранить картинку из буфера: {error}",
                     "Could not save the clipboard picture: {error}"),
    "drop_hint_paste": ("Ctrl+V — вставить картинку из буфера",
                        "Ctrl+V pastes a picture from the clipboard"),

    # --- предпросмотр в чате ---
    "preview_title": ("Так результат будет выглядеть в чате",
                      "This is how the result will look in chat"),
    "preview_empty": ("Выберите файл в очереди — здесь появится предпросмотр",
                      "Select a file in the queue to see a preview here"),
    "preview_video_note": ("кадр из видео", "a frame from the video"),
    "preview_msg_twitch": ("отличная игра", "great play"),
    "preview_msg_discord": ("смотрите, что получилось", "look what I made"),
    # Пишется над крупным эмодзи, как в настоящем Telegram (у стикеров
    # подписи нет).
    "preview_msg_telegram": ("оцени новый эмодзи", "rate my new emoji"),
    "preview_msg_whatsapp": ("держи", "here you go"),
    "preview_zoom": ("крупно", "zoomed"),
    "preview_today": ("Сегодня в {time}", "Today at {time}"),
    # Низ чата Twitch: поле ввода и строка баллов канала.
    "preview_send_message": ("Отправить сообщение", "Send a message"),
    "preview_chat_button": ("Чат", "Chat"),
    # Разряды по-русски разделяет узкий неразрывный пробел.
    "preview_points_balance": ("1\u202f129\u202f994", "1,129,994"),
    "preview_pack": ("Мой набор стикеров", "My sticker pack"),

    # --- проверка обновлений ---
    # Ссылка встаёт на место номера версии, поэтому короткая.
    "update_available": ("Обновить до {version}", "Update to {version}"),
    "update_tip": ("Установлена версия {current}, вышла {version}. Щелчок открывает "
                   "страницу выпуска на GitHub. Проверку можно отключить в меню "
                   "по правому щелчку.",
                   "Version {current} is installed, {version} is out. Click to open "
                   "the release page on GitHub. The check can be turned off from "
                   "the right-click menu."),
    "update_tip_install": ("Установлена версия {current}, вышла {version}. Щелчок "
                           "скачивает и ставит новую версию. Что в ней нового — "
                           "в меню по правому щелчку.",
                           "Version {current} is installed, {version} is out. Click to "
                           "download and install it. See what's new from the "
                           "right-click menu."),
    "update_downloading": ("Загрузка {percent} %", "Downloading {percent}%"),
    "menu_release_page": ("Что нового в новой версии", "What's new in the new version"),
    "dlg_update_title": ("Обновление", "Update"),
    "dlg_update_text": (
        "Скачать и установить версию {version}?\n\nПосле загрузки программа "
        "закроется, установщик поставит новую версию поверх и запустит её. "
        "Настройки сохранятся.",
        "Download and install version {version}?\n\nOnce downloaded, the app "
        "closes, the installer puts the new version over the old one and starts "
        "it. Settings are kept."),
    "btn_update_install": ("Обновить", "Update"),
    "dlg_update_busy": ("Идёт обработка файлов. Обновить программу можно, когда "
                        "она закончится.",
                        "Files are being processed. The app can be updated once "
                        "that is done."),
    "dlg_update_failed_title": ("Обновление не удалось", "Update failed"),
    "dlg_update_failed_text": (
        "Не получилось скачать или запустить установщик:\n{error}\n\nНовую "
        "версию можно скачать со страницы выпуска.",
        "Couldn't download or start the installer:\n{error}\n\nThe new "
        "version can be downloaded from the release page."),
    "btn_open_release_page": ("Открыть страницу", "Open the page"),
    "err_update_no_installer": ("в выпуске нет установщика для этой сборки",
                                "the release has no installer for this build"),
    "err_update_size": ("файл скачался не полностью", "the file didn't download completely"),
    "err_update_checksum": ("контрольная сумма файла не совпала с указанной на GitHub",
                            "the file's checksum doesn't match the one on GitHub"),
    "update_check_toggle": ("Проверять обновления при запуске",
                            "Check for updates at startup"),
    "menu_open_log": ("Открыть папку журнала", "Open the log folder"),
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
    "lbl_tg_sticker_png": ("Telegram: стикер PNG", "Telegram: PNG sticker"),
    "lbl_tg_sticker_webp": ("Telegram: стикер WEBP", "Telegram: WEBP sticker"),
    "lbl_tg_sticker_webm": ("Telegram: стикер WEBM", "Telegram: WEBM sticker"),
    "lbl_tg_emoji_png": ("Telegram: эмодзи PNG", "Telegram: PNG emoji"),
    "lbl_tg_emoji_webp": ("Telegram: эмодзи WEBP", "Telegram: WEBP emoji"),
    "lbl_tg_emoji_webm": ("Telegram: эмодзи WEBM", "Telegram: WEBM emoji"),
    "lbl_twitch_static_112": ("Twitch: PNG 112×112", "Twitch: PNG 112×112"),
    "lbl_twitch_static_pack": ("Twitch: PNG-комплект 28/56/112",
                               "Twitch: PNG set 28/56/112"),
    "lbl_twitch_animated_112": ("Twitch: GIF 112×112", "Twitch: GIF 112×112"),
    "lbl_twitch_animated_pack": ("Twitch: GIF-комплект 28/56/112",
                                 "Twitch: GIF set 28/56/112"),
    "lbl_dc_sticker_png": ("Discord: стикер PNG", "Discord: PNG sticker"),
    "lbl_dc_sticker_apng": ("Discord: стикер APNG", "Discord: APNG sticker"),
    "lbl_dc_emoji_png": ("Discord: эмодзи PNG", "Discord: PNG emoji"),
    "lbl_dc_emoji_gif": ("Discord: эмодзи GIF", "Discord: GIF emoji"),

    "kb": ("{value} КБ", "{value} KB"),
    "mb": ("{value} МБ", "{value} MB"),

    # --- ошибки обработки (errors.LocalizedError) ---
    "err_source_missing": ("Исходный файл не найден: {name}",
                           "Source file not found: {name}"),
    "err_no_ffmpeg": ("FFmpeg не найден, а без него эту операцию не выполнить. "
                      "Положите ffmpeg.exe и ffprobe.exe рядом с программой "
                      "или добавьте FFmpeg в PATH.",
                      "FFmpeg was not found, and this operation needs it. Put "
                      "ffmpeg.exe and ffprobe.exe next to the application or add "
                      "FFmpeg to PATH."),
    "err_audio_from_non_video": ("Звук можно извлечь только из видео: у изображений, "
                                 "GIF и анимированных картинок звуковой дорожки нет.",
                                 "Audio can only be extracted from video: images, GIFs "
                                 "and animated pictures have no audio track."),
    "err_frames_need_motion": ("Покадровый разбор доступен только для видео, GIF "
                               "и анимированных картинок.",
                               "Frame extraction only works on video, GIFs and "
                               "animated pictures."),
    "err_static_image_target": ("Статичное изображение можно конвертировать только "
                                "в JPG, PNG, WEBP, BMP или AVIF.",
                                "A still image can only be converted to JPG, PNG, "
                                "WEBP, BMP or AVIF."),
    "err_unknown_format": ("Неизвестный выходной формат: {fmt}",
                           "Unknown output format: {fmt}"),
    "err_unsupported_input": ("Неподдерживаемый тип файла: {name}",
                              "Unsupported file type: {name}"),
    "err_needs_motion": ("«{target}» делается только из видео, GIF или анимированной "
                         "картинки. Для неподвижного изображения выберите "
                         "статичный вариант пресета.",
                         "“{target}” can only be made from video, a GIF or an "
                         "animated picture. For a still image pick the static "
                         "version of the preset."),
    "err_ffmpeg_stalled": ("FFmpeg не отвечает более {minutes} мин и был остановлен. "
                           "Возможно, файл повреждён или использует неподдерживаемый "
                           "кодек.",
                           "FFmpeg did not respond for over {minutes} min and was "
                           "stopped. The file may be damaged or use an unsupported "
                           "codec."),
    # Без «Подробности ниже»: первая строка ошибки стоит в строке очереди,
    # и там «ниже» ничего нет. Вывод FFmpeg дописывается в окне подробностей.
    "err_ffmpeg_failed": ("FFmpeg завершился с ошибкой (код {code}).",
                          "FFmpeg failed (code {code})."),
    "err_target_too_small": ("Целевой размер {kb} КБ слишком мал для этого файла. "
                             "Увеличьте размер, обрежьте по времени или уменьшите "
                             "разрешение.",
                             "The target size of {kb} KB is too small for this file. "
                             "Raise the size, trim the duration or lower the "
                             "resolution."),
    "err_too_many_frames": ("В анимации больше {frames} кадров. Сократите фрагмент "
                            "или уменьшите частоту кадров.",
                            "The animation has more than {frames} frames. Trim the "
                            "clip or lower the frame rate."),
    "err_over_limit": ("Результат не удалось уложить в лимит {limit} КБ "
                       "(получено {got} КБ). Сократите длительность или упростите "
                       "анимацию.",
                       "The result could not fit into {limit} KB (got {got} KB). "
                       "Shorten the duration or simplify the animation."),
    "err_limit_unreachable": ("Результат не удалось уложить в лимит {limit} КБ. "
                              "Сократите длительность или упростите анимацию.",
                              "The result could not fit into {limit} KB. Shorten the "
                              "duration or simplify the animation."),
    "err_image_over_limit": ("Не удалось уложиться в лимит {limit} КБ (получено "
                             "{got} КБ). Упростите изображение или уменьшите "
                             "детализацию.",
                             "Could not fit into {limit} KB (got {got} KB). Simplify "
                             "the image or reduce its detail."),
    "err_image_over_limit_alpha": ("Не удалось уложиться в лимит {limit} КБ (получено "
                                   "{got} КБ). Попробуйте формат WEBP — он сжимает "
                                   "сильнее.",
                                   "Could not fit into {limit} KB (got {got} KB). Try "
                                   "the WEBP format — it compresses better."),
    "err_zero_size": ("Изображение имеет нулевой размер и, вероятно, повреждено.",
                      "The image has zero size and is probably damaged."),
    "err_duration_over": ("Длительность {duration} сек превышает лимит {limit} сек.",
                          "The duration of {duration} s exceeds the {limit} s "
                          "limit."),
    # Стикеры Telegram (.tgs) рисует библиотека rlottie.
    "err_no_rlottie": ("Для стикеров .tgs нужна библиотека rlottie, а она не найдена. "
                       "Переустановите программу; при запуске из исходников "
                       "выполните pip install rlottie-python.",
                       "The rlottie library is required for .tgs stickers but was not "
                       "found. Reinstall the application; when running from source, "
                       "run pip install rlottie-python."),
    "err_bad_tgs": ("Не удалось прочитать стикер {name}: файл повреждён или это не "
                    "анимированный стикер Telegram.",
                    "Could not read the sticker {name}: the file is damaged or is not "
                    "a Telegram animated sticker."),
    "err_duration_zero": ("Длительность фрагмента должна быть больше 0 секунд.",
                          "The fragment must be longer than 0 seconds."),
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


def number(value, decimals=2):
    """Число для подписи: без лишних нулей и с запятой по-русски.

    Поля ввода берут разделитель из локали языка интерфейса, и подписи
    рядом должны совпадать с ними: раньше поле показывало «3,00 сек», а
    строка под ним — «обрезан до 3.0 сек».
    """
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    text = f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if _current == RUSSIAN else text


def plural(key, count):
    """Слово в нужной форме для числа: «1 файл», «3 файла», «5 файлов».

    Формы лежат в STRINGS через «|»: у русского три (одна, две-четыре,
    пять и больше), у английского две. Раньше вместо этого писали
    «файла(ов)» и «шт.».
    """
    forms = tr(key).split("|")
    count = abs(int(count))
    if _current == RUSSIAN and len(forms) == 3:
        if count % 10 == 1 and count % 100 != 11:
            return forms[0]
        if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
            return forms[1]
        return forms[2]
    return forms[0] if count == 1 else forms[-1]


def missing_translations():
    """Ключи, у которых нет пары из двух строк. Нужна тестам."""
    broken = []
    for key, pair in STRINGS.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            broken.append(key)
        elif not all(isinstance(value, str) and value.strip() for value in pair):
            broken.append(key)
    return broken

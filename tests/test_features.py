"""Возможности: версия, журнал, память окна, меню, состояние очереди.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_features.py
"""
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
WORK_ROOT = os.path.join(tempfile.gettempdir(), "mcs_tests")
os.makedirs(WORK_ROOT, exist_ok=True)

import shutil
OUT = WORK_ROOT

from PyQt6.QtWidgets import QApplication, QMessageBox, QMenu
from PyQt6.QtCore import QSettings
app = QApplication.instance() or QApplication([])

from language_pin import pin_language
pin_language()  # набор сверяет русские подписи и сам переключает язык
app.setStyle("Fusion")
from styles import build_stylesheet
app.setStyleSheet(build_stylesheet())
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

from main_window import MainWindow
from app_info import version_string, APP_NAME, APP_VERSION, ORGANIZATION
from widgets import StatusDotDelegate

results = []
def check(name, fn):
    try:
        fn(); results.append((name, "OK", "")); print(f"[OK]   {name}")
    except Exception as e:
        results.append((name, "FAIL", f"{type(e).__name__}: {e}"))
        print(f"[FAIL] {name} -- {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()

WORK = os.path.join(OUT, "feattest")
if os.path.exists(WORK): shutil.rmtree(WORK)
os.makedirs(WORK)
from PIL import Image
img = os.path.join(WORK, "картинка.png"); Image.new("RGB",(200,150),(200,40,40)).save(img)
import subprocess
vid = os.path.join(WORK, "видео.mp4")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=1:size=160x120:rate=10",
                "-c:v","libx264","-pix_fmt","yuv420p",vid], check=True, capture_output=True)

# чистый профиль настроек
QSettings(ORGANIZATION, ORGANIZATION).clear(); pin_language()  # чистый тестовый профиль
w = MainWindow(); w.output_dir = WORK; w.output_dir_edit.setText(WORK); w.show(); app.processEvents()

def t_version():
    assert APP_VERSION == "1.1.0", APP_VERSION
    assert version_string() == "1.1.0", version_string()
    # В заголовке только название и версия — подзаголовка у окна нет.
    assert w.windowTitle() == f"{APP_NAME} {version_string()}", w.windowTitle()
    assert version_string() in w.version_label.text(), w.version_label.text()
check("версия видна в заголовке и в интерфейсе", t_version)


def t_legacy_settings_migrated():
    """Переименование не должно стирать сохранённые настройки.

    Имена берём выдуманные: настоящее хранилище трогать нельзя — это
    настройки пользователя, да и окно рядом читает их же.
    """
    from app_info import migrate_legacy_settings
    old_name, new_name = "DTTConvertTestOld", "DTTConvertTestNew"
    old_store = QSettings(old_name, old_name)
    new_store = QSettings(new_name, new_name)
    try:
        old_store.clear(); new_store.clear()
        old_store.setValue("output_dir", WORK)
        old_store.setValue("active_tab", 2)
        old_store.sync(); new_store.sync()

        assert migrate_legacy_settings(new_name, old_name) is True, "перенос не сработал"
        moved = QSettings(new_name, new_name)
        assert moved.value("output_dir", "", type=str) == WORK, moved.value("output_dir")
        assert moved.value("active_tab", 0, type=int) == 2, moved.value("active_tab")

        # Повторно не переносим: иначе правки пользователя откатывались бы
        # к состоянию до переименования при каждом запуске.
        old_store.setValue("output_dir", "C:\\другое"); old_store.sync()
        assert migrate_legacy_settings(new_name, old_name) is False, "перенос повторился"
        assert QSettings(new_name, new_name).value("output_dir", "", type=str) == WORK

        # Пустой источник — переносить нечего, ошибок быть не должно.
        old_store.clear(); new_store.clear()
        old_store.sync(); new_store.sync()
        assert migrate_legacy_settings(new_name, old_name) is False
    finally:
        old_store.clear(); old_store.sync()
        new_store.clear(); new_store.sync()
check("настройки переносятся со старого имени один раз",
      t_legacy_settings_migrated)

def t_log():
    from logging_setup import setup_logging
    path = setup_logging()
    import logging; logging.getLogger("test").info("проверка журнала")
    assert os.path.isfile(path), path
    assert os.path.getsize(path) > 0
check("журнал пишется в файл", t_log)

def t_reset():
    w.overwrite_checkbox.setChecked(True); w.width_spin.setValue(999)
    w._on_reset_settings()
    assert w.overwrite_checkbox.isChecked() is False
    assert w.width_spin.value() == 0, w.width_spin.value()
    assert w.output_dir == os.path.expanduser("~"), w.output_dir
    w.output_dir = WORK; w.output_dir_edit.setText(WORK)
check("сброс настроек", t_reset)

def t_window_state():
    w.resize(1234, 856); w.settings_tabs.setCurrentIndex(2)
    w._save_window_state()
    s = QSettings(ORGANIZATION, ORGANIZATION)
    assert s.value("window_geometry") is not None
    assert s.value("active_tab", type=int) == 2
    assert s.value("splitter_state") is not None
check("память окна: размер, вкладка, разделитель", t_window_state)

def t_eta():
    assert w._format_duration(45) == "45 сек"
    assert w._format_duration(90) == "1 мин 30 сек"
    assert w._format_duration(3700).startswith("1 ч")
    import time as _t
    w._run_started_at = _t.monotonic() - 10
    assert w._estimate_remaining(2, 10)  # непустая оценка
    assert w._estimate_remaining(0, 10) == ""
    assert w._estimate_remaining(10, 10) == ""
check("оценка оставшегося времени", t_eta)

def t_context_menu():
    w.file_list.clear()
    w._on_scan_finished([img, vid], []); app.processEvents()
    created = {}
    real_exec = QMenu.exec
    QMenu.exec = lambda self, *a, **k: created.update(actions=[a.text() for a in self.actions()])
    w._on_queue_context_menu(w.file_list.visualItemRect(w.file_list.item(0)).center())
    QMenu.exec = real_exec
    acts = created.get("actions", [])
    assert any("Открыть файл" in a for a in acts), acts
    assert any("проводнике" in a for a in acts), acts
    assert any("Убрать" in a for a in acts), acts
check("контекстное меню очереди", t_context_menu)

def t_status_dot():
    d = w.file_list.itemDelegate()
    assert isinstance(d, StatusDotDelegate), type(d)
    idx = w.file_list.model().index(0, 0)
    assert d._status_of(idx) is not None
    for status in ("Ожидание","Обработка","Готово","Ошибка"):
        assert status in StatusDotDelegate.STATUS_ROLES
        assert d._colors[status].startswith("#"), d._colors
    # статуса больше нет в тексте строки
    assert "[" not in w.file_list.item(0).text(), w.file_list.item(0).text()
check("статус-точка вместо текста в скобках", t_status_dot)


def t_write_check():
    ok_dir = w.output_dir
    assert w._output_dir_writable() is True
    w.output_dir = r"C:\Windows\System32\config"
    assert w._output_dir_writable() is False, "защищённая папка прошла проверку"
    w.output_dir = ok_dir
check("проверка прав на запись в папку", t_write_check)

def t_open_folder_button():
    assert w.open_folder_button.isVisible() is False, "кнопка видна до конвертации"
    w.file_list.clear(); w._on_scan_finished([img], []); app.processEvents()
    w.file_list.setCurrentRow(0)
    i = w.format_combo.findText("JPG"); w.format_combo.setCurrentIndex(i); w._apply_to_all()
    w._on_start_clicked(); w.worker.wait(30000); app.processEvents()
    assert w.open_folder_button.isVisible() is True, "кнопка не появилась после конвертации"
    assert "заняло" in w.current_file_label.text(), w.current_file_label.text()
check("кнопка «Открыть папку» и время выполнения", t_open_folder_button)

def t_source_protected():
    """Итог не должен затирать исходник даже при включённой перезаписи."""
    d2 = os.path.join(WORK, "same"); os.makedirs(d2, exist_ok=True)
    src = os.path.join(d2, "оригинал.png"); Image.new("RGB",(300,200),(0,200,0)).save(src)
    w.file_list.clear(); w._on_scan_finished([src], []); app.processEvents()
    w.output_dir = d2; w.output_dir_edit.setText(d2)
    w.overwrite_checkbox.setChecked(True)
    w.file_list.setCurrentRow(0)
    i = w.format_combo.findText("PNG"); w.format_combo.setCurrentIndex(i)
    w.resize_checkbox.setChecked(True); w.width_spin.setValue(60); w._apply_to_all()
    w._on_start_clicked(); w.worker.wait(30000); app.processEvents()
    with Image.open(src) as im:
        assert im.size == (300, 200), f"исходник изменён: {im.size}"
    assert os.path.isfile(os.path.join(d2, "оригинал_1.png")), sorted(os.listdir(d2))
    w.output_dir = WORK; w.output_dir_edit.setText(WORK); w.overwrite_checkbox.setChecked(False)
check("исходник защищён от перезаписи", t_source_protected)

def t_translation_table():
    """У каждой строки должен быть перевод на оба языка."""
    import i18n
    broken = i18n.missing_translations()
    assert not broken, f"без перевода: {broken[:5]}"
    assert len(i18n.STRINGS) > 150, len(i18n.STRINGS)
check("таблица перевода заполнена целиком", t_translation_table)

def t_locale_detection():
    """При первом запуске язык берётся из системной локали."""
    from i18n import language_from_locale, RUSSIAN, ENGLISH
    assert language_from_locale("ru_RU") == RUSSIAN
    assert language_from_locale("ru") == RUSSIAN
    for name in ("en_US", "en-GB", "de_DE", "zh_CN", "", None):
        assert language_from_locale(name) == ENGLISH, name
check("язык определяется по системной локали", t_locale_detection)

def t_language_switch():
    """Смена языка переводит интерфейс и не теряет очередь и настройки."""
    import i18n
    from main_window import DATA_ROLE
    i18n.set_language("ru")
    win = MainWindow()
    win.output_dir = WORK
    win._on_scan_finished([img], [])
    win.file_list.setCurrentRow(0)

    def format_codes():
        return {win.format_combo.itemData(i, DATA_ROLE)
                for i in range(win.format_combo.count())} - {None}

    codes_before = format_codes()
    win._apply_telegram_preset("tg_sticker_webm")
    app.processEvents()
    assert win.start_button.text() == "Старт", win.start_button.text()

    win.language_combo.setCurrentIndex(win.language_combo.findData("en"))
    app.processEvents()
    # Список форматов должен пережить пересборку целиком. Флаг «показана
    # строка пресета» оставался от прежнего списка, и первый же
    # _drop_preset_row снимал две первые строки новой модели — заголовок
    # «Изображения» и JPG: пункт пропадал до перезапуска программы.
    missing = codes_before - format_codes()
    assert not missing, f"после смены языка пропали форматы: {sorted(missing)}"
    assert i18n.current_language() == "en"
    assert win.start_button.text() == "Start", win.start_button.text()
    assert win.tab_buttons[0].text() == "General", win.tab_buttons[0].text()
    # очередь и выбранный пресет пережили пересборку окна
    assert win.file_list.count() == 1, win.file_list.count()
    assert win._selected_format == "tg_sticker_webm", win._selected_format
    # Заголовок от языка не зависит: в нём только название и версия.
    assert win.windowTitle() == f"{APP_NAME} {version_string()}", win.windowTitle()
    # и обратно
    win.language_combo.setCurrentIndex(win.language_combo.findData("ru"))
    app.processEvents()
    assert win.start_button.text() == "Старт"
    assert win.file_list.count() == 1
    win.close()
check("смена языка переводит окно и сохраняет состояние", t_language_switch)

def t_language_switch_keeps_selection():
    """Смена языка не должна терять выделение и невнесённый формат.

    При нескольких выделенных файлах выбор формата в списке в задачи ещё
    не записывается — ждёт кнопки «Применить». Пересборка окна возвращала
    выделение последним действием, и _on_selection_changed подставлял
    настройки строки поверх выбранного формата: пользователь жал
    «Применить ко всем» уже с прежним форматом, ничего не заметив.
    """
    from main_window import DATA_ROLE
    win = MainWindow()
    win.output_dir = WORK
    second = os.path.join(WORK, "второй.png")
    shutil.copyfile(img, second)
    win._on_scan_finished([img, second], [])
    for row in range(win.file_list.count()):
        win.file_list.item(row).setSelected(True)
    app.processEvents()
    assert len(win.file_list.selectedItems()) == 2, len(win.file_list.selectedItems())

    win.format_combo.setCurrentIndex(win.format_combo.findData("webp", DATA_ROLE))
    app.processEvents()
    assert win._selected_format == "webp", win._selected_format

    win.language_combo.setCurrentIndex(win.language_combo.findData("en"))
    app.processEvents()
    assert win._selected_format == "webp", \
        f"формат потерян при смене языка: {win._selected_format}"
    assert win.format_combo.currentData(DATA_ROLE) == "webp", \
        win.format_combo.currentData(DATA_ROLE)
    assert len(win.file_list.selectedItems()) == 2, \
        f"выделение схлопнулось до {len(win.file_list.selectedItems())}"
    win.language_combo.setCurrentIndex(win.language_combo.findData("ru"))
    app.processEvents()
    win.close()
check("смена языка сохраняет выделение и выбранный формат",
      t_language_switch_keeps_selection)

# ---------- Версия 1.1: темы, предпросмотр, вставка, обновления ----------
import time as _time
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtWidgets import QLabel as _QLabel


def settle(ms=300):
    deadline = _time.monotonic() + ms / 1000.0
    while _time.monotonic() < deadline:
        app.processEvents()
        _time.sleep(0.01)


def t_platform_themes():
    from styles import palette, theme_for_tab, THEMES
    from widgets import ToggleSwitch
    from main_window import TAB_MAIN, TAB_TWITCH, TAB_WHATSAPP
    win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
    assert len(THEMES) == win.settings_tabs.count(), "у каждой вкладки должна быть тема"
    geometry = {}
    for tab in range(win.settings_tabs.count()):
        win.settings_tabs.setCurrentIndex(tab)
        settle(260)
        sheet = win.right_panel.styleSheet()
        assert bool(sheet) == (tab != TAB_MAIN), f"вкладка {tab}: таблица стилей {bool(sheet)}"
        accent = palette(theme_for_tab(tab))["accent"]
        toggle = win.right_panel.findChildren(ToggleSwitch)[0]
        assert toggle._colors["track_on"] == accent, (tab, toggle._colors["track_on"], accent)
        # Тема меняет только цвета: кнопки вкладок и применения на месте.
        geometry[tab] = [b.geometry().getRect() for b in win.tab_buttons] + [
            win.apply_all_button.geometry().getRect(),
            win.apply_selected_button.geometry().getRect()]
        covers = [c for c in win.right_panel.findChildren(_QLabel)
                  if c.graphicsEffect() is not None]
        assert not covers, "снимок плавного перехода не убрался"
    assert all(g == geometry[0] for g in geometry.values()), geometry
    # Очередь остаётся в основной теме при любой вкладке.
    win.settings_tabs.setCurrentIndex(TAB_TWITCH); settle(260)
    assert win.styleSheet() == "" and win.file_list.styleSheet() == ""
    win.settings_tabs.setCurrentIndex(TAB_WHATSAPP); settle(260)
    win.close()
check("темы вкладок площадок: цвета меняются, вёрстка — нет", t_platform_themes)


def t_theme_contrast():
    from styles import palette, contrast_ratio, THEMES
    pairs = [("text", "surface"), ("button_text", "button_bg"),
             ("bright_text", "selected_bg"), ("callout_text", "callout_bg"),
             ("tab_text", "tab_bg"), ("caption_text", "surface"),
             ("check_text", "surface"), ("bright_text", "primary_bg"),
             ("text", "popup_bg")]
    problems = []
    for theme in THEMES:
        colors = palette(theme)
        for fg, bg in pairs:
            ratio = contrast_ratio(colors[fg], colors[bg])
            if ratio < 4.5:
                problems.append(f"{theme}: {fg} на {bg} = {ratio:.2f}")
        ratio = contrast_ratio(colors["note_text"], colors["surface"])
        if ratio < 4.5:
            problems.append(f"{theme}: note_text на surface = {ratio:.2f}")
    assert not problems, problems
check("контраст текста во всех темах не ниже WCAG AA", t_theme_contrast)


def t_fill_toggles_and_whatsapp():
    from main_window import DATA_ROLE
    win = MainWindow(); win.output_dir = WORK
    win._on_scan_finished([img], []); win.file_list.setCurrentRow(0)
    win._apply_whatsapp_preset("whatsapp_static")
    assert win._selected_format == "whatsapp_static"
    assert "512" in win.whatsapp_hint_label.text()
    win.fill_toggles["discord"].setChecked(True)
    app.processEvents()
    assert all(t.isChecked() for t in win.fill_toggles.values()), "тумблеры разошлись"
    entry = win.file_list.item(0).data(DATA_ROLE)
    assert entry.settings.fill_square, "заполнение не записалось в настройки файла"
    win.file_list.clearSelection(); app.processEvents()
    win.file_list.setCurrentRow(0); app.processEvents()
    assert win.fill_toggles["twitch"].isChecked(), "заполнение не вернулось при выборе файла"
    win._apply_telegram_preset("tg_sticker_png")
    assert not win.fill_toggles["telegram"].isEnabled(), "у стикера Telegram заполнять нечего"
    win._apply_telegram_preset("tg_emoji_png")
    assert win.fill_toggles["telegram"].isEnabled()
    win.close()
check("общий тумблер «заполнить квадрат» и пресеты WhatsApp", t_fill_toggles_and_whatsapp)


def t_chat_preview():
    from main_window import TAB_DISCORD
    win = MainWindow(); win.output_dir = WORK; win.show()
    preview = win.chat_previews["discord"]
    assert not preview.has_content()
    win._on_scan_finished([img, vid], [])
    win.file_list.setCurrentRow(0)
    deadline = _time.monotonic() + 10
    while not preview.has_content() and _time.monotonic() < deadline:
        settle(50)
    assert preview.has_content(), "кадр для предпросмотра не пришёл"
    win.settings_tabs.setCurrentIndex(TAB_DISCORD); settle(250)
    shot = preview.grab().toImage()
    assert not shot.isNull()
    # Поворот сразу виден в предпросмотре.
    width_before = preview._frame.width()
    win.rotate_combo.setCurrentIndex(1); app.processEvents()
    assert preview._frame.width() == preview._source.height(), "поворот не дошёл до предпросмотра"
    win.rotate_combo.setCurrentIndex(0); app.processEvents()
    assert preview._frame.width() == width_before
    # Видео: кадр готовит FFmpeg в фоне.
    win.file_list.setCurrentRow(1)
    deadline = _time.monotonic() + 15
    while not (preview.has_content() and preview._is_video) and _time.monotonic() < deadline:
        settle(50)
    assert preview._is_video and preview.has_content(), "кадр видео не пришёл"
    win.file_list.clearSelection(); app.processEvents()
    assert not preview.has_content(), "без выбранного файла предпросмотр должен опустеть"
    win.close()
check("предпросмотр в чате: картинка, видео, поворот", t_chat_preview)


def t_render_emote_fill():
    from chat_preview import render_emote
    wide = QImage(200, 50, QImage.Format.Format_ARGB32)
    wide.fill(QColor("#ff0000"))
    fit = render_emote(wide, 40, fill=False).toImage()
    fill = render_emote(wide, 40, fill=True).toImage()
    assert fit.pixelColor(20, 2).alpha() == 0, "при вписывании сверху должна быть пустота"
    assert fill.pixelColor(20, 2).alpha() == 255, "при заполнении квадрат должен быть залит"
check("предпросмотр повторяет вписывание и заполнение квадрата", t_render_emote_fill)


def t_paste():
    from PyQt6.QtWidgets import QApplication as _QApp
    win = MainWindow(); win.output_dir = WORK
    before = win.file_list.count()
    picture = QImage(64, 32, QImage.Format.Format_ARGB32); picture.fill(QColor("#00ff00"))
    _QApp.clipboard().setImage(picture)
    win._paste_from_clipboard()
    assert win.file_list.count() == before + 1, "картинка из буфера не добавилась"
    added = win.file_list.item(win.file_list.count() - 1).data(Qt.ItemDataRole.UserRole).input_path
    assert os.path.isfile(added) and os.path.basename(added).startswith("clipboard_"), added
    _QApp.clipboard().setText(vid)
    win._paste_from_clipboard()
    assert win.file_list.count() == before + 2, "путь из буфера не добавился"
    _QApp.clipboard().setText("просто текст")
    win._paste_from_clipboard()
    assert win.file_list.count() == before + 2
    assert "нет" in win.current_file_label.text(), win.current_file_label.text()
    os.remove(added)
    win.close()
from PyQt6.QtCore import Qt
check("Ctrl+V: картинка и путь из буфера встают в очередь", t_paste)


def t_update_check():
    import updater
    assert updater.is_newer("v1.2.0", "1.1.0") and not updater.is_newer("1.1.0", "1.1.0")
    assert updater.is_newer("2.0", "1.9.9") and not updater.is_newer("garbage", "1.0")
    original = updater.fetch_latest_release
    updater.fetch_latest_release = lambda timeout=0: ("9.9.9", "https://github.com/x/y/releases/9.9.9")
    try:
        store = QSettings(ORGANIZATION, ORGANIZATION)
        store.setValue("check_updates", True); store.setValue("last_update_check", 0.0)
        win = MainWindow()
        win._start_update_check()
        deadline = _time.monotonic() + 5
        while not win.update_button.isVisibleTo(win) and _time.monotonic() < deadline:
            settle(50)
        assert win.update_button.isVisibleTo(win), "ссылка на новую версию не появилась"
        assert "9.9.9" in win.update_button.text()
        # Отключённая проверка не ходит в сеть.
        store.setValue("check_updates", False); store.setValue("last_update_check", 0.0)
        win2 = MainWindow(); win2._start_update_check(); settle(200)
        assert not win2.update_button.isVisibleTo(win2)
        win.close(); win2.close()
    finally:
        updater.fetch_latest_release = original
        QSettings(ORGANIZATION, ORGANIZATION).setValue("check_updates", False)
check("проверка обновлений: ссылка появляется, отключение работает", t_update_check)


def t_twitch_long_warning():
    from job_model import ConversionJob, JobSettings
    long_clip = os.path.join(WORK, "долгий.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=20:size=64x64:rate=10",
                    "-c:v","libx264","-pix_fmt","yuv420p",long_clip], check=True, capture_output=True)
    win = MainWindow()
    # FFmpeg окно находит по таймеру после старта — здесь зовём сразу.
    win._check_ffmpeg_status(quiet=True)
    asked = []
    original = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: (asked.append(a), QMessageBox.StandardButton.No)[1])
    try:
        job = ConversionJob(input_path=long_clip, output_dir=WORK,
                            settings=JobSettings(output_format="twitch_animated_112"))
        assert win._confirm_twitch_animation_length([job]) is False
        assert asked, "предупреждение не показано"
        trimmed = ConversionJob(input_path=long_clip, output_dir=WORK,
                                settings=JobSettings(output_format="twitch_animated_112",
                                                     trim_enabled=True, trim_start=0,
                                                     trim_duration=3))
        asked.clear()
        assert win._confirm_twitch_animation_length([trimmed]) is True and not asked
    finally:
        QMessageBox.question = original
    win.close()
check("предупреждение о длинной анимации для Twitch", t_twitch_long_warning)


def t_error_language_follows_ui():
    from errors import LocalizedValueError
    from main_window import DATA_ROLE, STATUS_ERROR
    win = MainWindow(); win.output_dir = WORK
    win._on_scan_finished([img], [])
    item = win.file_list.item(0)
    entry = item.data(DATA_ROLE)
    entry.status = STATUS_ERROR
    entry.message = LocalizedValueError("err_audio_from_non_video")
    item.setData(DATA_ROLE, entry); win._refresh_item_text(item)
    assert "звук" in item.text().lower(), item.text()
    win.language_combo.setCurrentIndex(win.language_combo.findData("en")); app.processEvents()
    item = win.file_list.item(0)
    assert "audio" in item.text().lower(), item.text()
    win.language_combo.setCurrentIndex(win.language_combo.findData("ru")); app.processEvents()
    win.close()
check("текст ошибки в очереди переводится при смене языка", t_error_language_follows_ui)

w.grab().save(os.path.join(OUT, "features.png"))
# Закрываем окно: иначе фоновые потоки доживают до выхода интерпретатора
# и Qt иногда завершает процесс с ненулевым кодом.
w.close()
app.processEvents()
QSettings(ORGANIZATION, ORGANIZATION).clear(); pin_language()  # чистый тестовый профиль
shutil.rmtree(WORK, ignore_errors=True)

print()
failed=[r for r in results if r[1]!="OK"]
print(f"{len(results)-len(failed)}/{len(results)} passed")
for n,s,d in results:
    if s!="OK": print(f"  FAIL {n}: {d}")
sys.exit(1 if failed else 0)

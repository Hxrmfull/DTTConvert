"""Возможности: версия, журнал, память окна, меню, состояние очереди.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_features.py
"""
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
# Помощники тестов (tgs_fixture) лежат рядом с наборами.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
# Подтверждения окно задаёт своим _confirm («<действие> / Отмена»).
MainWindow._confirm = lambda self, *a, **k: True
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
    assert APP_VERSION == "1.2.2", APP_VERSION
    assert version_string() == "1.2.2", version_string()
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
    from chat_preview import SCENES
    # Текст в правой панели — во всех темах (она перекрашивается под вкладку).
    pairs = [("text", "surface"), ("button_text", "button_bg"),
             ("bright_text", "selected_bg"), ("callout_text", "callout_bg"),
             ("tab_text", "tab_bg"), ("caption_text", "surface"),
             ("check_text", "surface"), ("bright_text", "primary_bg"),
             ("text", "popup_bg"), ("note_text", "surface"), ("hint_text", "surface"),
             ("button_text", "button_hover_bg"), ("button_text", "quiet_bg")]
    # Очередь и низ окна всегда в основной теме — их пары только для неё.
    main_pairs = [("bright_text", "start_bg"), ("bright_text", "start_hover"),
                  ("stop_text", "stop_bg"), ("note_text", "window_bg"),
                  ("hint_text", "window_bg"), ("section_text", "window_bg"),
                  ("drop_text", "surface"), ("format_header", "popup_bg"),
                  ("muted_text", "sunken_bg"), ("accent_bright", "window_bg"),
                  ("warning_text", "window_bg")]
    # Границы и значки (WCAG 1.4.11): поле и выключенный тумблер узнаются
    # только по рамке, поэтому нужно хотя бы 3:1 к фону карточки.
    graphics = [("input_border", "surface"), ("check_border", "surface"),
                ("accent_bright", "surface"), ("focus_ring", "button_bg"),
                ("focus_ring", "selected_bg")]
    main_graphics = [("drop_border", "surface"), ("status_pending", "surface"),
                     ("status_done", "surface"), ("status_error", "surface"),
                     ("status_stopped", "surface"), ("status_processing", "surface")]
    problems = []

    def need(colors, theme, fg, bg, minimum):
        ratio = contrast_ratio(colors[fg], colors[bg])
        if ratio < minimum:
            problems.append(f"{theme}: {fg} на {bg} = {ratio:.2f} < {minimum}")

    for theme in THEMES:
        colors = palette(theme)
        for fg, bg in pairs:
            need(colors, theme, fg, bg, 4.5)
        for fg, bg in graphics:
            need(colors, theme, fg, bg, 3.0)
    main = palette()
    for fg, bg in main_pairs:
        need(main, "main", fg, bg, 4.5)
    for fg, bg in main_graphics:
        need(main, "main", fg, bg, 3.0)
    # Точка состояния видна и на выделенной строке очереди.
    for role in ("status_pending", "status_done", "status_error", "status_stopped",
                 "status_processing"):
        need(main, "main", role, "selected_bg", 3.0)
    # Сцены предпросмотра: подписи и текст сообщений на фоне чата и пузыря.
    for name, scene in SCENES.items():
        for fg in ("text", "muted", "name"):
            for bg in ("bg", "panel"):
                need(scene, f"сцена {name}", fg, bg, 4.5)
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
    asked = []

    def fake_fetch(timeout=0):
        asked.append(1)
        return "9.9.9", "https://github.com/x/y/releases/9.9.9"

    updater.fetch_latest_release = fake_fetch
    try:
        store = QSettings(ORGANIZATION, ORGANIZATION)
        store.setValue("check_updates", True); store.setValue("last_update_check", 9e12)
        win = MainWindow()
        win._start_update_check()
        deadline = _time.monotonic() + 5
        while not win.update_button.isVisibleTo(win) and _time.monotonic() < deadline:
            settle(50)
        assert win.update_button.isVisibleTo(win), "ссылка на новую версию не появилась"
        assert "9.9.9" in win.update_button.text()
        # Проверка при каждом запуске: и сразу после прошлой, и при старой
        # отметке времени из прежних версий (выше она стоит «в будущем»).
        assert len(asked) == 1, asked
        assert not store.contains("last_update_check"), "отметка прежнего интервала осталась"
        win3 = MainWindow(); win3._start_update_check()
        deadline = _time.monotonic() + 5
        while len(asked) < 2 and _time.monotonic() < deadline:
            settle(50)
        assert len(asked) == 2, "повторный запуск не спросил GitHub"
        win3.close()
        # Отключённая проверка не ходит в сеть.
        store.setValue("check_updates", False)
        win2 = MainWindow(); win2._start_update_check(); settle(200)
        assert not win2.update_button.isVisibleTo(win2)
        assert len(asked) == 2, "отключённая проверка всё равно спросила GitHub"
        win.close(); win2.close()
    finally:
        updater.fetch_latest_release = original
        QSettings(ORGANIZATION, ORGANIZATION).setValue("check_updates", False)
check("проверка обновлений: ссылка появляется, отключение работает", t_update_check)


def t_update_one_click():
    """Обновление в один щелчок — без сети: «GitHub» отдаёт описание
    выпуска, а установщик лежит в локальном файле (file://)."""
    import hashlib
    import pathlib
    import updater
    import main_window as mw

    # Вариант сборки: по деинсталлятору рядом с exe и FFmpeg внутри сборки.
    app_dir = os.path.join(WORK, "installed"); bundle = os.path.join(app_dir, "_internal")
    os.makedirs(bundle, exist_ok=True)
    exe = os.path.join(app_dir, "DTTConvert.exe")
    assert updater.installed_variant(exe, bundle) is None, "без деинсталлятора — не установщик"
    open(os.path.join(app_dir, "unins000.exe"), "wb").close()
    assert updater.installed_variant(exe, bundle) == updater.VARIANT_WITHOUT_FFMPEG
    open(os.path.join(bundle, "ffmpeg.exe"), "wb").close()
    assert updater.installed_variant(exe, bundle) == updater.VARIANT_WITH_FFMPEG
    assert updater.installed_variant() is None, "запуск из исходников не обновляется установщиком"

    payload = b"MZ" + os.urandom(300_000)
    src = os.path.join(WORK, "setup_src.exe"); open(src, "wb").write(payload)
    file_url = pathlib.Path(src).as_uri()
    prefix = file_url.rsplit("/", 1)[0] + "/"
    name = updater.setup_asset_name("9.9.9", updater.VARIANT_WITH_FFMPEG)
    assert name == "DTTConvert-9.9.9-windows-x64-with-ffmpeg-setup.exe"

    def release(size=len(payload), digest=hashlib.sha256(payload).hexdigest(), url=file_url):
        return {"tag_name": "v9.9.9", "html_url": "https://github.com/x/y/releases/9.9.9",
                "assets": [{"name": name.replace("with-", "without-"), "size": 1,
                            "browser_download_url": url},
                           {"name": name, "size": size, "digest": f"sha256:{digest}",
                            "browser_download_url": url}]}

    original_prefix = updater.DOWNLOAD_PREFIX
    original_fetch = updater.fetch_latest_data
    original = (mw.installed_variant, mw.launch_installer)
    try:
        # Чужие ссылки и выпуск без нужного файла отвергаются.
        assert updater.find_installer(release(), updater.VARIANT_WITH_FFMPEG) is None
        updater.DOWNLOAD_PREFIX = prefix
        found = updater.find_installer(release(), updater.VARIANT_WITH_FFMPEG)
        assert found and found[0] == name and found[2] == len(payload), found
        assert updater.find_installer({"tag_name": "v9.9.9", "html_url": "https://github.com/a",
                                       "assets": []}, updater.VARIANT_WITH_FFMPEG) is None

        # Скачивание: целиком и с верной суммой — да; иначе файла не остаётся.
        target = os.path.join(WORK, "setup_dl.exe")
        seen = []
        assert updater.download_verified(file_url, target, len(payload),
                                         hashlib.sha256(payload).hexdigest(), seen.append)
        assert open(target, "rb").read() == payload and seen[-1] == 100
        os.remove(target)
        for size, digest, key in ((len(payload) + 5, None, "err_update_size"),
                                  (len(payload) - 5, None, "err_update_size"),
                                  (len(payload), "0" * 64, "err_update_checksum")):
            try:
                updater.download_verified(file_url, target, size, digest)
                raise AssertionError(f"ошибка {key} не поднялась")
            except updater.LocalizedRuntimeError as exc:
                assert exc.key == key, exc.key
            assert not os.path.exists(target) and not os.path.exists(target + ".part")
        assert not updater.download_verified(file_url, target, len(payload), None,
                                             cancelled=lambda: True)
        assert not os.path.exists(target)

        # Окно: щелчок → подтверждение → загрузка → запуск установщика → закрытие.
        launched = []
        updater.fetch_latest_data = lambda timeout=0: release()
        mw.installed_variant = lambda: updater.VARIANT_WITH_FFMPEG
        mw.launch_installer = launched.append
        win = MainWindow()
        win._on_update_found("9.9.9", "https://github.com/x/y/releases/9.9.9")
        win.show(); settle(50)
        win._on_update_clicked()
        deadline = _time.monotonic() + 10
        while not launched and _time.monotonic() < deadline:
            settle(50)
        assert launched, "установщик не запустился"
        assert open(launched[0], "rb").read() == payload
        assert os.path.basename(launched[0]) == name
        assert not win.isVisible(), "окно не закрылось перед установкой"

        # Сбой загрузки: ссылка возвращается, окно не закрывается.
        updater.fetch_latest_data = lambda timeout=0: release(digest="0" * 64)
        opened = []
        win2 = MainWindow(); win2._open_update_page = lambda: opened.append(1)
        win2._on_update_found("9.9.9", "https://github.com/x/y/releases/9.9.9")
        win2.show(); settle(50)
        launched.clear()
        win2._on_update_clicked()
        deadline = _time.monotonic() + 10
        while win2._update_download is not None and _time.monotonic() < deadline:
            settle(50)
        settle(50)
        assert not launched and win2.isVisible()
        assert win2.update_button.isEnabled() and "9.9.9" in win2.update_button.text()
        assert opened, "после сбоя не предложили страницу выпуска"
        win2.close()
    finally:
        updater.DOWNLOAD_PREFIX = original_prefix
        updater.fetch_latest_data = original_fetch
        mw.installed_variant, mw.launch_installer = original
check("обновление в один щелчок: проверка файла, запуск установщика", t_update_one_click)


def t_links():
    """Файлы по ссылкам — с локального сервера, без интернета."""
    import io
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import url_import
    from main_window import SUPPORTED_INPUT_EXTS

    png = io.BytesIO(); Image.new("RGBA", (40, 40), (0, 200, 0, 255)).save(png, "PNG")
    gif = io.BytesIO()
    Image.new("P", (30, 30), 1).save(gif, "GIF", save_all=True,
                                       append_images=[Image.new("P", (30, 30), 2)], duration=100)
    routes = {
        "/pic.png": ("image/png", png.getvalue()),
        # CDN без расширения в адресе и с неверным типом — решает сигнатура.
        "/emote/abc/3x": ("application/octet-stream", gif.getvalue()),
        "/page": ("text/html", b'<html><head><meta property="og:image" '
                               b'content="/emote/abc/3x"></head></html>'),
        "/empty": ("text/html", b"<html><body>nothing</body></html>"),
        "/text.txt": ("text/plain", b"hello"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = routes.get(self.path)
            if route is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", route[0])
            self.send_header("Content-Length", str(len(route[1])))
            self.end_headers()
            self.wfile.write(route[1])

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    store = os.path.join(WORK, "links_store")
    original_get_json = url_import._get_json
    try:
        assert url_import.extract_urls(f"смотри {base}/pic.png и\n{base}/page.") == \
            [f"{base}/pic.png", f"{base}/page"]
        # Известные сайты — без сети (API недоступен — правило всё равно работает).
        def offline(url):
            raise OSError("offline")
        url_import._get_json = offline
        assert url_import.resolve_known_site("https://7tv.app/emotes/01ABC") == \
            ("https://cdn.7tv.app/emote/01ABC/4x.webp", "7tv_01ABC")
        assert url_import.resolve_known_site("https://betterttv.com/emotes/5f1b") == \
            ("https://cdn.betterttv.net/emote/5f1b/3x", "bttv_5f1b")
        assert url_import.resolve_known_site("https://www.frankerfacez.com/emoticon/28136-LilZ") == \
            ("https://cdn.frankerfacez.com/emote/28136/4", "LilZ")
        assert url_import.resolve_known_site("https://giphy.com/gifs/cat-funny-JIX9t2") == \
            ("https://i.giphy.com/JIX9t2.gif", "cat-funny")
        assert url_import.resolve_known_site(
            "https://static-cdn.jtvnw.net/emoticons/v2/25/default/dark/1.0") == (
            "https://static-cdn.jtvnw.net/emoticons/v2/25/default/dark/3.0", "twitch_25")
        url_import._get_json = lambda url: {"name": "RainTime"}
        assert url_import.resolve_known_site("https://7tv.app/emotes/01ABC")[1] == "RainTime"

        # Тип — по содержимому, имя — из адреса; страница ведёт к og:image.
        path = url_import.download_url(f"{base}/pic.png", store, SUPPORTED_INPUT_EXTS)
        assert os.path.basename(path) == "pic.png" and open(path, "rb").read() == png.getvalue()
        path = url_import.download_url(f"{base}/emote/abc/3x", store, SUPPORTED_INPUT_EXTS)
        assert os.path.basename(path) == "abc.gif", path
        path = url_import.download_url(f"{base}/page", store, SUPPORTED_INPUT_EXTS)
        assert path.endswith(".gif") and open(path, "rb").read() == gif.getvalue()
        for url, key in ((f"{base}/empty", "err_link_no_media"),
                         (f"{base}/text.txt", "err_link_unsupported"),
                         (f"{base}/missing", "err_link_download"),
                         ("ftp://example/x.png", "err_link_bad")):
            try:
                url_import.download_url(url, store, SUPPORTED_INPUT_EXTS)
                raise AssertionError(f"{url}: ошибка не поднялась")
            except url_import.LocalizedRuntimeError as exc:
                assert exc.key == key, (url, exc.key)

        # Окно: ссылки встают в очередь, ошибки собираются в одно сообщение.
        import main_window as mw
        original_dir = mw.pasted_directory
        mw.pasted_directory = lambda: store
        warnings = []
        original_warning = QMessageBox.warning
        QMessageBox.warning = staticmethod(lambda *a, **k: warnings.append(a))
        try:
            win = MainWindow(); win.show(); settle(50)
            win._add_files_from_urls([f"{base}/pic.png", f"{base}/text.txt"])
            win._add_files_from_urls([f"{base}/page"])  # пока идёт первая загрузка
            deadline = _time.monotonic() + 15
            while (win._link_worker is not None or win.file_list.count() < 2) \
                    and _time.monotonic() < deadline:
                settle(50)
            settle(100)
            names = sorted(os.path.basename(win._entry(win.file_list.item(i)).input_path)
                           for i in range(win.file_list.count()))
            assert names == ["abc.gif", "pic.png"], names
            assert len(warnings) == 1 and "text.txt" in warnings[0][2], warnings

            # Ctrl+V из браузера: адрес из <img src> важнее картинки в буфере.
            from PyQt6.QtCore import QMimeData
            mime = QMimeData()
            mime.setHtml(f'<img src="{base}/emote/abc/3x">')
            mime.setImageData(QImage(8, 8, QImage.Format.Format_ARGB32))
            QApplication.clipboard().setMimeData(mime)
            win.file_list.clear()
            win._paste_from_clipboard()
            deadline = _time.monotonic() + 15
            while win.file_list.count() < 1 and _time.monotonic() < deadline:
                settle(50)
            entry = win._entry(win.file_list.item(0))
            assert entry.input_path.endswith(".gif"), entry.input_path
            win.close()
        finally:
            mw.pasted_directory = original_dir
            QMessageBox.warning = original_warning

        # Старые загрузки чистятся целиком, свежие остаются.
        old = url_import.link_directory(store)
        os.utime(old, (0, 0))
        url_import.cleanup_links(store, 7)
        assert not os.path.exists(old) and os.listdir(os.path.join(store, "links"))
    finally:
        url_import._get_json = original_get_json
        server.shutdown()
check("файлы по ссылкам: прямые, страницы, Ctrl+V из браузера", t_links)


def t_twitch_long_warning():
    from job_model import ConversionJob, JobSettings
    long_clip = os.path.join(WORK, "долгий.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=20:size=64x64:rate=10",
                    "-c:v","libx264","-pix_fmt","yuv420p",long_clip], check=True, capture_output=True)
    win = MainWindow()
    # FFmpeg окно находит по таймеру после старта — здесь зовём сразу.
    win._check_ffmpeg_status(quiet=True)
    asked = []
    # Подмена только у этого окна: ответ «Отмена», вопрос запоминается.
    win._confirm = lambda *a, **k: (asked.append(a), False)[1]
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


# ---------- Разбор интерфейса: фокус, выключенные поля, очередь, низ окна ----------

def _brightest(widget):
    """Самый светлый цвет на снимке виджета — грубо, это цвет текста."""
    image = widget.grab().toImage()
    best = 0
    for y in range(image.height()):
        for x in range(image.width()):
            best = max(best, image.pixelColor(x, y).lightness())
    return best


def _pixels_changed(widget, action):
    before = widget.grab().toImage()
    action(); settle(80)
    after = widget.grab().toImage()
    return sum(before.pixel(x, y) != after.pixel(x, y)
               for y in range(before.height()) for x in range(before.width()))


def t_focus_visible():
    from PyQt6.QtCore import Qt as _Qt
    win = MainWindow(); win.resize(1140, 790); win.show(); win.activateWindow(); settle(200)
    win._on_scan_finished([img], []); settle(100)
    targets = [win.start_button, win.format_combo, win.resize_checkbox,
               win.overwrite_checkbox, win.tab_buttons[1]]
    for widget in targets:
        changed = _pixels_changed(widget,
                                  lambda: widget.setFocus(_Qt.FocusReason.TabFocusReason))
        if not widget.hasFocus():
            continue  # окно не стало активным (свёрнут рабочий стол) — проверить нечем
        assert changed > 20, f"фокус не виден: {widget.objectName() or type(widget).__name__}"
    # Кнопки берут фокус только с клавиатуры, область прокрутки — никогда.
    assert win.start_button.focusPolicy() == _Qt.FocusPolicy.TabFocus
    from PyQt6.QtWidgets import QScrollArea
    assert win.findChild(QScrollArea, "SettingsScroll").focusPolicy() == _Qt.FocusPolicy.NoFocus
    win.close()
check("фокус клавиатуры виден на кнопках, полях и тумблерах", t_focus_visible)


def t_disabled_fields_look_disabled():
    win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
    win.resize_checkbox.setChecked(False); settle(50)
    assert not win.width_spin.isEnabled() and not win.width_label.isEnabled()
    off_spin, off_label = _brightest(win.width_spin), _brightest(win.width_label)
    win.resize_checkbox.setChecked(True); settle(50)
    on_spin, on_label = _brightest(win.width_spin), _brightest(win.width_label)
    assert on_spin - off_spin > 60, (on_spin, off_spin)
    assert on_label - off_label > 60, (on_label, off_label)
    # Тихая кнопка (#QuietButton) тоже гаснет: правило по имени перебивало
    # общее :disabled. Очередь пуста — снимать отметки не с чего.
    assert not win.uncheck_all_button.isEnabled()
    quiet_off = _brightest(win.uncheck_all_button)
    win._on_scan_finished([img], []); settle(50)
    assert win.uncheck_all_button.isEnabled()
    assert _brightest(win.uncheck_all_button) - quiet_off > 60
    win.close()
check("выключенное поле и его подпись выглядят выключенными", t_disabled_fields_look_disabled)


def t_queue_row_fits():
    from main_window import DATA_ROLE, STATUS_ERROR
    from errors import LocalizedRuntimeError
    long_name = os.path.join(WORK, "очень_длинное_имя_файла_для_проверки_очереди_" * 2 + ".png")
    Image.new("RGB", (64, 64), (0, 120, 200)).save(long_name)
    win = MainWindow(); win.resize(980, 680); win.show(); settle(100)
    win._on_scan_finished([long_name, img], []); settle(100)
    item = win.file_list.item(1)
    entry = item.data(DATA_ROLE)
    entry.status = STATUS_ERROR
    entry.message = LocalizedRuntimeError("err_ffmpeg_failed", detail="x" * 300, code=1)
    item.setData(DATA_ROLE, entry); win._refresh_item_text(item); settle(50)
    assert win.file_list.horizontalScrollBar().maximum() == 0, "у очереди появилась прокрутка вбок"
    viewport = win.file_list.viewport().width()
    for row in range(win.file_list.count()):
        rect = win.file_list.visualItemRect(win.file_list.item(row))
        assert rect.right() <= viewport, (row, rect, viewport)
    # Состояние словами — в подсказке, «Подробности ниже» в строке нет.
    assert win.file_list.item(1).toolTip().startswith("Ошибка"), win.file_list.item(1).toolTip()
    assert "ниже" not in win.file_list.item(1).text()
    # Сокращение не трогает формат.
    from widgets import fit_item_text
    metrics = win.file_list.fontMetrics()
    text = fit_item_text(metrics, 200, "а" * 80 + ".png", "  →  MP4", "   ·   ошибка " * 5)
    assert text.endswith("…") or "→  MP4" in text, text
    assert "→  MP4" in fit_item_text(metrics, 200, "а" * 80 + ".png", "  →  MP4"), "формат пропал"
    win.close()
check("строка очереди: без прокрутки вбок, формат и значок видны", t_queue_row_fits)


def t_bottom_row_fits():
    for language in ("ru", "en"):
        win = MainWindow(); win.resize(980, 680); win.show(); settle(100)
        win.language_combo.setCurrentIndex(win.language_combo.findData(language)); settle(100)
        win.report_button.setVisible(True)
        win.open_folder_button.setVisible(True)
        win._on_update_found("9.9.9", "https://example.invalid")
        win.current_file_label.setText("Обработка завершена — успешно: 10, с ошибкой: 2"
                                       "   ·   заняло 12 мин 30 сек")
        settle(100)
        for widget in (win.overwrite_checkbox, win.update_button, win.open_folder_button,
                       win.report_button, win.stop_button, win.start_button,
                       win.language_combo):
            assert widget.width() >= widget.sizeHint().width() - 1, \
                (language, widget.text() if hasattr(widget, "text") else widget, widget.width(),
                 widget.sizeHint().width())
        assert not win.version_label.isVisible(), "ссылка на обновление должна заменить номер"
        # Полный итог — в text() и в подсказке, даже если на экране сокращён.
        assert "заняло" in win.current_file_label.text()
        win.language_combo.setCurrentIndex(win.language_combo.findData("ru")); settle(50)
        win.close()
check("низ окна: при 980 px ничего не обрезано", t_bottom_row_fits)


def t_numbers_and_plurals():
    from i18n import number, plural, set_language
    set_language("ru")
    assert number(3.0) == "3" and number(3.5) == "3,5" and number(0.25) == "0,25"
    assert [plural("word_files", n) for n in (1, 2, 5, 11, 21, 22, 112)] == \
        ["файл", "файла", "файлов", "файлов", "файл", "файла", "файлов"]
    set_language("en")
    assert number(3.5) == "3.5" and plural("word_files", 1) == "file"
    assert plural("word_files", 2) == "files"
    set_language("ru")
    from errors import LocalizedValueError
    assert "3,25" in LocalizedValueError("err_duration_over", duration=3.25, limit=3.0).text()
check("числа и склонения по языку интерфейса", t_numbers_and_plurals)


def t_platform_tab_states():
    from main_window import TAB_MAIN, TAB_TELEGRAM
    win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
    win._on_scan_finished([img], []); win.file_list.setCurrentRow(0); settle(100)
    win._set_selected_format("png")
    win.settings_tabs.setCurrentIndex(TAB_TELEGRAM); settle(260)
    # Пресет не выбран: выноска говорит об этом, предпросмотр приглушён.
    assert "не выбран" in win.telegram_hint_label.text(), win.telegram_hint_label.text()
    assert not win.chat_previews["telegram"]._active
    # На площадке вместо кнопок применения — примечание той же высоты.
    assert win.apply_stack.currentIndex() == 1
    height_platform = win.apply_stack.height()
    win._apply_telegram_preset("tg_sticker_png"); settle(50)
    assert "512" in win.telegram_hint_label.text()
    assert win.chat_previews["telegram"]._active
    win.settings_tabs.setCurrentIndex(TAB_MAIN); settle(260)
    assert win.apply_stack.currentIndex() == 0
    assert win.apply_stack.height() == height_platform, "строка применения прыгает по высоте"
    # Сообщение о пресете снимается при смене выделения, итог обработки — нет.
    win.file_list.clearSelection(); settle(50)
    assert win.current_file_label.text() == idle_status_text(), win.current_file_label.text()
    win.close()


def t_combo_popup_corners():
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtWidgets import QComboBox
    win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
    for combo in win.findChildren(QComboBox):
        container = combo.view().window()
        # Окно списка на экран не выводим — снимок рисуется и так.
        container.setAttribute(_Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        combo.showPopup(); settle(150)
        image = container.grab().toImage()
        combo.hidePopup(); settle(50)
        corners = [image.pixelColor(x, y).alpha()
                   for x, y in ((0, 0), (image.width() - 1, 0),
                                (0, image.height() - 1),
                                (image.width() - 1, image.height() - 1))]
        # За скруглённой карточкой не должно быть квадратного окна.
        assert corners == [0, 0, 0, 0], (combo.currentText(), corners)
    win.close()
check("выпадающие списки без квадрата за скруглёнными углами", t_combo_popup_corners)


def t_twitch_preview_uses_user_icons():
    from chat_preview import (ChatPreview, PADDING, TWITCH_BADGE_SIZE,
                              TWITCH_BALANCE_HEIGHT)
    green = QImage(64, 64, QImage.Format.Format_ARGB32)
    green.fill(QColor("#00ff00"))

    def render(code):
        preview = ChatPreview("twitch"); preview.resize(470, 170)
        preview.set_preset(code, False); preview.set_image(green)
        return preview.grab().toImage()

    def green_pixels(image, x0, y0, x1, y1):
        return sum(image.pixelColor(x, y).green() > 200 and image.pixelColor(x, y).red() < 60
                   for y in range(y0, y1) for x in range(x0, x1))

    badge_box = (PADDING, PADDING, PADDING + TWITCH_BADGE_SIZE, PADDING + 24)
    balance_box = (PADDING, 170 - PADDING - TWITCH_BALANCE_HEIGHT, 200, 170 - PADDING)
    plain = render("twitch_static_112")
    # По умолчанию у ников нарисованные значки, а не картинка пользователя.
    assert green_pixels(plain, *badge_box) == 0
    assert green_pixels(plain, *balance_box) == 0
    # Пресет значка — картинка пользователя на месте значка у ника.
    assert green_pixels(render("twitch_badge_pack"), *badge_box) > 100
    # Пресет баллов — в строке баллов под полем ввода.
    assert green_pixels(render("twitch_points_pack"), *balance_box) > 100
check("предпросмотр Twitch: свой значок и иконка баллов встают на место стандартных",
      t_twitch_preview_uses_user_icons)


def t_spinbox_text_fits():
    from PyQt6.QtWidgets import QAbstractSpinBox
    from main_window import TAB_MAIN, TAB_TELEGRAM
    for language in ("ru", "en"):
        win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
        win.language_combo.setCurrentIndex(win.language_combo.findData(language)); settle(100)
        # Длинные, но реальные значения: конец обрезки у ролика на
        # пару часов, начало фрагмента Telegram у часового видео.
        win.trim_end_spin.setValue(9999.99); win.trim_start_spin.setValue(9999.5)
        win.tg_start_spin.setMaximum(3600.0); win.tg_start_spin.setValue(3599.9)
        for tab in (TAB_MAIN, TAB_TELEGRAM):
            win.settings_tabs.setCurrentIndex(tab); settle(260)
            for spin in win.settings_tabs.currentWidget().findChildren(QAbstractSpinBox):
                edit = spin.lineEdit()
                need = edit.fontMetrics().horizontalAdvance(edit.text())
                # Кнопки счётчика не должны съедать текст: «0,00 сек» целиком.
                assert edit.width() >= need, (language, edit.text(), edit.width(), need)
        win.language_combo.setCurrentIndex(win.language_combo.findData("ru")); settle(50)
        win.close()
check("текст в полях чисел не обрезается кнопками", t_spinbox_text_fits)


def t_tgs_in_queue_and_preview():
    from tgs_fixture import make_tgs
    from main_window import DATA_ROLE, TAB_TELEGRAM, supported_files_filter
    sticker = make_tgs(os.path.join(WORK, "стикер.tgs"), frames=90, fps=30)
    assert "*.tgs" in supported_files_filter()
    win = MainWindow(); win.resize(1140, 790); win.show(); settle(100)
    win._on_scan_finished([sticker], [])
    win.file_list.setCurrentRow(0)
    item = win.file_list.item(0)
    # Формат по умолчанию — GIF, длительность видна прямо в очереди.
    assert item.data(DATA_ROLE).settings.output_format == "gif"
    assert "3" in item.text() and "→" in item.text(), item.text()
    deadline = _time.monotonic() + 10
    while item.icon().isNull() and _time.monotonic() < deadline:
        settle(50)
    assert not item.icon().isNull(), "у стикера нет миниатюры"
    # Предпросмотр проигрывает стикер, а не показывает один кадр.
    win.settings_tabs.setCurrentIndex(TAB_TELEGRAM); settle(260)
    preview = win.chat_previews["telegram"]
    deadline = _time.monotonic() + 10
    while preview._movie is None and _time.monotonic() < deadline:
        settle(50)
    assert preview._movie is not None and preview.has_content(), "стикер не проигрывается"
    win.close()
check("стикер .tgs: миниатюра, длительность, проигрывание в предпросмотре",
      t_tgs_in_queue_and_preview)


def idle_status_text():
    from main_window import idle_status
    return idle_status()
check("вкладки площадок: пресет не выбран, примечание вместо кнопок", t_platform_tab_states)

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

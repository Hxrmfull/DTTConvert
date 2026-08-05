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
QSettings(ORGANIZATION, ORGANIZATION).clear()
w = MainWindow(); w.output_dir = WORK; w.output_dir_edit.setText(WORK); w.show(); app.processEvents()

def t_version():
    assert APP_VERSION == "1.0.0", APP_VERSION
    assert version_string() == "1.0.0", version_string()
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
        assert status in StatusDotDelegate.STATUS_COLORS
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

w.grab().save(os.path.join(OUT, "features.png"))
# Закрываем окно: иначе фоновые потоки доживают до выхода интерпретатора
# и Qt иногда завершает процесс с ненулевым кодом.
w.close()
app.processEvents()
QSettings(ORGANIZATION, ORGANIZATION).clear()
shutil.rmtree(WORK, ignore_errors=True)

print()
failed=[r for r in results if r[1]!="OK"]
print(f"{len(results)-len(failed)}/{len(results)} passed")
for n,s,d in results:
    if s!="OK": print(f"  FAIL {n}: {d}")
sys.exit(1 if failed else 0)

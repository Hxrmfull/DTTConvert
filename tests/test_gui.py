"""Интерфейс: очередь, пресеты, настройки, отчёт, ошибки.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_gui.py
"""
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
WORK_ROOT = os.path.join(tempfile.gettempdir(), "mcs_tests")
os.makedirs(WORK_ROOT, exist_ok=True)

import shutil, subprocess, traceback
WORK = WORK_ROOT
if os.path.exists(WORK): shutil.rmtree(WORK)
os.makedirs(WORK)
SUB = os.path.join(WORK, "sub"); os.makedirs(SUB)

from PIL import Image
img1 = os.path.join(WORK, "картинка.png"); Image.new("RGBA",(400,300),(255,0,0,255)).save(img1)
img2 = os.path.join(SUB, "nested.jpg"); Image.new("RGB",(200,200),(0,255,0)).save(img2)
junk = os.path.join(WORK, "readme.txt"); open(junk,"w").write("x")
vid = os.path.join(WORK, "видео.mp4")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=2:size=320x240:rate=25",
                "-c:v","libx264","-pix_fmt","yuv420p",vid],check=True,capture_output=True)

from PyQt6.QtWidgets import QApplication, QMessageBox
app = QApplication.instance() or QApplication([])

from language_pin import pin_language
pin_language()  # набор сверяет русские подписи

# Silence modal dialogs so the test can run unattended
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import main_window as mw
from app_info import ORGANIZATION
from main_window import MainWindow, DATA_ROLE, STATUS_ERROR, STATUS_DONE
# Подтверждения окно задаёт своим _confirm («<действие> / Отмена»).
MainWindow._confirm = lambda self, *a, **k: True
def E(item): return item.data(DATA_ROLE)

results=[]
def check(name, fn):
    try:
        fn(); results.append((name,"OK","")); print(f"[OK] {name}")
    except Exception as e:
        results.append((name,"FAIL",f"{type(e).__name__}: {e}")); print(f"[FAIL] {name} -- {e}")
        traceback.print_exc()

w = MainWindow()
w.output_dir = WORK
w.output_dir_edit.setText(WORK)

def t_add_files():
    w._on_scan_finished([img1, vid], [junk])
    assert w.file_list.count() == 2, w.file_list.count()
check("GUI add files (accepted + skipped)", t_add_files)

def t_dedup():
    before = w.file_list.count()
    w._on_scan_finished([img1], [])
    assert w.file_list.count() == before, "duplicate was added (#12)"
check("GUI duplicate detection (#12)", t_dedup)

def t_thumbnail():
    """Миниатюры строятся в фоне, поэтому ждём воркер, а не проверяем сразу."""
    worker = w._image_thumb_worker
    assert worker is not None, "разбор миниатюр не запустился"
    worker.wait(15000)
    app.processEvents()
    item = w.file_list.item(0)
    assert not item.icon().isNull(), "no thumbnail for image"
check("GUI thumbnail generated for image", t_thumbnail)


def t_reorder():
    w.file_list.setCurrentRow(1)
    first_before = E(w.file_list.item(0)).input_path
    w._move_selected(-1)
    first_after = E(w.file_list.item(0)).input_path
    assert first_before != first_after, "move up did nothing"
    assert E(w.file_list.item(0)) is not None, "data lost on reorder"
    w._move_selected(1)  # restore
check("GUI reorder up/down keeps data", t_reorder)

def t_settings_apply():
    w.file_list.setCurrentRow(0)
    idx = w.format_combo.findData("png", DATA_ROLE)
    w.format_combo.setCurrentIndex(idx)
    w._apply_to_selected()
    fmt = E(w.file_list.item(0)).settings.output_format
    assert fmt == "png", fmt
check("GUI apply format to selected", t_settings_apply)

def t_telegram_preset():
    w._apply_telegram_preset("tg_sticker_webp")
    codes = {E(w.file_list.item(i)).settings.output_format
             for i in range(w.file_list.count())}
    assert "tg_sticker_webp" in codes, codes
check("GUI telegram preset applies", t_telegram_preset)

def t_twitch_preset():
    w._apply_twitch_preset("twitch_static_112")
    codes = {E(w.file_list.item(i)).settings.output_format
             for i in range(w.file_list.count())}
    assert "twitch_static_112" in codes, codes
check("GUI twitch preset applies", t_twitch_preset)





def t_conversion_flow():
    w.file_list.clear()
    w._on_scan_finished([img1], [])
    w.file_list.setCurrentRow(0)
    idx = w.format_combo.findData("jpg", DATA_ROLE)
    w.format_combo.setCurrentIndex(idx)
    w._apply_to_all()
    w._on_start_clicked()
    assert w.worker is not None, "worker not started"
    w.worker.wait(30000)
    app.processEvents()
    st = E(w.file_list.item(0)).status
    assert st == STATUS_DONE, f"status={st}"
    out = os.path.join(WORK, "картинка.jpg")
    assert os.path.isfile(out), "output file missing"
check("GUI full conversion run (image->jpg)", t_conversion_flow)

def t_progress_and_report():
    app.processEvents()
    assert w.report_button.isVisible() or w.report_button.isEnabled(), "report button should be available"
    assert w._last_report, "report empty"
    label = w.current_file_label.text()
    assert "успешно" in label, label
    val = w.overall_progress_bar.value()
    assert val == 100, f"progress {val}"
check("GUI progress + report after run (#6)", t_progress_and_report)

def t_report_csv():
    csv_path = os.path.join(WORK, "rep.csv")
    mw.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (csv_path, ""))
    w._on_save_report()
    assert os.path.isfile(csv_path)
    content = open(csv_path, encoding="utf-8-sig").read()
    assert "Файл" in content and "Готово" in content, content[:200]
check("GUI CSV report written", t_report_csv)

def t_error_display():
    # frames format on an image is invalid -> should surface as error, short text in list
    w.file_list.clear()
    w._on_scan_finished([img1], [])
    w.file_list.setCurrentRow(0)
    idx = w.format_combo.findData("frames", DATA_ROLE)
    w.format_combo.setCurrentIndex(idx)
    w._apply_to_all()
    w._on_start_clicked()
    w.worker.wait(30000)
    app.processEvents()
    item = w.file_list.item(0)
    st = E(item).status
    assert st == STATUS_ERROR, f"expected error, got {st}"
    assert "\n" not in item.text(), "list text must be single line (#3 error display)"
    assert item.toolTip(), "tooltip with details expected"
check("GUI error shows short text + tooltip", t_error_display)

def t_stopped_label():
    label = w.current_file_label.text()
    assert "ошибкой: 1" in label, label
check("GUI failure counted in summary (#6)", t_stopped_label)

def t_settings_persist():
    w.overwrite_checkbox.setChecked(True)
    w.settings_store.setValue("output_dir", WORK)
    w.settings_store.setValue("overwrite", True)
    w.settings_store.sync()
    from PyQt6.QtCore import QSettings
    s2 = QSettings(ORGANIZATION, ORGANIZATION)
    assert s2.value("output_dir", "", type=str) == WORK
    assert s2.value("overwrite", False, type=bool) is True
check("GUI QSettings persistence (#10)", t_settings_persist)

def t_overwrite_mode():
    from worker import resolve_output_path
    p1 = resolve_output_path(WORK, "картинка", "jpg", overwrite=False)
    assert p1.endswith("_1.jpg") or not os.path.exists(os.path.join(WORK,"картинка.jpg")), p1
    p2 = resolve_output_path(WORK, "картинка", "jpg", overwrite=True)
    assert p2.endswith("картинка.jpg"), p2
check("GUI overwrite setting honoured", t_overwrite_mode)

w.close()
def t_dialog_filter_matches_supported():
    """Фильтр диалога должен покрывать все поддерживаемые расширения.

    Раньше он был отдельной строкой: AVIF и HEIC принимались
    перетаскиванием, но в окне выбора файлов не показывались.
    """
    from main_window import supported_files_filter, SUPPORTED_INPUT_EXTS
    text = supported_files_filter()
    missing = [ext for ext in SUPPORTED_INPUT_EXTS if f"*{ext}" not in text]
    assert not missing, f"нет в фильтре: {missing}"
check("GUI фильтр диалога покрывает все форматы", t_dialog_filter_matches_supported)

def t_queue_checkboxes():
    """Обрабатываются только отмеченные файлы."""
    from PyQt6.QtCore import Qt
    w.file_list.clear(); w._update_queue_counter()
    extra = []
    for i in range(3):
        p = os.path.join(WORK, f"выбор{i}.png")
        Image.new("RGB", (60, 40), (i * 60, 90, 140)).save(p)
        extra.append(p)
    w._on_scan_finished(extra, []); app.processEvents()
    assert all(w.file_list.item(i).checkState() == Qt.CheckState.Checked for i in range(3))

    w.file_list.item(1).setCheckState(Qt.CheckState.Unchecked); app.processEvents()
    assert E(w.file_list.item(1)).enabled is False, "галочка не сохранилась в данных"
    assert "Отмечено 2 из 3" in w.queue_check_all.text(), w.queue_check_all.text()
    assert w.queue_check_all.checkState() == Qt.CheckState.PartiallyChecked
    # Галочка «все»: при частичной отметке — отмечает все, при полной — снимает.
    w.queue_check_all.click(); app.processEvents()
    assert len(w._checked_rows()) == 3 and w.queue_check_all.checkState() == Qt.CheckState.Checked
    w.queue_check_all.click(); app.processEvents()
    assert not w._checked_rows() and w.queue_check_all.checkState() == Qt.CheckState.Unchecked

    w._set_all_checked(False); app.processEvents()
    assert not w._checked_rows(), "отметки не сняты"
    w._set_all_checked(True); app.processEvents()
    assert len(w._checked_rows()) == 3, "отметки не выставлены"
check("GUI галочки очереди: выбор и счётчик", t_queue_checkboxes)

def t_start_processes_only_checked():
    from PyQt6.QtCore import Qt
    from main_window import STATUS_DONE, STATUS_PENDING
    w.file_list.item(0).setCheckState(Qt.CheckState.Unchecked); app.processEvents()
    idx = w.format_combo.findData("jpg", DATA_ROLE); w.format_combo.setCurrentIndex(idx); w._apply_to_all()
    w._on_start_clicked()
    assert w.worker is not None, "обработка не запустилась"
    w.worker.wait(30000); app.processEvents()
    statuses = [E(w.file_list.item(i)).status for i in range(3)]
    assert statuses[0] == STATUS_PENDING, f"неотмеченный файл обработан: {statuses}"
    assert statuses[1] == STATUS_DONE and statuses[2] == STATUS_DONE, statuses
    assert w.overall_progress_bar.value() == 100, w.overall_progress_bar.value()
check("GUI старт обрабатывает только отмеченные", t_start_processes_only_checked)

def t_discord_preset():
    # Кнопка пресета вкладку не переключает: её нажимают, уже находясь на ней.
    w.file_list.setCurrentRow(1)
    w._apply_discord_preset("discord_emoji_gif")
    app.processEvents()
    assert E(w.file_list.item(1)).settings.output_format == "discord_emoji_gif"
    assert w.discord_preset_buttons["discord_emoji_gif"].isChecked()
    assert not w.discord_preset_buttons["discord_sticker_png"].isChecked()
check("GUI пресет Discord применяется и подсвечивается", t_discord_preset)

def t_tab_switch_keeps_preset():
    """Смена вкладки не должна сбрасывать выбранный пресет площадки."""
    from main_window import TAB_MAIN
    w.file_list.setCurrentRow(1)
    w._apply_telegram_preset("tg_sticker_webm")
    app.processEvents()
    w.settings_tabs.setCurrentIndex(TAB_MAIN)
    app.processEvents()
    w._store_panel_settings([w.file_list.item(1)])
    fmt = E(w.file_list.item(1)).settings.output_format
    assert fmt == "tg_sticker_webm", f"пресет потерян при смене вкладки: {fmt}"
check("GUI пресет площадки переживает смену вкладки", t_tab_switch_keeps_preset)

def t_tab_not_switched_on_add():
    """Добавление и выбор файла не должны выбрасывать с текущей вкладки."""
    from main_window import TAB_TWITCH
    w.settings_tabs.setCurrentIndex(TAB_TWITCH)
    app.processEvents()
    extra = os.path.join(WORK, "ещё.png")
    Image.new("RGB", (120, 90), (10, 20, 30)).save(extra)
    w._on_scan_finished([extra], [])
    app.processEvents()
    assert w.settings_tabs.currentIndex() == TAB_TWITCH,         f"вкладка переключилась при добавлении файла на {w.settings_tabs.currentIndex()}"
    w.file_list.setCurrentRow(0)
    app.processEvents()
    assert w.settings_tabs.currentIndex() == TAB_TWITCH,         "вкладка переключилась при выборе файла в очереди"
check("GUI вкладка не переключается при добавлении и выборе файла",
      t_tab_not_switched_on_add)

def t_format_groups():
    """Список форматов разбит на группы, заголовки не выбираются."""
    from main_window import FORMAT_GROUPS
    from PyQt6.QtCore import Qt
    model = w.format_combo.model()
    headers, codes = [], []
    for row in range(model.rowCount()):
        item = model.item(row)
        if item.flags() == Qt.ItemFlag.NoItemFlags:
            headers.append(item.text())
        else:
            # Код лежит в данных пункта: подписи переводятся, искать формат
            # по тексту после смены языка стало бы нечем.
            codes.append(item.data(DATA_ROLE))
    assert len(headers) == len(FORMAT_GROUPS), (len(headers), len(FORMAT_GROUPS))
    expected = [code for _caption, group in FORMAT_GROUPS for code in group]
    assert codes == expected, (codes, expected)
    # Пресетов площадок в списке нет: у них свои вкладки.
    for code in ("tg_sticker_webm", "twitch_static_112", "discord_emoji_gif"):
        assert code not in codes, f"пресет площадки {code} не должен быть в списке"
    # Заголовок отличается от пунктов оттенком, иначе группа сливается со списком.
    # Начертание задаёт элемент, а приглушённый цвет — делегат: и правило QSS,
    # и setForeground у элемента таблица стилей списка перебивает.
    from styles import palette
    from widgets import GroupHeaderDelegate
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QStyleOptionViewItem
    header_row = next(r for r in range(model.rowCount())
                      if model.item(r).flags() == Qt.ItemFlag.NoItemFlags)
    header_item = model.item(header_row)
    assert header_item.font().bold(), "заголовок группы должен быть выделен"
    from PyQt6.QtGui import QFontInfo
    assert QFontInfo(header_item.font()).pixelSize() < \
        QFontInfo(w.format_combo.font()).pixelSize()

    # В Qt 6 делегат спрашивают по индексу: itemDelegate() отдаёт
    # стандартный, даже когда свой уже назначен.
    delegate = w.format_combo.itemDelegate()
    assert hasattr(delegate, "_separator_color"), "нет черты между группами"
    assert isinstance(delegate, GroupHeaderDelegate), type(delegate).__name__
    muted = QColor(palette()["format_header"])
    for row, expect_muted in ((header_row, True), (header_row + 1, False)):
        option = QStyleOptionViewItem()
        delegate.initStyleOption(option, model.index(row, 0))
        painted = option.palette.color(QPalette.ColorRole.Text)
        assert (painted == muted) is expect_muted, \
            f"строка {row}: цвет {painted.name()}, приглушённый ожидался={expect_muted}"
check("GUI список форматов разбит на группы с заголовками", t_format_groups)

def t_preset_shown_in_format_combo():
    """Пресета площадки в списке нет, но поле формата обязано его показывать."""
    from main_window import format_label
    w.file_list.setCurrentRow(0)
    w._apply_telegram_preset("tg_sticker_webm")
    app.processEvents()
    assert w.format_combo.currentText() == format_label("tg_sticker_webm"), \
        w.format_combo.currentText()
    assert w._preset_row_shown, "временная строка пресета не добавлена"
    # Выбор обычного формата убирает временную строку
    before = w.format_combo.count()
    idx = w.format_combo.findData("png", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert not w._preset_row_shown, "временная строка осталась в списке"
    assert w.format_combo.count() == before - 2, (w.format_combo.count(), before)
    assert w._selected_format == "png", w._selected_format
check("GUI выбранный пресет виден в поле формата", t_preset_shown_in_format_combo)


def t_platform_disables_size():
    """У пресета площадки размер и качество задаёт спецификация."""
    w._apply_twitch_preset("twitch_static_112")
    app.processEvents()
    assert not w.resize_checkbox.isEnabled(), "размер должен быть недоступен"
    assert not w.quality_checkbox.isEnabled(), "качество должно быть недоступно"
    idx = w.format_combo.findData("mp4", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert w.resize_checkbox.isEnabled() and w.quality_checkbox.isEnabled()
check("GUI пресет площадки гасит несовместимые настройки", t_platform_disables_size)

def t_audio_fields():
    """Звук доступен только там, где он есть."""
    idx = w.format_combo.findData("mp4", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert w.audio_combo.isEnabled(), "у MP4 звук настраивается"
    idx = w.format_combo.findData("png", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert not w.audio_combo.isEnabled(), "у картинки звука нет"
    idx = w.format_combo.findData("mp3", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert not w.resize_checkbox.isEnabled(), "у звука нет размера кадра"
    assert w.audio_bitrate_combo.isEnabled(), "битрейт звука должен быть доступен"
check("GUI поля звука включаются по выбранному формату", t_audio_fields)

def t_trim_and_quality_availability():
    """Поля доступны там, где они правда работают.

    Обрезка по времени доходит до extract_audio, поэтому у MP3 она открыта.
    Качество и «уложить в размер» крутить нечем у PNG (нет ни качества
    сжатия, ни битрейта) — раньше оба поля были доступны и молча ничего
    не делали.
    """
    idx = w.format_combo.findData("mp3", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert w.trim_checkbox.isEnabled(), "обрезка звука должна быть доступна"
    assert not w.quality_checkbox.isEnabled(), "у MP3 качества кодека нет"
    assert not w.target_size_checkbox.isEnabled(), "у MP3 целевой размер не работает"

    idx = w.format_combo.findData("png", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert not w.quality_checkbox.isEnabled(), "у PNG качества нет"
    assert not w.target_size_checkbox.isEnabled(), "у PNG целевой размер не работает"

    idx = w.format_combo.findData("jpg", DATA_ROLE); w.format_combo.setCurrentIndex(idx)
    app.processEvents()
    assert w.quality_checkbox.isEnabled() and w.target_size_checkbox.isEnabled(), \
        "у JPG работают оба"
check("GUI качество и обрезка доступны там, где действуют", t_trim_and_quality_availability)

def t_settings_round_trip():
    """Все новые поля доходят от панели до очереди и обратно."""
    from job_model import JobSettings
    source = JobSettings(
        output_format="webm", rotate=270, flip_horizontal=True,
        flip_vertical=True, quality_enabled=True, quality=42,
        trim_enabled=True, trim_start=2.5, trim_duration=4.0,
        audio_mode="none", audio_bitrate=256,
    )
    w._load_settings_into_panel(source)
    app.processEvents()
    back = w._current_panel_settings()
    for field in ("output_format", "rotate", "flip_horizontal", "flip_vertical",
                  "quality_enabled", "quality", "trim_enabled", "trim_start",
                  "trim_duration", "audio_mode", "audio_bitrate"):
        assert getattr(back, field) == getattr(source, field), \
            f"{field}: {getattr(back, field)!r} вместо {getattr(source, field)!r}"
check("GUI новые настройки переживают запись и чтение панели", t_settings_round_trip)

def t_trim_start_end():
    """В панели задаются начало и конец, наружу уходит длительность."""
    from job_model import JobSettings
    w.file_list.setCurrentRow(0)
    w._on_queue_info_ready(vid, {"width": 320, "height": 240,
                                 "duration": 10.0, "fps": 25.0})
    app.processEvents()
    w.trim_checkbox.setChecked(True)
    w.trim_start_spin.setValue(3.0)
    w.trim_end_spin.setValue(7.0)
    app.processEvents()
    settings = w._current_panel_settings()
    assert settings.trim_start == 3.0, settings.trim_start
    assert abs(settings.trim_duration - 4.0) < 0.01, settings.trim_duration

    # Обратно в панель длительность разворачивается в момент конца
    w._load_settings_into_panel(JobSettings(output_format="mp4", trim_enabled=True,
                                            trim_start=2.0, trim_duration=5.0))
    app.processEvents()
    assert w.trim_start_spin.value() == 2.0, w.trim_start_spin.value()
    assert abs(w.trim_end_spin.value() - 7.0) < 0.01, w.trim_end_spin.value()

    # Конец не может оказаться раньше начала
    w.trim_start_spin.setValue(9.9)
    app.processEvents()
    assert w.trim_end_spin.value() > w.trim_start_spin.value(), \
        (w.trim_start_spin.value(), w.trim_end_spin.value())
check("GUI длительность задаётся началом и концом", t_trim_start_end)

def t_apng_in_format_list():
    """APNG — обычный выходной формат, а покадровый разбор — папка."""
    from main_window import format_label
    assert w.format_combo.findData("apng", DATA_ROLE) >= 0, "APNG нет в списке форматов"
    frames_row = w.format_combo.findData("frames", DATA_ROLE)
    assert frames_row >= 0, "покадрового разбора нет в списке"
    frames_label = w.format_combo.itemText(frames_row)
    assert "папка" in frames_label.lower(), frames_label
    # разные пункты, их нельзя путать
    assert format_label("apng") != frames_label
check("GUI APNG есть в списке, кадры помечены как папка", t_apng_in_format_list)

def t_stopped_status():
    """Прерванный файл получает своё состояние, а не виснет в «Обработке»."""
    from main_window import STATUS_PROCESSING, STATUS_STOPPED
    w._on_scan_finished([img1], [])
    w._job_rows = [0]
    item = w.file_list.item(0)
    entry = E(item); entry.status = STATUS_PROCESSING; entry.progress = 45
    item.setData(DATA_ROLE, entry)
    w._on_file_cancelled(0)
    assert E(w.file_list.item(0)).status == STATUS_STOPPED, E(w.file_list.item(0)).status
check("GUI отменённый файл выходит из состояния «Обработка»", t_stopped_status)

# Окно закрываем до выхода: closeEvent останавливает фоновые потоки (копию
# видео для предпросмотра FFmpeg делает секундами). Без этого поток
# уничтожался на ходу при выходе интерпретатора, и Qt ронял процесс
# с кодом 0xC0000409 — уже после того, как все проверки прошли.
w.close()
app.processEvents()

print()
failed=[r for r in results if r[1]!="OK"]
print(f"{len(results)-len(failed)}/{len(results)} passed")
for n,s,d in results:
    if s!="OK": print(f"  FAIL {n}: {d}")
sys.exit(1 if failed else 0)

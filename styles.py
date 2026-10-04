"""Тёмная тема приложения и её варианты для вкладок площадок.

Все цвета живут в палитрах: роль → цвет. Таблица стилей — шаблон с
подстановками вида $surface, поэтому одна и та же разметка собирается
в основной теме и в темах Telegram, Twitch и Discord. Темы площадок
меняют только цвета: отступы, рамки и начертание шрифта общие, иначе
вкладки разъехались бы по высоте (у тестов вёрстки запас около 20 px).

Стрелки списков и счётчиков Qt не умеет рисовать средствами QSS
(CSS-приём с нулевым размером и рамками даёт квадраты), поэтому нужные
иконки генерируются один раз при запуске и подставляются в стили.
"""

import os
import tempfile
from string import Template

THEME_MAIN = "main"
THEME_TELEGRAM = "telegram"
THEME_TWITCH = "twitch"
THEME_DISCORD = "discord"
THEME_WHATSAPP = "whatsapp"
THEME_KICK = "kick"
THEME_YOUTUBE = "youtube"

# Основная тема. Роли названы по назначению, а не по цвету: одинаковые
# значения у разных ролей — совпадение, темы площадок их разводят.
BASE_PALETTE = {
    "surface": "#24252e",
    "border_subtle": "#3a3b48",
    "card_border": "#45475f",
    "text": "#e6e6e6",
    "bright_text": "#ffffff",
    "hover_bg": "#2c2e3a",
    "accent": "#6c63ff",
    "window_bg": "#1e1f26",
    "selected_bg": "#3a3d63",
    "accent_hover": "#7a72ff",
    # Рамки полей и выключенного тумблера — не ниже 3:1 к фону карточки
    # (WCAG 1.4.11): фон поля совпадает с карточкой, и поле узнаётся только
    # по рамке. Было #3a3b48 и #4a4c60 — 1,4 и 1,8, поля почти терялись.
    "check_border": "#6f7180",
    "input_border": "#71727b",
    "input_border_hover": "#86868e",
    # Рамка элемента с фокусом клавиатуры. Белая, а не акцентная: акцентом
    # уже обведены выбранный пресет и вкладка, и фокус на них был бы не виден.
    "focus_ring": "#ffffff",
    "button_hover_bg": "#3d4060",
    "hover_border": "#565a80",
    "disabled_text": "#55566a",
    "danger_border": "#6c3a44",
    "accent_bright": "#8a83ff",
    "muted_text": "#a9abb8",
    "sunken_bg": "#202129",
    "hint_text": "#9a9ba5",
    "section_text": "#8a8dfc",
    "tab_bg": "#292a34",
    "tab_text": "#aeb0bc",
    "tab_hover_bg": "#323440",
    "tab_checked_border": "#676b9c",
    "button_bg": "#33354a",
    "button_text": "#f0f0f5",
    "button_border": "#55587a",
    "button_pressed": "#2a2c3e",
    "disabled_bg": "#232430",
    "disabled_border": "#34364a",
    # Кнопка «Старт» — своя роль, а не accent: белый текст 14 px на #6c63ff
    # давал 4,3 — меньше AA. При наведении кнопка темнеет, а не светлеет,
    # иначе контраст падал до 3,7.
    "start_bg": "#5b52f0",
    "start_hover": "#4f46dc",
    "start_border": "#7a72ff",
    "start_disabled_bg": "#2b2b3a",
    "start_disabled_text": "#6a6b7c",
    "stop_bg": "#4a2c33",
    "stop_text": "#ffb3bb",
    "stop_hover": "#5c333c",
    "stop_disabled_bg": "#2b2629",
    "stop_disabled_border": "#45383c",
    "stop_disabled_text": "#6b5c60",
    "primary_bg": "#3b3670",
    "primary_hover": "#494290",
    "quiet_bg": "#2a2b35",
    "quiet_hover_bg": "#3a2f34",
    "quiet_hover_text": "#ffc9cf",
    "selected_hover": "#464a76",
    "callout_text": "#c2c4d0",
    "callout_bg": "#2b2d3b",
    "caption_text": "#9ea2c8",
    "caption_line": "#3c3f5c",
    # Было #7e808c: на фоне карточки контраст 3,9 — мелкий текст читался
    # с трудом. Теперь 4,6, по WCAG AA.
    "note_text": "#8a8c98",
    "bottom_line": "#2f3040",
    "faint_text": "#5f6070",
    "popup_bg": "#272834",
    "popup_hover": "#32344a",
    "popup_selected": "#4a4d7a",
    "check_text": "#d7d8e0",
    # Цвета, которые рисует сам Python-код (тумблеры, точки статуса,
    # пустая очередь, заголовки групп в списке форматов).
    "toggle_track_off": "#383a48",
    "toggle_knob_off": "#b9bbc9",
    "toggle_track_off_disabled": "#26272f",
    "toggle_track_on_disabled": "#3a3760",
    "arrow": "#b9bbc9",
    "arrow_off": "#5f6070",
    # Заголовки групп в списке форматов и подсказка пустой очереди: были
    # #74768a и #6f7180 — около 3,2, меньше AA. Приглушённость заголовка
    # теперь держится на мелком жирном начертании, а не на тусклом цвете.
    "format_header": "#9a9ba5",
    # Пунктир пустой очереди — граница зоны перетаскивания, нужно 3:1.
    "drop_border": "#71727b",
    "drop_text": "#9a9ba5",
    "drop_text_active": "#9a95ff",
    # Точки состояния в очереди — не ниже 3:1 и к фону списка, и к
    # выделенной строке: прежние серый и красный на выделении давали 2,2 и 2,8.
    "status_pending": "#a3a4ae",
    "status_processing": "#9a95ff",
    "status_done": "#5cc98f",
    "status_error": "#ff7a85",
    "status_stopped": "#c9a227",
    # Выделенный текст в полях: поверх акцента. Белый не читается на
    # кислотно-зелёном акценте Kick — там он тёмный.
    "selection_text": "#ffffff",
    "warning_text": "#ff6b6b",
}

# Темы площадок: только то, что отличается от основной. Цвета взяты из
# тёмных тем самих площадок, чтобы вкладка узнавалась с первого взгляда.
# Twitch нельзя ограничить одним акцентом: его фиолетовый почти совпадает
# с акцентом программы, поэтому меняются и фоны.
PLATFORM_OVERRIDES = {
    THEME_TWITCH: {
        "surface": "#18181b", "card_border": "#3a3a3d",
        "border_subtle": "#3a3a3d", "hover_bg": "#26262c",
        "text": "#efeff1", "bright_text": "#ffffff",
        "accent": "#9146ff", "accent_hover": "#a970ff", "accent_bright": "#bf94ff",
        "selected_bg": "#3f2a6b", "selected_hover": "#4d3384",
        "tab_bg": "#1f1f23", "tab_text": "#adadb8", "tab_hover_bg": "#2a2a30",
        "tab_checked_border": "#9146ff",
        "button_bg": "#2f2f35", "button_text": "#efeff1", "button_border": "#53535f",
        "button_hover_bg": "#3a3a44", "hover_border": "#7a7a88",
        "button_pressed": "#232327",
        "primary_bg": "#772ce8", "primary_hover": "#9146ff",
        "callout_bg": "#232327", "callout_text": "#c8c8d0",
        "caption_text": "#c3a8f5", "caption_line": "#3a3a3d",
        "note_text": "#9b9ba8",
        "popup_bg": "#1f1f23", "popup_hover": "#2f2f35", "popup_selected": "#3f2a6b",
        "check_border": "#666671", "check_text": "#dedee3",
        "input_border": "#67676a", "input_border_hover": "#7d7d80",
        "section_text": "#bf94ff", "hint_text": "#adadb8",
        "toggle_track_off": "#35353b", "toggle_track_on_disabled": "#3b2d5c",
    },
    THEME_DISCORD: {
        "surface": "#2b2d31", "card_border": "#3f4147",
        "border_subtle": "#3f4147", "hover_bg": "#35373c",
        "text": "#dbdee1", "bright_text": "#ffffff",
        "accent": "#5865f2", "accent_hover": "#6d78f4", "accent_bright": "#8891f7",
        "selected_bg": "#3c4270", "selected_hover": "#474e85",
        "tab_bg": "#232428", "tab_text": "#b5bac1", "tab_hover_bg": "#35373c",
        "tab_checked_border": "#5865f2",
        "button_bg": "#4e5058", "button_text": "#ffffff", "button_border": "#5c5f66",
        "button_hover_bg": "#5c5f68", "hover_border": "#80848e",
        "button_pressed": "#3f4147",
        "primary_bg": "#5865f2", "primary_hover": "#4752c4",
        "callout_bg": "#232428", "callout_text": "#c4c9ce",
        "caption_text": "#b5bac1", "caption_line": "#3f4147",
        "note_text": "#9aa0aa",
        "popup_bg": "#232428", "popup_hover": "#35373c", "popup_selected": "#404249",
        "check_border": "#75787f", "check_text": "#dbdee1",
        "input_border": "#76787d", "input_border_hover": "#8d9094",
        "section_text": "#8891f7", "hint_text": "#b5bac1",
        "toggle_track_off": "#4e5058", "toggle_track_on_disabled": "#3a3f6e",
    },
    THEME_TELEGRAM: {
        "surface": "#17212b", "card_border": "#2b3a4a",
        "border_subtle": "#2b3a4a", "hover_bg": "#202b36",
        "text": "#f5f5f5", "bright_text": "#ffffff",
        "accent": "#2ea6ff", "accent_hover": "#4cb4ff", "accent_bright": "#64b5ef",
        "selected_bg": "#2b5278", "selected_hover": "#33608c",
        "tab_bg": "#1e2833", "tab_text": "#a9b7c6", "tab_hover_bg": "#253445",
        "tab_checked_border": "#2ea6ff",
        "button_bg": "#232e3c", "button_text": "#f5f5f5", "button_border": "#3a4d63",
        "button_hover_bg": "#2b3b4d", "hover_border": "#4f6a88",
        "button_pressed": "#1b2531",
        "primary_bg": "#2b5278", "primary_hover": "#33608c",
        "callout_bg": "#1e2c3a", "callout_text": "#c0ccd8",
        "caption_text": "#8fa3b8", "caption_line": "#2b3a4a",
        "note_text": "#8496a9",
        "popup_bg": "#1e2833", "popup_hover": "#253445", "popup_selected": "#2b5278",
        "check_border": "#5f6f80", "check_text": "#e1e6eb",
        "input_border": "#646e7a", "input_border_hover": "#7a838d",
        "section_text": "#64b5ef", "hint_text": "#8fa3b8",
        "toggle_track_off": "#2b3a4a", "toggle_track_on_disabled": "#22405e",
    },
    THEME_WHATSAPP: {
        "surface": "#111b21", "card_border": "#2a3942",
        "border_subtle": "#2a3942", "hover_bg": "#202c33",
        "text": "#e9edef", "bright_text": "#ffffff",
        "accent": "#00a884", "accent_hover": "#06cf9c", "accent_bright": "#25d366",
        "selected_bg": "#005c4b", "selected_hover": "#006e5a",
        "tab_bg": "#202c33", "tab_text": "#aebac1", "tab_hover_bg": "#2a3942",
        "tab_checked_border": "#00a884",
        "button_bg": "#2a3942", "button_text": "#e9edef", "button_border": "#3b4a54",
        "button_hover_bg": "#33444f", "hover_border": "#54656f",
        "button_pressed": "#1f2c33",
        "primary_bg": "#005c4b", "primary_hover": "#006e5a",
        "callout_bg": "#1f2c33", "callout_text": "#c5ced3",
        "caption_text": "#99a8b1", "caption_line": "#2a3942",
        "note_text": "#8f9ea8",
        "popup_bg": "#233138", "popup_hover": "#2a3942", "popup_selected": "#005c4b",
        "check_border": "#5e6b73", "check_text": "#d1d7db",
        "input_border": "#5e6a71", "input_border_hover": "#747f85",
        "section_text": "#25d366", "hint_text": "#99a8b1",
        "toggle_track_off": "#2a3942", "toggle_track_on_disabled": "#0b4a3e",
    },
    # Kick: почти чёрный фон и кислотно-зелёный акцент. На таком зелёном
    # белый текст не читается, поэтому кнопки и выделение — тёмно-зелёные,
    # а яркий зелёный остаётся для рамок, подписей и тумблеров.
    THEME_KICK: {
        "surface": "#141517", "card_border": "#2f3237",
        "border_subtle": "#2f3237", "hover_bg": "#1d1f22",
        "text": "#e8e8e8", "bright_text": "#ffffff",
        "accent": "#53fc18", "accent_hover": "#6ffd3d", "accent_bright": "#53fc18",
        "selected_bg": "#1f4a10", "selected_hover": "#275a15",
        "tab_bg": "#191b1e", "tab_text": "#b0b3b8", "tab_hover_bg": "#24272b",
        "tab_checked_border": "#53fc18",
        "button_bg": "#24272b", "button_text": "#e8e8e8", "button_border": "#3d4147",
        "button_hover_bg": "#2e3237", "hover_border": "#5a6068",
        "button_pressed": "#1a1c1f",
        "primary_bg": "#1f6a0c", "primary_hover": "#267f10",
        "callout_bg": "#1b1d20", "callout_text": "#c9ccd1",
        "caption_text": "#8fe86b", "caption_line": "#2f3237",
        "note_text": "#9a9ea5",
        "popup_bg": "#191b1e", "popup_hover": "#24272b", "popup_selected": "#1f4a10",
        "check_border": "#6a6f76", "check_text": "#dcdee1",
        "input_border": "#676c73", "input_border_hover": "#7d8289",
        "section_text": "#53fc18", "hint_text": "#a6aab0",
        "toggle_track_off": "#2f3237", "toggle_track_on_disabled": "#22401a",
        "selection_text": "#0b0c0d",
    },
    # YouTube: тёмная тема самого YouTube и его красный. Красный кнопок
    # темнее фирменного #ff0000: белый текст на нём давал меньше 4,5.
    THEME_YOUTUBE: {
        "surface": "#181818", "card_border": "#303030",
        "border_subtle": "#303030", "hover_bg": "#222222",
        "text": "#f1f1f1", "bright_text": "#ffffff",
        "accent": "#ff3b30", "accent_hover": "#ff5a50", "accent_bright": "#ff6e66",
        "selected_bg": "#5a1714", "selected_hover": "#6c1c18",
        "tab_bg": "#1f1f1f", "tab_text": "#aaaaaa", "tab_hover_bg": "#2a2a2a",
        "tab_checked_border": "#ff3b30",
        "button_bg": "#272727", "button_text": "#f1f1f1", "button_border": "#3f3f3f",
        "button_hover_bg": "#323232", "hover_border": "#5f5f5f",
        "button_pressed": "#1c1c1c",
        "primary_bg": "#cc0000", "primary_hover": "#e00000",
        "callout_bg": "#212121", "callout_text": "#cfcfcf",
        "caption_text": "#ff8a82", "caption_line": "#303030",
        "note_text": "#a0a0a0",
        "popup_bg": "#1f1f1f", "popup_hover": "#2a2a2a", "popup_selected": "#5a1714",
        "check_border": "#717171", "check_text": "#e0e0e0",
        "input_border": "#6c6c6c", "input_border_hover": "#848484",
        "section_text": "#ff6e66", "hint_text": "#aaaaaa",
        "toggle_track_off": "#303030", "toggle_track_on_disabled": "#4a1a17",
    },
}

THEMES = (THEME_MAIN, THEME_TELEGRAM, THEME_TWITCH, THEME_DISCORD, THEME_WHATSAPP,
          THEME_KICK, THEME_YOUTUBE)


def palette(theme=THEME_MAIN):
    """Полная палитра темы: основная плюс отличия площадки."""
    colors = dict(BASE_PALETTE)
    colors.update(PLATFORM_OVERRIDES.get(theme, {}))
    return colors


_STYLESHEET_TEMPLATE = Template("""
QWidget {
    background-color: $window_bg;
    color: $text;
    font-family: "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: $window_bg;
}

/* Фон прозрачный: иначе подписи рисуют прямоугольник цвета окна
   поверх более светлой карточки настроек. */
QLabel {
    color: $text;
    background: transparent;
}

/* Подпись выключенного поля гаснет вместе с ним: иначе «Ширина» и
   «Начало» выглядели доступными, хотя поле рядом заперто. */
QLabel:disabled {
    color: $faint_text;
}

QLabel#HintLabel {
    color: $hint_text;
    font-size: 12px;
}

QLabel#SectionLabel {
    color: $section_text;
    font-weight: 600;
    font-size: 13px;
    padding: 0 0 2px 2px;
}

/* Вкладки-«таблетки» и карточка настроек. Раньше здесь был QTabWidget,
   но Qt не рисует дуги скруглённых углов у его ::pane — рамка получалась
   разорванной. Обычный виджет скругляется корректно. */
QPushButton#TabButton {
    background: $tab_bg;
    color: $tab_text;
    border: 1px solid $border_subtle;
    border-radius: 6px;
    /* Поля по бокам скромные: семь вкладок и кнопка порядка должны
       поместиться в правую панель — иначе кнопки наезжали друг на друга. */
    padding: 7px 8px;
    font-weight: 500;
}

QPushButton#TabButton:hover {
    background: $tab_hover_bg;
    color: $text;
}

QPushButton#TabButton:checked {
    background: $selected_bg;
    color: $bright_text;
    border-color: $tab_checked_border;
    font-weight: 600;
}

/* Режим правки порядка: пунктир — вкладку можно взять и перетащить. */
QPushButton#TabButton[editing="true"] {
    border-style: dashed;
    border-color: $hover_border;
}

/* Кнопка порядка вкладок — квадратик с карандашом в той же строке. */
QPushButton#TabEditButton {
    background: $tab_bg;
    border: 1px solid $border_subtle;
    border-radius: 6px;
    padding: 0;
}

QPushButton#TabEditButton:hover {
    background: $tab_hover_bg;
}

QPushButton#TabEditButton:checked {
    background: $selected_bg;
    border-color: $tab_checked_border;
}

/* Фон и рамку рисует контейнер: Qt не закрашивает фон под полосой
   прокрутки, и в углах карточки просвечивал фон окна. */
QFrame#SettingsCardFrame {
    background: $surface;
    border: 1px solid $card_border;
    border-radius: 8px;
}

/* Непрозрачный фон цвета карточки: под полосой прокрутки Qt рисует
   фон окна, а сюда полоса уже не достаёт до скруглённых углов. */
QScrollArea#SettingsScroll {
    background: $surface;
    border: none;
}

QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

QStackedWidget#SettingsCard {
    border: none;
    background: transparent;
}

/* Страницы прозрачные, иначе их прямоугольный фон закрывает
   скруглённые углы карточки. */
QWidget#SettingsPage {
    background: transparent;
    border: none;
}

QListWidget {
    background-color: $surface;
    border: 1px solid $card_border;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    padding: 8px;
    border-radius: 6px;
    margin-bottom: 2px;
}

QListWidget::item:selected {
    background-color: $selected_bg;
    color: $bright_text;
}

QListWidget::item:hover {
    background-color: $hover_bg;
}

QPushButton {
    background-color: $button_bg;
    color: $button_text;
    border: 1px solid $button_border;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: $button_hover_bg;
    border: 1px solid $hover_border;
}

QPushButton:pressed {
    background-color: $button_pressed;
}

/* Недоступная кнопка: заметно бледнее и без рамки-«кнопочности»,
   чтобы её нельзя было спутать с активной. */
QPushButton:disabled {
    background-color: $disabled_bg;
    color: $disabled_text;
    border: 1px dashed $disabled_border;
}

QPushButton#StartButton {
    background-color: $start_bg;
    border: 1px solid $start_border;
    color: $bright_text;
    font-weight: 700;
    padding: 10px 20px;
    font-size: 14px;
}

QPushButton#StartButton:hover {
    background-color: $start_hover;
}

QPushButton#StartButton:disabled {
    background-color: $start_disabled_bg;
    border: 1px dashed $card_border;
    color: $start_disabled_text;
}

QPushButton#StopButton {
    background-color: $stop_bg;
    border: 1px solid $danger_border;
    color: $stop_text;
    /* Те же метрики, что у StartButton, иначе кнопки разной высоты. */
    font-weight: 700;
    padding: 10px 20px;
    font-size: 14px;
}

QPushButton#StopButton:hover {
    background-color: $stop_hover;
}

QPushButton#StopButton:disabled {
    background-color: $stop_disabled_bg;
    border: 1px dashed $stop_disabled_border;
    color: $stop_disabled_text;
}

/* Главное действие в очереди — выделено акцентом. */
QPushButton#PrimaryButton {
    background-color: $primary_bg;
    border: 1px solid $accent;
    color: $bright_text;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: $primary_hover;
    border-color: $accent_bright;
}

/* Убирающие/разрушительные действия — приглушены фоном и рамкой, но не
   текстом: с серым текстом они выглядели выключенными. */
QPushButton#QuietButton {
    background-color: $quiet_bg;
    border: 1px solid $border_subtle;
    color: $button_text;
}

QPushButton#QuietButton:hover {
    background-color: $quiet_hover_bg;
    border-color: $danger_border;
    color: $quiet_hover_text;
}

/* Пресеты Telegram/Twitch: выбранный остаётся подсвеченным. */
QPushButton#PresetButton {
    text-align: center;
    padding: 7px 10px;
    min-height: 16px;
}

QPushButton#PresetButton:checked {
    background-color: $selected_bg;
    border: 1px solid $accent_bright;
    color: $bright_text;
    font-weight: 600;
}

QPushButton#PresetButton:checked:hover {
    background-color: $selected_hover;
}

/* Подсказка к выбранному пресету — выноска с акцентной полосой слева,
   иначе строка текста висит в воздухе и выглядит инородно. */
QLabel#HintCallout {
    color: $callout_text;
    font-size: 12px;
    background: $callout_bg;
    border-left: 3px solid $accent;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 9px 11px;
}

/* Заголовок группы настроек. Подчёркнут линией во всю ширину: раньше это
   была просто мелкая серая строка, и она терялась среди самих настроек. */
QLabel#GroupCaption {
    color: $caption_text;
    /* Было 10 px заглавными — на грани читаемости. 11 px прибавляют по
       пикселю на заголовок; запас высоты на «Основной» это выдерживает. */
    font-size: 11px;
    font-weight: 700;
    padding: 7px 0 3px 2px;
    border-bottom: 1px solid $caption_line;
    margin-bottom: 3px;
}

/* Номер версии в углу. Был цвета выключенного текста (2,3:1), хотя это
   не выключенный элемент, а сведения — теперь как у примечаний. */
QLabel#VersionLabel {
    color: $note_text;
    font-size: 11px;
    padding: 0 6px 6px 0;
}

/* Примечание под карточкой на вкладках площадок — на месте кнопок
   применения, поэтому без верхней черты и с отступом как у кнопок. */
QLabel#ApplyNote {
    color: $note_text;
    font-size: 11px;
    padding: 0 4px;
}

/* Нижняя панель отделена линией: раньше блок сохранения сливался
   с кнопками очереди, стоящими прямо над ним. */
QWidget#BottomPanel {
    border-top: 1px solid $bottom_line;
}

QLineEdit#ReadOnlyPath {
    background-color: $sunken_bg;
    color: $muted_text;
    border: 1px solid $border_subtle;
}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: $surface;
    border: 1px solid $input_border;
    border-radius: 6px;
    padding: 6px 8px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $selection_text;
}

/* Список — обычный, под полем, а не «меню» поверх него. В режиме меню
   окно-контейнер списка само закрашивает себя прямоугольной панелью из
   палитры и таблицу стилей не слушает: за скруглённой карточкой торчал
   квадрат. Заодно Qt начинает учитывать предел высоты списка. */
QComboBox {
    combobox-popup: 0;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    border: 1px solid $input_border_hover;
}

/* Выключенное поле: тусклый текст и тусклая рамка. Без этого правила
   запертое поле рисовалось тем же #e6e6e6, что и рабочее, и «Ширина: Авто»
   при выключенном «Изменить разрешение» выглядела доступной. */
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    color: $disabled_text;
    border: 1px solid $border_subtle;
}

/* Стрелка выпадающего списка: без неё поле неотличимо от обычного ввода. */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 22px;
}

QComboBox::down-arrow {
    image: url("$arrow_down_icon");
    width: 10px;
    height: 6px;
    margin-right: 8px;
}

QComboBox::down-arrow:disabled {
    image: url("$arrow_down_off_icon");
}

/* Окно-контейнер выпадающего списка прозрачно (см. widgets.round_combo_popup):
   скругление и рамку рисует сам список, а без этого правила контейнер
   заливался фоном окна, и за скруглёнными углами торчал квадрат. */
QFrame#ComboPopup {
    background: transparent;
    border: none;
}

/* Меню — та же карточка, что у выпадающего списка: скругление, отступы,
   подсветка пункта. Без этих правил оно было плоским системным меню и
   выглядело чужим рядом со списками. */
QMenu#PopupMenu {
    background-color: $popup_bg;
    border: 1px solid $card_border;
    border-radius: 8px;
    padding: 5px;
}

QMenu#PopupMenu::item {
    background: transparent;
    color: $text;
    border-radius: 5px;
    padding: 7px 16px 7px 32px;
}

QMenu#PopupMenu::item:selected {
    background-color: $popup_hover;
    color: $bright_text;
}

QMenu#PopupMenu::item:disabled {
    color: $note_text;
}

QMenu#PopupMenu::separator {
    height: 1px;
    background: $card_border;
    margin: 5px 8px;
}

QMenu#PopupMenu::indicator {
    width: 14px;
    height: 14px;
    left: 10px;
}

QMenu#PopupMenu::indicator:checked {
    image: url("$check_icon");
}

/* Номер версии в правом верхнем углу — тихая кнопка, открывающая меню. */
QPushButton#VersionButton {
    background: transparent;
    color: $hint_text;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 22px 4px 8px;
}

QPushButton#VersionButton:hover {
    background: $hover_bg;
    border-color: $border_subtle;
    color: $text;
}

QPushButton#VersionButton::menu-indicator {
    image: url("$arrow_down_icon");
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 10px;
    height: 6px;
    right: 7px;
}

/* Язык в углу — компактнее обычного списка: строка заголовка не должна
   расти, у вкладок настроек запас по высоте небольшой. */
QComboBox#CornerCombo {
    padding: 3px 8px;
}

/* Выпадающий список: своя карточка со скруглением и «воздухом» вокруг
   пунктов. По умолчанию Qt рисует плоский прямоугольник впритык к тексту,
   и на тёмной теме он выглядит инородно рядом со скруглёнными полями. */
QComboBox QAbstractItemView {
    background-color: $popup_bg;
    border: 1px solid $card_border;
    border-radius: 8px;
    selection-background-color: $selected_bg;
    outline: none;
    padding: 5px;
}

QComboBox QAbstractItemView::item {
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 20px;
    border: none;
}

QComboBox QAbstractItemView::item:hover {
    background-color: $popup_hover;
}

QComboBox QAbstractItemView::item:selected {
    background-color: $popup_selected;
    color: $bright_text;
}

/* Заголовок группы форматов: не выбирается, поэтому и выглядит как
   подпись, а не как пункт списка. */
/* Заголовок группы: цвет ему задаёт сам элемент (setForeground), поэтому
   ни здесь, ни у самого списка цвет не указан — любое правило QSS с color
   перебило бы цвет элемента, и подписи групп сливались бы с форматами. */
QComboBox QAbstractItemView::item:disabled {
    background: transparent;
    padding: 9px 8px 4px 8px;
    min-height: 0;
}

/* Счётчики: стрелки вверх/вниз, иначе поле выглядит как обычный ввод. */
/* Кнопки счётчика — тонкие «шевроны» внутри поля, а не серая колонка
   с перегородкой и заливными треугольниками: та выглядела чужеродно
   рядом со скруглёнными полями. Кнопки прозрачные и подсвечиваются
   только под курсором. Ширина и высота поля прежние, место под кнопки
   Qt сам вычитает из поля текста — вёрстка вкладок не сдвигается.
   Отдельный padding-right не нужен: он резервировал место второй раз,
   и в узких полях «0,00 сек» обрезалось до «0,00». */

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    /* 16 + 3 отступа — почти прежние 18: шире — и в узких полях
       «Начало/Конец» хвост «сек» уже не помещался. */
    width: 16px;
    border: none;
    border-radius: 4px;
    background: transparent;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right;
    margin: 4px 3px 0 0;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right;
    margin: 0 3px 4px 0;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: $button_hover_bg;
}

QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: $button_pressed;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("$arrow_up_icon");
    width: 10px;
    height: 6px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("$arrow_down_icon");
    width: 10px;
    height: 6px;
}

/* Шеврон гаснет и у выключенного поля, и на границе диапазона (:off):
   видно, что дальше крутить некуда. */
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off {
    image: url("$arrow_up_off_icon");
}

QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off {
    image: url("$arrow_down_off_icon");
}

QCheckBox {
    spacing: 8px;
    color: $check_text;
    background: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid $check_border;
    background-color: $surface;
}

QCheckBox::indicator:checked {
    background-color: $accent;
    border: 1px solid $accent_hover;
}

QProgressBar {
    background-color: $surface;
    border: 1px solid $card_border;
    border-radius: 6px;
    text-align: center;
    color: $text;
    height: 20px;
}

QProgressBar::chunk {
    background-color: $accent;
    border-radius: 5px;
}

/* Цвет фона совпадает с панелями, внутри которых полосы появляются
   (список файлов и карточка настроек). «transparent» здесь не работает:
   Qt всё равно заливает полосу цветом из палитры окна, и в углах
   панелей просвечивал фон приложения. */
QScrollBar:vertical {
    background: $surface;
    width: 12px;
    /* Без отступов: в них Qt рисует фон окна, и по краям панели
       оставались светлые просветы. Воздух даёт padding у ползунка. */
    margin: 0;
    padding: 3px 2px;
}

QScrollBar:horizontal {
    background: $surface;
    height: 12px;
    margin: 0;
    padding: 2px 3px;
}

QScrollBar::handle:horizontal {
    background: $border_subtle;
    border-radius: 4px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: $check_border;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: $surface;
}

/* Полоса прокрутки длинного выпадающего списка — цвета самого списка,
   иначе по его правому краю шла полоса цвета карточки. */
QComboBox QAbstractItemView QScrollBar:vertical,
QComboBox QAbstractItemView QScrollBar::add-page,
QComboBox QAbstractItemView QScrollBar::sub-page {
    background: $popup_bg;
}

QScrollBar::handle:vertical {
    background: $border_subtle;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: $check_border;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QSplitter::handle:horizontal {
    background-color: $window_bg;
    width: 14px;
    /* Тонкая полоска-указатель по центру зазора между панелями. */
    image: none;
    border-left: 6px solid $window_bg;
    border-right: 6px solid $window_bg;
}

QSplitter::handle:horizontal:hover {
    border-left-color: $hover_bg;
    border-right-color: $hover_bg;
    background-color: $card_border;
}

QMessageBox {
    background-color: $surface;
}

QToolTip {
    background-color: $hover_bg;
    color: $text;
    border: 1px solid $card_border;
    padding: 4px;
}

/* Ссылка на новую версию рядом с номером версии: заметная, но не кричащая. */
QPushButton#UpdateButton {
    background: transparent;
    border: none;
    color: $accent_bright;
    padding: 0 4px 6px 4px;
    font-size: 11px;
    text-decoration: underline;
}

QPushButton#UpdateButton:hover {
    color: $bright_text;
}

/* Предупреждение об отсутствии FFmpeg над очередью. */
QLabel#WarningLabel {
    color: $warning_text;
    font-weight: 600;
}

/* Выключенные кнопки с #именем: правило по имени специфичнее общего
   QPushButton:disabled, и без этого выключенная «Снять отметки» выглядела
   рабочей — светлый текст и сплошная рамка. */
QPushButton#QuietButton:disabled,
QPushButton#PrimaryButton:disabled,
QPushButton#PresetButton:disabled {
    background-color: $disabled_bg;
    color: $disabled_text;
    border: 1px dashed $disabled_border;
}

/* Фокус клавиатуры. Правило в самом конце и с теми же #именами, что у
   кнопок выше: при равной специфичности побеждает последнее, иначе рамку
   фокуса перебивала бы рамка выбранного пресета или вкладки. Меняется
   только цвет рамки — толщина та же, и вёрстка не сдвигается. Кнопки
   получают фокус только с клавиатуры (Tab), поэтому после щелчка мышью
   белой рамки нет. */
QPushButton:focus,
QPushButton#TabButton:focus,
QPushButton#TabEditButton:focus,
QPushButton#PresetButton:focus,
QPushButton#PrimaryButton:focus,
QPushButton#QuietButton:focus,
QPushButton#StartButton:focus,
QPushButton#StopButton:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: $focus_ring;
}

QPushButton#UpdateButton:focus, QLabel#VersionLabel:focus {
    color: $focus_ring;
    text-decoration: underline;
}
""")


def _draw_arrow(path, color, pointing_down):
    """Рисует шеврон (галочку-стрелку линией) и сохраняет его в PNG для QSS.

    Раньше это был заливной треугольник — грубый рядом с тонким текстом.
    Рисуется вдвое крупнее, чем показывается (20×12 → 10×6 в стилях):
    на экранах с масштабом 150–200 % линия остаётся чёткой.
    """
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    width, height = 20, 12
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    margin_x, margin_y = 3.0, 2.5
    top, bottom = margin_y, height - margin_y
    if pointing_down:
        tip, base = bottom, top
    else:
        tip, base = top, bottom
    chevron = QPainterPath(QPointF(margin_x, base))
    chevron.lineTo(width / 2, tip)
    chevron.lineTo(width - margin_x, base)
    painter.drawPath(chevron)
    painter.end()
    pixmap.save(path, "PNG")


def _draw_check(path, color):
    """Галочка для пунктов-переключателей меню (QSS её не рисует)."""
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    size = 28
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 3.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    check = QPainterPath(QPointF(5.5, 14.5))
    check.lineTo(11.5, 20.5)
    check.lineTo(22.5, 8.0)
    painter.drawPath(check)
    painter.end()
    pixmap.save(path, "PNG")


# Иконки рисуются один раз на процесс: темы переключаются на каждой смене
# вкладки, и перерисовывать PNG при этом незачем.
_arrow_icons = None


def _arrow_icon_paths(colors):
    global _arrow_icons
    if _arrow_icons is not None:
        return _arrow_icons
    assets_dir = os.path.join(tempfile.gettempdir(), "dttconvert_assets")
    os.makedirs(assets_dir, exist_ok=True)
    icons = {
        # Имена другие, чем у прежних треугольников: сборка старой версии,
        # запущенная рядом, пишет в ту же папку свои картинки.
        "arrow_down_icon": ("chevron_down.png", colors["arrow"], True),
        "arrow_up_icon": ("chevron_up.png", colors["arrow"], False),
        "arrow_down_off_icon": ("chevron_down_off.png", colors["arrow_off"], True),
        "arrow_up_off_icon": ("chevron_up_off.png", colors["arrow_off"], False),
    }
    paths = {}
    for key, (file_name, color, pointing_down) in icons.items():
        icon_path = os.path.join(assets_dir, file_name)
        try:
            _draw_arrow(icon_path, color, pointing_down)
        except Exception:
            # Без иконок Qt нарисует стрелки сам — интерфейс не сломается.
            paths[key] = ""
            continue
        # В QSS путь всегда через прямые слэши, даже на Windows.
        paths[key] = icon_path.replace("\\", "/")
    check_path = os.path.join(assets_dir, "menu_check.png")
    try:
        _draw_check(check_path, colors["text"])
        paths["check_icon"] = check_path.replace("\\", "/")
    except Exception:
        paths["check_icon"] = ""
    _arrow_icons = paths
    return paths


_stylesheets = {}


def build_stylesheet(theme=THEME_MAIN):
    """Таблица стилей темы с уже сгенерированными иконками стрелок.

    Результат кэшируется: тема площадки ставится при каждом переключении
    вкладки, и собирать строку заново незачем.
    """
    cached = _stylesheets.get(theme)
    if cached is not None:
        return cached
    colors = palette(theme)
    values = dict(colors)
    values.update(_arrow_icon_paths(colors))
    stylesheet = _STYLESHEET_TEMPLATE.substitute(values)
    _stylesheets[theme] = stylesheet
    return stylesheet


def theme_for_tab(index):
    """Какая тема у вкладки настроек: порядок как у кнопок вкладок."""
    return THEMES[index] if 0 <= index < len(THEMES) else THEME_MAIN


def _relative_luminance(color):
    channels = []
    for i in (1, 3, 5):
        value = int(color[i:i + 2], 16) / 255.0
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first, second):
    """Контраст двух цветов по WCAG: 1 — неразличимы, 21 — чёрное на белом."""
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)),
                             reverse=True)
    return (lighter + 0.05) / (darker + 0.05)

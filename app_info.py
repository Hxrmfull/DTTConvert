"""Название и версия приложения — в одном месте, чтобы не расходились
между заголовком окна, интерфейсом и сборкой.
"""

APP_NAME = "DTTConvert"
APP_VERSION = "1.0.0"
# Пустая стадия — релиз. Для беты сюда возвращается "beta".
APP_STAGE = ""

# Идентификатор для QSettings и панели задач Windows.
ORGANIZATION = "DTTConvert"
APP_ID = "DTTConvert.App"

# Под каким именем настройки лежали до переименования из Media Converter
# Studio. Нужно один раз, чтобы не потерять размер окна, папку сохранения
# и выбранный язык; см. migrate_legacy_settings.
LEGACY_ORGANIZATION = "MediaConverterStudio"


def version_string():
    """Например: «1.0.0» или «1.1.0 beta», если стадия задана."""
    return f"{APP_VERSION} {APP_STAGE}".strip()


def window_title():
    """Заголовок окна: только название и версия, без подзаголовка."""
    return f"{APP_NAME} {version_string()}"


def migrate_legacy_settings(organization=ORGANIZATION,
                            legacy_organization=LEGACY_ORGANIZATION):
    """Переносит настройки со старого имени, если новых ещё нет.

    QSettings на Windows хранит их в ветке реестра с именем организации,
    поэтому переименование приложения обнулило бы сохранённые размер окна,
    положение разделителя, папку сохранения и язык. Перенос одноразовый:
    как только у нового имени появился хоть один ключ, старое не трогаем —
    иначе правки пользователя откатывались бы к состоянию до переименования.

    Имена — параметры, чтобы тест не трогал настоящее хранилище: проверка
    на живых ключах правила бы настройки пользователя, да и соседние наборы
    сбивались бы с толку очисткой чужого кэша.
    """
    from PyQt6.QtCore import QSettings

    current = QSettings(organization, organization)
    if current.allKeys():
        return False
    legacy = QSettings(legacy_organization, legacy_organization)
    keys = legacy.allKeys()
    if not keys:
        return False
    for key in keys:
        current.setValue(key, legacy.value(key))
    current.sync()
    return True

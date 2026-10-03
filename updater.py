"""Проверка новой версии на GitHub.

Раз в сутки при запуске программа спрашивает у GitHub, какой выпуск
последний, и, если он новее, показывает ненавязчивую ссылку рядом с
номером версии. Окон не открывает и ничего сама не скачивает. Проверку
можно отключить в контекстном меню номера версии.

Запрос уходит только к api.github.com и не несёт никаких данных о
пользователе, кроме самого факта обращения и версии программы в
заголовке User-Agent (его GitHub требует от всех клиентов API).
"""

import json
import logging
import re
import urllib.error
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from app_info import APP_NAME, APP_VERSION, GITHUB_REPO

LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_SEC = 6
# Не чаще раза в сутки: выпуски выходят редко, а лишние запросы ни к чему.
CHECK_INTERVAL_SEC = 24 * 60 * 60

_log = logging.getLogger(__name__)


def parse_version(text):
    """«v1.2.3», «1.2» или «1.2.3-beta» → (1, 2, 3). None, если не версия."""
    match = re.match(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def is_newer(remote, local=APP_VERSION):
    remote_version = parse_version(remote)
    local_version = parse_version(local)
    if remote_version is None or local_version is None:
        return False
    return remote_version > local_version


def fetch_latest_release(timeout=REQUEST_TIMEOUT_SEC):
    """(версия, ссылка на страницу выпуска) последнего выпуска или None."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name") or ""
    url = data.get("html_url") or ""
    if not tag or not url.startswith("https://github.com/"):
        return None
    return tag.lstrip("vV"), url


class UpdateCheckWorker(QThread):
    """Спрашивает GitHub в фоне: сеть может отвечать секундами."""

    update_found = pyqtSignal(str, str)

    def run(self):
        try:
            latest = fetch_latest_release()
        except urllib.error.HTTPError as exc:
            # 404 — у репозитория ещё нет ни одного выпуска.
            if exc.code == 404:
                _log.info("Проверка обновлений: выпусков пока нет")
            else:
                _log.info("Проверка обновлений: GitHub ответил %s", exc.code)
            return
        except Exception as exc:
            # Нет сети, GitHub недоступен, лимит запросов — для пользователя
            # это не ошибка: проверим в следующий раз. Одной строкой: полный
            # traceback раз в сутки только засорял бы журнал.
            _log.info("Проверка обновлений не удалась: %s", exc)
            return
        if latest and is_newer(latest[0]):
            self.update_found.emit(*latest)

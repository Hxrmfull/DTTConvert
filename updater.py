"""Проверка новой версии на GitHub и обновление в один щелчок.

При каждом запуске программа спрашивает у GitHub, какой выпуск
последний, и, если он новее, показывает ненавязчивую ссылку на месте
номера версии. Проверку можно отключить в контекстном меню номера версии.

Щелчок по ссылке в программе, поставленной установщиком, скачивает
установщик новой версии того же варианта (с FFmpeg или без), сверяет его
размер и SHA-256 с тем, что сообщает GitHub, и запускает его в тихом
режиме. Программа при этом закрывается, установщик ставит новую версию
поверх и запускает её снова. Копия из архива и запуск из исходников
установщиком не обновить — для них щелчок по-прежнему открывает страницу
выпуска.

Запросы уходят только к GitHub и не несут никаких данных о пользователе,
кроме самого факта обращения и версии программы в заголовке User-Agent
(его GitHub требует от всех клиентов API).
"""

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from app_info import APP_NAME, APP_VERSION, GITHUB_REPO
from errors import LocalizedRuntimeError

LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
# Установщики берём только из выпусков этого репозитория.
DOWNLOAD_PREFIX = f"https://github.com/{GITHUB_REPO}/releases/download/"
REQUEST_TIMEOUT_SEC = 6
DOWNLOAD_TIMEOUT_SEC = 30
DOWNLOAD_CHUNK = 256 * 1024

VARIANT_WITH_FFMPEG = "with-ffmpeg"
VARIANT_WITHOUT_FFMPEG = "without-ffmpeg"
# Ключи установщика: /SILENT — без вопросов мастера, только полоса
# прогресса; /RELAUNCH — запустить программу после установки (в тихом
# режиме обычный пункт «Запустить» пропускается, см. installer.iss).
INSTALLER_ARGUMENTS = "/SILENT /SP- /RELAUNCH"

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


def _request(url, accept="application/vnd.github+json"):
    return urllib.request.Request(
        url, headers={"Accept": accept, "User-Agent": f"{APP_NAME}/{APP_VERSION}"}
    )


def fetch_latest_data(timeout=REQUEST_TIMEOUT_SEC):
    """Описание последнего выпуска от GitHub (словарь) или None."""
    with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("draft") or data.get("prerelease"):
        return None
    return data


def release_version_and_url(data):
    """(версия, ссылка на страницу выпуска) или None, если описание странное."""
    if not data:
        return None
    tag = data.get("tag_name") or ""
    url = data.get("html_url") or ""
    if not tag or not url.startswith("https://github.com/"):
        return None
    return tag.lstrip("vV"), url


def fetch_latest_release(timeout=REQUEST_TIMEOUT_SEC):
    """(версия, ссылка на страницу выпуска) последнего выпуска или None."""
    return release_version_and_url(fetch_latest_data(timeout))


def installed_variant(executable=None, bundle_dir=None):
    """Вариант установленной программы или None, если обновлять нечем.

    Установщиком поставлена программа, у которой рядом с exe лежит
    деинсталлятор Inno Setup. Вариант определяется по FFmpeg внутри
    сборки (папка _internal), а не рядом с exe: туда пользователь может
    положить свою копию и в лёгкий вариант.
    """
    if executable is None:
        if not getattr(sys, "frozen", False):
            return None
        executable = sys.executable
    app_dir = os.path.dirname(os.path.abspath(executable))
    if not os.path.isfile(os.path.join(app_dir, "unins000.exe")):
        return None
    if bundle_dir is None:
        bundle_dir = getattr(sys, "_MEIPASS", None) or os.path.join(app_dir, "_internal")
    bundled = os.path.isfile(os.path.join(bundle_dir, "ffmpeg.exe"))
    return VARIANT_WITH_FFMPEG if bundled else VARIANT_WITHOUT_FFMPEG


def setup_asset_name(version, variant):
    """Имя установщика в выпуске — так его называет build_windows.ps1."""
    return f"{APP_NAME}-{version}-windows-x64-{variant}-setup.exe"


def find_installer(data, variant):
    """(имя, ссылка, размер, sha256 или None) установщика нужного варианта."""
    found = release_version_and_url(data)
    if found is None:
        return None
    name = setup_asset_name(found[0], variant)
    for asset in data.get("assets") or []:
        if asset.get("name") != name:
            continue
        url = asset.get("browser_download_url") or ""
        size = asset.get("size")
        if not url.startswith(DOWNLOAD_PREFIX) or not isinstance(size, int) or size <= 0:
            return None
        digest = asset.get("digest") or ""
        sha256 = digest[len("sha256:"):].lower() if digest.startswith("sha256:") else None
        return name, url, size, sha256
    return None


def download_verified(url, path, size, sha256=None, progress=None, cancelled=None,
                      timeout=DOWNLOAD_TIMEOUT_SEC):
    """Скачивает файл и сверяет размер и SHA-256. При несовпадении файл удаляется.

    progress(percent) зовётся по мере загрузки, cancelled() — между кусками:
    если вернёт True, загрузка прерывается без сообщения об ошибке.
    Возвращает True, если файл скачан целиком и проверен.
    """
    digest = hashlib.sha256()
    received = 0
    partial = path + ".part"
    try:
        with urllib.request.urlopen(_request(url, "application/octet-stream"),
                                    timeout=timeout) as response, \
                open(partial, "wb") as target:
            while True:
                if cancelled is not None and cancelled():
                    return False
                chunk = response.read(DOWNLOAD_CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > size:
                    raise LocalizedRuntimeError("err_update_size")
                digest.update(chunk)
                target.write(chunk)
                if progress is not None:
                    progress(int(received * 100 / size))
        if received != size:
            raise LocalizedRuntimeError("err_update_size")
        if sha256 and digest.hexdigest() != sha256:
            raise LocalizedRuntimeError("err_update_checksum")
        os.replace(partial, path)
        return True
    finally:
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass


def update_download_dir():
    directory = os.path.join(tempfile.gettempdir(), f"{APP_NAME}-update")
    os.makedirs(directory, exist_ok=True)
    return directory


def launch_installer(path):
    """Запускает установщик через оболочку: она сама спросит права
    администратора, если программа стоит для всех пользователей."""
    os.startfile(path, arguments=INSTALLER_ARGUMENTS)


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
            # traceback на каждом запуске только засорял бы журнал.
            _log.info("Проверка обновлений не удалась: %s", exc)
            return
        if latest and is_newer(latest[0]):
            self.update_found.emit(*latest)


class UpdateDownloadWorker(QThread):
    """Скачивает и проверяет установщик последнего выпуска.

    Описание выпуска запрашивается заново: ссылка на обновление могла
    остаться с прошлого запуска, а выпуск с тех пор — смениться.
    """

    progress = pyqtSignal(int)
    downloaded = pyqtSignal(str)
    # Ошибка — объект LocalizedError или текст исключения; переводит окно.
    failed = pyqtSignal(object)

    def __init__(self, variant, parent=None):
        super().__init__(parent)
        self.variant = variant
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            installer = find_installer(fetch_latest_data(), self.variant)
            if installer is None:
                raise LocalizedRuntimeError("err_update_no_installer")
            name, url, size, sha256 = installer
            path = os.path.join(update_download_dir(), name)
            _log.info("Обновление: скачиваю %s (%s байт)", name, size)
            # Окно при закрытии просит потоки прерваться — загрузка тоже слушается.
            if download_verified(url, path, size, sha256, self.progress.emit,
                                 lambda: self._cancel or self.isInterruptionRequested()):
                _log.info("Обновление: установщик скачан и проверен")
                self.downloaded.emit(path)
        except Exception as exc:
            _log.info("Обновление не удалось: %s", exc)
            self.failed.emit(exc)

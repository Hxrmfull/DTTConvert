"""Файлы по ссылкам: картинка, GIF, видео или стикер — в очередь.

Ссылку можно вставить Ctrl+V, перетащить из браузера или ввести в
диалоге «Добавить по ссылке». Подходит прямая ссылка на файл и ссылка на
страницу:

- страницы смайликов 7TV и FrankerFaceZ, гифки Giphy — по известным
  правилам превращаются в ссылку на сам файл в наибольшем размере (у 7TV
  и FFZ заодно берётся имя смайлика);
- смайлики Twitch с CDN — берётся наибольший размер 3.0;
- любая другая страница — файл из её метатегов og:video / og:image
  (так их показывают мессенджеры при вставке ссылки).

Тип файла определяется по содержимому, а не по адресу: у CDN адреса часто
без расширения. Файл сохраняется в папку программы, каждый в свою
подпапку, под именем смайлика или файла из адреса: имя результата
берётся из имени исходника, и «RainTime_7tv.webp» понятнее, чем
«link_20261004_164433_7tv.webp».
"""

import html
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.request

from app_info import APP_NAME, APP_VERSION
from errors import LocalizedRuntimeError

# Некоторые CDN отказывают клиентам без браузерного User-Agent.
USER_AGENT = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              f"{APP_NAME}/{APP_VERSION}")
TIMEOUT_SEC = 20
MAX_BYTES = 300 * 1024 * 1024
PAGE_MAX_BYTES = 2 * 1024 * 1024
CHUNK = 256 * 1024
LINKS_SUBDIR = "links"

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Расширение по Content-Type — когда сигнатура ничего не сказала.
_CONTENT_TYPES = {
    "image/png": ".png", "image/apng": ".apng", "image/gif": ".gif",
    "image/webp": ".webp", "image/jpeg": ".jpg", "image/avif": ".avif",
    "image/heic": ".heic", "image/heif": ".heif", "image/bmp": ".bmp",
    "image/tiff": ".tiff", "video/mp4": ".mp4", "video/webm": ".webm",
    "video/quicktime": ".mov", "video/x-matroska": ".mkv",
    "application/x-tgsticker": ".tgs",
}


def extract_urls(text):
    """Ссылки http(s) из текста — по одной на строку или через пробелы."""
    found = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip(").,;]")
        if url not in found:
            found.append(url)
    return found


def _sanitize_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name or "").strip(" ._")
    return name[:80]


def _request(url, accept="*/*"):
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})


def _get_json(url):
    with urllib.request.urlopen(_request(url, "application/json"), timeout=TIMEOUT_SEC) as response:
        return json.loads(response.read(PAGE_MAX_BYTES).decode("utf-8"))


def resolve_known_site(url):
    """(прямая ссылка, имя) для страниц известных сайтов, иначе (url, None).

    Сеть нужна только 7TV и FFZ — ради имени смайлика и анимированной
    версии; если их API не ответил, используется ссылка по правилу.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    segments = [segment for segment in parts.path.split("/") if segment]

    # 7TV: 7tv.app/emotes/<id>
    if host in ("7tv.app", "old.7tv.app") and len(segments) >= 2 and segments[0] == "emotes":
        emote_id = segments[1]
        name = None
        try:
            name = _get_json(f"https://7tv.io/v3/emotes/{emote_id}").get("name")
        except Exception:
            pass
        # WEBP у 7TV есть у всех смайликов, анимированных и нет, и он
        # сохраняет полупрозрачность, в отличие от GIF.
        return f"https://cdn.7tv.app/emote/{emote_id}/4x.webp", name or f"7tv_{emote_id}"

    # FrankerFaceZ: frankerfacez.com/emoticon/<id>-<имя>
    if host == "frankerfacez.com" and len(segments) >= 2 and segments[0] == "emoticon":
        match = re.match(r"(\d+)(?:-(.+))?", segments[1])
        if match:
            emote_id, slug = match.group(1), match.group(2)
            direct = f"https://cdn.frankerfacez.com/emote/{emote_id}/4"
            name = slug
            try:
                emote = _get_json(f"https://api.frankerfacez.com/v1/emote/{emote_id}")["emote"]
                name = emote.get("name") or name
                # Анимированные смайлики FFZ лежат отдельно от статичной версии.
                for key in ("animated", "urls"):
                    sizes = emote.get(key) or {}
                    if sizes:
                        direct = sizes[max(sizes, key=lambda size: int(size))]
                        break
            except Exception:
                pass
            return direct, name or f"ffz_{emote_id}"

    # Giphy: giphy.com/gifs/<что-то>-<id>
    if host == "giphy.com" and len(segments) >= 2 and segments[0] in ("gifs", "stickers"):
        gif_id = segments[1].rsplit("-", 1)[-1]
        return f"https://i.giphy.com/{gif_id}.gif", segments[1].rsplit("-", 1)[0] or None

    # Смайлик Twitch с CDN (emoticons/v2/<id>/<вид>/<тема>/<размер>):
    # берём наибольший размер, имя — по номеру, а не «dark» из адреса.
    if host == "static-cdn.jtvnw.net" and segments[:2] == ["emoticons", "v2"] \
            and len(segments) >= 3:
        direct = url
        if segments[-1] in ("1.0", "2.0"):
            direct = url.rsplit("/", 1)[0] + "/3.0"
        return direct, f"twitch_{segments[2]}"
    return url, None


def sniff_extension(head, content_type="", url=""):
    """Расширение файла по первым байтам; затем по Content-Type и адресу."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        # APNG — тот же PNG с чанком acTL до первого кадра.
        return ".apng" if b"acTL" in head[:256] else ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:2] == b"BM":
        return ".bmp"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tiff"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return ".avif"
        if brand in (b"heic", b"heix", b"mif1", b"msf1"):
            return ".heic"
        if brand == b"qt  ":
            return ".mov"
        return ".mp4"
    if head[:2] == b"\x1f\x8b":
        # gzip бывает разным; стикер Telegram — если так сказано адресом или типом.
        if url.lower().split("?")[0].endswith(".tgs") or "tgsticker" in content_type:
            return ".tgs"
        return None
    mime = (content_type or "").split(";")[0].strip().lower()
    return _CONTENT_TYPES.get(mime)


def _is_html(content_type, head):
    mime = (content_type or "").split(";")[0].strip().lower()
    return mime in ("text/html", "application/xhtml+xml") or head.lstrip()[:15].lower().startswith(
        (b"<!doctype html", b"<html"))


def page_media_url(page, base_url):
    """Ссылка на видео или картинку из метатегов страницы (og:video, og:image)."""
    found = {}
    for tag in re.findall(r"<meta\b[^>]*>", page, re.IGNORECASE):
        key = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)', tag, re.IGNORECASE)
        value = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.IGNORECASE)
        if key and value:
            found.setdefault(key.group(1).lower(), html.unescape(value.group(1)))
    for key in ("og:video:secure_url", "og:video:url", "og:video", "og:image:secure_url",
                "og:image:url", "og:image", "twitter:image", "twitter:image:src"):
        if found.get(key):
            url = urllib.parse.urljoin(base_url, found[key])
            if url.lower().startswith(("http://", "https://")):
                return url
    return None


def _name_from_url(url):
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    stem = os.path.splitext(os.path.basename(path.rstrip("/")))[0]
    # Адреса вида …/emote/<id>/3x дают в имени только размер — он не нужен.
    if re.fullmatch(r"\d(\.\d)?x?|fullsize|default|original|giphy", stem or "", re.IGNORECASE):
        stem = os.path.basename(os.path.dirname(path.rstrip("/")))
    return _sanitize_name(stem)


def link_directory(base_directory):
    """Своя подпапка на каждую загрузку: имена файлов не сталкиваются."""
    root = os.path.join(base_directory, LINKS_SUBDIR)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for counter in range(1000):
        path = os.path.join(root, f"{stamp}_{counter}")
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            continue
    raise OSError(root)


def cleanup_links(base_directory, max_age_days):
    """Удаляет старые загрузки: файл нужен, пока стоит в очереди."""
    root = os.path.join(base_directory, LINKS_SUBDIR)
    if not os.path.isdir(root):
        return
    limit = time.time() - max_age_days * 24 * 60 * 60
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if os.path.isdir(path) and os.path.getmtime(path) < limit:
            shutil.rmtree(path, ignore_errors=True)


def download_url(url, base_directory, supported_exts, cancelled=None, _depth=0):
    """Скачивает файл по ссылке и возвращает путь к нему.

    Ссылка на страницу ведёт к файлу из её метатегов — не глубже одного
    шага. Бросает LocalizedRuntimeError, если по ссылке нет подходящего файла.
    """
    if not url.lower().startswith(("http://", "https://")):
        raise LocalizedRuntimeError("err_link_bad", url=url)
    direct, name = resolve_known_site(url) if _depth == 0 else (url, None)
    try:
        response = urllib.request.urlopen(_request(direct), timeout=TIMEOUT_SEC)
    except Exception as exc:
        raise LocalizedRuntimeError("err_link_download", url=url, detail=str(exc)) from exc
    with response:
        content_type = response.headers.get("Content-Type", "")
        head = response.read(4096)
        final_url = response.geturl() or direct
        if _is_html(content_type, head):
            if _depth > 0:
                raise LocalizedRuntimeError("err_link_no_media", url=url)
            page = (head + response.read(PAGE_MAX_BYTES)).decode("utf-8", "replace")
            media = page_media_url(page, final_url)
            if not media:
                raise LocalizedRuntimeError("err_link_no_media", url=url)
            return download_url(media, base_directory, supported_exts, cancelled, _depth + 1)
        extension = sniff_extension(head, content_type, final_url)
        if extension is None or extension not in supported_exts:
            raise LocalizedRuntimeError("err_link_unsupported", url=url)
        stem = _sanitize_name(name) or _name_from_url(final_url) or "link"
        directory = link_directory(base_directory)
        path = os.path.join(directory, stem + extension)
        received = len(head)
        try:
            with open(path, "wb") as target:
                target.write(head)
                while True:
                    if cancelled is not None and cancelled():
                        raise LocalizedRuntimeError("err_link_cancelled")
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_BYTES:
                        raise LocalizedRuntimeError("err_link_too_big",
                                                    limit=MAX_BYTES // (1024 * 1024))
                    target.write(chunk)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return path

"""Ядро: конвертация, модель настроек, очередь, параллелизм, отмена.

Запуск всех наборов:  python tests/run_all.py
Запуск одного:        python tests/test_core.py
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

import shutil, subprocess, threading, time, traceback


BASE = WORK_ROOT
WORK = os.path.join(WORK_ROOT, "core")
if os.path.exists(WORK):
    shutil.rmtree(WORK)
os.makedirs(WORK)

results = []
def check(name, fn):
    try:
        fn(); results.append((name, "OK", "")); print(f"[OK]   {name}")
    except Exception as e:
        results.append((name, "FAIL", f"{type(e).__name__}: {e}"))
        print(f"[FAIL] {name} -- {type(e).__name__}: {e}")
        traceback.print_exc()

SRC = os.path.join(WORK, "люси1.mp4")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=3:size=320x240:rate=25",
                "-c:v","libx264","-pix_fmt","yuv420p",SRC], check=True, capture_output=True)

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

import ffmpeg_utils, image_utils, worker
from ffmpeg_utils import FFmpegProcessor, INDETERMINATE_PROGRESS, scaled_progress
from job_model import JobSettings, ConversionJob
from worker import ConversionWorker, resolve_output_path, default_worker_count
from PIL import Image, ImageDraw

fp = FFmpegProcessor()
IMG = os.path.join(WORK, "img.png")
Image.new("RGBA", (800, 400), (255, 0, 0, 255)).save(IMG)

def mkjob(path, fmt, **kw):
    return ConversionJob(input_path=path, output_dir=WORK,
                         settings=JobSettings(output_format=fmt, **kw))

# ---------- FFmpeg core (регрессия) ----------
check("F1 video->gif (кириллица)", lambda: (
    fp.video_to_gif(SRC, os.path.join(WORK,"a.gif"), 0,0,True,15),
    (_ for _ in ()).throw(AssertionError("empty")) if os.path.getsize(os.path.join(WORK,"a.gif"))==0 else None))
check("F2 video->webm", lambda: fp.convert_video(SRC, os.path.join(WORK,"a.webm"),160,0,True,None))
check("F3 video->avi", lambda: fp.convert_video(SRC, os.path.join(WORK,"a.avi"),0,0,True,None))
check("F4 video->mp4", lambda: fp.convert_video(SRC, os.path.join(WORK,"a.mp4"),0,0,True,20))
check("F5 extract_single_frame", lambda: fp.extract_single_frame(SRC, os.path.join(WORK,"f.png"),0,0,True))
check("F6 extract_frames", lambda: fp.extract_frames(SRC, os.path.join(WORK,"frames"),0,0,True,5))
check("F7 gif->video", lambda: fp.gif_to_video(os.path.join(WORK,"a.gif"), os.path.join(WORK,"rt.mp4"),0,0,True,None))

def t_tg():
    out=os.path.join(WORK,"st.webm"); fp.convert_telegram_webm(SRC,out,"sticker",max_duration=2.0)
    assert os.path.getsize(out)<=256*1024
check("F8 telegram webm <=256KB", t_tg)

def t_tw():
    out=os.path.join(WORK,"tw.gif"); fp.convert_twitch_gif(SRC,out,112)
    assert os.path.getsize(out)<=1024*1024
    fc=fp.get_frame_count(out); assert fc is None or fc<=60, fc
check("F9 twitch gif лимиты", t_tw)

def t_img():
    out=os.path.join(WORK,"i.jpg")
    image_utils.ImageProcessor.convert_image(IMG,out,"jpg",400,0,True)
    with Image.open(out) as im: assert im.size==(400,200), im.size
check("F10 image resize", t_img)

check("F11 telegram static 512", lambda: image_utils.ImageProcessor.convert_telegram_static(
    IMG, os.path.join(WORK,"tgs.png"), "tg_sticker_png"))
check("F12 twitch static 112", lambda: image_utils.ImageProcessor.convert_twitch_static(
    IMG, os.path.join(WORK,"tws.png"), 112))

def t_avif():
    out=os.path.join(WORK,"o.avif")
    image_utils.ImageProcessor.convert_image(IMG,out,"avif",200,0,True)
    with Image.open(out) as im: assert im.size==(200,100)
check("F13 AVIF", t_avif)

def t_heic():
    heic=os.path.join(WORK,"t.heic")
    Image.new("RGB",(300,200),(0,128,255)).save(heic, format="HEIF")
    out=os.path.join(WORK,"fh.jpg")
    image_utils.ImageProcessor.convert_image(heic,out,"jpg",150,0,True)
    with Image.open(out) as im: assert im.size==(150,100)
check("F14 HEIC вход", t_heic)

def t_awebp():
    """D1: анимированный webp раскладывается в кадры без потерь."""
    src=os.path.join(WORK,"anim.webp")
    frames=[Image.new("RGBA",(120,120),(i*8 % 255, 60, 200, 255)) for i in range(24)]
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=60, loop=0)
    frames_dir=os.path.join(WORK,"anim_frames")
    image_utils.ImageProcessor.dump_animation_frames(src, frames_dir)
    written=[n for n in os.listdir(frames_dir) if n.endswith(".png")]
    assert len(written)==24, f"кадров {len(written)} вместо 24"
check("F15 animated webp -> кадры (D1, все кадры на месте)", t_awebp)

def t_animated_webp_detection():
    """Анимированный WebP с обычным расширением .webp (эмодзи 7TV)
    должен распознаваться как анимация, а не как статичная картинка."""
    from worker import get_category, is_animated_image
    src = os.path.join(WORK, "анимация.webp")
    frames = [Image.new("RGBA", (100, 100), (i * 10 % 255, 80, 200, 255)) for i in range(12)]
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=80, loop=0)
    assert is_animated_image(src) is True, "анимация не распознана"
    assert get_category(src) == "animated_image", get_category(src)

    static = os.path.join(WORK, "статика.webp")
    Image.new("RGBA", (100, 100), (10, 200, 10, 255)).save(static)
    assert is_animated_image(static) is False
    assert get_category(static) == "image", get_category(static)

    apng = os.path.join(WORK, "анимация.png")
    frames[0].save(apng, save_all=True, append_images=frames[1:], duration=80)
    assert get_category(apng) == "animated_image", "APNG не распознан как анимация"
check("F16 анимированные .webp и .png распознаются по содержимому", t_animated_webp_detection)

def t_animated_webp_to_telegram():
    """Из анимированного WebP должен получаться корректный видео-стикер."""
    src = os.path.join(WORK, "анимация.webp")
    fin = []
    job = ConversionJob(input_path=src, output_dir=WORK,
                        settings=JobSettings(output_format="tg_sticker_webm"))
    w = ConversionWorker([job], max_workers=1)
    w.file_finished.connect(lambda i, ok, m: fin.append((ok, m)))
    w.run()
    assert fin and fin[0][0], f"не сконвертировался: {fin}"
    out = os.path.join(WORK, "анимация_tg_sticker.webm")
    assert os.path.isfile(out), sorted(os.listdir(WORK))
    assert os.path.getsize(out) <= 256 * 1024
    assert fp.get_frame_count(out) > 1, "анимация потеряна"
check("F17 анимированный WebP -> Telegram WEBM", t_animated_webp_to_telegram)

def t_animated_avif():
    """Анимированный AVIF (эмодзи 7TV) должен распознаваться и конвертироваться."""
    from worker import get_category
    from animation_info import animated_image_info
    src = os.path.join(WORK, "анимация.avif")
    frames = [Image.new("RGBA", (64, 64), (i * 9 % 255, 70, 190, 255)) for i in range(10)]
    try:
        frames[0].save(src, save_all=True, append_images=frames[1:], duration=40)
    except Exception:
        print("       AVIF-запись недоступна в этой сборке Pillow, пропуск")
        return
    assert get_category(src) == "animated_image", get_category(src)
    info = animated_image_info(src, fp.ffprobe_path)
    assert info and info["frames"] > 1, info
check("F18 анимированный AVIF распознаётся", t_animated_avif)

def t_real_frame_timing():
    """Скорость анимации берётся из файла, а не из выдуманных 100 мс на кадр."""
    from animation_info import animated_image_info
    src = os.path.join(WORK, "быстрая.webp")
    frames = [Image.new("RGBA", (60, 60), (i * 20 % 255, 90, 160, 255)) for i in range(20)]
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=30, loop=0)
    info = animated_image_info(src)
    assert info, "анимация не распознана"
    assert abs(info["duration"] - 0.6) < 0.05, f"длительность {info['duration']}"
    assert abs(info["fps"] - 33.3) < 2, f"fps {info['fps']}"

    # Те же задержки обязаны дойти до конвертации: обработчик раскладывает
    # анимацию в кадры и передаёт тайминги FFmpeg concat-списком.
    frames_dir = os.path.join(WORK, "быстрая_кадры")
    list_path = image_utils.ImageProcessor.dump_animation_frames(src, frames_dir)
    with open(list_path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    durations = [float(line.split()[1]) for line in lines if line.startswith("duration ")]
    assert len(durations) == 20, f"задержек {len(durations)} вместо 20"
    assert abs(sum(durations) - 0.6) < 0.05, sum(durations)
check("F19 реальная скорость анимации сохраняется", t_real_frame_timing)

def t_telegram_no_padding_and_trim():
    """Короткий файл не растягивается до 3 сек, длинный обрезается с выбранного места."""
    short_src = os.path.join(WORK, "короткое.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=1:size=160x120:rate=25",
                    "-c:v","libx264","-pix_fmt","yuv420p",short_src], check=True, capture_output=True)
    out = os.path.join(WORK, "короткое.webm")
    fp.convert_telegram_webm(short_src, out, "sticker", max_duration=3.0)
    got = fp.get_duration(out)
    assert got < 1.4, f"короткий файл растянут до {got:.2f} сек"

    long_src = os.path.join(WORK, "длинное.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=8:size=160x120:rate=25",
                    "-c:v","libx264","-pix_fmt","yuv420p",long_src], check=True, capture_output=True)
    out2 = os.path.join(WORK, "обрезка.webm")
    fp.convert_telegram_webm(long_src, out2, "sticker", max_duration=2.0, start_time=5.0)
    got2 = fp.get_duration(out2)
    assert abs(got2 - 2.0) < 0.25, f"обрезка дала {got2:.2f} сек вместо 2.0"
check("F20 Telegram: без растягивания и с обрезкой по времени", t_telegram_no_padding_and_trim)

def t_static_size_limits():
    """Статичные стикеры должны укладываться в лимиты площадок."""
    from telegram_utils import MAX_STATIC_SIZE_BYTES
    import random
    src = os.path.join(WORK, "шум512.png")
    noise = Image.new("RGBA", (512, 512))
    noise.putdata([(random.randrange(256), random.randrange(256),
                    random.randrange(256), random.randrange(256))
                   for _ in range(512 * 512)])
    noise.save(src)
    assert os.path.getsize(src) > MAX_STATIC_SIZE_BYTES, "тестовый файл слишком лёгкий"
    for fmt in ("tg_sticker_png", "tg_sticker_webp"):
        out = os.path.join(WORK, fmt + ".out")
        image_utils.ImageProcessor.convert_telegram_static(src, out, fmt)
        size = os.path.getsize(out)
        assert size <= MAX_STATIC_SIZE_BYTES, f"{fmt}: {size // 1024} КБ"
        with Image.open(out) as im:
            assert max(im.size) == 512, f"{fmt}: размер стикера {im.size}"
check("F21 статичные стикеры укладываются в лимит размера", t_static_size_limits)

def t_trim_general_conversion():
    """Тумблер длительности: обрезка работает для обычных конвертаций."""
    src = os.path.join(WORK, "для_обрезки.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=10:size=160x120:rate=25",
                    "-c:v","libx264","-pix_fmt","yuv420p",src], check=True, capture_output=True)
    settings = JobSettings(output_format="mp4", trim_enabled=True,
                           trim_start=2.0, trim_duration=3.0)
    assert settings.effective_trim == (2.0, 3.0), settings.effective_trim
    assert JobSettings(output_format="mp4", trim_start=2.0).effective_trim is None

    job = ConversionJob(input_path=src, output_dir=WORK, settings=settings)
    fin = []
    w = ConversionWorker([job], max_workers=1)
    w.file_finished.connect(lambda i, ok, m: fin.append((ok, m)))
    w.run()
    assert fin and fin[0][0], fin
    out = os.path.join(WORK, "для_обрезки_1.mp4")
    if not os.path.isfile(out):
        out = os.path.join(WORK, "для_обрезки.mp4")
    duration = fp.get_duration(out)
    assert abs(duration - 3.0) < 0.3, f"получилось {duration:.2f} сек вместо 3.0"

    gif_job = ConversionJob(input_path=src, output_dir=WORK,
                            settings=JobSettings(output_format="gif", trim_enabled=True,
                                                 trim_start=1.0, trim_duration=2.0))
    fin2 = []
    w2 = ConversionWorker([gif_job], max_workers=1)
    w2.file_finished.connect(lambda i, ok, m: fin2.append((ok, m)))
    w2.run()
    assert fin2 and fin2[0][0], fin2
    gif_duration = fp.get_duration(os.path.join(WORK, "для_обрезки.gif"))
    assert abs(gif_duration - 2.0) < 0.4, f"GIF вышел {gif_duration:.2f} сек"
check("F22 обрезка по времени для видео и GIF", t_trim_general_conversion)

# ---------- Модель настроек (D2) ----------
def t_model():
    s=JobSettings(output_format="png", resize_enabled=True, width=100, height=0)
    assert s.effective_width==100 and s.effective_height==0
    s2=JobSettings(output_format="png", resize_enabled=False, width=100)
    assert s2.effective_width==0, "resize выключен — размер игнорируется"
    assert JobSettings(fps_enabled=False, fps=30).effective_fps is None
    assert JobSettings(fps_enabled=True, fps=30).effective_fps==30
    assert s.copy(width=77).width==77 and s.width==100, "copy правит оригинал"
    assert JobSettings(rotate=45).effective_rotate==0, "кривой угол не проходит"
    assert JobSettings(rotate=90).has_transform is True
check("M1 JobSettings: свойства и копирование", t_model)

# ---------- Worker ----------
def t_pipeline():
    jobs=[mkjob(SRC,"gif",fps_enabled=True,fps=10), mkjob(IMG,"tg_sticker_webp")]
    fin=[]; w=ConversionWorker(jobs, max_workers=1)
    w.file_finished.connect(lambda i,ok,m: fin.append((i,ok,m))); w.run()
    assert len(fin)==2, fin
    for i,ok,m in fin: assert ok, f"{i}: {m}"
check("W1 конвейер 2 задачи", t_pipeline)

def t_missing():
    fin=[]; w=ConversionWorker([mkjob(os.path.join(WORK,"нет.mp4"),"gif")], max_workers=1)
    w.file_finished.connect(lambda i,ok,m: fin.append((ok,m))); w.run()
    assert fin and not fin[0][0] and "не найден" in str(fin[0][1]).lower(), fin
check("W2 отсутствующий файл -> понятная ошибка", t_missing)

def t_overwrite():
    p=os.path.join(WORK,"ov.txt"); open(p,"w").close()
    worker.release_reserved_paths()
    assert resolve_output_path(WORK,"ov","txt",overwrite=True)==p
    worker.release_reserved_paths()
    assert resolve_output_path(WORK,"ov","txt",overwrite=False).endswith("ov_1.txt")
check("W3 перезапись/уникальное имя", t_overwrite)

def t_path_race():
    """C2: параллельные потоки не должны получить один и тот же путь."""
    worker.release_reserved_paths()
    got=[]; lock=threading.Lock()
    def grab():
        p=resolve_output_path(WORK,"race","png",overwrite=False)
        with lock: got.append(p)
    threads=[threading.Thread(target=grab) for _ in range(12)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len(set(got))==12, f"дубликаты путей: {len(set(got))} из 12"
    worker.release_reserved_paths()
check("W4 гонка имён файлов при параллели (C2)", t_path_race)

def t_report():
    w=ConversionWorker([mkjob(IMG,"png")], max_workers=1); w.run()
    assert len(w.report)==1 and w.report[0]["status"]=="Готово", w.report
    assert "index" in w.report[0]
check("W5 отчёт по задачам", t_report)

# ---------- Параллелизм и производительность (C2) ----------
def t_parallel_correctness():
    imgs=[]
    for i in range(8):
        p=os.path.join(WORK,f"batch{i}.png")
        Image.new("RGB",(600,400),(i*30,90,140)).save(p); imgs.append(p)
    jobs=[mkjob(p,"jpg") for p in imgs]
    fin=[]
    w=ConversionWorker(jobs)
    w.file_finished.connect(lambda i,ok,m: fin.append((i,ok,m)))
    assert w.max_workers>1, f"ожидалась параллель, получено {w.max_workers}"
    # Сигналы из потоков пула доставляются через цикл событий — крутим его,
    # как это делает настоящее приложение.
    from PyQt6.QtCore import QEventLoop
    loop=QEventLoop()
    w.all_finished.connect(lambda _stopped: loop.quit())
    w.start()
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(120000, loop.quit)
    loop.exec()
    w.wait(5000)
    assert len(fin)==8, f"получено {len(fin)} результатов"
    assert all(ok for _,ok,_ in fin), [f for f in fin if not f[1]]
    assert len({i for i,_,_ in fin})==8, "индексы задач перепутаны"
    outs=[os.path.join(WORK,f"batch{i}.jpg") for i in range(8)]
    assert all(os.path.isfile(o) for o in outs), "не все файлы созданы"
check("P1 параллельная обработка 8 картинок: все задачи и файлы", t_parallel_correctness)

def t_parallel_speed():
    imgs=[]
    for i in range(12):
        p=os.path.join(WORK,f"perf{i}.png")
        Image.new("RGB",(1400,1000),(i*20,120,200)).save(p); imgs.append(p)

    def run(workers, tag):
        d=os.path.join(WORK,f"perf_out_{tag}"); os.makedirs(d, exist_ok=True)
        jobs=[ConversionJob(input_path=p, output_dir=d,
                            settings=JobSettings(output_format="webp")) for p in imgs]
        w=ConversionWorker(jobs, max_workers=workers)
        t0=time.monotonic(); w.run(); return time.monotonic()-t0

    seq=run(1,"seq"); par=run(4,"par")
    print(f"       последовательно: {seq:.2f}s | параллельно(4): {par:.2f}s | ускорение x{seq/par:.2f}")
    assert par < seq, f"параллель не быстрее: {par:.2f} vs {seq:.2f}"
check("P2 параллель быстрее последовательной", t_parallel_speed)

def t_default_workers():
    imgs=[mkjob(IMG,"jpg") for _ in range(5)]
    assert default_worker_count(imgs)>1, "картинки должны параллелиться"
    assert default_worker_count([mkjob(IMG,"jpg")])==1, "одна задача — один поток"
    vids=[mkjob(SRC,"webm") for _ in range(5)]
    assert default_worker_count(vids)<=2, "видео параллелим осторожно"
check("P3 выбор числа потоков", t_default_workers)

# ---------- Отмена ----------
def t_cancel():
    long_src=os.path.join(WORK,"long.mp4")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=90:size=1280x720:rate=30",
                    "-c:v","libx264","-pix_fmt","yuv420p",long_src], check=True, capture_output=True)
    w=ConversionWorker([mkjob(long_src,"webm")], max_workers=1)
    th=threading.Thread(target=w.run); th.start(); time.sleep(4)
    running = "ffmpeg.exe" in (subprocess.run(["tasklist","/FI","IMAGENAME eq ffmpeg.exe"],
              capture_output=True,text=True,encoding="utf-8",errors="replace").stdout or "")
    assert running, "ffmpeg должен работать до отмены"
    t0=time.monotonic(); w.request_stop(); th.join(timeout=25)
    elapsed=time.monotonic()-t0
    assert not th.is_alive(), "поток не остановился"
    time.sleep(1.5)
    after = "ffmpeg.exe" in (subprocess.run(["tasklist","/FI","IMAGENAME eq ffmpeg.exe"],
            capture_output=True,text=True,encoding="utf-8",errors="replace").stdout or "")
    assert not after, "ffmpeg остался в памяти"
    assert elapsed<15, f"отмена заняла {elapsed:.1f}s"
    print(f"       отмена за {elapsed:.1f}s, процессов не осталось")
check("C1 отмена убивает ffmpeg", t_cancel)

# ---------- Прогресс ----------
def t_progress_monotonic():
    bad=[]
    for fmt in ("twitch_animated_112","twitch_animated_pack","tg_sticker_webm","twitch_static_pack"):
        seq=[]
        w=ConversionWorker([mkjob(SRC,fmt)], max_workers=1)
        w.progress_updated.connect(lambda i,p: seq.append(p))
        ok=[]; w.file_finished.connect(lambda i,o,m: ok.append((o,m)))
        w.run()
        real=[p for p in seq if p!=INDETERMINATE_PROGRESS]
        drops=[(a,b) for a,b in zip(real,real[1:]) if b<a]
        if drops: bad.append((fmt,drops[:3]))
        if ok and not ok[0][0]: bad.append((fmt,"conversion failed: "+ok[0][1][:120]))
    assert not bad, bad
check("PR1 прогресс не откатывается", t_progress_monotonic)

def t_indeterminate():
    seen=[]; cb=scaled_progress(seen.append, 50, 0.5)
    cb(INDETERMINATE_PROGRESS); cb(50)
    assert seen==[INDETERMINATE_PROGRESS,75], seen
check("PR2 неопределённый прогресс пробрасывается", t_indeterminate)

# ---------- Прочее ----------
def t_frames_cleanup():
    d=os.path.join(WORK,"fr_clean"); os.makedirs(d,exist_ok=True)
    for i in range(1,200): open(os.path.join(d,f"frame_{i:05d}.png"),"w").close()
    fp.extract_frames(SRC,d,0,0,True,2)
    assert len(os.listdir(d))<50, f"старые кадры остались: {len(os.listdir(d))}"
check("O1 очистка старых кадров", t_frames_cleanup)

def t_frames_dir_collision():
    """Два одноимённых исходника не должны писать кадры в одну папку.

    Раньше имя папки собиралось напрямую из имени файла, а extract_frames
    чистит её перед работой: кадры первого файла пропадали, а при
    параллельной обработке оба писали вперемешку.
    """
    from worker import release_reserved_paths, resolve_frames_dir
    release_reserved_paths()
    try:
        base = os.path.join(WORK, "collide")
        os.makedirs(base, exist_ok=True)
        first = resolve_frames_dir(base, "клип")
        second = resolve_frames_dir(base, "клип")
        assert first != second, f"обе задачи получили одну папку: {first}"
        assert second.endswith("_1"), second
        # С перезаписью первая задача берёт имя без суффикса, вторая всё
        # равно получает своё: иначе они затрут кадры друг друга.
        release_reserved_paths()
        over_first = resolve_frames_dir(base, "перезапись", overwrite=True)
        over_second = resolve_frames_dir(base, "перезапись", overwrite=True)
        assert over_first.endswith("перезапись_frames"), over_first
        assert over_first != over_second, over_second
    finally:
        release_reserved_paths()
check("O2 папка кадров не достаётся двум задачам", t_frames_dir_collision)

def t_zero_size():
    try:
        image_utils.ImageProcessor.compute_target_size(0,100,200,0,True)
    except ValueError as e:
        assert "нулев" in str(e).lower(); return
    raise AssertionError("нет понятной ошибки")
check("O2 нулевой размер -> ValueError", t_zero_size)

def t_bundle_order():
    import inspect
    src=inspect.getsource(ffmpeg_utils._bundled_binary)
    assert "directories.append(bundle_dir)" in src
check("O3 внешний ffmpeg приоритетнее вшитого", t_bundle_order)

def t_twitch_hint():
    from twitch_utils import twitch_hint
    animated=twitch_hint("twitch_animated_pack")
    assert "60" in animated and "МБ" in animated and "1024" not in animated, animated
    assert "3 файла" in animated, animated
    static=twitch_hint("twitch_static_112")
    assert "112" in static
    assert animated != static, "подсказка должна зависеть от пресета"
check("O4 динамическая подсказка Twitch с лимитами (B4/B5)", t_twitch_hint)

# ---------- Discord ----------
from discord_utils import (MAX_EMOJI_BYTES, MAX_STICKER_BYTES, MAX_STICKER_DURATION_SEC,
                           discord_byte_limit, discord_hint, discord_size)

def t_discord_apng():
    out=os.path.join(WORK,"dc.png")
    fp.convert_discord_apng(SRC,out,320,MAX_STICKER_BYTES,
                            max_duration=MAX_STICKER_DURATION_SEC,fps_cap=30)
    assert os.path.getsize(out)<=MAX_STICKER_BYTES, os.path.getsize(out)
    info=fp.get_media_info(out)
    assert (info["width"],info["height"])==(320,320), info
    frames=fp.get_frame_count(out)
    assert frames and frames>1, f"APNG получился одним кадром: {frames}"
check("D1 Discord APNG: 320x320, лимит веса, анимация на месте", t_discord_apng)

def t_discord_gif():
    out=os.path.join(WORK,"dce.gif")
    fp.convert_discord_gif(SRC,out,128,MAX_EMOJI_BYTES,fps_cap=30)
    assert os.path.getsize(out)<=MAX_EMOJI_BYTES, os.path.getsize(out)
    info=fp.get_media_info(out)
    assert (info["width"],info["height"])==(128,128), info
check("D2 Discord GIF-эмодзи: 128x128 в пределах 256 КБ", t_discord_gif)

def t_discord_static():
    out=os.path.join(WORK,"dcs.png")
    image_utils.ImageProcessor.convert_discord_static(IMG,out,320,MAX_STICKER_BYTES)
    with Image.open(out) as im:
        assert im.size==(320,320), im.size
        assert im.mode=="RGBA", im.mode
    assert os.path.getsize(out)<=MAX_STICKER_BYTES
check("D3 статичный стикер Discord вписан в квадрат с прозрачным фоном", t_discord_static)

def t_discord_meta():
    assert discord_size("discord_emoji_png")==128 and discord_size("discord_sticker_png")==320
    assert discord_byte_limit("discord_emoji_gif")==MAX_EMOJI_BYTES
    assert discord_byte_limit("discord_sticker_apng")==MAX_STICKER_BYTES
    assert "320" in discord_hint("discord_sticker_apng")
    assert discord_hint("discord_emoji_png")!=discord_hint("discord_sticker_png")
check("D4 размеры, лимиты и подсказки Discord согласованы", t_discord_meta)

def t_discord_job():
    job=ConversionJob(input_path=SRC,output_dir=WORK,source_path=SRC,
                      settings=JobSettings(output_format="discord_sticker_apng"))
    ConversionWorker([job])._process_job(0,job)
    made=[f for f in os.listdir(WORK) if f.endswith("_dc_sticker.png")]
    assert made, "стикер Discord не создан"
check("D5 задача Discord проходит через обработчик очереди", t_discord_job)

# ---------- Звук ----------
AUD = os.path.join(WORK, "звук.mp4")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=4:size=160x120:rate=25",
                "-f","lavfi","-i","sine=frequency=440:duration=4","-c:v","libx264",
                "-pix_fmt","yuv420p","-c:a","aac","-shortest",AUD],check=True,capture_output=True)

def has_audio(path):
    r=subprocess.run(["ffprobe","-v","error","-select_streams","a","-show_entries",
                      "stream=index","-of","csv=p=0",path],capture_output=True,text=True)
    return bool(r.stdout.strip())

def t_audio_mp3():
    out=os.path.join(WORK,"a.mp3"); fp.extract_audio(AUD,out,192)
    assert os.path.getsize(out)>1000, os.path.getsize(out)
    assert abs(fp.get_duration(out)-4)<0.5, fp.get_duration(out)
check("A1 извлечение звука в MP3", t_audio_mp3)

def t_audio_trim():
    out=os.path.join(WORK,"a.wav"); fp.extract_audio(AUD,out,trim=(1.0,2.0))
    assert abs(fp.get_duration(out)-2)<0.3, fp.get_duration(out)
check("A2 WAV с обрезкой по времени", t_audio_trim)

def t_audio_job():
    job=ConversionJob(input_path=AUD,output_dir=WORK,source_path=AUD,
                      settings=JobSettings(output_format="m4a",audio_bitrate=128))
    ConversionWorker([job])._process_job(0,job)
    assert os.path.exists(os.path.join(WORK,"звук.m4a"))
check("A3 задача «только звук» проходит через обработчик", t_audio_job)

def t_audio_image_error():
    job=mkjob(IMG,"mp3")
    try:
        ConversionWorker([job])._process_job(0,job)
    except ValueError as e:
        assert "звук" in str(e).lower(), e; return
    raise AssertionError("у картинки не может быть звуковой дорожки")
check("A4 звук из картинки — понятная ошибка", t_audio_image_error)

def t_mute():
    out=os.path.join(WORK,"mute.mp4")
    fp.convert_video(AUD,out,0,0,True,None,drop_audio=True)
    assert has_audio(AUD), "в исходнике звука нет — тест бессмысленный"
    assert not has_audio(out), "звуковая дорожка осталась"
check("A5 тумблер «убрать звук» действительно убирает дорожку", t_mute)

# ---------- Качество и целевой размер ----------
def t_quality_scale():
    from ffmpeg_utils import quality_to_codec_value
    for ext in (".mp4",".webm",".avi"):
        values=[quality_to_codec_value(ext,q) for q in (1,50,100)]
        assert values[0]>values[1]>values[2], (ext,values)
    assert quality_to_codec_value(".mp4",None) is None
check("Q1 шкала качества монотонна для всех кодеков", t_quality_scale)

def t_quality_size():
    low=os.path.join(WORK,"q15.mp4"); high=os.path.join(WORK,"q95.mp4")
    fp.convert_video(SRC,low,0,0,True,None,quality=15)
    fp.convert_video(SRC,high,0,0,True,None,quality=95)
    assert os.path.getsize(low)<os.path.getsize(high), \
        (os.path.getsize(low),os.path.getsize(high))
check("Q2 низкое качество даёт файл меньше высокого", t_quality_size)

def t_target_size():
    out=os.path.join(WORK,"target.mp4"); limit=300*1024
    fp.convert_video(SRC,out,0,0,True,None,target_bytes=limit)
    assert os.path.getsize(out)<=limit*1.05, (os.path.getsize(out),limit)
check("Q3 целевой размер выдержан", t_target_size)

def t_target_unreachable():
    try:
        fp.convert_video(SRC,os.path.join(WORK,"tiny.mp4"),0,0,True,None,target_bytes=512)
    except ValueError as e:
        assert "слишком мал" in str(e), e; return
    raise AssertionError("недостижимый размер должен давать понятную ошибку")
check("Q4 недостижимый целевой размер объясняется человеку", t_target_unreachable)

def t_quality_image():
    small=os.path.join(WORK,"q30.jpg"); big=os.path.join(WORK,"q95.jpg")
    noisy=os.path.join(WORK,"noisy.png")
    import random
    rnd=Image.new("RGB",(400,400))
    rnd.putdata([(random.randrange(256),random.randrange(256),random.randrange(256))
                 for _ in range(400*400)])
    rnd.save(noisy)
    image_utils.ImageProcessor.convert_image(noisy,small,"jpg",0,0,True,quality=30)
    image_utils.ImageProcessor.convert_image(noisy,big,"jpg",0,0,True,quality=95)
    assert os.path.getsize(small)<os.path.getsize(big)
check("Q5 качество влияет и на картинки", t_quality_image)

# ---------- Кадрирование, поворот, отражение ----------
from ffmpeg_utils import Transform

def t_transform_filters():
    t=Transform(rotate=90,flip_horizontal=True,flip_vertical=True)
    assert t.filters()==["transpose=1","hflip","vflip"], t.filters()
    assert Transform(rotate=180).filters()==["transpose=1,transpose=1"]
    assert Transform(rotate=270).filters()==["transpose=2"]
    assert not Transform()
    # поворот идёт до масштабирования, иначе размер применился бы к
    # неповёрнутому кадру и стороны поменялись бы местами
    chain=FFmpegProcessor.build_filter_string(100,0,True,10,Transform(rotate=90))
    assert chain.index("transpose=")<chain.index("scale="), chain
check("T1 фильтры преобразования и их порядок", t_transform_filters)

def t_rotate_video():
    out=os.path.join(WORK,"rot.mp4")
    fp.convert_video(SRC,out,0,0,True,None,transform=Transform(rotate=90))
    info=fp.get_media_info(out)
    assert (info["width"],info["height"])==(240,320), info
check("T2 поворот видео на 90° меняет стороны местами", t_rotate_video)

def t_rotate_image():
    out=os.path.join(WORK,"rot.png")
    image_utils.ImageProcessor.convert_image(
        IMG,out,"png",0,0,True,transform=Transform(rotate=270,flip_horizontal=True))
    with Image.open(out) as im:
        assert im.size==(400,800), im.size
check("T3 поворот картинки на 270° меняет стороны местами", t_rotate_image)





def t_transform_applies_over_preset():
    # Правки кадра действуют и поверх пресета площадки: пресет отвечает
    # за размер и лимиты, кадрирование — за то, что попадёт в кадр.
    plain=JobSettings(output_format="tg_sticker_webm")
    assert worker.transform_for(plain) is None, "без правок преобразования быть не должно"
    assert worker.transform_for(plain.copy(rotate=90)) is not None
    assert worker.transform_for(plain.copy(flip_horizontal=True)) is not None
check("T4 поворот действует и поверх пресета площадки",
      t_transform_applies_over_preset)

# ---------- Исправленные дефекты ----------
def t_protect_animated_source():
    d=os.path.join(WORK,"protect"); os.makedirs(d,exist_ok=True)
    src=os.path.join(d,"эмодзи.webp")
    frames=[Image.new("RGBA",(120,120),(255,0,0,180+i*5)) for i in range(6)]
    frames[0].save(src,save_all=True,append_images=frames[1:],duration=50,loop=0)
    before=os.path.getsize(src)
    job=ConversionJob(input_path=src,output_dir=d,overwrite=True,source_path=src,
                      settings=JobSettings(output_format="webp"))
    ConversionWorker([job])._process_job(0,job)
    assert os.path.getsize(src)==before, "исходник перезаписан результатом!"
    assert [f for f in os.listdir(d) if f!="эмодзи.webp"], "результат не создан"
check("B1 анимированный исходник не затирается при перезаписи в ту же папку",
      t_protect_animated_source)

def t_alpha_survives():
    # промежуточный GIF съедал полупрозрачность: у него альфа однобитная
    src=os.path.join(WORK,"alpha.webp")
    frames=[]
    for i in range(10):
        im=Image.new("RGBA",(160,160),(0,0,0,0))
        ImageDraw.Draw(im).ellipse((10+i,10,150,150),fill=(255,90,40,128))
        frames.append(im)
    frames[0].save(src,save_all=True,append_images=frames[1:],duration=40,loop=0)
    job=ConversionJob(input_path=src,output_dir=WORK,source_path=src,
                      settings=JobSettings(output_format="tg_sticker_webm"))
    ConversionWorker([job])._process_job(0,job)
    made=[f for f in os.listdir(WORK) if f.startswith("alpha") and f.endswith(".webm")]
    assert made, "webm не создан"
    png=os.path.join(WORK,"alpha_check.png")
    subprocess.run(["ffmpeg","-y","-c:v","libvpx-vp9","-i",os.path.join(WORK,made[0]),
                    "-frames:v","1","-pix_fmt","rgba",png],check=True,capture_output=True)
    with Image.open(png) as im:
        alpha=im.convert("RGBA").getchannel("A").tobytes()
    semi=sum(1 for v in alpha if 0<v<255)/len(alpha)
    assert semi>0.15, f"полупрозрачных пикселей всего {semi:.3f} — альфа потеряна"
check("B2 полупрозрачность анимации доживает до Telegram WEBM", t_alpha_survives)

def t_cancel_signal():
    import inspect
    src=inspect.getsource(ConversionWorker._run_single)
    assert "file_cancelled" in src, \
        "отмена обязана сообщать окну, иначе строка виснет в состоянии «Обработка»"
    assert hasattr(ConversionWorker,"file_cancelled")
check("B3 прерванный файл получает собственный сигнал", t_cancel_signal)

def t_worker_count_no_file_reads():
    # Функция вызывается в потоке интерфейса: чтение содержимого каждого
    # файла подвешивало окно ещё до старта обработки. Проверяем поведением,
    # а не текстом: подменяем распознавание анимации на взрывающееся.
    original = worker.is_animated_image
    worker.is_animated_image = lambda path: (_ for _ in ()).throw(
        AssertionError("файл открывать нельзя"))
    try:
        jobs=[mkjob(IMG,"png") for _ in range(4)]
        assert default_worker_count(jobs)>1
        assert default_worker_count([mkjob(SRC,"mp4")]*4)<=2
    finally:
        worker.is_animated_image = original
check("B4 выбор числа потоков не открывает файлы", t_worker_count_no_file_reads)

def t_webp_limit_raises():
    # раньше недостижимый лимит молча отдавал файл больше нужного
    big=Image.new("RGBA",(512,512))
    import random
    big.putdata([(random.randrange(256),random.randrange(256),random.randrange(256),255)
                 for _ in range(512*512)])
    try:
        image_utils.save_within_limit(big,os.path.join(WORK,"lim.webp"),"WEBP",800)
    except RuntimeError as e:
        assert "лимит" in str(e), e; return
    raise AssertionError("превышение лимита WEBP должно быть ошибкой, а не тишиной")
check("B5 недостижимый лимит WEBP больше не проходит молча", t_webp_limit_raises)

def t_frame_estimate_trim():
    full=fp.estimate_frame_count(SRC,25)
    part=fp.estimate_frame_count(SRC,25,(0.0,1.0))
    assert part<full, (part,full)
check("B6 предупреждение о кадрах учитывает обрезку", t_frame_estimate_trim)

def t_twitch_trim():
    out=os.path.join(WORK,"twtrim.gif")
    fp.convert_twitch_gif(SRC,out,112,trim=(1.0,1.0))
    assert fp.get_duration(out)<2.0, fp.get_duration(out)
check("B7 у Twitch появилась обрезка по времени", t_twitch_trim)

def t_apng_input():
    apng=os.path.join(WORK,"in.apng")
    frames=[Image.new("RGBA",(80,80),(0,120+i*10,200,255)) for i in range(5)]
    frames[0].save(apng,format="PNG",save_all=True,append_images=frames[1:],
                   duration=60,loop=0)
    assert worker.get_category(apng)=="animated_image", worker.get_category(apng)
check("B8 APNG на входе распознаётся как анимация", t_apng_input)

def t_apng_output():
    """APNG — одна картинка со всеми кадрами и полной прозрачностью."""
    out=os.path.join(WORK,"anim_out.png")
    fp.convert_apng(SRC,out,160,0,True,10)
    assert os.path.getsize(out)>0
    frames=fp.get_frame_count(out)
    assert frames and frames>1, f"APNG получился одним кадром: {frames}"
    info=fp.get_media_info(out)
    assert info["width"]==160, info
check("N1 APNG: анимация одним файлом", t_apng_output)

def t_apng_keeps_alpha():
    """У APNG прозрачность полноценная, в отличие от GIF."""
    src=os.path.join(WORK,"alpha_apng.webp")
    from PIL import ImageDraw
    frames=[]
    for i in range(8):
        im=Image.new("RGBA",(120,120),(0,0,0,0))
        ImageDraw.Draw(im).ellipse((8+i,8,112,112),fill=(240,100,50,128))
        frames.append(im)
    frames[0].save(src,save_all=True,append_images=frames[1:],duration=50,loop=0)
    job=ConversionJob(input_path=src,output_dir=WORK,source_path=src,
                      settings=JobSettings(output_format="apng"))
    ConversionWorker([job])._process_job(0,job)
    out=os.path.join(WORK,"alpha_apng.png")
    assert os.path.isfile(out), sorted(os.listdir(WORK))[:20]
    with Image.open(out) as im:
        alpha=im.convert("RGBA").getchannel("A").tobytes()
    semi=sum(1 for v in alpha if 0<v<255)/len(alpha)
    assert semi>0.15, f"полупрозрачных пикселей всего {semi:.3f}"
check("N2 APNG сохраняет полупрозрачность", t_apng_keeps_alpha)

def t_apng_job_from_video():
    job=ConversionJob(input_path=SRC,output_dir=WORK,source_path=SRC,
                      settings=JobSettings(output_format="apng",fps_enabled=True,fps=8))
    ConversionWorker([job])._process_job(0,job)
    assert os.path.isfile(os.path.join(WORK,"люси1.png"))
check("N3 задача APNG проходит через обработчик очереди", t_apng_job_from_video)

# ---------- Исправления и ускорение (версия 1.1) ----------
LONG = os.path.join(WORK, "длинный.mp4")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=8:size=320x240:rate=25",
                "-c:v","libx264","-pix_fmt","yuv420p",LONG],check=True,capture_output=True)

def t_discord_apng_trim():
    # Раньше -t всегда равнялся 5 сек, и конец обрезки терялся.
    out=os.path.join(WORK,"dc_trim.png")
    fp.convert_discord_apng(LONG,out,320,512*1024,max_duration=5.0,fps_cap=10,
                            trim=(2.0,1.0))
    frames=fp.get_frame_count(out)
    assert frames and frames<=12, f"кадров {frames}: обрезка до 1 сек не сработала"
    out2=os.path.join(WORK,"dc_trim_long.png")
    fp.convert_discord_apng(LONG,out2,320,512*1024,max_duration=5.0,fps_cap=10,
                            trim=(0.0,7.0))
    frames2=fp.get_frame_count(out2)
    assert frames2 and frames2<=52, f"кадров {frames2}: лимит 5 сек не сработал"
check("V1 Discord APNG учитывает конец обрезки и лимит 5 сек", t_discord_apng_trim)

def t_errors_translated():
    import i18n
    from errors import LocalizedError, message_text
    job=mkjob(IMG,"mp3")
    try:
        ConversionWorker([job])._process_job(0,job)
    except LocalizedError as e:
        err=e
    else:
        raise AssertionError("ошибка не возникла")
    was=i18n.current_language()
    try:
        i18n.set_language("en"); en=message_text(err)
        i18n.set_language("ru"); ru=message_text(err)
    finally:
        i18n.set_language(was)
    assert "audio" in en.lower() and "звук" in ru.lower(), (en, ru)
    # Сигнал несёт саму ошибку, а не готовую строку: язык выбирается при показе.
    fin=[]; w=ConversionWorker([mkjob(IMG,"mp3")],max_workers=1)
    w.file_finished.connect(lambda i,ok,m: fin.append(m)); w.run()
    assert isinstance(fin[0],LocalizedError), type(fin[0])
check("V2 ошибки обработки переводятся при показе", t_errors_translated)

def t_no_russian_literals_in_core():
    # Всё, что видит пользователь, должно идти через ключи перевода.
    import re
    for name in ("worker.py","ffmpeg_utils.py","image_utils.py","telegram_utils.py"):
        src=open(os.path.join(PROJECT_DIR,name),encoding="utf-8").read()
        for m in re.finditer(r"raise\s+\w*Error\(\s*f?\"([^\"]*)",src):
            assert not re.search("[а-яА-Я]",m.group(1)), f"{name}: {m.group(0)[:80]}"
check("V3 в ядре не осталось ошибок с русским текстом вместо ключа", t_no_russian_literals_in_core)

def t_new_inputs():
    mkv=os.path.join(WORK,"запись.mkv"); mov=os.path.join(WORK,"айфон.mov")
    for path in (mkv,mov):
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=1:size=160x120:rate=10",
                        "-c:v","libx264","-pix_fmt","yuv420p",path],check=True,capture_output=True)
        assert worker.get_category(path)=="video", worker.get_category(path)
        job=ConversionJob(input_path=path,output_dir=WORK,source_path=path,
                          settings=JobSettings(output_format="mp4"))
        ConversionWorker([job])._process_job(0,job)
    assert os.path.isfile(os.path.join(WORK,"запись.mp4"))
    assert os.path.isfile(os.path.join(WORK,"айфон.mp4"))
    tif=os.path.join(WORK,"скан.tiff"); Image.new("RGB",(64,32),(9,9,9)).save(tif)
    assert worker.get_category(tif)=="image"
check("V4 MKV, MOV и TIFF принимаются на вход", t_new_inputs)

def t_twitch_pack_shared_fps():
    calls=[]
    original=fp._run_with_progress
    def spy(cmd,duration,cb):
        calls.append(cmd); return original(cmd,duration,cb)
    fp._run_with_progress=spy
    try:
        d=os.path.join(WORK,"pack"); os.makedirs(d,exist_ok=True)
        job=ConversionJob(input_path=SRC,output_dir=d,source_path=SRC,
                          settings=JobSettings(output_format="twitch_animated_pack"))
        w=ConversionWorker([job]); w._processors[threading.get_ident()]=fp
        w._process_job(0,job)
    finally:
        fp._run_with_progress=original
    made=sorted(f for f in os.listdir(d) if f.endswith(".gif"))
    assert len(made)==3, made
    rates=set()
    for f in made:
        info=fp.get_media_info(os.path.join(d,f)); rates.add(round(info["fps"] or 0))
        assert os.path.getsize(os.path.join(d,f))<=1024*1024
    assert len(rates)==1, f"у размеров комплекта разная частота: {rates}"
    assert len(calls)<=5, f"запусков FFmpeg {len(calls)} — подбор не переиспользован"
check("V5 комплект Twitch: одна частота на все размеры и мало запусков", t_twitch_pack_shared_fps)

def t_single_pass_gif():
    calls=[]
    original=fp._run_with_progress
    def spy(cmd,duration,cb):
        calls.append(cmd); return original(cmd,duration,cb)
    fp._run_with_progress=spy
    try:
        out=os.path.join(WORK,"onepass.gif")
        fp.video_to_gif(SRC,out,160,0,True,10,trim=(1.0,1.0))
    finally:
        fp._run_with_progress=original
    assert len(calls)==1, f"GIF собирался за {len(calls)} запуска"
    assert abs(fp.get_duration(out)-1.0)<0.25, fp.get_duration(out)
    # А при огромном объёме кадров — по-старому, в два прохода.
    assert ffmpeg_utils.frames_memory(3840,2160,30,600)>ffmpeg_utils.SINGLE_PASS_GIF_MEMORY
check("V6 короткий GIF собирается за один запуск FFmpeg", t_single_pass_gif)

def t_search_matches_binary():
    # Ускоренный подбор обязан давать тот же ответ, что честный перебор.
    import random
    rnd=random.Random(7)
    for _ in range(300):
        cap=rnd.randint(1,30); boundary=rnd.randint(0,cap)
        per_fps=rnd.uniform(5_000,80_000); limit=int(per_fps*boundary+per_fps/2) if boundary else 1
        tried=[]
        def encode(fps,dest,_cb):
            tried.append(fps)
            with open(dest,"wb") as h: h.write(b"x"*int(per_fps*fps))
        def fits(path):
            return None if os.path.getsize(path)<=limit else RuntimeError("big")
        try:
            _blob,got=fp._search_fps_within_limit(None,None,cap,encode,fits,None,
                                                  RuntimeError("none"),limit_bytes=limit)
        except RuntimeError:
            got=0
        assert got==boundary, (cap,boundary,got,tried)
check("V7 ускоренный подбор FPS находит ту же границу", t_search_matches_binary)

def t_twitch_long_helpers():
    from twitch_utils import twitch_effective_fps, twitch_smooth_duration_limit, TWITCH_MIN_SMOOTH_FPS
    assert twitch_effective_fps(2)==15
    assert twitch_effective_fps(30)==2
    assert twitch_effective_fps(twitch_smooth_duration_limit())==TWITCH_MIN_SMOOTH_FPS
check("V8 расчёт плавности анимации Twitch", t_twitch_long_helpers)

# ---------- Новые пресеты ----------
ANIM_WEBP = os.path.join(WORK, "эмоут.webp")
_frames=[]
for i in range(20):
    im=Image.new("RGBA",(200,100),(0,0,0,0))
    ImageDraw.Draw(im).ellipse((10+i*3,10,90+i*3,90),fill=(255,120,40,200))
    _frames.append(im)
_frames[0].save(ANIM_WEBP,save_all=True,append_images=_frames[1:],duration=50,loop=0)
WIDE = os.path.join(WORK, "широкая.png")
Image.new("RGBA",(400,100),(20,200,90,255)).save(WIDE)

def run_job(path, fmt, out_dir, **kw):
    os.makedirs(out_dir, exist_ok=True)
    job=ConversionJob(input_path=path,output_dir=out_dir,source_path=path,
                      settings=JobSettings(output_format=fmt,**kw))
    fin=[]; w=ConversionWorker([job],max_workers=1)
    w.file_finished.connect(lambda i,ok,m: fin.append((ok,str(m))))
    w.run()
    assert fin and fin[0][0], fin
    return sorted(os.listdir(out_dir))

def t_twitch_badges_points():
    d=os.path.join(WORK,"badges"); made=run_job(IMG,"twitch_badge_pack",d)
    assert made==["img_twitch_badge_18.png","img_twitch_badge_36.png","img_twitch_badge_72.png"], made
    for f in made:
        assert os.path.getsize(os.path.join(d,f))<=25*1024
    d2=os.path.join(WORK,"points"); made2=run_job(SRC,"twitch_points_pack",d2)
    sizes=[]
    for f in made2:
        with Image.open(os.path.join(d2,f)) as im: sizes.append(im.size[0])
        assert os.path.getsize(os.path.join(d2,f))<=25*1024
    assert sorted(sizes)==[28,56,112], sizes
check("N4 значки подписки и иконки баллов Twitch: размеры и лимит 25 КБ", t_twitch_badges_points)

def t_7tv_auto():
    d=os.path.join(WORK,"7tv_anim"); made=run_job(ANIM_WEBP,"seventv_emote",d)
    assert made==["эмоут_7tv.webp"], made
    with Image.open(os.path.join(d,made[0])) as im:
        assert im.size==(128,128) and getattr(im,"n_frames",1)>1, (im.size, getattr(im,"n_frames",1))
    d2=os.path.join(WORK,"7tv_static"); made2=run_job(IMG,"seventv_emote",d2)
    assert made2==["img_7tv.png"], made2
check("N5 7TV: анимация из анимации, PNG из картинки", t_7tv_auto)

def t_whatsapp():
    d=os.path.join(WORK,"wa"); made=run_job(IMG,"whatsapp_static",d)
    out=os.path.join(d,made[0])
    with Image.open(out) as im: assert im.format=="WEBP" and im.size==(512,512)
    assert os.path.getsize(out)<=100*1024
    made=run_job(LONG,"whatsapp_animated",os.path.join(WORK,"wa_anim"))
    out=os.path.join(WORK,"wa_anim",made[0])
    with Image.open(out) as im:
        assert im.size==(512,512) and im.n_frames>1, (im.size, im.n_frames)
        total=0
        for k in range(im.n_frames):
            im.seek(k); total+=im.info.get("duration",0)
    assert os.path.getsize(out)<=500*1024, os.path.getsize(out)
    assert total<=10_050, f"анимация {total} мс длиннее 10 сек"
    made=run_job(IMG,"whatsapp_tray",os.path.join(WORK,"wa_tray"))
    with Image.open(os.path.join(WORK,"wa_tray",made[0])) as im:
        assert im.size==(96,96) and im.format=="PNG"
    try:
        run_job(IMG,"whatsapp_animated",os.path.join(WORK,"wa_bad"))
    except AssertionError as e:
        assert "только из видео" in str(e), e
    else:
        raise AssertionError("анимированный стикер из картинки должен давать ошибку")
check("N6 WhatsApp: стикер, анимированный стикер и иконка набора по лимитам", t_whatsapp)

def t_kick_youtube():
    ONE_MB = 1_000_000
    d=os.path.join(WORK,"kick"); made=run_job(IMG,"kick_emote",d)
    assert made==["img_kick.png"], made
    with Image.open(os.path.join(d,made[0])) as im: assert im.size==(500,500) and im.format=="PNG"
    assert os.path.getsize(os.path.join(d,made[0]))<ONE_MB
    d=os.path.join(WORK,"kick_gif"); made=run_job(LONG,"kick_emote_gif",d)
    out=os.path.join(d,made[0])
    assert made[0].endswith("_kick.gif"), made
    with Image.open(out) as im:
        assert im.size==(256,256) and im.n_frames>1, (im.size, im.n_frames)
    assert os.path.getsize(out)<ONE_MB, os.path.getsize(out)
    d=os.path.join(WORK,"kick_badge"); made=run_job(IMG,"kick_badge_pack",d)
    assert made==["img_kick_badge_36.png","img_kick_badge_72.png"], made
    d=os.path.join(WORK,"yt"); made=run_job(SRC,"youtube_emoji",d)
    with Image.open(os.path.join(d,made[0])) as im:
        assert im.size==(480,480) and im.format=="PNG" and getattr(im,"n_frames",1)==1
    assert made==["люси1_yt_emoji.png"], made
    d=os.path.join(WORK,"yt_badge"); made=run_job(IMG,"youtube_badge",d)
    with Image.open(os.path.join(d,made[0])) as im: assert im.size==(128,128)
    try:
        run_job(IMG,"kick_emote_gif",os.path.join(WORK,"kick_bad"))
    except AssertionError as e:
        assert "только из видео" in str(e), e
    else:
        raise AssertionError("анимированный смайлик Kick из картинки должен давать ошибку")
    assert worker.is_static_target("kick_emote") and not worker.is_static_target("kick_emote_gif")
    assert worker.is_static_target("youtube_emoji")
check("N6a Kick и YouTube: смайлики, GIF, значки и эмодзи по требованиям", t_kick_youtube)

def t_fill_square():
    fit=os.path.join(WORK,"fit"); fill=os.path.join(WORK,"fill")
    run_job(WIDE,"discord_emoji_png",fit)
    run_job(WIDE,"discord_emoji_png",fill,fill_square=True)
    with Image.open(os.path.join(fit,"широкая_dc_emoji.png")) as im:
        corner_fit=im.convert("RGBA").getpixel((2,2))[3]
    with Image.open(os.path.join(fill,"широкая_dc_emoji.png")) as im:
        corner_fill=im.convert("RGBA").getpixel((2,2))[3]
    assert corner_fit==0 and corner_fill==255, (corner_fit, corner_fill)
    vid=os.path.join(WORK,"fill_gif"); run_job(SRC,"twitch_animated_112",vid,fill_square=True)
    png=os.path.join(WORK,"fill_check.png")
    subprocess.run(["ffmpeg","-y","-i",os.path.join(vid,"люси1_twitch_112.gif"),"-frames:v","1",png],
                   check=True,capture_output=True)
    with Image.open(png) as im:
        assert im.convert("RGBA").getpixel((1,1))[3]==255, "в режиме заполнения поля остались прозрачными"
check("N7 режим «заполнить квадрат» обрезает края вместо полей", t_fill_square)

# ---------- Стикеры Telegram (.tgs) ----------
from tgs_fixture import make_tgs

TGS = make_tgs(os.path.join(WORK, "стикер.tgs"), frames=90, fps=30)

def t_tgs_category_and_info():
    from worker import get_category
    from animation_info import animated_image_info
    assert get_category(TGS) == "animated_image", get_category(TGS)
    info = animated_image_info(TGS)
    # Ровно 90 кадров и 3 секунды: rlottie считает кадры включительно с
    # последним, и без поправки выходил бы 91 кадр и 3,03 с.
    assert info["frames"] == 90 and abs(info["duration"] - 3.0) < 1e-6, info
    assert (info["width"], info["height"]) == (512, 512), info
check("TGS1 .tgs распознаётся: 90 кадров, 3 с, 512×512", t_tgs_category_and_info)

def t_tgs_conversions():
    d = os.path.join(WORK, "tgs_out")
    for fmt in ("gif", "webp", "apng", "mp4", "png"):
        run_job(TGS, fmt, d)
    made = sorted(os.listdir(d))
    expected = ["стикер.gif", "стикер.mp4", "стикер.png", "стикер.webp", "стикер_1.png"]
    assert made == expected, made
    # GIF и видео — анимация, а не один кадр, и примерно той же длины.
    assert fp.get_frame_count(os.path.join(d, "стикер.gif")) > 30
    assert fp.get_frame_count(os.path.join(d, "стикер.mp4")) > 30
    # «WEBP» в списке форматов — статичная картинка (анимированный WEBP
    # делает пресет 7TV): из стикера берётся кадр.
    with Image.open(os.path.join(d, "стикер.webp")) as im:
        assert getattr(im, "n_frames", 1) == 1
        assert im.convert("RGBA").getbbox() is not None, "пустой кадр"
    # PNG без анимации — кадр, и на нём оранжевый круг на прозрачном фоне.
    static = [f for f in made if f.endswith(".png")]
    has_static = False
    for name in static:
        with Image.open(os.path.join(d, name)) as im:
            if getattr(im, "n_frames", 1) == 1:
                has_static = True
                rgba = im.convert("RGBA")
                assert rgba.getpixel((2, 2))[3] == 0, "фон стикера не прозрачный"
                assert rgba.getbbox() is not None
    assert has_static, "нет статичного кадра"
check("TGS2 .tgs -> GIF, WEBP, APNG, MP4, PNG", t_tgs_conversions)

def t_tgs_presets():
    d = os.path.join(WORK, "tgs_presets")
    run_job(TGS, "tg_sticker_webm", d)
    out = os.path.join(d, "стикер_tg_sticker.webm")
    assert os.path.getsize(out) <= 256 * 1024
    assert fp.get_frame_count(out) > 30, "видео-стикер без анимации"
    made = run_job(TGS, "discord_emoji_gif", d)
    assert any(name.endswith("_dc_emoji.gif") for name in made), made
    made = run_job(TGS, "twitch_animated_112", d)
    assert any(name.endswith("_twitch_112.gif") for name in made), made
    made = run_job(TGS, "seventv_emote", d)
    webp = [name for name in made if name.endswith(".webp")]
    assert webp, made
    with Image.open(os.path.join(d, webp[0])) as im:
        assert getattr(im, "n_frames", 1) > 1, "7TV из стикера должен быть анимированным"
check("TGS3 .tgs -> пресеты Telegram, Discord, Twitch, 7TV", t_tgs_presets)

def t_tgs_damaged():
    bad = os.path.join(WORK, "битый.tgs")
    with open(bad, "wb") as handle:
        handle.write(b"not a sticker at all")
    d = os.path.join(WORK, "tgs_bad")
    os.makedirs(d, exist_ok=True)
    job = ConversionJob(input_path=bad, output_dir=d, source_path=bad,
                        settings=JobSettings(output_format="gif"))
    fin = []
    w = ConversionWorker([job], max_workers=1)
    w.file_finished.connect(lambda i, ok, m: fin.append((ok, m)))
    w.run()
    assert fin and not fin[0][0], fin
    from errors import message_text
    assert "битый.tgs" in message_text(fin[0][1]), message_text(fin[0][1])
check("TGS4 битый .tgs — понятная ошибка, а не падение", t_tgs_damaged)

print()
failed=[r for r in results if r[1]!="OK"]
print("="*72)
print(f"{len(results)-len(failed)}/{len(results)} passed")
for n,s,d in results:
    if s!="OK": print(f"  FAIL {n}: {d}")
print("="*72)
sys.exit(1 if failed else 0)

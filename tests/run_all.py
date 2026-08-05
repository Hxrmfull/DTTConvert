"""Прогон всех наборов тестов одной командой.

    python tests/run_all.py

Для набора test_core нужен установленный FFmpeg — он проверяет реальную
конвертацию, а не заглушки.
"""

import os
import subprocess
import sys
import time

# Консоль Windows по умолчанию не в UTF-8, и русский текст с символами
# вроде стрелок ломает вывод — переключаем поток явно.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)

SUITES = [
    ("test_layout_normal.py", "Вёрстка: обычный размер окна"),
    ("test_layout_min.py", "Вёрстка: минимальный размер окна"),
    ("test_corners.py", "Углы панелей при прокрутке"),
    ("test_gui.py", "Интерфейс: очередь и настройки"),
    ("test_features.py", "Возможности: пресеты, журнал, меню"),
    ("test_core.py", "Ядро: конвертация и параллелизм"),
]


def run_suite(file_name):
    started = time.monotonic()
    # Без PYTHONIOENCODING дочерний процесс пишет в кодировке системы,
    # а мы читаем как UTF-8 — русский текст превращается в мусор.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, os.path.join(TESTS_DIR, file_name)],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return result, time.monotonic() - started


def main():
    print(f"Тесты запускаются из {PROJECT_DIR}\n")
    failed = []
    for file_name, title in SUITES:
        print(f"→ {title} ({file_name})")
        result, elapsed = run_suite(file_name)
        tail = [line for line in (result.stdout or "").splitlines() if line.strip()]
        summary = tail[-1] if tail else "(без вывода)"
        status = "ОК" if result.returncode == 0 else "ОШИБКА"
        print(f"   {status}   {summary}   [{elapsed:.1f} с]")
        if result.returncode != 0:
            failed.append((file_name, result))
        print()

    if failed:
        print("=" * 70)
        print(f"НЕ ПРОЙДЕНО НАБОРОВ: {len(failed)} из {len(SUITES)}\n")
        for file_name, result in failed:
            print(f"--- {file_name} ---")
            print((result.stdout or "")[-2500:])
            if result.stderr:
                print((result.stderr or "")[-1500:])
        return 1

    print("=" * 70)
    print(f"Все наборы пройдены ({len(SUITES)} из {len(SUITES)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

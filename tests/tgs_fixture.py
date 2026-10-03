"""Маленький стикер .tgs для тестов: оранжевый круг едет слева направо.

Настоящих стикеров в репозитории нет — их авторы свои, — поэтому Lottie
собирается здесь же: одна фигура, одна анимация положения.
"""

import gzip
import json


def make_tgs(path, frames=30, fps=30, size=512):
    """Записывает .tgs: frames кадров при fps кадрах в секунду."""
    last = frames - 1
    circle = {
        "ddd": 0, "ind": 1, "ty": 4, "nm": "circle", "sr": 1,
        "ks": {
            "o": {"a": 0, "k": 100},
            "r": {"a": 0, "k": 0},
            "p": {"a": 1, "k": [
                {"t": 0, "s": [size * 0.3, size / 2, 0], "e": [size * 0.7, size / 2, 0],
                 "i": {"x": [0.5], "y": [0.5]}, "o": {"x": [0.5], "y": [0.5]}},
                {"t": last, "s": [size * 0.7, size / 2, 0]},
            ]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 0, "k": [100, 100, 100]},
        },
        "ao": 0,
        "shapes": [{
            "ty": "gr", "nm": "group",
            "it": [
                {"ty": "el", "nm": "ellipse", "d": 1,
                 "p": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [size * 0.4, size * 0.4]}},
                {"ty": "fl", "nm": "fill", "r": 1,
                 "c": {"a": 0, "k": [1, 0.55, 0, 1]}, "o": {"a": 0, "k": 100}},
                {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]},
                 "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0},
                 "o": {"a": 0, "k": 100}},
            ],
        }],
        "ip": 0, "op": frames, "st": 0, "bm": 0,
    }
    lottie = {"tgs": 1, "v": "5.5.2", "fr": fps, "ip": 0, "op": frames,
              "w": size, "h": size, "nm": "test", "ddd": 0, "assets": [],
              "layers": [circle]}
    with gzip.open(path, "wb") as handle:
        handle.write(json.dumps(lottie).encode("utf-8"))
    return path

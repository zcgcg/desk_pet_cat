"""月薪喵 · 预处理脚本

把 cat.gif 的每一帧抠底、Mask Erosion、存成透明 PNG 序列，
main.py 启动时直接播放，不用每次实时抠图。
用法：python preprocess.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import QApplication

import main as cat


def main():
    app = QApplication([])
    cache = cat.FRAME_CACHE
    cache.mkdir(parents=True, exist_ok=True)

    reader = cat.QImageReader(str(cat.GIF))
    index = 0
    while True:
        img = reader.read()
        if img.isNull():
            break
        img = img.convertToFormat(cat.QImage.Format.Format_ARGB32)
        keyed = cat._key_background(img)
        keyed.save(str(cache / ("frame_%03d.png" % index)), "PNG")
        index += 1

    for p in cache.glob("frame_*.png"):
        if int(p.stem.split("_")[1]) >= index:
            p.unlink()

    print("preprocessed %d frames -> %s" % (index, cache))


if __name__ == "__main__":
    main()

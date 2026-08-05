"""月薪喵 · 预处理脚本

把项目里所有皮肤 GIF（cat/idle/work/alert/follow）逐帧做
Alpha Mask + 边缘侵蚀抠底，存成透明 PNG 序列并写入版本标记，
main.py 启动和切换皮肤时直接读缓存，不用实时抠图。
用法：python preprocess.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import QApplication

import main as cat


def process_gif(gif, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    reader = cat.QImageReader(str(gif))
    index = 0
    while True:
        img = reader.read()
        if img.isNull():
            break
        img = img.convertToFormat(cat.QImage.Format.Format_ARGB32)
        keyed = cat._key_background(img)
        keyed.save(str(cache_dir / ("frame_%03d.png" % index)), "PNG")
        index += 1

    for p in cache_dir.glob("frame_*.png"):
        if int(p.stem.split("_")[1]) >= index:
            p.unlink()

    (cache_dir / cat.CACHE_MARKER).write_text(
        "keyer v%d\n" % cat.CACHE_VERSION, encoding="utf-8"
    )
    return index


def main():
    app = QApplication([])
    gifs = {cat.GIF}
    for base in (cat.ASSET_DIR, cat.ASSET_DIR / "assets"):
        if base.is_dir():
            gifs.update(base.glob("*.gif"))

    for gif in sorted(gifs, key=lambda p: p.name):
        cache_dir = (
            cat.FRAME_CACHE if gif == cat.GIF else cat.FRAME_CACHE / gif.stem
        )
        count = process_gif(gif, cache_dir)
        print("preprocessed %d frames -> %s" % (count, cache_dir))


if __name__ == "__main__":
    main()

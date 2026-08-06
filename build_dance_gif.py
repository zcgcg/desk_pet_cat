"""从 .frames_cache/dance/ 的透明 PNG 帧生成 dance.gif（帧间隔可调）。

用法（desk_pet conda 环境）：
    D:\\conda\\envs\\desk_pet\\python.exe build_dance_gif.py [--delay 50]

生成的 GIF 与缓存帧数一致（34 帧），main.py 运行时仍优先读取缓存 PNG
以保留软边羽化质量；GIF 提供帧延迟信息和兜底素材源。
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
FRAME_DIR = ROOT / ".frames_cache" / "dance"
OUT = ROOT / "dance.gif"


def main():
    parser = argparse.ArgumentParser(description="由缓存帧生成 dance.gif")
    parser.add_argument(
        "--delay",
        type=int,
        default=50,
        help="每帧延迟（毫秒），默认 50",
    )
    args = parser.parse_args()

    frames = sorted(FRAME_DIR.glob("frame_*.png"))
    if not frames:
        sys.exit(f"找不到缓存帧：{FRAME_DIR}")

    images = [Image.open(p).convert("RGBA") for p in frames]
    images[0].save(
        OUT,
        save_all=True,
        append_images=images[1:],
        duration=args.delay,
        loop=0,
        disposal=2,
    )
    print(f"生成 {len(images)} 帧 -> {OUT}（{args.delay}ms/帧）")


if __name__ == "__main__":
    main()

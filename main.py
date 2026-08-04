"""月薪喵 · 桌面宠物

透明、无边框、永远置顶的小猫。
GIF 自带白底灰边 + 抗锯齿毛边？启动时按“R+G+B>700 全透明”
的强制阈值 + 泛洪抠底，透明边界再做 2px Mask Erosion 内收，
宁可砍一圈毛也不留一根白边。
"""

import sys
from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction, QImage, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QMessageBox,
    QWidget,
)

GIF = Path(__file__).resolve().parent / "cat.gif"
FRAME_CACHE = Path(__file__).resolve().parent / ".frames_cache"

# 背景判定：R+G+B > WHITE_SUM 一律算“接近白色”，强制全透明；
# 另外 GIF 自带的灰边色族（描边 + 底部阴影条）也算背景。
BG_COLORS = ((205, 206, 204), (90, 90, 89))
BG_TOL = 18            # 与灰边色族的距离阈值，以内视为背景
WHITE_SUM = 700        # R+G+B 超过它：无论在哪，Alpha 强制置 0
EDGE_CUT = 560         # 贴边浅色像素超过它：1px mask 缩减直接裁掉
DEFAULT_DELAY = 100    # 解析不到 GIF 帧延迟时的兜底（毫秒）
TOL2 = BG_TOL ** 2


def _is_bg(r, g, b):
    """背景家族：近白（>700）或 GIF 自带灰边。"""
    if r + g + b > WHITE_SUM:
        return True
    return any(
        (br - r) ** 2 + (bg - g) ** 2 + (bb - b) ** 2 <= TOL2
        for br, bg, bb in BG_COLORS
    )


def _key_background(img):
    """抠掉白底灰边：强制阈值 + 泛洪 + 填洞 + 1px mask 缩减 + 羽化。"""
    w, h = img.width(), img.height()
    raw = bytearray(img.constBits().asstring(w * h * 4))  # BGRA
    bg = bytearray(w * h)
    queue = deque()

    def visit(x, y):
        i = y * w + x
        if not bg[i] and _is_bg(raw[i * 4 + 2], raw[i * 4 + 1], raw[i * 4]):
            bg[i] = 1
            queue.append((x, y))

    # 种子：四边背景
    for x in range(w):
        visit(x, 0)
        visit(x, h - 1)
    for y in range(h):
        visit(0, y)
        visit(w - 1, y)

    # 泛洪：吃掉与边框连通的白色 + 灰边
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                visit(nx, ny)

    # 1) 强制规则：R+G+B > 700 的像素，Alpha 一律置 0（含猫身上的近白）
    for i in range(w * h):
        if raw[i * 4 + 2] + raw[i * 4 + 1] + raw[i * 4] > WHITE_SUM:
            raw[i * 4 + 3] = 0

    # 2) 泛洪标记出的背景（含灰边）也置 0
    for i in range(w * h):
        if bg[i]:
            raw[i * 4 + 3] = 0

    # 3) 填洞：被猫咪完全包围的透明区（脸/胸等近白毛色）恢复不透明
    reached = bytearray(w * h)
    q2 = deque()

    def seed(x, y):
        i = y * w + x
        if not reached[i] and raw[i * 4 + 3] == 0:
            reached[i] = 1
            q2.append((x, y))

    for x in range(w):
        seed(x, 0)
        seed(x, h - 1)
    for y in range(h):
        seed(0, y)
        seed(w - 1, y)
    while q2:
        x, y = q2.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not reached[ny * w + nx] \
                    and raw[(ny * w + nx) * 4 + 3] == 0:
                reached[ny * w + nx] = 1
                q2.append((nx, ny))
    for i in range(w * h):
        if raw[i * 4 + 3] == 0 and not reached[i]:
            raw[i * 4 + 3] = 255

    # 4) 浅色毛边裁除：贴着透明区的浅色像素直接归零（去“白毛汗”）
    for _ in range(6):
        cut = 0
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if raw[i * 4 + 3] == 0:
                    continue
                near_t = (
                    (x and raw[(i - 1) * 4 + 3] == 0)
                    or (x + 1 < w and raw[(i + 1) * 4 + 3] == 0)
                    or (y and raw[(i - w) * 4 + 3] == 0)
                    or (y + 1 < h and raw[(i + w) * 4 + 3] == 0)
                )
                if near_t and raw[i * 4 + 2] + raw[i * 4 + 1] + raw[i * 4] > EDGE_CUT:
                    raw[i * 4 + 3] = 0
                    cut += 1
        if cut == 0:
            break

    # 5) Mask Erosion：透明边界向内收缩 2px（宁可砍毛，不留白边）
    dist = [-1] * (w * h)
    q3 = deque()
    for i in range(w * h):
        if raw[i * 4 + 3] == 0:
            dist[i] = 0
            q3.append((i % w, i // w))
    while q3:
        x, y = q3.popleft()
        d = dist[y * w + x]
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if dist[j] == -1:
                    dist[j] = d + 1
                    q3.append((nx, ny))
    for i in range(w * h):
        d = dist[i]
        if d <= 2:
            raw[i * 4 + 3] = 0
        elif d == 3:
            raw[i * 4 + 3] = 130   # 软边缘第一圈
        elif d == 4:
            raw[i * 4 + 3] = 210   # 软边缘第二圈

    # 6) 收尾：软边圈上若还有浅色像素，一律裁掉
    for _ in range(4):
        cut = 0
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if raw[i * 4 + 3] == 0:
                    continue
                near_t = (
                    (x and raw[(i - 1) * 4 + 3] == 0)
                    or (x + 1 < w and raw[(i + 1) * 4 + 3] == 0)
                    or (y and raw[(i - w) * 4 + 3] == 0)
                    or (y + 1 < h and raw[(i + w) * 4 + 3] == 0)
                )
                if near_t and raw[i * 4 + 2] + raw[i * 4 + 1] + raw[i * 4] > EDGE_CUT:
                    raw[i * 4 + 3] = 0
                    cut += 1
        if cut == 0:
            break

    return QImage(bytes(raw), w, h, w * 4, QImage.Format.Format_ARGB32)


def _gif_delays():
    """从 GIF 图形控制扩展里读出每帧延迟（毫秒）。"""
    data = GIF.read_bytes()
    delays = []
    i = 13  # 6 字节文件头 + 7 字节逻辑屏幕描述符
    if data[10] & 0x80:  # 有全局调色板，跳过
        i += 3 << ((data[10] & 0x07) + 1)
    while i < len(data):
        marker = data[i]
        if marker == 0x21 and data[i + 1] == 0xF9:  # 图形控制扩展
            delay = int.from_bytes(data[i + 4:i + 6], "little") * 10
            delays.append(delay or DEFAULT_DELAY)
            i += 8
        elif marker == 0x21:  # 注释 / 循环次数等扩展
            i += 2
            while data[i]:
                i += data[i] + 1
            i += 1
        elif marker == 0x2C:  # 图像描述符
            j = i + 10
            if data[i + 9] & 0x80:  # 局部调色板
                j += 3 << ((data[i + 9] & 0x07) + 1)
            j += 1  # 跳过 LZW 最小码长字节
            while data[j]:
                j += data[j] + 1
            i = j + 1
        elif marker == 0x3B:  # 文件结束
            break
        else:
            i += 1
    return delays


def load_frames():
    """优先播放预处理好的透明 PNG 序列；没有缓存才实时抠图。"""
    delays = _gif_delays()
    reader = QImageReader(str(GIF))
    gif_count = 0
    while True:
        img = reader.read()
        if img.isNull():
            break
        gif_count += 1

    pngs = sorted(FRAME_CACHE.glob("frame_*.png")) if FRAME_CACHE.is_dir() else []
    if pngs and len(pngs) == gif_count:
        frames = [QPixmap(str(p)) for p in pngs]
    else:
        reader = QImageReader(str(GIF))
        frames = []
        while True:
            img = reader.read()
            if img.isNull():
                break
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            frames.append(QPixmap.fromImage(_key_background(img)))
    if len(delays) < len(frames):
        delays += [DEFAULT_DELAY] * (len(frames) - len(delays))
    return frames, delays[:len(frames)]


class Cat(QWidget):
    """一只猫：无边框、透明背景、可以拎着到处走。"""

    def __init__(self):
        super().__init__()
        self._drag_offset = QPoint()
        self._frame = 0
        self._frames, self._delays = load_frames()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self._build_ui()

    def _build_ui(self):
        # 透明 + 无边框 + 置顶，一气呵成
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._label = QLabel(self)
        if self._frames:
            size = self._frames[0].size()
            self._label.setGeometry(0, 0, size.width(), size.height())
            self.resize(size)
            self._next_frame()
            self._timer.start(self._delays[0])
        else:
            # GIF 缺失时的粉色方块替身
            self._label.setStyleSheet(
                "background:#ffb6c1;border-radius:24px;"
            )
            self._label.setFixedSize(140, 140)
            self.resize(140, 140)

    def _next_frame(self):
        self._label.setPixmap(self._frames[self._frame])
        self._timer.start(self._delays[self._frame])
        self._frame = (self._frame + 1) % len(self._frames)

    # ---- 左键：拎起小猫 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    # ---- 右键：猫咪菜单 ----
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        menu.exec(event.globalPos())


def main():
    app = QApplication(sys.argv)

    if not GIF.exists():
        QMessageBox.warning(
            None,
            "月薪喵",
            f"找不到 cat.gif（{GIF}）\n先用粉色小方块顶班啦～",
        )

    cat = Cat()
    cat.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

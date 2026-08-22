"""月薪喵 · 桌面宠物

透明、无边框、永远置顶的小猫。
行为由状态机驱动：PetState(IDLE / WORKING / DANCE / ALERT / FOLLOWING)
决定当前播放哪套素材与逻辑（阶段三：本地台词气泡 + 终极 Alpha Mask 抠图）。
每秒心跳感知：CPU>80% → ALERT；Codex 桌面 App 前台 → DANCE；
VS Code 前台且有近期输入 → WORKING；否则 IDLE；
FOLLOWING 由拖拽事件触发（左键拎起，松开自动复位）。
抠图不再靠颜色家族过滤：亮度 >235 的像素直接进 Alpha Mask 变透明，
再做 1px 边缘侵蚀 + 全像素平滑羽化，让猫像“长”在任意背景上。
"""

import math
import random
import sys
import time
from collections import deque
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QImage,
    QImageReader,
    QPainter,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsColorizeEffect,
    QLabel,
    QMenu,
    QMessageBox,
    QWidget,
)

try:
    import psutil
except ImportError:  # 感官缺失时降级：CPU 感知不可用，其余照常
    psutil = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    from pynput import keyboard, mouse
except ImportError:
    keyboard = None
    mouse = None

ASSET_DIR = Path(__file__).resolve().parent
GIF = ASSET_DIR / "cat.gif"
FRAME_CACHE = ASSET_DIR / ".frames_cache"

# 终极抠图（阶段三）：亮度 Alpha Mask 管线
LUMA_BG = 235          # 亮度超过它 → 完全透明
ERODE_PX = 1           # 1px 边缘侵蚀：裁掉半透明残余白边环
SOFT_EDGE = (110, 190) # 平滑羽化两圈 alpha（全像素平滑）
RING_LUMA_CUT = 200    # 软边圈上亮度超过它 → 直接裁掉（去白毛汗）
DEFAULT_DELAY = 100    # 解析不到 GIF 帧延迟时的兜底（毫秒）

# 帧缓存版本：抠图算法升级后，旧缓存一律作废
CACHE_VERSION = 2
CACHE_MARKER = f"keyer_v{CACHE_VERSION}.txt"

# 感官阈值（阶段二）
CPU_ALERT = 80.0        # CPU 使用率超过它 → ALERT
WORK_IDLE_SEC = 30      # WORKING 下无输入超过它 → 降级 IDLE
SENSE_INTERVAL = 1000   # 心跳感知周期（毫秒）
JITTER_PX = 5           # ALERT 窗口震动幅度（像素）

# 台词气泡（阶段三）
BUBBLE_MARGIN = 10      # 气泡底边到猫头顶的间距（像素，贴近猫咪）
BUBBLE_DURATION = 5000  # 气泡持续显示时长（毫秒）
DIALOGUE_INTERVAL = (30, 60)  # 随机弹气泡的间隔范围（秒）

# 尺寸对齐（阶段三终放）
TARGET_SIZE = 188       # 标准画布：装得下所有 90px 高的猫咪肉身
BODY_HEIGHT = 135        # 猫咪肉身统一高度（宽度按比例自适应）


class PetState(Enum):
    """宠物行为状态机：每个状态对应一套素材与播放逻辑。"""

    IDLE = "IDLE"
    WORKING = "WORKING"
    DANCE = "DANCE"
    ALERT = "ALERT"
    FOLLOWING = "FOLLOWING"


# 本地语料库（Zero-Token 对话：不联网、不花钱）
DIALOGUE_LIB = {
    PetState.IDLE: [
        "发呆中...",
        "想吃电子鱼干了喵",
        "世界真安静喵",
        "工资什么时候涨喵…",
        "数星星中：1、2、3…",
        "今天也是摸鱼的一天喵",
        "尾巴痒痒，挠不到喵",
    ],
    PetState.WORKING: [
        "主公加油，月薪翻倍！",
        "这种代码 Vibe 极了",
        "我在帮你盯着 Bug 喵",
        "Ctrl+S 保平安喵",
        "这段逻辑好烧脑喵…",
        "冲鸭！把需求全干掉！",
        "我是懂打工的猫喵",
    ],
    PetState.DANCE: [
        "主公召唤 Codex，猫咪摸鱼！",
        "代码写累了？开始摸鱼喵~",
        "Vibe 到位，舞力全开喵！",
        "AI 跳舞时间到，前排围观喵！",
        "左三圈右三圈，脖子扭扭喵~",
    ],
    PetState.ALERT: [
        "主公快看！CPU 要炸了喵！",
        "热死猫了，救命喵！",
        "风扇在哭，猫在抖喵！",
        "这温度猫都要熟了喵…",
        "警报！警报！主机冒烟了喵！",
    ],
    PetState.FOLLOWING: [
        "哎呀！被抓住了喵！",
        "放开我，我要去搬砖喵！",
        "主公，我们要去哪儿喵？",
        "起飞咯喵~",
    ],
}


def _key_background(img):
    """终极抠图：Alpha Mask + 1px 边缘侵蚀 + 全像素平滑羽化。

    自动识别素材类型：
    - 自带透明通道（如 work/follow）：源 Alpha 直接当掩码；
    - 白底不透明图（如 cat/idle/alert）：亮度 > LUMA_BG 全透明 + 填洞保白毛。
    统一走距离场：边缘浅色/半透明残边裁掉（深色线条保留），
    再用两圈软 Alpha 平滑，任何皮肤都能干净“长”在背景上。
    """
    w, h = img.width(), img.height()
    raw = bytearray(img.constBits().asstring(w * h * 4))  # BGRA
    luma = [0] * (w * h)
    mask = bytearray(w * h)
    has_alpha = False

    for i in range(w * h):
        b, g, r = raw[i * 4], raw[i * 4 + 1], raw[i * 4 + 2]
        luma[i] = (299 * r + 587 * g + 114 * b) // 1000
        if raw[i * 4 + 3] < 255:
            has_alpha = True

    if has_alpha:
        # 素材自带透明通道：源 Alpha 即掩码（软边原样保留）
        for i in range(w * h):
            mask[i] = raw[i * 4 + 3]
    else:
        # 白底图：亮度规则 + 填洞（被猫包住的白毛恢复不透明）
        for i in range(w * h):
            mask[i] = 0 if luma[i] > LUMA_BG else 255

        reached = bytearray(w * h)
        q = deque()

        def seed(x, y):
            i = y * w + x
            if not reached[i] and mask[i] == 0:
                reached[i] = 1
                q.append((x, y))

        for x in range(w):
            seed(x, 0)
            seed(x, h - 1)
        for y in range(h):
            seed(0, y)
            seed(w - 1, y)
        while q:
            x, y = q.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h and not reached[ny * w + nx] \
                        and mask[ny * w + nx] == 0:
                    reached[ny * w + nx] = 1
                    q.append((nx, ny))
        for i in range(w * h):
            if mask[i] == 0 and not reached[i]:
                mask[i] = 255

    # 距离场：0=透明；-1=实心内部
    dist = [-1] * (w * h)
    q2 = deque()
    for i in range(w * h):
        if mask[i] == 0:
            dist[i] = 0
            q2.append((i % w, i // w))
    while q2:
        x, y = q2.popleft()
        d = dist[y * w + x]
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if dist[j] == -1:
                    dist[j] = d + 1
                    q2.append((nx, ny))

    for i in range(w * h):
        d = dist[i]
        if d == -1:
            mask[i] = 255               # 实心内部：不透明
        elif d <= ERODE_PX:
            # 1px 边缘侵蚀：浅色或半透明残边裁掉，深色线条保留
            if mask[i] < 255 or luma[i] > RING_LUMA_CUT:
                mask[i] = 0
        elif d == 2:
            if mask[i] == 255:
                mask[i] = SOFT_EDGE[0]  # 平滑第一圈
        elif d == 3:
            if mask[i] == 255:
                mask[i] = SOFT_EDGE[1]  # 平滑第二圈
        # 兜底：任何软边/半透明圈上的偏亮像素一律裁掉，杜绝白毛汗
        if mask[i] < 255 and luma[i] > RING_LUMA_CUT:
            mask[i] = 0

    for i in range(w * h):
        raw[i * 4 + 3] = mask[i]

    return QImage(bytes(raw), w, h, w * 4, QImage.Format.Format_ARGB32)


def _gif_delays(gif: Path = GIF):
    """从 GIF 图形控制扩展里读出每帧延迟（毫秒）。"""
    data = gif.read_bytes()
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


def _fit_frame(img):
    """自动裁切猫咪肉身 → 统一高度 180px → 底部对齐放进 200x200 画布。

    先扫描非透明像素的最小矩形（Auto-Crop，忽略空白/透明区），
    再对猫身做等比例缩放（KeepAspectRatio + SmoothTransformation），
    所有猫个头整齐、脚踩同一条地平线。
    """
    w, h = img.width(), img.height()
    raw = img.constBits().asstring(w * h * 4)
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = y * w
        for x in range(w):
            if raw[(row + x) * 4 + 3] > 0:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y

    canvas = QImage(TARGET_SIZE, TARGET_SIZE, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    if max_x < 0:
        return QPixmap.fromImage(canvas)  # 全透明帧：空白画布

    crop = img.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
    scale = min(TARGET_SIZE / crop.width(), BODY_HEIGHT / crop.height())
    scaled = crop.scaled(
        max(1, round(crop.width() * scale)),
        max(1, round(crop.height() * scale)),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter = QPainter(canvas)
    painter.drawImage(
        (TARGET_SIZE - scaled.width()) // 2,   # 水平居中
        TARGET_SIZE - scaled.height(),         # 底部对齐：脚踩底线
        scaled,
    )
    painter.end()
    return QPixmap.fromImage(canvas)


def load_frames(gif: Path = GIF, cache_dir: Path = FRAME_CACHE):
    """优先播放预处理好的透明 PNG 序列；没有缓存才实时抠图。"""
    delays = _gif_delays(gif)
    reader = QImageReader(str(gif))
    gif_count = 0
    while True:
        img = reader.read()
        if img.isNull():
            break
        gif_count += 1

    pngs = sorted(cache_dir.glob("frame_*.png")) if cache_dir.is_dir() else []
    marker_ok = cache_dir.is_dir() and (cache_dir / CACHE_MARKER).exists()
    if marker_ok and pngs and len(pngs) == gif_count:
        frames = [_fit_frame(QImage(str(p))) for p in pngs]
    else:
        reader = QImageReader(str(gif))
        frames = []
        while True:
            img = reader.read()
            if img.isNull():
                break
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            frames.append(_fit_frame(_key_background(img)))
    if len(delays) < len(frames):
        delays += [DEFAULT_DELAY] * (len(frames) - len(delays))
    return frames, delays[:len(frames)]


class Cat(QWidget):
    """一只猫：无边框、透明背景、可以拎着到处走。"""

    def __init__(self):
        super().__init__()
        self._drag_offset = QPoint()
        self._frame = 0

        # ---- 状态机 ----
        self.current_state = PetState.IDLE
        # 状态 → 素材文件映射；优先 assets/ 目录，缺失则回退 cat.gif。
        self.assets = {
            PetState.IDLE: "idle.gif",
            PetState.WORKING: "work.gif",
            PetState.DANCE: "dance.gif",
            PetState.ALERT: "alert.gif",
            PetState.FOLLOWING: "follow.gif",
        }
        self._active_gif = None
        self._body_top = 0        # 猫身在画布内的顶部偏移（气泡定位用）
        # 皮肤帧缓存：每套 GIF 只解码一次，切状态不再重复解码
        self._skin_cache = {}

        self._frames, self._delays = [], []

        # ---- 感官 + 视觉补偿 ----
        self._last_input_ts = time.monotonic()
        self._has_input = False
        self._jitter_base = None
        self._breath_phase = 0.0
        self._dragging = False
        self._mirrored = False

        self._alert_timer = QTimer(self)
        self._alert_timer.timeout.connect(self._on_alert_tick)
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._on_breath_tick)
        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._on_follow_tick)

        # ---- 台词气泡（Zero-Token 对话）----
        self._dialogue_timer = QTimer(self)
        self._dialogue_timer.timeout.connect(self._on_dialogue_tick)
        self._bubble_hide_timer = QTimer(self)
        self._bubble_hide_timer.timeout.connect(self._hide_bubble)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self._build_ui()
        self.update_behavior()
        self._schedule_dialogue()

        # ---- 心跳信号：每秒感知一次 ----
        self._sense_timer = QTimer(self)
        self._sense_timer.timeout.connect(self._sense)
        self._sense_timer.start(SENSE_INTERVAL)
        self._start_input_listener()

    def _build_ui(self):
        # 透明 + 无边框 + 置顶，一气呵成
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._label = QLabel(self)

        # 台词气泡（半透明黑底白字，不拦截鼠标）
        self._bubble = QLabel(self)
        self._bubble.setText("喵")
        self._bubble.setStyleSheet(
            "background:rgba(0,0,0,180);color:#ffffff;"
            "border:1px solid rgba(255,255,255,80);"
            "border-radius:8px;padding:2px 6px;font-size:10px;"
        )
        self._bubble.adjustSize()
        self._bubble.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self._bubble.hide()

        self._switch_asset(self.current_state)

    def _asset_for_state(self, state):
        """状态 → 素材路径：优先 assets/，其次项目根目录，最后回退 cat.gif。"""
        name = self.assets[state]
        for base in (ASSET_DIR / "assets", ASSET_DIR):
            path = base / name
            if path.exists():
                return path
        return GIF

    def _switch_asset(self, state):
        """切到该状态的皮肤；同皮肤不重载，解码结果进缓存。"""
        gif = self._asset_for_state(state)
        if gif == self._active_gif and self._frames:
            return  # 同一皮肤，无需重载

        frames, delays, body_top = self._load_skin(gif)
        self._body_top = body_top
        self._active_gif = gif
        self._frames, self._delays = frames, delays
        self._frame = 0
        top = self._bubble.height() + BUBBLE_MARGIN
        if frames:
            self._label.setGeometry(0, top, TARGET_SIZE, TARGET_SIZE)
            self._label.setStyleSheet("")
            self._next_frame()
        else:
            # 全部素材都读不出来时的粉色方块替身（绝不崩溃）
            self._label.setStyleSheet(
                "background:#ffb6c1;border-radius:24px;"
            )
            self._label.setFixedSize(TARGET_SIZE, TARGET_SIZE)
            self._label.move(0, top)
        self.setFixedSize(TARGET_SIZE, top + TARGET_SIZE)

    def _load_skin(self, gif):
        """解码并缓存一套皮肤；读取/解码失败自动降级 cat.gif，严禁报错。"""
        if gif in self._skin_cache:
            return self._skin_cache[gif]

        frames, delays = [], []
        try:
            cache_dir = FRAME_CACHE if gif == GIF else FRAME_CACHE / gif.stem
            frames, delays = load_frames(gif, cache_dir)
        except Exception:
            frames, delays = [], []

        if not frames and gif != GIF:
            # 降级：用 cat.gif 顶班（同样走缓存）
            frames, delays = self._load_skin(GIF)[:2]

        body_top = self._body_top_of(frames)
        self._skin_cache[gif] = (frames, delays, body_top)
        return frames, delays, body_top

    @staticmethod
    def _body_top_of(frames):
        """猫身顶部在画布内的偏移（第一帧 Alpha 包围盒上沿）。"""
        if not frames:
            return 0
        raw = frames[0].toImage().constBits().asstring(
            TARGET_SIZE * TARGET_SIZE * 4
        )
        for y in range(TARGET_SIZE):
            base = y * TARGET_SIZE
            if any(raw[(base + x) * 4 + 3] > 0 for x in range(TARGET_SIZE)):
                return y
        return 0

    # ---- 视觉补偿（虚拟素材）----
    def _clear_effects(self):
        """关掉全部状态特效，回到原样。"""
        for t in (self._alert_timer, self._breath_timer, self._follow_timer):
            t.stop()
        self.setWindowOpacity(1.0)
        self._label.setGraphicsEffect(None)
        if self._mirrored:
            self._mirrored = False
            self._repaint_current_frame()
        self._bubble.hide()
        if self._jitter_base is not None:
            self.move(self._jitter_base)
            self._jitter_base = None

    def _on_alert_tick(self):
        """ALERT：±5px 随机震动。"""
        if self._jitter_base is None:
            return
        dx = random.randint(-JITTER_PX, JITTER_PX)
        dy = random.randint(-JITTER_PX, JITTER_PX)
        self.move(self._jitter_base + QPoint(dx, dy))

    def _on_breath_tick(self):
        """WORKING：80%–100% 缓慢呼吸。"""
        self._breath_phase += 0.08
        self.setWindowOpacity(0.8 + 0.2 * abs(math.sin(self._breath_phase)))

    def _on_follow_tick(self):
        """FOLLOWING：水平镜像，让猫始终面向鼠标。"""
        pos = self._mouse_pos()
        if pos is None:
            return
        self._flip_horizontal(pos[0] < self.frameGeometry().center().x())

    def _flip_horizontal(self, flip):
        """沿垂直中线镜像（Qt6 无 QWidget.setTransform，改用 QPixmap 变换）。"""
        if flip == self._mirrored:
            return
        self._mirrored = flip
        self._repaint_current_frame()

    def _repaint_current_frame(self):
        """按当前镜像状态重画正在显示的帧。"""
        if not self._frames:
            return
        idx = (self._frame - 1) % len(self._frames)
        pm = self._frames[idx]
        if self._mirrored:
            pm = pm.transformed(
                QTransform().translate(pm.width(), 0).scale(-1, 1)
            )
        self._label.setPixmap(pm)

    # ---- 状态机调度 ----
    def update_behavior(self):
        """状态机入口：按 current_state 决定播放哪段逻辑 + 视觉特效。"""
        self._clear_effects()
        if self.current_state == PetState.IDLE:
            self._play_idle()
        elif self.current_state == PetState.WORKING:
            self._play_working()
        elif self.current_state == PetState.DANCE:
            self._play_dance()
        elif self.current_state == PetState.ALERT:
            self._play_alert()
        elif self.current_state == PetState.FOLLOWING:
            self._play_following()

    def set_state(self, state):
        """切状态：更新 current_state 并立刻按新状态刷新行为。"""
        if state not in PetState:
            raise ValueError(f"未知状态：{state}")
        self.current_state = state
        self.update_behavior()

    # 阶段二：素材仍只有 cat.gif，先用代码特效区分各状态；后续换素材即可。
    def _play_idle(self):
        """IDLE：发呆摸鱼，原样播放。"""
        self._switch_asset(PetState.IDLE)
        self._say_current()

    def _play_working(self):
        """WORKING：搬砖打工 + 呼吸透明度。"""
        self._switch_asset(PetState.WORKING)
        self._breath_phase = 0.0
        self._breath_timer.start(100)
        self._say_current()

    def _play_dance(self):
        """DANCE：主公召唤 Codex 时献舞，原样播放。"""
        self._switch_asset(PetState.DANCE)
        self._say_current()

    def _play_alert(self):
        """ALERT：红色滤镜 + 5px 随机震动。"""
        self._switch_asset(PetState.ALERT)
        effect = QGraphicsColorizeEffect(self._label)
        effect.setColor(QColor(255, 0, 0))
        effect.setStrength(0.35)
        self._label.setGraphicsEffect(effect)
        self._jitter_base = self.pos()
        self._alert_timer.start(50)
        self._say_current()

    def _play_following(self):
        """FOLLOWING：实时水平镜像，盯住鼠标方向。"""
        self._switch_asset(PetState.FOLLOWING)
        self._follow_timer.start(100)
        self._on_follow_tick()
        self._say_current()

    # ---- 台词气泡（Zero-Token 对话）----
    def _say_current(self):
        """立刻按当前状态弹一句随机台词，5 秒后自动消失。"""
        lines = DIALOGUE_LIB.get(
            self.current_state, DIALOGUE_LIB[PetState.IDLE]
        )
        self._bubble.setText(random.choice(lines))
        self._layout_bubble()
        self._bubble.show()
        self._bubble_hide_timer.start(BUBBLE_DURATION)

    def _layout_bubble(self):
        """气泡贴着猫头顶（按肉身包围盒定位，不是 GIF 画布顶）。"""
        self._bubble.adjustSize()
        top = self._bubble.height() + BUBBLE_MARGIN
        self._label.move(0, top)
        self.setFixedSize(TARGET_SIZE, top + TARGET_SIZE)
        head = top + self._body_top
        self._bubble.move(
            max(0, (TARGET_SIZE - self._bubble.width()) // 2),
            max(0, head - self._bubble.height() - BUBBLE_MARGIN),
        )

    def _hide_bubble(self):
        self._bubble.hide()

    def _schedule_dialogue(self):
        """30–60 秒后随机弹一句当前状态的台词。"""
        self._dialogue_timer.start(random.randint(*DIALOGUE_INTERVAL) * 1000)

    def _on_dialogue_tick(self):
        self._say_current()
        self._schedule_dialogue()

    # ---- 感官（心跳信号）----
    def _sense(self):
        """每秒心跳：按优先级把感知结果映射到状态（拖拽中保持 FOLLOWING）。"""
        if self._dragging:
            return  # 拎着猫时环境感知不打断，松开后再复位

        cpu = self._cpu_percent()
        vscode = self._vscode_active()
        codex = self._codex_active()

        if cpu > CPU_ALERT:
            target = PetState.ALERT          # 优先级最高
        elif codex:
            target = PetState.DANCE          # 次高：Codex 前台献舞
        elif vscode and self._has_input \
                and time.monotonic() - self._last_input_ts <= WORK_IDLE_SEC:
            target = PetState.WORKING        # 高：前台工作且有近期输入
        else:
            target = PetState.IDLE           # 低：默认

        if target != self.current_state:
            self.set_state(target)

    def _cpu_percent(self):
        if psutil is None:
            return 0.0
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return 0.0

    def _vscode_active(self):
        """VS Code 是否在前台。"""
        if gw is None:
            return False
        try:
            win = gw.getActiveWindow()
            title = (win.title if win is not None else "") or ""
        except Exception:
            try:
                title = gw.getActiveWindowTitle() or ""
            except Exception:
                return False
        return "visual studio code" in title.lower()

    def _codex_active(self):
        """OpenAI 桌面 App（ChatGPT/Codex）是否在前台。

        该 App 的窗口标题固定为 "ChatGPT"（Codex 也在这个 App 里工作），
        所以以进程名判定：ChatGPT.exe / codex.exe 在前台即视为 Codex 工作，
        避免 VS Code 打开名为 codex.py 的文件时误触发；
        进程信息拿不到时退化为按标题含 "codex" 或 "chatgpt" 判断。
        """
        pname = self._foreground_process_name()
        if pname:
            return pname in ("chatgpt.exe", "chatgpt", "codex.exe", "codex")
        title = ""
        if gw is not None:
            try:
                win = gw.getActiveWindow()
                title = (win.title if win is not None else "") or ""
            except Exception:
                try:
                    title = gw.getActiveWindowTitle() or ""
                except Exception:
                    pass
        return bool(title) and (
            "codex" in title.lower() or "chatgpt" in title.lower()
        )

    def _foreground_process_name(self):
        """返回前台窗口的进程名（小写）；获取失败返回空串。"""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(
                hwnd, ctypes.byref(pid)
            )
            if pid.value and psutil is not None:
                return psutil.Process(pid.value).name().lower()
        except Exception:
            pass
        return ""

    def _mouse_pos(self):
        if mouse is None:
            return None
        try:
            return mouse.Controller().position
        except Exception:
            return None

    def _note_input(self):
        """pynput 全局钩子回调：记录最近一次输入时间。"""
        self._last_input_ts = time.monotonic()
        self._has_input = True

    def _start_input_listener(self):
        """安装全局鼠标/键盘监听（独立线程，不卡 UI）。"""
        try:
            kb = keyboard.Listener(on_press=lambda _k: self._note_input())
            kb.daemon = True
            kb.start()
            self._listener_kb = kb
        except Exception:
            self._listener_kb = None
        try:
            ms = mouse.Listener(
                on_move=lambda x, y: self._note_input(),
                on_click=lambda x, y, b, p: self._note_input(),
                on_scroll=lambda x, y, dx, dy: self._note_input(),
            )
            ms.daemon = True
            ms.start()
            self._listener_ms = ms
        except Exception:
            self._listener_ms = None

    def _next_frame(self):
        pm = self._frames[self._frame]
        if self._mirrored:
            pm = pm.transformed(
                QTransform().translate(pm.width(), 0).scale(-1, 1)
            )
        self._label.setPixmap(pm)
        self._timer.start(self._delays[self._frame])
        self._frame = (self._frame + 1) % len(self._frames)

    # ---- 左键：拎起小猫 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.set_state(PetState.FOLLOWING)  # 拎起即进入 FOLLOWING
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        if event.button() == Qt.MouseButton.LeftButton:
            self._sense()  # 松开立即复测环境：回 IDLE / WORKING / ALERT

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

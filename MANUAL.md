# 月薪喵 · 使用说明书

> 一只透明、无边框、永远置顶、会感知环境、会说台词、会换皮肤的桌面猫咪。

---

## 1. 这是什么

月薪喵（Salary Cat）是一个桌面宠物程序，基于 Python + PyQt6 开发。
它通过「心跳感知」实时观察你的电脑状态（CPU、前台窗口、鼠标位置、
全局输入活动），在五种状态间自动切换，并用不同皮肤 + 特效 + 台词
气泡来回应你。

---

## 2. 安装依赖

要求：Python 3.10+，Windows。

```bash
pip install PyQt6 psutil pygetwindow pynput
```

| 依赖 | 用途 |
| --- | --- |
| PyQt6 | 窗口、动画、抠图、特效 |
| psutil | 读取 CPU 使用率（ALERT 判定） |
| pygetwindow | 检测前台窗口（WORKING 判定） |
| pynput | 全局鼠标/键盘监听 + 鼠标位置读取 |

---

## 3. 启动与运行

在项目目录下执行：

```bash
# 正式运行（桌面常驻猫咪）
python main.py

# 可选：预先抠图生成帧缓存，让启动/切皮肤秒开
python preprocess.py

# 可选：由缓存帧生成 dance.gif（默认 50ms/帧，可加 --delay 调整）
python build_dance_gif.py

# 可选：全形态切换演示（五种皮肤轮流展示 3.5 秒后自动退出）
python demo_skins.py
```

找不到素材时会自动降级，程序不会崩溃。

---

## 4. 基本操作

| 操作 | 效果 |
| --- | --- |
| 左键按住猫咪 | 进入 FOLLOWING，猫喊“哎呀！被抓住了喵！”并转头看你 |
| 左键按住拖动 | 拎着猫满屏跑，松开自动复位环境状态 |
| 右键点击猫咪 | 弹出菜单，选择「退出」 |
| 什么都不做 | 猫会发呆，偶尔自言自语 |

---

## 5. 状态机

### 5.1 五种状态

| 状态 | 触发条件 | 优先级 | 视觉表现 | 台词示例 |
| --- | --- | --- | --- | --- |
| ALERT | CPU 使用率 > 80% | 最高 | 红色滤镜 + 窗口 ±5px 随机震动 | “主公快看！CPU 要炸了喵！” |
| FOLLOWING | 左键按住猫咪（拎起） | 用户主动触发 | 水平镜像，拎到哪跟到哪 | “哎呀！被抓住了喵！” |
| WORKING | VS Code 在前台 且 30 秒内有输入 | 中 | 半透明呼吸（80%–100%） | “主公加油，月薪翻倍！” |
| DANCE | OpenAI 桌面 App（ChatGPT/Codex）在前台 | 次高 | 原样播放 dance 动画 | “主公召唤 Codex，猫咪献舞！” |
| IDLE | 以上都不满足 | 低（默认） | 原样发呆 | “发呆中...” |

### 5.2 心跳感知逻辑

程序每秒执行一次 `_sense()`，按优先级从高到低判定目标状态：

```
CPU > 80%                    → ALERT
OpenAI 桌面 App（ChatGPT/Codex）前台 → DANCE
VS Code 前台 + 有近期输入    → WORKING（停手超过 30 秒自动降级 IDLE）
否则                          → IDLE
```

FOLLOWING 不再由距离感应触发，改为**拖拽事件**驱动：
左键按住猫咪 → 立即进入 FOLLOWING；松开 → 立即复测环境复位。
拖拽期间心跳感知被冻结，不会中途切走，杜绝闪烁。

切状态时立即弹出该状态的一句随机台词，5 秒后自动消失；
平时每 30–60 秒随机冒一句气泡。

### 5.3 FOLLOWING 状态详解（调用链）

FOLLOWING 由拖拽事件触发，完整调用链如下：

1. 左键按下 → `mousePressEvent()`：`_dragging = True`，
   立刻 `set_state(PetState.FOLLOWING)`
2. `set_state()` → `update_behavior()` → `_play_following()`
3. `_play_following()`：
   - `_switch_asset()` 加载 follow.gif（缺失则回退 cat.gif）
   - 启动 `_follow_timer`（每 100ms）
   - 立即执行一次 `_on_follow_tick()` 对齐方向
   - `_say_current()` 弹出 FOLLOWING 台词
4. 拖动中：`_on_follow_tick()` 每 100ms 按鼠标位置水平镜像
   （鼠标在猫左边 → 面向左；在右边 → 面向右），
   心跳 `_sense()` 检测到拖拽中直接跳过，状态不会被抢走
5. 松开左键 → `mouseReleaseEvent()`：`_dragging = False`，
   立即调用 `_sense()` 复测环境 → 回到 IDLE / WORKING / DANCE / ALERT

注意一点：

- FOLLOWING 只在拎着的时候存在，松手即复位；
  CPU 飙高（ALERT）或 VS Code 工作态（WORKING）会在松手后立刻接管。

---

## 6. 皮肤与素材

### 6.1 文件约定

| 状态 | 默认素材文件 |
| --- | --- |
| IDLE | `idle.gif` |
| WORKING | `work.gif` |
| DANCE | `dance.gif` |
| ALERT | `alert.gif` |
| FOLLOWING | `follow.gif` |
| 兜底 | `cat.gif` |

查找顺序：`assets/` 目录 → 项目根目录 → `cat.gif` 兜底。
把对应文件放进 `assets/` 即可换皮肤，无需改代码。

### 6.2 统一尺寸（自动裁切 + 肉身归一）

每帧先扫描非透明像素的最小矩形（Auto-Crop，忽略空白/透明区），
再把“猫身”等比例缩放到统一高度 `BODY_HEIGHT = 180`：
宽度按比例自适应（若过宽则按画布宽度 200 兜底）。

- `KeepAspectRatio`：等比例缩放，不变形
- `SmoothTransformation`：抗锯齿平滑，边缘无毛刺
- 水平居中、底部对齐：所有猫脚踩同一条地平线
- 画布 `125 × 125`，窗口宽固定 `125`、高 = 气泡高度 + 10 + 125
  （含气泡头顶空间），切换皮肤大小恒定

---

## 7. 抠图算法

「Alpha Mask + 边缘侵蚀」自动识别素材类型：

- 自带透明通道的 GIF（如 work/follow）：直接用源 Alpha 作掩码
- 白底不透明 GIF（如 cat/idle/alert）：亮度 > 235 全透明，
  被猫包住的白毛自动填洞保留

统一流程：亮度 Alpha Mask → 1px 边缘侵蚀（裁掉浅色/半透明残边，
保留深色线条）→ 两圈软 Alpha 平滑羽化，让猫“长”在任意背景上，
不留白边。

---

## 8. 性能说明

- **皮肤解码缓存**：每套 GIF 只解码一次，之后切状态直接读内存，
  反复切换零重复解码
- **帧缓存**：`python preprocess.py` 会把全部皮肤预抠成透明 PNG
  存入 `.frames_cache/`（带版本标记，算法升级自动作废重建），
  启动和切换都是秒开
- 内存占用约几十 MB，常驻无压力

---

## 9. 常见问题

**Q：猫不进入 WORKING？**
检查：是否 VS Code 在前台、30 秒内是否有输入（鼠标移动/键盘都算）；
依赖是否安装（缺 pygetwindow 时该感知自动失效）。

**Q：猫一直不进入 ALERT？**
ALERT 需要 CPU > 80%，只有跑高负载程序（编译、转码、压测等）才会触发。

**Q：换了新 GIF 没生效？**
确认文件名与上表一致（如 `idle.gif`），放在 `assets/` 或项目根目录；
改完重新运行 `python preprocess.py` 刷新缓存。

**Q：找不到素材会怎样？**
自动降级 `cat.gif`；连 cat.gif 都没有时显示粉色方块，程序不会崩溃。

**Q：中文路径/目录被移动了怎么办？**
项目对路径无硬编码，但 Windows 下中文路径在部分环境有编码问题，
建议放在纯英文路径（如 `D:\code\Salary_Cat`）下运行。

---

## 10. 项目结构

```
Salary_Cat/
├── main.py          # 主程序（状态机 + 感知 + 抠图 + 特效 + 台词）
├── preprocess.py    # 预抠图缓存生成器
├── build_dance_gif.py # 由缓存帧生成 dance.gif
├── demo_skins.py    # 全形态切换演示
├── cat.gif          # 兜底皮肤
├── idle.gif         # IDLE 皮肤
├── work.gif         # WORKING 皮肤
├── dance.gif        # DANCE 皮肤
├── alert.gif        # ALERT 皮肤
├── follow.gif       # FOLLOWING 皮肤
├── assets/          # 自定义皮肤目录（可选）
├── .frames_cache/   # 预抠图缓存（自动生成）
└── MANUAL.md        # 本说明书
```

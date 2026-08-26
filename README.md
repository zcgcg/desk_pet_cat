# 🐱 Salary-Cat-Vibe · 月薪喵

```
      /\_/\
     ( o.o )  ~ 月薪喵 · Salary Cat
      > ^ <
   —— 赛博禅意 · Cyber Zen ——
```

> 一只透明、无边框、永远置顶、会感知环境、会说台词、会换皮肤的桌面小猫。
> A transparent, frameless, always-on-top desktop kitten with senses, words, and skins.
>
> 传说桌面上有猫，月薪会翻倍——纯属玄学，但值得一试。喵。

## 🏷️ v1.1 — Sensory Evolution

感官进化版：从「一只会动的猫」进化为「一只懂你的猫」。

这不是代码，这是 **Vibe Coding 的实践**：DeepSeek 当大脑，Codex 当双手，而你是导演。

---

## ✨ 功能亮点 / Features

- 🧠 **环境感知系统** — 实时监控 CPU 负载、自动识别 VS Code 办公状态、
  OpenAI 桌面 App（ChatGPT/Codex）与 DeepSeek Harness 前台，并能通过
  LLM 网络连接 / 会话文件写入判断 DSH 的 agent 是否正在运行
  （psutil + pygetwindow + pynput 三件套）
- 🤖 **智能状态机** — 支持 `IDLE` / `WORKING` / `DANCE` / `ALERT` / `FOLLOWING`
  五种行为逻辑，按优先级自动切换
- 🖼️ **视觉归一化** — 独创「肉身识别」算法：自动裁切 GIF 空白边缘，
  统一猫咪大小，所有猫脚踩同一条地平线
- 💬 **零成本互动** — 本地化语料库气泡，不联网不花钱，随状态弹台词
- 🪟 **透明无边框** — Frameless translucent window, always on top
- 🎨 **Alpha Mask 抠图** — 亮度掩码 + 边缘侵蚀 + 全像素平滑，无白边
- ⚡ **秒开帧缓存** — 离线预抠透明 PNG 帧，启动与切皮肤秒开

---

## 🧠 环境感知 / Sensing

程序每秒执行一次心跳感知，按优先级判定状态：

| 状态 | 触发条件 | 视觉表现 |
| --- | --- | --- |
| ALERT | CPU > 80% | 红色滤镜 + 窗口随机震动 |
| FOLLOWING | 左键拎起猫咪 | 拖拽跟随 + 拎起台词 |
| DANCE | OpenAI 桌面 App（ChatGPT/Codex）前台 | 原样播放舞蹈动画 + 台词 |
| WORKING | DeepSeek Harness 前台 + agent 运行中（LLM 连接 / 会话文件持续写入） | AI 代劳搬砖，猫咪呼吸 |
| IDLE | DeepSeek Harness 前台 + 无 agent 运行（如输入框打字） | AI 待命，猫咪发呆摸鱼 |
| WORKING | VS Code 前台 + 30 秒内有输入 | 半透明呼吸 + Coding 气泡 |
| IDLE | 默认 | 发呆 + 随机台词 |

---

## 🖼️ 视觉归一化 / Auto-Crop

每帧扫描非透明像素的最小矩形（Auto-Crop，忽略空白/透明区），
再把猫身等比例缩放到统一高度 `180px`（宽度按比例自适应），
水平居中、底部对齐——五只猫个头整齐，像排队领工资。

---

## 📖 视觉进化之夜 / The Night of Visual Evolution

### 0x00 · 白边猫咪 / The White-Bordered Cat

早期只用一个朴素阈值 `R+G+B > 700 强制全透明`。猫是透明了，
但残留的浅色毛边像一圈廉价光晕。

### 0x01 · Alpha Mask 抠图 / Alpha Mask Keying

亮度 > 235 的像素直接进 Alpha Mask 变透明；被猫完全包围的白毛
靠「填洞」保留；1px 边缘侵蚀裁掉浅色/半透明残边；两圈软 Alpha
平滑羽化，让猫像「长」在任意背景上。

### 0x02 · 肉身归一 / Body Normalization

从「整张 GIF 缩放」进化为「只缩猫身」：自动裁切空白边缘 + 统一
180px 高度 + 底部对齐，杜绝「有的猫飘在空中，有的猫钻进地下」。

---

## 🧠 抠图算法 / Keying Algorithm

核心常量（`main.py`）：

| 常量 | 值 | 作用 |
| --- | --- | --- |
| `LUMA_BG` | 235 | 亮度超过它 → 完全透明 |
| `ERODE_PX` | 1 | 1px 边缘侵蚀，裁掉半透明残边 |
| `SOFT_EDGE` | (110, 190) | 两圈软 Alpha 平滑羽化 |
| `RING_LUMA_CUT` | 200 | 软边圈偏亮像素直接裁掉 |
| `TARGET_SIZE` | 125 | 标准画布尺寸 |
| `BODY_HEIGHT` | 90 | 猫咪肉身统一高度 |

完整管线：亮度 Alpha Mask → 填洞保白毛 → 1px 边缘侵蚀 →
全像素平滑羽化。自动识别自带透明通道的 GIF（直接用源 Alpha）。

---

## 🚀 安装运行 / Setup

要求：Python 3.10+、Windows。

```bash
pip install PyQt6 psutil pynput pygetwindow
```

启动：

```bash
python main.py
```

可选：预生成全部皮肤的帧缓存（秒开启动）：

```bash
python preprocess.py
```

可选：由缓存帧生成 `dance.gif`（默认 50ms/帧，可加 `--delay` 调整）：

```bash
python build_dance_gif.py
```

全形态切换演示（五套皮肤轮播后自动退出）：

```bash
python demo_skins.py
```

开机自启动（Windows，写入当前用户注册表，无需管理员权限）：

```bash
python autostart.py enable     # 启用：开机用 pythonw 静默启动，不弹黑框
python autostart.py disable    # 禁用
python autostart.py status     # 查询状态
```

也可以右键猫咪 → 勾选「开机自启动」直接切换。
程序自带单实例保护：开机自启后手动再启动不会出现两只猫。

---

## 🎮 玩法 / Usage

- 左键按住猫咪：拎起来 → FOLLOWING，猫喊「哎呀！被抓住了喵！」
- 左键按住拖动：拎着猫满屏跑，松手自动复位环境状态
- 右键点击猫咪：弹出菜单，选择「退出」
- 台词气泡：切状态立即弹一句，每 30–60 秒再随机冒一句
- 换皮肤：把 `idle.gif` / `work.gif` / `dance.gif` / `alert.gif` / `follow.gif`
  放进 `assets/` 即可，缺失自动回退 `cat.gif`

---

## 📁 项目结构 / Project Structure

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
├── .frames_cache/   # 预抠图缓存（自动生成，已 gitignore）
└── MANUAL.md        # 使用说明书
```

---

## 💝 Credits / 致谢

AI 时代原生的协作结晶，三个人格的联合创作：

- 🧠 **DeepSeek R1** — 大脑：算法设计与状态机方案
- ✋ **OpenAI Codex** — 双手：编码与工程落地
- 🎬 **kaelan0528** — 导演：定义 Vibe 与产品方向

**Vibe Coding 1.1** —— 月薪喵，感官进化的桌面守护者。🐱

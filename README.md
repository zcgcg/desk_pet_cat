# 🐱 Salary-Cat-Vibe · 月薪喵

```
      /\_/\
     ( o.o )  ~ 月薪喵 · Salary Cat
      > ^ <
   —— 赛博禅意 · Cyber Zen ——
```

> 一只透明、无边框、永远置顶的桌面小猫。
> A transparent, frameless, always-on-top desktop kitten.
>
> 传说桌面上有猫，月薪会翻倍——纯属玄学，但值得一试。喵。
> Legend says a cat on your desktop doubles your salary — pure superstition, but worth a try. Meow.

这不是代码，这是 **Vibe Coding 的实践**：DeepSeek 当大脑，Codex 当双手，而你是导演。
This is **Vibe Coding in practice**: DeepSeek as the brain, Codex as the hands, and you as the director.

---

## ✨ 功能亮点 / Features

- 🪟 **透明无边框** — Frameless translucent window
- 🖱️ **鼠标拽动** — Drag the cat anywhere with the left mouse button
- 📌 **始终置顶** — Always on top
- 🎨 **完美抠图算法** — R+G+B threshold + flood fill + mask erosion, zero white fringes
- ⚡ **秒开帧缓存** — Offline pre-processed transparent PNG frames for instant startup

## 📖 视觉进化之夜 / The Night of Visual Evolution

这是一只猫咪一夜之间从「白边廉价感」进化到「完美透明」的故事。
This is the story of a kitten evolving overnight, from cheap white fringes to perfect transparency.

### 0x00 · 白边猫咪 / The White-Bordered Cat

`cat.gif` 自带白底、灰边描边和抗锯齿毛边。最初只用一个朴素阈值：
`R+G+B > 700 强制全透明`。猫是透明了，但残留的浅色毛边像一圈光晕——廉价的抠图感扑面而来。

The GIF ships with a white background, gray outline, and anti-aliased fur edges.
The first naive attempt used a single hard threshold: `R+G+B > 700 → fully transparent`.
The cat became see-through, but the leftover light fringes looked like a cheap halo.

### 0x01 · 泛洪抠底 / Flood-Fill Keying

从图片四边播种 **flood fill**，吃掉所有与边缘连通的白色与灰边背景；再用「填洞」把被猫完全包围的
白色毛发（耳朵、胸口）恢复为不透明——抠底不再误伤猫身。

Seeds from all four borders, **flood fill** eats every white/gray pixel connected to the edge;
then a hole-filling pass restores white fur fully enclosed by the cat (ears, chest).

### 0x02 · Mask Erosion / 透明边界内收

透明边界向内收缩 **2px**，并生成两圈软边缘（alpha 130 / 210），让边缘从「生硬裁剪」变成
「细腻过渡」——抗锯齿毛边在这里彻底退场。

The transparency mask erodes **2px** inward, then two soft-edge rings (alpha 130 / 210)
turn harsh clipping into a smooth transition — goodbye, anti-aliased fringes.

### 0x03 · 收尾剪除 / Final Trim

软边圈上残留的浅色像素再补 4 轮裁剪，宁可砍一圈毛，也不留一根白边。

Four final trim passes cut any remaining light pixels on the soft rings.
**Better to shave off a ring of fur than leave a single white edge.**

## 🧠 抠图算法 / Keying Algorithm

核心常量（`main.py`）：

| 常量 | 值 | 作用 |
| --- | --- | --- |
| `WHITE_SUM` | 700 | R+G+B 超过即强制 alpha=0（近白判定） |
| `BG_COLORS` | (205,206,204) / (90,90,89) | GIF 自带灰边色族 |
| `BG_TOL` | 18 | 与灰边色族的欧氏距离阈值 |
| `EDGE_CUT` | 560 | 贴边浅色像素的剪除阈值 |

完整流水线：

1. 强制阈值：`R+G+B > 700` → 全透明
2. 泛洪抠底：吃掉与边缘连通的白底 + 灰边
3. 填洞：恢复被猫完全包围的白色毛发
4. 浅色毛边剪除：贴透明区的浅色像素直接归零
5. Mask Erosion：内收 2px + 两圈软边缘（alpha 130 / 210）
6. 收尾：软边圈浅色像素再补 4 轮裁剪

## 🚀 安装运行 / Setup

要求：Python 3.14+（3.10+ 亦可）、PyQt6

```bash
pip install PyQt6
python main.py
```

可选：预先生成透明帧缓存，让启动秒开：

```bash
python preprocess.py
```

## 🎮 玩法 / Usage

- 左键按住猫咪：拎着满屏跑 / Drag with left mouse button
- 右键点击猫咪：弹出菜单，选择「退出」/ Right-click for menu → Quit
- 找不到 `cat.gif`：弹窗提醒，并先用粉色小方块顶班 / Falls back to a pink square

## 📁 项目结构 / Project Structure

```
Salary-Cat-Vibe/
├── main.py          # 桌面宠物主程序（实时抠图 / 播放帧缓存）
├── preprocess.py    # 离线预抠：GIF → 透明 PNG 帧序列
├── cat.gif          # 小猫素材（白底灰边，运行时抠除）
└── .frames_cache/   # 预处理帧缓存（自动生成，已 gitignore）
```

## 💝 Credits / 致谢

AI 时代原生的协作结晶，三个人格的联合创作：

- 🧠 **DeepSeek R1** — 大脑：算法设计与抠图方案
- ✋ **OpenAI Codex** — 双手：编码与工程落地
- 🎬 **kaelan0528** — 导演：定义 Vibe 与产品方向

**Vibe Coding 1.0** —— 月薪喵，赛博禅意的桌面守护者。🐱

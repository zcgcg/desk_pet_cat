"""月薪喵 · 开机自启动管理（Windows）

纯标准库实现，无第三方依赖。通过写入当前用户的注册表
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 实现自启动，
无需管理员权限；使用 pythonw.exe 静默启动 main.py，开机不弹黑框。

用法：
    python autostart.py enable    启用开机自启动
    python autostart.py disable   禁用开机自启动
    python autostart.py status    查询当前状态（已启用 / 未启用）

也可以在程序里右键猫咪 → 勾选「开机自启动」直接切换，
效果与命令行一致。
"""

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # 非 Windows 环境
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "SalaryCat"  # 注册表值名，换名即换注册项


def _entry():
    """构造 Run 键的值：pythonw.exe（无控制台）+ main.py 绝对路径。"""
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = exe  # 找不到 pythonw 时退回 python（会带控制台窗口）
    main_py = Path(__file__).resolve().parent / "main.py"
    return f'"{pythonw}" "{main_py}"'


def is_enabled():
    """当前是否已启用自启动（注册表值存在且路径与当前一致）。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
        return value == _entry()
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable():
    """写入自启动注册表项；成功返回 True。"""
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _entry())
        return True
    except OSError:
        return False


def disable():
    """删除自启动注册表项；本来就没启用时也算成功。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "enable":
        print("启用成功：" + _entry() if enable() else "启用失败。")
    elif action == "disable":
        print("已禁用。" if disable() else "禁用失败。")
    else:  # status
        print("已启用：" + _entry() if is_enabled() else "未启用。")


if __name__ == "__main__":
    main()

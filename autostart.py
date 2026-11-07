"""月薪喵 · 开机自启动管理（Windows）

通过「启动文件夹 + VBS 静默启动器」实现开机自启动：
在用户启动文件夹（Win+R 输入 shell:startup 可打开）放入 SalaryCat.vbs，
登录时由系统静默执行 pythonw.exe main.py，无控制台窗口。

为什么不用注册表 Run 键：部分安全软件/策略会拦截 HKCU\...\Run 的写入
（写入返回成功但实际不生效），而启动文件夹是普通文件写入，兼容性最好。

用法：
    python autostart.py enable    启用开机自启动
    python autostart.py disable   禁用开机自启动
    python autostart.py status    查询当前状态（已启用 / 未启用）

也可以在程序里右键猫咪 → 勾选「开机自启动」直接切换，
效果与命令行一致。
"""

import os
import sys
from pathlib import Path

VBS_NAME = "SalaryCat.vbs"


def _pythonw():
    """当前解释器同目录的 pythonw.exe（无控制台）；找不到则退回 python。"""
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return pythonw if pythonw.exists() else exe


def _main_py():
    return Path(__file__).resolve().parent / "main.py"


def _startup_dir():
    return (
        Path(os.environ["APPDATA"])
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    )


def _vbs_path():
    return _startup_dir() / VBS_NAME


def _vbs_content():
    # VBS 中 "" 转义为一个引号：Run 收到 "pythonw.exe" "main.py"，窗口模式 0（隐藏）
    return (
        'CreateObject("WScript.Shell").Run '
        f'"""{_pythonw()}"" ""{_main_py()}""", 0, False'
    )


def is_enabled():
    """启动文件夹里已有内容匹配当前路径的 SalaryCat.vbs。"""
    p = _vbs_path()
    if not p.exists():
        return False
    try:
        return p.read_bytes().decode("mbcs") == _vbs_content()
    except OSError:
        return False


def enable():
    """写入启动文件夹 VBS；成功返回 True。"""
    try:
        _startup_dir().mkdir(parents=True, exist_ok=True)
        _vbs_path().write_bytes(_vbs_content().encode("mbcs"))
        return True
    except OSError:
        return False


def disable():
    """删除启动文件夹 VBS；本来就没有时也算成功。"""
    try:
        p = _vbs_path()
        if p.exists():
            p.unlink()
        return True
    except OSError:
        return False


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "enable":
        print("启用成功：" + str(_vbs_path()) if enable() else "启用失败。")
    elif action == "disable":
        print("已禁用。" if disable() else "禁用失败。")
    else:  # status
        print("已启用：" + str(_vbs_path()) if is_enabled() else "未启用。")


if __name__ == "__main__":
    main()

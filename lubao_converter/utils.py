# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
小工具：时间/大小格式化、路径处理、回收站、错误报告。
"""
import os
import sys
import time
import subprocess
from tkinter import messagebox

from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *


def fmt_t(t):
    t = int(max(t, 0))
    if t >= 3600:
        return "{:02d}:{:02d}:{:02d}".format(t // 3600, t % 3600 // 60, t % 60)
    return "{:02d}:{:02d}".format(t // 60, t % 60)


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "{:.0f} {}".format(n, unit) if unit == "B" else "{:.1f} {}".format(n, unit)
        n /= 1024.0
    return "{:.2f} TB".format(n)


def codec_name(c):
    return MPEG_CODECS.get(c, {"h264": "H.264", "hevc": "HEVC", "av1": "AV1"}.get(c, c.upper()))


def remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def clean_path(p):
    p = p.strip()
    if p.startswith("& "):
        p = p[2:].strip()
    if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
        p = p[1:-1]
    return os.path.expanduser(p)


try:
    from send2trash import send2trash as _send2trash
except Exception:
    _send2trash = None
TRASH_OK = _send2trash is not None or os.name == "nt" or sys.platform == "darwin"


def move_to_trash(path):
    """把文件放进回收站：优先用 send2trash，Windows 没装也能用系统自带接口。"""
    path = os.path.abspath(path)
    if _send2trash is not None:
        _send2trash(path)
        return
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
        # FO_DELETE=3；允许撤销(进回收站) | 不确认 | 不显示进度 | 不弹错误框
        op = SHFILEOPSTRUCTW(None, 3, path + "\0", None, 0x40 | 0x10 | 0x4 | 0x400, False, None, None)
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc != 0 or op.fAnyOperationsAborted or os.path.exists(path):
            raise OSError(T("放进回收站失败（错误码 {}）").format(rc))
        return
    if sys.platform == "darwin":
        esc = path.replace("\\", "\\\\").replace('"', '\\"')
        r = subprocess.run(["osascript", "-e", 'tell application "Finder" to delete POSIX file "{}"'.format(esc)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode == 0:
            return
    raise OSError(T("放不进回收站，请先 pip install send2trash"))


def report_crash(detail, title=T("程序出错了")):
    """把错误写进日志，并弹窗告诉用户（.pyw 运行时没有黑窗口，不弹窗就什么都看不到）。"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n[{}] Python {}\n{}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   sys.version.split()[0], detail))
    except Exception:
        pass
    last = detail.strip().splitlines()[-1] if detail.strip() else T("未知错误")
    msg = T("呜…程序出错了 >_<\n\n{}\n\n详细信息已保存到：\n{}\n\n把这个文件发给鹿包就能查原因啦").format(last, LOG_PATH)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, title, 0x10 | 0x40000)  # 错误图标 + 置顶
            return
        except Exception:
            pass
    try:
        messagebox.showerror(title, msg)
    except Exception:
        print(msg, file=sys.stderr)


def dark_titlebar(win):
    """深色模式下，把 Windows 窗口的标题栏也变成深色（Win10 2004 以后 / Win11 支持，不支持就保持原样）。"""
    if not DARK or os.name != "nt":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):  # 20 = 新版 Windows，19 = 早期 Win10
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:
        pass


# ---------- 动画用的缓动函数（k 从 0 走到 1，返回进度） ----------
def ease_out_spring(k):
    """像弹簧一样：冲过头一点、回弹一下，再停稳，Q 弹的感觉。"""
    import math
    return 1.0 if k >= 1 else 1 - math.exp(-5 * k) * math.cos(2.5 * math.pi * k)


def ease_bump_out(k, bump=0.08):
    """收起用：先轻轻鼓起来一点（前 25% 的时间），再顺滑地缩走。"""
    import math
    if k < 0.25:
        return -bump * math.sin(k / 0.25 * math.pi / 2)
    u = (k - 0.25) / 0.75
    u = 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    return -bump + (1 + bump) * u

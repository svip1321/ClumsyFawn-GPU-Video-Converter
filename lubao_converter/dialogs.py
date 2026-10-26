# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
弹窗：ffmpeg 安装指引、一键添加环境变量、投喂鹿包、可爱的提示条。
"""
import os
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import config as cfg
from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数
from .widgets import RoundButton, bind_wrap, auto_set
import base64
import hashlib

# 内置收款码的指纹：qr_data.py 里的图片被改过，指纹就对不上，软件不会显示被改过的码
QR_SHA256 = {"wx": "df445a04334d7fa2ddc3d17cde5a2811700dd862026e407065d5aa2ad075026f",
             "zfb": "f9627de0ae717f40f5288f771fdb97b88734a99da931829d1dafccd26220e99e"}


def qr_state(key):
    """内置收款码的状态："ok" 正常、"missing" 缺了 qr_data.py、"changed" 被改动过。"""
    try:
        from . import qr_data
    except Exception:
        return "missing"
    data = "".join(getattr(qr_data, key.upper(), ()) or ())
    if not data:
        return "missing"
    return "ok" if hashlib.sha256(data.encode()).hexdigest() == QR_SHA256[key] else "changed"


def qr_bytes(key):
    """校验通过的收款码图片（base64 文本），不通过返回 None。"""
    if qr_state(key) != "ok":
        return None
    from . import qr_data
    return "".join(getattr(qr_data, key.upper()))


class DialogsMixin:
    """各种弹出窗口。"""

    def place_center(self, win, ypos=0.5, size=None):
        """把弹窗放到软件主窗口的正中间。
        先隐藏、算好大小和位置后再显示，Windows 上无边框窗口才不会跑到屏幕左上角。"""
        win.withdraw()
        win.update_idletasks()
        self.root.update_idletasks()
        w, h = size or (win.winfo_reqwidth(), win.winfo_reqheight())  # 预先定好大小的窗口直接用那个大小
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + int((rh - h) * ypos)
        win.geometry("{}x{}+{}+{}".format(w, h, x, y))  # 不再强行改成 0，主窗口在副屏上也能居中
        dark_titlebar(win)
        win.deiconify()
        win.lift()

    def show_ffmpeg_help(self, reason=None):
        """弹出 ffmpeg 安装指引窗口。"""
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.lift()
            self.help_win.focus_force()
            return
        w = tk.Toplevel(self.root)
        self.help_win = w
        w.title(T("ffmpeg 安装方法"))
        w.configure(bg=C_BG)
        w.transient(self.root)
        sf = max(float(self.root.tk.call("tk", "scaling")) / 1.3333, 1.0)
        w.withdraw()
        help_size = (int(680 * sf), int(640 * sf))
        w.minsize(int(520 * sf), int(480 * sf))

        head = tk.Label(w, text=T("ffmpeg 不可用，转换器需要它才能工作。按下面 4 步装好就行啦～"), bg=C_BANNER, fg="white",
                        anchor="w", justify="left", padx=14, pady=10, font=FONT_BOLD, width=1)
        head.pack(fill="x")
        bind_wrap(head, 28)
        if reason:
            r = tk.Label(w, text=T("检测结果：") + reason, bg=C_BG, fg=C_BAD, anchor="w", justify="left",
                         padx=14, pady=6, font=FONT, width=1)
            r.pack(fill="x")
            bind_wrap(r, 28)

        # 底部按钮先固定住，中间内容区可以滚动
        bf = ttk.Frame(w, padding=(14, 10, 14, 14))
        bf.pack(side="bottom", fill="x")
        holder = ttk.Frame(w)
        holder.pack(fill="both", expand=True)
        cv = tk.Canvas(holder, bg=C_BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        cv.pack(side="left", fill="both", expand=True)
        # 内容放不下时才显示滚动条
        cv.configure(yscrollcommand=auto_set(vsb, lambda: vsb.pack(side="right", fill="y", before=cv), vsb.pack_forget))
        body = ttk.Frame(cv, padding=(14, 10, 14, 0))
        win_id = cv.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win_id, width=e.width))

        def wheel(e):
            if e.num == 4 or e.delta > 0:
                cv.yview_scroll(-2, "units")
            else:
                cv.yview_scroll(2, "units")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            w.bind_all(seq, lambda e: wheel(e) if str(e.widget).startswith(str(w)) else None, add="+")

        def step(num, title, lines, links=()):
            o, c = self.card(body)
            o.pack(fill="x", pady=(0, 10))
            c.columnconfigure(1, weight=1)
            tk.Label(c, text=str(num), bg=C_ACCENT, fg="white", font=FONT_BOLD, width=2).grid(
                row=0, column=0, rowspan=10, sticky="n", padx=(0, 12), pady=(2, 0))
            ttk.Label(c, text=title, style="Title.TLabel").grid(row=0, column=1, sticky="w")
            row = 1
            for ln in lines:
                self.wrap_label(c, ln, style="Card.TLabel").grid(row=row, column=1, sticky="ew", pady=(4, 0))
                row += 1
            for txt, url in links:
                self.link(c, txt, lambda u=url: webbrowser.open(u)).grid(row=row, column=1, sticky="w", pady=(4, 0))
                row += 1

        step(1, T("下载 ffmpeg"),
             [T("打开下面的下载页面，在「release builds」里下载 ffmpeg-release-essentials.zip "
              "（essentials 版就支持 NVENC 显卡加速；也可以下载 full 版）。")],
             ((T("点我前往下载页面：") + FFMPEG_DL_URL, FFMPEG_DL_URL),
              (T("FFmpeg 官网下载页（Windows 那一栏里就有上面这个链接）：") + FFMPEG_HOME_URL, FFMPEG_HOME_URL)))
        step(2, T("解压"),
             [T("在下载好的 zip 上点右键 → 「全部解压缩」→ 「提取」。"),
              T("会得到一个类似 ffmpeg-7.x-essentials_build 的文件夹，里面有 bin 文件夹。")])
        step(3, T("放到固定的位置"),
             [T("把这个文件夹改名为 ffmpeg，剪切到 C 盘根目录，也就是 C:\\ffmpeg。"),
              T("放好后确认这个文件存在：C:\\ffmpeg\\bin\\ffmpeg.exe（同一个文件夹里还要有 ffprobe.exe）。"),
              T("不要放在桌面或「下载」文件夹里，免得以后清理时误删。")])
        step(4, T("设置环境变量"),
             [T("按 Win + R，输入 sysdm.cpl 回车 → 「高级」→ 「环境变量」。"),
              T("在上面的「用户变量」里双击 Path → 「新建」→ 填入 C:\\ffmpeg\\bin → 一路点「确定」。"),
              T("设置完以后关掉本软件重新打开，ffmpeg 路径填 ffmpeg 就能用了。"),
              T("也可以点下面的「一键添加到环境变量」，选好 ffmpeg.exe 后自动帮你加好。"),
              T("不想设置环境变量的话，点「选择 ffmpeg.exe」直接选 C:\\ffmpeg\\bin\\ffmpeg.exe 也可以。")])

        RoundButton(bf, T("打开下载页面"), lambda: webbrowser.open(FFMPEG_DL_URL), kind="accent", bg=C_BG).pack(side="left")
        RoundButton(bf, T("选择 ffmpeg.exe"), lambda: self.pick_ffmpeg(parent=w), bg=C_BG).pack(side="left", padx=(10, 0))
        if os.name == "nt":
            RoundButton(bf, T("一键添加到环境变量"), lambda: self.add_ffmpeg_to_path(w), bg=C_BG).pack(
                side="left", padx=(10, 0))
        RoundButton(bf, T("关闭"), w.destroy, bg=C_BG, width=int(80 * cfg.SF)).pack(side="right")
        self.place_center(w, ypos=0.4, size=help_size)

    def add_ffmpeg_to_path(self, parent):
        """把 ffmpeg.exe 所在的文件夹加进当前用户的 Path 环境变量（只限 Windows）。"""
        cur = self.v_ffmpeg.get().strip()
        exe = cur if os.path.isfile(cur) else filedialog.askopenfilename(
            parent=parent, title=T("选择 ffmpeg.exe"), filetypes=[("ffmpeg", "ffmpeg.exe"), (T("所有文件"), "*.*")])
        if not exe:
            return
        folder = os.path.dirname(os.path.normpath(exe))
        if not messagebox.askyesno(T("添加到环境变量"), T("要把下面这个文件夹加进当前用户的 Path 环境变量吗？\n\n") + folder,
                                   parent=parent):
            return
        try:
            import winreg
            import ctypes
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                                winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    old, typ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    old, typ = "", winreg.REG_EXPAND_SZ
                parts = [x for x in old.split(";") if x]
                if any(os.path.normcase(x.rstrip("\\")) == os.path.normcase(folder) for x in parts):
                    messagebox.showinfo(T("添加到环境变量"), T("这个文件夹已经在 Path 里啦～"), parent=parent)
                else:
                    parts.append(folder)
                    winreg.SetValueEx(key, "Path", 0, typ if typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ)
                                      else winreg.REG_EXPAND_SZ, ";".join(parts))
                    # 通知系统环境变量变了（新打开的程序会生效）
                    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000,
                                                             ctypes.byref(ctypes.c_ulong()))
                    messagebox.showinfo(T("添加到环境变量"), T("添加成功！\n\n") + folder +
                                        T("\n\n本软件这次先直接用完整路径，下次打开就可以只填 ffmpeg 了。"), parent=parent)
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
            self.v_ffmpeg.set(os.path.normpath(exe))
            self.save_cfg()
            self.check_ffmpeg(manual=True)
        except Exception as e:
            messagebox.showerror(T("添加失败"), T("没能修改环境变量：{}\n\n可以按第 4 步手动设置哦").format(e), parent=parent)

    def load_qr(self, key):
        """读取收款码：图片数据内置在 qr_data.py 里（不读 assets 文件夹，替换文件夹里的图片换不掉收款码）。
        数据的指纹对不上（被改过）就不显示。返回 PhotoImage 或 None。"""
        data = qr_bytes(key)
        if data is None:
            return None
        box = int(220 * cfg.SF)
        try:
            try:
                import io
                from PIL import Image, ImageTk  # 有 Pillow 就按屏幕缩放得更清楚
                im = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
                if max(im.size) > box:
                    im.thumbnail((box, box), Image.LANCZOS)
                return ImageTk.PhotoImage(im, master=self.root)
            except ImportError:
                img = tk.PhotoImage(master=self.root, data=data)
            k = max(1, -(-max(img.width(), img.height()) // box))  # 向上取整的缩小倍数
            return img.subsample(k, k) if k > 1 else img
        except Exception:
            return None

    def show_feed(self):
        if getattr(self, "feed_win", None) is not None and self.feed_win.winfo_exists():
            self.feed_win.lift()
            return
        w = tk.Toplevel(self.root)
        w.withdraw()  # 先藏起来，内容放好、位置算好再显示
        self.feed_win = w
        w.title(T("投喂鹿包"))
        w.configure(bg=C_BG)
        w.transient(self.root)
        w.resizable(False, False)
        body = ttk.Frame(w, padding=(20, 16, 20, 16))
        body.pack(fill="both", expand=True)
        if self.avatar:
            tk.Label(body, image=self.avatar, bg=C_BG).pack()
        ttk.Label(body, text=T("谢谢你愿意投喂鹿包～"), style="AppTitle.TLabel").pack(pady=(8, 2))
        ttk.Label(body, text=T("扫一扫下面任意一个码就可以啦"), style="TLabel", foreground=C_SUB).pack()

        row = ttk.Frame(body)
        row.pack(pady=(14, 6))
        self._qr = {}
        for key, name, color in (("wx", T("微信"), "#07c160"), ("zfb", T("支付宝"), "#1677ff")):
            o, c = self.card(row)
            o.pack(side="left", padx=8)
            img = self.load_qr(key)
            if img is not None:
                self._qr[key] = img
                tk.Label(c, image=img, bg=C_CARD).pack()
            else:
                tk.Label(c, text=T("呜…{}收款码不见了\n鹿包要饿肚子啦 (｡•́︿•̀｡)\n\n请重新下载完整的软件～").format(name),
                         bg=C_LOG, fg=C_SUB, font=FONT, width=22, height=9, justify="center").pack()
            tk.Label(c, text=name, bg=C_CARD, fg=color, font=FONT_TITLE).pack(pady=(8, 0))

        bf = ttk.Frame(body)
        bf.pack(fill="x", pady=(12, 0))

        def fed():
            w.destroy()
            self.toast(T("收到投喂啦！鹿包开心得转圈圈，谢谢你～ (*≧▽≦)ノ♥"))

        def refuse():
            w.destroy()
            self.toast(T("呜呜…那鹿包下次再来讨饭饭～ (｡•́︿•̀｡)"), color="#8a8f99")
        RoundButton(bf, T("残忍拒绝"), refuse, bg=C_BG, width=int(120 * cfg.SF)).pack(side="right")
        RoundButton(bf, T("已投喂"), fed, kind="accent", bg=C_BG, width=int(120 * cfg.SF)).pack(side="right", padx=(0, 10))
        self.place_center(w)

    def toast(self, text, color=C_ACCENT, ms=2600):
        """在软件窗口正中间弹出一行提示，过一会儿自己淡出消失。"""
        t = tk.Toplevel(self.root)
        t.withdraw()  # 先藏起来，位置算好再显示
        t.overrideredirect(True)
        t.configure(bg=color)
        tk.Label(t, text=text, bg=color, fg="white", font=FONT_BIG, padx=int(26 * cfg.SF), pady=int(14 * cfg.SF)).pack()
        self.place_center(t)
        try:
            t.attributes("-topmost", True)
        except tk.TclError:
            pass

        def fade(a=1.0):
            if not t.winfo_exists():
                return
            if a <= 0.05:
                t.destroy()
                return
            try:
                t.attributes("-alpha", a)
            except tk.TclError:
                t.destroy()
                return
            t.after(30, lambda: fade(a - 0.08))
        t.after(ms, fade)

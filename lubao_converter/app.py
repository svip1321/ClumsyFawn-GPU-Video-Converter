# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
主程序：设置读写、扫描视频、开始/停止转换、后台转换线程、界面消息循环。
"""
import os
import sys
import json
import time
import queue
import tempfile
import threading
import subprocess
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

from . import config as cfg
from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数
from .engine import Engine
from .widgets import WidgetMixin
from .layout import LayoutMixin
from .dialogs import DialogsMixin
from .music import MusicMixin


def TARGET_HINT():
    """格式转换模块下面的说明（每一条单独一行，方便阅读）。"""
    return "\n".join([
        T("· 分辨率、画面比例和帧率都和原视频一样，不会降低"),
        T("· 音频原样复制、不重新编码"),
        T("· H.264 / HEVC 视频只换文件格式、不重新编码，很快且画质完全不变（.avi 除外）"),
        T("· 其他编码用显卡重新编码成 HEVC；.avi / .flv 装不了 HEVC，会改用 H.264"),
    ])


class App(LayoutMixin, DialogsMixin, MusicMixin, WidgetMixin):
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.items = []          # 扫描到的视频
        self.running = False
        self.scanning = False
        self.stop_flag = False
        self.gpu_ok = False
        self.detect_seq = 0      # 第几次检测；旧的检测结果回来时直接丢掉
        cfg = self.load_cfg()
        self.eng = Engine(cfg.get("ffmpeg", "ffmpeg"))

        self.v_path = tk.StringVar()
        self.v_target = tk.StringVar(value="mp4")
        self.v_only_mpeg = tk.BooleanVar(value=False)   # 启用文件夹视频格式纠正
        self.v_fix_mpeg = tk.BooleanVar(value=True)     # 纠正 MPEG 编码
        self.v_fix_av1 = tk.BooleanVar(value=True)      # 纠正 AV1 编码
        self.v_fix_audio = tk.BooleanVar(value=True)    # 纠正苹果设备没声音的 mp4 音频
        self.v_target_hint = tk.StringVar(value=TARGET_HINT())
        mode = cfg.get("delete_mode")
        if mode not in DEL_TEXT:  # 兼容旧版的勾选框设置
            mode = "trash" if cfg.get("delete") else "keep"
        if mode == "trash" and not TRASH_OK:
            mode = "keep"
        self.v_del_mode = tk.StringVar(value=mode)
        self.v_del_info = tk.StringVar(value=DEL_TEXT[mode])
        self.v_del_mode.trace_add("write", lambda *a: self.on_del_mode())
        self.v_ffmpeg = tk.StringVar(value=self.eng.ffmpeg)
        self.v_cq = tk.IntVar(value=cfg.get("cq", 19))
        self.v_gpu = tk.StringVar(value=T("正在检测编码方式..."))
        backend = cfg.get("backend", "auto")
        self.v_backend = tk.StringVar(value=backend if backend in BACKEND_CHOICES else "auto")
        self.v_enc_info = tk.StringVar(value=T("正在检测..."))
        self.v_lang = tk.StringVar(value=LANG_NAMES[LANG])
        self.v_theme = tk.StringVar(value=self.theme_names()[THEME])
        self.out_dir = None  # 用户指定的视频输出文件夹；None = 默认（视频旁边的 output）
        self.v_out_info = tk.StringVar(value=T("默认：视频旁边的 output 文件夹（选的是文件夹时，就是那个文件夹里的 output）"))
        self.v_ff = tk.StringVar(value="")
        self.help_win = None
        self.v_mpeg_info = tk.StringVar(value="")
        self.v_cur_name = tk.StringVar(value=T("当前：等待开始"))
        self.v_cur_info = tk.StringVar(value="")
        self.v_total_info = tk.StringVar(value=T("总进度：0/0"))

        self.init_music()
        self.build_ui()
        self.on_del_mode()  # 打开时就按当前设置给"原视频"那一行上色（永久删除 = 红色）
        self.saved_settings = self.settings_now()
        self.cur_tab = self.nb.select()
        self._tab_guard = False
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll)
        self.check_gpu()

    def load_cfg(self):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def theme_names():
        return {"light": T("浅色"), "dark": T("深色"), "system": T("跟随系统")}

    def theme_code(self):
        name = self.v_theme.get()
        return next((k for k, n in self.theme_names().items() if n == name), THEME)

    def lang_code(self):
        """设置页语言下拉框里选的是哪种语言（返回语言代码）。"""
        name = self.v_lang.get()
        return next((c for c, n in LANGS if n == name), LANG)

    def settings_now(self):
        return (self.v_ffmpeg.get().strip() or "ffmpeg", self.get_cq(), self.v_del_mode.get(), self.v_backend.get(),
                self.lang_code(), self.theme_code())

    def settings_dirty(self):
        return self.settings_now() != self.saved_settings

    def revert_settings(self):
        ff, cq, mode, backend, lang, theme = self.saved_settings
        self.v_lang.set(LANG_NAMES.get(lang, LANG_NAMES[LANG]))
        self.v_theme.set(self.theme_names().get(theme, self.theme_names()[THEME]))
        self.v_ffmpeg.set(ff)
        self.v_cq.set(cq)
        self.v_del_mode.set(mode)
        self.v_backend.set(backend)
        self.eng.ffmpeg = ff
        self.apply_backend()

    def on_tab_changed(self, event=None):
        new, prev = self.nb.select(), self.cur_tab
        self.cur_tab = new
        self.refresh_tabs()
        if self._tab_guard or prev != str(self.tab_set) or new == str(self.tab_set) or not self.settings_dirty():
            return
        ans = messagebox.askyesnocancel(
            T("保存设置"), T("设置有改动，是否保存本次更改？\n\n是：保存\n否：放弃这次改动\n取消：留在设置页继续改"))
        if ans is None:
            self._tab_guard = True
            self.nb.select(self.tab_set)
            self.cur_tab = str(self.tab_set)
            self._tab_guard = False
        elif ans:
            self.apply_settings(from_tab=True)
        else:
            self.revert_settings()

    def save_cfg(self):
        self.saved_settings = self.settings_now()
        try:
            with open(CFG_PATH, "w", encoding="utf-8") as f:
                json.dump({"ffmpeg": self.v_ffmpeg.get().strip() or "ffmpeg",
                           "cq": self.get_cq(), "delete_mode": self.v_del_mode.get(),
                           "backend": self.v_backend.get(), "lang": self.lang_code(),
                           "theme": self.theme_code()},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_cq(self):
        try:
            return min(max(int(self.v_cq.get()), 10), 35)
        except (tk.TclError, ValueError):
            return 19

    def post(self, *msg):
        self.q.put(msg)

    def log(self, text):
        self.post("log", text)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", "[{}] {}\n".format(time.strftime("%H:%M:%S"), text))
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def set_status(self, iid, text, tag=None):
        self.post("row", iid, text, tag)

    def refresh_start_btn(self):
        ok = self.gpu_ok and not self.running and not self.scanning and bool(self.items)
        self.btn_start.configure(state="normal" if ok else "disabled")

    def check_ffmpeg(self, manual=False):
        if self.running:
            messagebox.showinfo(T("提示"), T("正在转换中，ffmpeg 肯定能用～等转完再检测吧"))
            return
        self.eng.ffmpeg = self.v_ffmpeg.get().strip() or "ffmpeg"
        self.v_ff.set(T("正在检测 ffmpeg..."))
        self.lbl_ff.configure(style="Sub.TLabel")
        self.btn_ff.configure(state="disabled")

        def job():
            ok, msg = self.eng.check_ffmpeg()
            self.post("ffmpeg", ok, msg, manual)
        threading.Thread(target=job, daemon=True).start()

    # ---------- 顶部提示条：Q 弹地出现 / 消失 ----------
    BANNER_GAP = 12  # 提示条和下面内容之间的空隙

    def show_banner(self, text, kind="bad"):
        """转换页顶部的提示条：kind="info" 蓝灰色（正在检测），"bad" 红色（出问题了）。
        出现时从 0 弹出来、稍微冲过头再回弹；已经显示着就只换文字和颜色。"""
        self.gpu_banner.configure(text=text, bg=C_ACCENT if kind == "info" else C_BANNER)
        self._banner_on = True
        box = self.banner_box
        if not box.winfo_manager():  # 还没显示：弹出来
            box.configure(height=1)
            box.pack(fill="x", before=self.top_row)
            if self.tab_convert.winfo_ismapped():
                self._banner_anim([(0, self._banner_full, 600, ease_out_spring)])
            else:  # 用户在别的页面，看不到动画，直接摆好
                self._banner_anim([])
        else:
            self.root.after(80, self._banner_fit)  # 文字变了，行数可能也变了（等自动换行算好再调高度）

    def hide_banner(self):
        """提示条 Q 弹地消失：先轻轻鼓一下，再缩回去，内容往上滑走。"""
        if not getattr(self, "_banner_on", False):
            return
        self._banner_on = False
        if not self.banner_box.winfo_manager():
            return
        if not self.tab_convert.winfo_ismapped():  # 在别的页面，看不到动画，直接收起
            self._banner_anim([], done=lambda: self.banner_box.pack_forget())
            return
        self._banner_anim([(None, 0, 460, ease_bump_out)], done=lambda: self.banner_box.pack_forget())

    def _banner_full(self):
        return self.gpu_banner.winfo_reqheight() + self.BANNER_GAP

    def _banner_set(self, h):
        h = max(0, int(round(h)))
        self.banner_box.configure(height=max(h, 1))
        full = self._banner_full()
        # 缩小时文字跟着往上滑，而不是被从下面硬切掉；冲过头的时候文字停在顶上
        self.gpu_banner.place_configure(y=min(0, h - full))

    def _banner_fit(self):
        if getattr(self, "_banner_job", None) is None and getattr(self, "_banner_on", False):
            self._banner_set(self._banner_full())

    def _banner_anim(self, steps, done=None):
        """按顺序播放几段高度动画。steps = [(起点或 None=接着上一段, 终点或函数, 毫秒, 缓动函数), ...]"""
        job = getattr(self, "_banner_job", None)
        if job is not None:
            self.root.after_cancel(job)
            self._banner_job = None
        if not steps:
            if done:
                done()
            else:
                self._banner_fit()
            return
        start, end, ms, ease = steps[0]
        a = self.banner_box.winfo_height() if start is None else start
        t0 = time.perf_counter()

        def tick():
            b = end() if callable(end) else end
            k = min((time.perf_counter() - t0) * 1000 / ms, 1.0)
            self._banner_set(a + (b - a) * ease(k))
            if k < 1.0:
                self._banner_job = self.root.after(15, tick)
            else:
                self._banner_job = None
                self._banner_anim(steps[1:], done)
        tick()

    def update_backend_radios(self):
        """检测完以后，在设置页每个编码方式后面标上能不能用，用不了的变灰。"""
        for bid, (rb, base) in self.backend_radios.items():
            if bid == "auto":
                gpus = [BACKEND_BY_ID[x]["short"] for x in self.eng.found if BACKEND_BY_ID[x]["gpu"]]
                rb.configure(text=base + "  —— " + (T("会用 {}").format(gpus[0]) if gpus else T("没检测到显卡加速")))
                continue
            ok = bid in self.eng.found
            rb.configure(text=base + "  —— " + self.eng.status_text(bid), state="normal" if ok else "disabled")

    def missing_files(self):
        """检查项目文件夹里软件需要的文件：缺失、是空文件、语言文件坏了、头像 / 图标被换掉（SHA256 不对），都算有问题。
        返回 [(文件相对路径, 缺了会影响什么), ...]。打包成 exe 后 .py 文件已经编译进去了，就不检查它们。"""
        from .i18n import LANG_DIR, LANGS
        frozen = getattr(sys, "frozen", False)
        need = []
        if not frozen:
            need += [(os.path.join(APP_DIR, "main.pyw"), T("双击启动软件"))]
            for name, what in (("__init__.py", T("整个软件")), ("app.py", T("整个软件")), ("config.py", T("整个软件")),
                               ("i18n.py", T("界面文字和语言切换")), ("utils.py", T("删除原文件、出错报告")),
                               ("engine.py", T("视频和音乐转换")), ("widgets.py", T("界面按钮和样式")),
                               ("layout.py", T("主界面")), ("music.py", T("音乐转换")),
                               ("dialogs.py", T("ffmpeg 安装指引和投喂窗口")), ("qr_data.py", None)):
                need.append((os.path.join(PKG_DIR, name), what))
        for k in AVATAR_SIZES:
            need.append((os.path.join(ASSET_DIR, "avatar_%d.png" % k), T("头像")))
        need.append((os.path.join(ASSET_DIR, ICON_PNG), T("软件图标")))
        for code, lname in LANGS:
            need.append((os.path.join(LANG_DIR, code + ".json"), T("切换到「{}」界面").format(lname)))
        bad = []
        for path, what in need:
            try:
                ok = os.path.getsize(path) > 0
                if ok and path.endswith(".json"):
                    with open(path, "r", encoding="utf-8") as f:
                        json.load(f)
            except (OSError, ValueError):
                ok = False
            if ok and os.path.dirname(path) == ASSET_DIR:  # 头像和图标还要核对 SHA256，被换掉也算缺失
                ok = asset_ok(os.path.basename(path))
            if not ok:
                rel = os.path.relpath(path, APP_DIR) if not frozen else os.path.basename(path)
                bad.append((rel, what))
        return bad

    def qr_problems(self):
        """内置收款码有没有问题（缺了 qr_data.py，或者收款码被改过），返回给用户看的可爱提示行。"""
        from .dialogs import qr_state
        lines = []
        for key, name in (("wx", T("微信")), ("zfb", T("支付宝"))):
            st = qr_state(key)
            if st == "missing":
                lines.append(T("· {}收款码不见了（缺失 qr_data.py），投喂窗口里扫不到码，鹿包要饿肚子啦 (｡•́︿•̀｡)").format(name))
            elif st == "changed":
                lines.append(T("· {}收款码好像被人换掉了，为了不让投喂送错地方，鹿包先把它藏起来啦 (｡•́︿•̀｡)").format(name))
        return lines

    def check_files(self):
        """有文件缺失时，在窗口正中间弹出警告：缺失哪个文件，可能导致什么不能用。"""
        try:
            bad = [(rel, what) for rel, what in self.missing_files() if what]  # qr_data.py 单独用可爱的话提示
            qr = self.qr_problems()
        except Exception:
            return
        if not bad and not qr:
            return
        if not bad:  # 只有收款码的问题：温柔一点地说
            self._append_log(T("文件检查：收款码有问题"))
            messagebox.showwarning(T("鹿包要饿肚子啦"), T("小小提醒～\n\n{}\n\n转换功能完全不受影响，可以放心用；"
                                                      "想让鹿包吃上饭饭的话，重新下载一份完整的软件就好啦 ♥").format(
                "\n".join(qr)), parent=self.root)
            return
        lines = [T("· 缺失 {}，可能导致「{}」无法正常使用").format(rel, what) for rel, what in bad[:12]] + qr
        if len(bad) > 12:
            lines.append(T("……还有 {} 个文件").format(len(bad) - 12))
        self._append_log(T("文件检查：缺少 {} 个文件：").format(len(bad)) + T("，").join(rel for rel, _ in bad))
        messagebox.showwarning(T("文件缺失"), T("软件文件夹里缺少下面这些文件（或者文件损坏了）：\n\n{}\n\n"
                                              "请重新下载完整的软件，或者从备份里把这些文件放回原位置").format(
            "\n".join(lines)), parent=self.root)

    def set_gpu_lines(self, lines):
        """设置页「重新检测」右边的检测结果：每行单独一种颜色。lines = [(文字, 样式), ...]"""
        self.v_gpu.set("\n".join(t for t, _ in lines))  # 弹窗里也会用到这段文字
        box = getattr(self, "gpu_box", None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        for i, (text, style) in enumerate(lines):
            self.wrap_label(box, text, style=style).grid(row=i, column=0, sticky="ew")

    def apply_backend(self):
        """按设置里选的编码方式定下当前用哪个，并更新提示。返回能不能开始转换。"""
        if not self.eng.detected:
            return False
        pref = self.v_backend.get()
        act = self.eng.pick(pref)
        self.gpu_ok = act is not None
        # 每种编码方式一行：能用的绿色，没检测到的红色
        rows = [(self.eng.describe(b["id"]), "Ok.TLabel" if b["id"] in self.eng.found else "Bad.TLabel")
                for b in BACKENDS]
        if act:
            be = BACKEND_BY_ID[act]
            self.v_enc_info.set(self.eng.model_text(act) + (T("（显卡加速）") if be["gpu"] else T("（比显卡慢不少，但哪台电脑都能用）")))
            self.lbl_enc_info.configure(style="Key.TLabel" if be["gpu"] else "Bad.TLabel")
            self.set_gpu_lines([(T("[当前使用] {}").format(self.eng.model_text(act)), "Ok.TLabel")] + rows)
            self.hide_banner()
        else:
            if pref == "auto":
                tip = T("没检测到可用的显卡加速（NVIDIA / AMD / Intel 都不行）。可以到「设置」把编码方式改成「CPU」继续转换，会慢一些")
            else:
                tip = T("设置里选的「{}」在这台电脑上用不了，请到「设置」换一种编码方式").format(BACKEND_BY_ID[pref]["name"])
            self.v_enc_info.set(T("没有可用的编码方式"))
            self.lbl_enc_info.configure(style="Bad.TLabel")
            self.set_gpu_lines([(T("[未就绪] {}").format(tip), "Bad.TLabel")] + rows)
            self.show_banner(T("警告：") + tip)
        self.refresh_start_btn()
        return self.gpu_ok

    def check_gpu(self, manual=False):
        if self.running:
            messagebox.showinfo(T("提示"), T("正在转换中，编码器肯定在干活呢～等转完再检测吧"))
            return
        if manual:  # 按当前填写的 ffmpeg 路径检测
            self.eng.ffmpeg = self.v_ffmpeg.get().strip() or "ffmpeg"
        self.gpu_ok = False
        self.set_gpu_lines([(T("正在检测 NVIDIA / AMD / Intel / CPU 四种编码方式，大约需要几秒..."), "Sub.TLabel")])
        self.v_enc_info.set(T("正在检测..."))
        self.v_ff.set(T("正在检测 ffmpeg..."))
        self.lbl_ff.configure(style="Sub.TLabel")
        self.show_banner(T("正在检测 ffmpeg 和显卡加速（NVIDIA / AMD / Intel），几秒钟就好，请稍等～"), kind="info")
        self.btn_gpu.configure(state="disabled")
        self.refresh_start_btn()

        self.root.after(400, self.check_files)  # 顺便检查项目文件齐不齐
        self.detect_seq += 1
        seq = self.detect_seq

        def job():
            ok, msg = self.eng.check()
            self.post("gpu", ok, msg, manual, seq)
        threading.Thread(target=job, daemon=True).start()

    def apply_settings(self, from_tab=False):
        if self.running:
            messagebox.showinfo(T("提示"), T("正在转换中，等转完再改设置吧～"))
            return
        ff_changed = (self.v_ffmpeg.get().strip() or "ffmpeg") != self.saved_settings[0] or not self.gpu_ok
        self.eng.ffmpeg = self.v_ffmpeg.get().strip() or "ffmpeg"
        self.v_cq.set(self.get_cq())
        self.save_cfg()
        self._append_log(T("设置已保存"))
        if self.lang_code() != LANG or self.theme_code() != THEME:  # 换了语言或外观：要重启软件才生效
            if messagebox.askyesno(T("重启软件"), T("语言 / 外观已保存，需要重启软件才会生效。\n\n要现在重启吗？")):
                self.restart_app()
                return
        self.apply_backend()
        if ff_changed:  # ffmpeg 路径变了才需要重新检测
            self.check_gpu(manual=not from_tab)
        elif not from_tab:
            messagebox.showinfo(T("保存设置"), T("设置已保存～"))

    def restart_app(self):
        """重新打开软件（换语言后用）。正在转换时不重启。"""
        if self.running or self.m_running:
            messagebox.showinfo(T("提示"), T("正在转换中，等转完再重启吧～"))
            return
        if getattr(sys, "frozen", False):          # 打包成 exe 时
            args = [sys.executable] + sys.argv[1:]
        else:
            args = [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
        try:
            subprocess.Popen(args, cwd=APP_DIR)
        except Exception as e:
            messagebox.showerror(T("重启失败"), T("没能自动重启：{}\n\n请手动关掉软件再打开").format(e))
            return
        self.root.destroy()

    def pick_ffmpeg(self, parent=None):
        ft = [("ffmpeg", "ffmpeg.exe"), (T("所有文件"), "*.*")] if os.name == "nt" else [(T("所有文件"), "*")]
        p = filedialog.askopenfilename(parent=parent or self.root, title=T("选择 ffmpeg"), filetypes=ft)
        if p:
            self.v_ffmpeg.set(os.path.normpath(p))
            self.save_cfg()
            self.check_ffmpeg(manual=True)  # 选好就马上检测

    def pick_files(self):
        exts = " ".join("*" + e for e in sorted(VIDEO_EXTS))
        ps = filedialog.askopenfilenames(title=T("选择视频"), filetypes=[(T("视频文件"), exts), (T("所有文件"), "*.*")])
        if ps:
            self.scan(list(ps))

    def pick_dir(self):
        p = filedialog.askdirectory(title=T("选择视频文件夹"))
        if p:
            self.scan([p])

    def on_drop(self, event):
        """拖进窗口：在音乐转换页就当音乐，其他页面当视频。"""
        paths = list(self.root.tk.splitlist(event.data))
        if self.nb.select() == str(self.tab_music):
            self.m_scan(paths)
        else:
            self.nb.select(self.tab_convert)
            self.scan(paths)

    def scan(self, paths):
        if self.running or self.scanning:
            return
        paths = [os.path.normpath(p) for p in paths if p]
        if not paths:
            return
        self.v_path.set(paths[0] if len(paths) == 1 else T("已选择 {} 个文件").format(len(paths)))
        self.clear_list()
        self.scanning = True
        self.refresh_start_btn()
        self.v_mpeg_info.set(T("正在读取视频信息..."))

        def job():
            files = []
            for p in paths:
                if os.path.isdir(p):
                    out = os.path.join(os.path.abspath(p), "output")
                    for x in sorted(os.listdir(p)):
                        f = os.path.join(p, x)
                        if os.path.isfile(f) and os.path.splitext(x)[1].lower() in VIDEO_EXTS:
                            files.append((f, out))
                elif os.path.isfile(p):
                    files.append((p, os.path.join(os.path.dirname(os.path.abspath(p)), "output")))
                else:
                    self.log(T("找不到：") + p)
            if not files:
                self.post("scan_done", T("没找到视频哦～"))
                return
            for i, (f, out) in enumerate(files):
                info = self.eng.probe(f)
                try:
                    size = os.path.getsize(f)
                except OSError:
                    size = 0
                item = dict(path=f, out=out, size=size, **info)
                self.post("add", item)
                self.post("scan_progress", i + 1, len(files))
            self.post("scan_done", None)
        threading.Thread(target=job, daemon=True).start()

    def clear_list(self):
        if self.running:
            return
        self.items = []
        self.tv.delete(*self.tv.get_children())
        self.v_mpeg_info.set("")
        self.refresh_start_btn()

    def remove_selected(self):
        if self.running:
            return
        sel = set(self.tv.selection())
        if not sel:
            return
        for iid in sel:
            self.tv.delete(iid)
        self.items = [it for it in self.items if it["iid"] not in sel]
        self.update_mpeg_info()
        self.refresh_start_btn()

    def fix_codecs(self):
        """格式纠正里勾选了的编码。mp4 只有是这些编码时才会被转换。"""
        codecs = set()
        if self.v_fix_mpeg.get():
            codecs |= set(MPEG_CODECS)
        if self.v_fix_av1.get():
            codecs |= set(AV1_CODECS)
        return codecs

    def audio_fix(self, it):
        """这个视频要不要做音频纠正：勾选了、是 mp4，而且有苹果设备放不出声音的音轨。"""
        return (self.v_fix_audio.get() and os.path.splitext(it["path"])[1].lower() in AUDIO_FIX_EXTS
                and bool(self.eng.apple_silent(it)))

    def needs_fix(self, it):
        return it["vcodec"] in self.fix_codecs() or self.audio_fix(it)

    def on_fix_change(self):
        """勾选/取消纠正选项时，刷新列表里的颜色和上方的提示。"""
        for it in self.items:
            if self.tv.exists(it["iid"]) and not self.tv.set(it["iid"], "status"):
                self.tv.item(it["iid"], tags=("mpeg",) if self.needs_fix(it) else ())
        self.update_mpeg_info()

    def update_mpeg_info(self):
        n_mpeg = sum(1 for it in self.items if it["vcodec"] in MPEG_CODECS)
        n_av1 = sum(1 for it in self.items if it["vcodec"] in AV1_CODECS)
        n_aud = sum(1 for it in self.items if os.path.splitext(it["path"])[1].lower() in AUDIO_FIX_EXTS
                    and self.eng.apple_silent(it))
        if n_mpeg or n_av1 or n_aud:
            parts = ([T("MPEG 编码 {} 个").format(n_mpeg)] if n_mpeg else []) + \
                    ([T("AV1 编码 {} 个").format(n_av1)] if n_av1 else []) + \
                    ([T("苹果设备没声音的 mp4 {} 个").format(n_aud)] if n_aud else [])
            self.v_mpeg_info.set(T("找到需要纠正的视频：{}。勾选「启用文件夹视频格式纠正」就会把它们纠正成"
                                 "兼容性更好的 mp4").format(T("，").join(parts)))
        else:
            self.v_mpeg_info.set(T("共 {} 个视频，没有需要纠正的视频（MPEG / AV1 编码、苹果没声音的 mp4）").format(len(self.items))
                                 if self.items else "")

    def on_del_mode(self):
        mode = self.v_del_mode.get()
        self.v_del_info.set(DEL_TEXT.get(mode, ""))
        self.lbl_del_info.configure(style="Bad.TLabel" if mode == "delete" else "Key.TLabel")

    def on_only_mpeg(self):
        """启用格式纠正时，格式转换模块变灰：统一转成 mp4。"""
        if self.v_only_mpeg.get():
            self.v_target.set("mp4")
            self.cb_target.configure(state="disabled")
            self.v_target_hint.set(T("已启用下面的「格式纠正」：这次统一转成 mp4，只处理需要纠正的视频"))
            self.lbl_target_hint.configure(style="Info.TLabel")
        else:
            self.cb_target.configure(state="readonly")
            self.v_target_hint.set(TARGET_HINT())
            self.lbl_target_hint.configure(style="Sub.TLabel")

    def open_folder(self, path):
        """用资源管理器打开文件夹。"""
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception as e:
            messagebox.showerror(T("提示"), T("打不开文件夹：{}").format(e))

    def pick_out_dir(self, music=False):
        """指定输出文件夹（视频和音乐各自单独设置）。"""
        p = filedialog.askdirectory(title=T("选择输出文件夹"))
        if not p:
            return
        p = os.path.normpath(p)
        if music:
            self.m_out_dir = p
            self.v_m_out_info.set(p)
        else:
            self.out_dir = p
            self.v_out_info.set(p)
        self.log(T("输出文件夹改为：{}").format(p))

    def reset_out_dir(self, music=False):
        if music:
            self.m_out_dir = None
            self.v_m_out_info.set(T("默认：音乐旁边的 output 文件夹（选的是文件夹时，就是那个文件夹里的 output）"))
        else:
            self.out_dir = None
            self.v_out_info.set(T("默认：视频旁边的 output 文件夹（选的是文件夹时，就是那个文件夹里的 output）"))

    def show_done(self, summary, dirs):
        """转换结束：告诉用户文件保存到了哪里（完整路径），问要不要直接打开。"""
        if not dirs:
            messagebox.showinfo(T("完成啦"), summary)
            return
        shown = "\n".join(dirs[:6]) + ("\n……" if len(dirs) > 6 else "")
        if messagebox.askyesno(T("完成啦"), "{}\n\n{}\n{}\n\n{}".format(
                summary, T("文件保存在："), shown, T("要现在打开这个文件夹吗？"))):
            self.open_folder(dirs[0])

    def open_output(self):
        if self.out_dir and os.path.isdir(self.out_dir):
            self.open_folder(self.out_dir)
            return
        outs = []
        for it in self.items:
            if it["out"] not in outs:
                outs.append(it["out"])
        target = next((o for o in outs if os.path.isdir(o)), None)
        if not target:
            messagebox.showinfo(T("提示"), T("还没有输出文件夹哦，转换开始后才会创建～"))
            return
        self.open_folder(target)

    def plan_jobs(self):
        """按当前选项决定哪些视频要转换，跳过的直接在列表里标出来。返回 (目标格式, 要转的视频) 或 (目标格式, None)。"""
        target = "mp4" if self.v_only_mpeg.get() else self.v_target.get()
        only_fix = self.v_only_mpeg.get()
        fix = self.fix_codecs()
        if only_fix and not fix and not self.v_fix_audio.get():
            messagebox.showinfo(T("提示"), T("格式纠正里还没勾选要纠正什么（MPEG / AV1 / 苹果设备没声音）哦～"))
            return target, None
        jobs = []
        for it in self.items:
            iid, vc = it["iid"], it["vcodec"]
            need_fix = vc in fix
            # 音频纠正：只在输出是 mp4 时有意义（转成 mkv 等格式时，音频本来就原样保留）
            it["afix"] = target in ("mp4", "m4v") and self.audio_fix(it)
            if only_fix and not need_fix and not it["afix"]:
                self.tv.set(iid, "status", T("跳过（{} 编码，不需要纠正）").format(codec_name(vc)))
                self.tv.item(iid, tags=("skip",))
            elif os.path.splitext(it["path"])[1].lower() == "." + target and not need_fix and not it["afix"]:
                # 已经是目标格式、编码也没问题：不用再转一遍
                self.tv.set(iid, "status", T("跳过（已经是 .{}，{} 编码不需要转）").format(target, codec_name(vc)))
                self.tv.item(iid, tags=("skip",))
            else:
                # H.264 / HEVC 只换文件格式时直接复制视频流；需要纠正的编码才重新编码
                # 只纠正音频时，画面一律原样复制（画质 100% 不变）
                it["remux"] = (not need_fix) and (self.eng.can_remux(it, target) or it["afix"])
                jobs.append(it)
        if not jobs:
            messagebox.showinfo(T("提示"), T("列表里没有需要转换的视频哦～"))
            return target, None
        return target, jobs

    def start(self):
        if self.running or not self.items:
            return
        if not self.gpu_ok or self.eng.active is None:
            messagebox.showwarning(T("还不能转换"), T("现在没有可用的编码方式，请先到「设置」里选一种能用的～"))
            return
        target, jobs = self.plan_jobs()
        if jobs is None:
            return
        for it in jobs:
            self.tv.set(it["iid"], "status", T("等待中"))

        delete_fn = None
        mode = self.v_del_mode.get()
        if mode != "keep":
            delete_fn, how = (move_to_trash, T("放进回收站")) if mode == "trash" else (os.remove, T("永久删除（无法找回）"))
            if not messagebox.askyesno(T("确认处理原视频"),
                                       T("设置里的原视频处理方式是：{}。\n\n每个视频转换完成并检查能正常播放后，"
                                       "会立刻处理对应的原视频。\n\n确定要这样做吗？").format(how)):
                return

        self.save_cfg()
        self.running = True
        self.stop_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.pb_cur["value"] = 0
        self.pb_total["value"] = 0
        self.log(T("开始转换：{} 个视频，目标格式 {}，CQ {}").format(len(jobs), target, self.get_cq()))
        if self.out_dir:
            self.log(T("这次输出到：{}").format(self.out_dir))
        threading.Thread(target=self.worker, args=(jobs, target, delete_fn, self.get_cq(), self.out_dir),
                         daemon=True).start()

    def stop(self):
        if not self.running:
            return
        self.stop_flag = True
        self.btn_stop.configure(state="disabled")
        p = self.eng.proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        self.log(T("正在停止..."))

    def worker(self, jobs, target, delete_fn, cq, out_dir=None):
        n = len(jobs)
        ok = fail = removed = 0
        saved_dirs = []  # 这一轮实际保存到了哪些文件夹（完成时告诉用户）
        t0 = time.time()
        used_names = set()  # 本轮已用过的输出文件名，防止同名视频互相覆盖
        for k, it in enumerate(jobs, 1):
            if self.stop_flag:
                break
            iid, src = it["iid"], it["path"]
            stem, src_ext = os.path.splitext(os.path.basename(src))
            name = stem + "." + target
            out = out_dir or it["out"]  # 指定了输出文件夹就用它，否则用视频旁边的 output
            if os.path.normcase(os.path.join(out, name)) in used_names:
                name = "{}_{}.{}".format(stem, src_ext.lstrip(".").lower(), target)  # 例如 abc_avi.mp4
            dst = os.path.join(out, name)
            used_names.add(os.path.normcase(dst))
            if os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src):
                self.log(T("输出文件夹里已经有同名文件，直接覆盖：{}").format(dst))
            if os.path.abspath(dst) == os.path.abspath(src):
                self.set_status(iid, T("跳过（输出会覆盖原文件）"), "skip")
                continue
            try:
                os.makedirs(out, exist_ok=True)  # 真正开始转时才创建输出文件夹
            except OSError as e:
                self.set_status(iid, T("失败：无法创建输出文件夹"), "bad")
                self.log(T("无法创建文件夹 {}：{}").format(out, e))
                fail += 1
                continue
            cmd, venc, anote = self.eng.build(src, dst, it, target, cq, remux=it.get("remux", False))
            self.set_status(iid, T("转换中..."))
            self.post("focus", iid)
            self.post("cur_name", T("当前 [{}/{}]：{}").format(k, n, os.path.basename(src)))
            if venc == "copy":
                vnote = T("视频 {} 原样复制（只换文件格式，画质不变）").format(codec_name(it["vcodec"]))
            else:
                vnote = T("视频 {} -> {}（{}）").format(codec_name(it["vcodec"]), venc, BACKEND_BY_ID[self.eng.active]["short"])
            self.log(T("[{}/{}] {} -> output\\{}  {}，音频 {}").format(k, n, os.path.basename(src), name, vnote, anote))

            start = time.time()
            rc, err = self.run_ffmpeg(cmd, it["dur"], k, n)
            if self.stop_flag:
                remove(dst)
                self.set_status(iid, T("已停止，删掉了没转完的文件"), "skip")
                break
            if rc != 0 or not os.path.isfile(dst):
                remove(dst)
                fail += 1
                short = err.strip().splitlines()[-1] if err.strip() else T("未知错误")
                self.set_status(iid, T("失败：") + short[:60], "bad")
                self.log(T("转换失败：{}\n{}").format(os.path.basename(src), err.strip()[-800:]))
                if "No space left" in err:
                    self.log(T("硬盘空间满了，已停止后面的转换"))
                    break
                continue

            used = fmt_t(time.time() - start)
            self.set_status(iid, T("检查新视频能否正常播放..."))
            good, why = self.eng.verify(dst, it["dur"])
            ok += 1
            if not good:
                self.set_status(iid, T("完成，但检查未通过：{}（原视频保留）").format(why), "bad")
                self.log(T("检查未通过：{}（{}）").format(name, why))
                continue
            try:
                new_size = fmt_size(os.path.getsize(dst))
            except OSError:
                new_size = "?"
            status = T("完成 {}，{} -> {}").format(used, fmt_size(it["size"]), new_size)
            if it.get("afix") and it.get("remux"):
                status += T("，画面原样复制，声音换成苹果能放的 AAC")
            elif it.get("remux"):
                status += T("，只换格式画质不变")
            if delete_fn:
                try:
                    delete_fn(src)
                    removed += 1
                    status += T("，原视频已删除")
                    self.log(T("已删除原视频：") + os.path.basename(src))
                except Exception as e:
                    status += T("，原视频删除失败")
                    self.log(T("删除失败：{}（{}）").format(os.path.basename(src), e))
            self.set_status(iid, status, "ok")
            self.log(T("完成：{}  耗时 {}").format(name, used))
            self.log(T("已保存到：{}").format(dst))
            if out not in saved_dirs:
                saved_dirs.append(out)
        summary = T("本轮完成 {} 个，失败 {} 个，删除原视频 {} 个，总耗时 {}").format(
            ok, fail, removed, fmt_t(time.time() - t0))
        if self.stop_flag:
            summary = T("已停止。") + summary
        self.post("finished", summary, saved_dirs)

    def run_ffmpeg(self, cmd, dur, k, n):
        err = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                    creationflags=NO_WINDOW,
                                    universal_newlines=True, encoding="utf-8", errors="ignore")
        except OSError as e:
            return 1, str(e)
        self.eng.proc = proc
        start, cur, fps, speed = time.time(), 0.0, "0", "-"
        for line in proc.stdout:
            key, _, v = line.strip().partition("=")
            if key in ("out_time_us", "out_time_ms"):
                try:
                    cur = max(cur, int(v) / 1e6)
                except ValueError:
                    pass
            elif key == "fps":
                fps = v
            elif key == "speed":
                speed = v.strip()
            elif key == "progress":
                el = time.time() - start
                if dur > 0:
                    p = 1.0 if v == "end" else min(cur / dur, 1.0)
                    eta = fmt_t(el * (1 - p) / p) if p > 0.005 else "--:--"
                    info = T("{:.1f}%    {} fps    速度 {}    已用 {}    剩余 {}").format(p * 100, fps, speed, fmt_t(el), eta)
                else:
                    p = 0.0
                    info = T("已处理 {}    {} fps    速度 {}    已用 {}").format(fmt_t(cur), fps, speed, fmt_t(el))
                self.post("cur", p * 100, info)
                self.post("total", ((k - 1) + p) / n * 100, T("总进度：{}/{}").format(k - 1, n))
        proc.wait()
        self.eng.proc = None
        err.seek(0)
        msg = err.read().decode("utf-8", "ignore")
        err.close()
        return proc.returncode, msg

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind.startswith("m_"):  # 音乐转换页的消息
                    self.m_handle(msg)
                elif kind == "log":
                    self._append_log(msg[1])
                elif kind == "ffmpeg":
                    _, ok, text, manual = msg
                    self.ffmpeg_ok = ok
                    self.m_refresh_btns()
                    self.btn_ff.configure(state="normal")
                    self._append_log((T("ffmpeg 可用：") if ok else T("ffmpeg 不可用：")) + text)
                    if ok:
                        self.v_ff.set(T("[可用] ") + text)
                        self.lbl_ff.configure(style="Ok.TLabel")
                        if self.help_win is not None and self.help_win.winfo_exists():
                            self.help_win.destroy()
                        if manual:
                            messagebox.showinfo(T("ffmpeg 可用"), T("ffmpeg 可以用啦～接下来自动检测编码方式\n\n") + text)
                            self.check_gpu()
                    else:
                        self.v_ff.set(T("[不可用] ") + text)
                        self.lbl_ff.configure(style="Bad.TLabel")
                        self.show_ffmpeg_help(text)
                elif kind == "gpu":
                    _, ok, text, manual, seq = msg
                    if seq != self.detect_seq:  # 已经有更新的一次检测在进行，这个结果过时了
                        continue
                    self.ffmpeg_ok = not text.startswith("NO_FFMPEG:")
                    self.m_refresh_btns()
                    if text.startswith("NO_FFMPEG:"):  # ffmpeg 都找不到：显示安装指引
                        reason = text[len("NO_FFMPEG:"):]
                        self.gpu_ok = False
                        self.btn_gpu.configure(state="normal")
                        self.set_gpu_lines([(T("[未就绪] 需要先装好 ffmpeg"), "Bad.TLabel")])
                        self.v_ff.set(T("[不可用] ") + reason)
                        self.lbl_ff.configure(style="Bad.TLabel")
                        self._append_log(T("ffmpeg 不可用：") + reason)
                        self.show_banner(T("警告：找不到 ffmpeg，现在不能转换！请按弹窗里的方法装好 ffmpeg"))
                        self.nb.select(self.tab_set)
                        self.show_ffmpeg_help(reason)
                        self.refresh_start_btn()
                        continue
                    self.btn_gpu.configure(state="normal")
                    self._append_log(text.replace("\n", "  |  "))
                    self.v_ff.set(T("[可用] ") + text.splitlines()[0])
                    self.lbl_ff.configure(style="Ok.TLabel")
                    self.update_backend_radios()
                    usable = self.apply_backend()
                    if manual:
                        if usable:
                            messagebox.showinfo(T("检测完成"), T("可以开始转换啦～\n\n当前使用：{}\n\n{}").format(
                                self.eng.model_text(self.eng.active), "\n".join(text.splitlines()[1:])))
                        else:
                            messagebox.showwarning(T("没有可用的编码方式"), self.v_gpu.get())
                    elif not usable:
                        self.nb.select(self.tab_set)
                        messagebox.showwarning(T("没有可用的显卡加速"), self.v_gpu.get())
                elif kind == "add":
                    it = msg[1]
                    iid = self.tv.insert("", "end", values=(
                        os.path.basename(it["path"]),
                        codec_name(it["vcodec"]) + (" · " + it["acodec"].upper() if it.get("acodec") else ""),
                        fmt_size(it["size"]), ""),
                        tags=("mpeg",) if self.needs_fix(it) else ())
                    it["iid"] = iid
                    self.items.append(it)
                elif kind == "scan_progress":
                    self.v_mpeg_info.set(T("正在读取视频信息... {}/{}").format(msg[1], msg[2]))
                elif kind == "scan_done":
                    self.scanning = False
                    if msg[1]:
                        self.v_mpeg_info.set(msg[1])
                    else:
                        self.update_mpeg_info()
                        if any(self.needs_fix(it) for it in self.items):
                            self.v_only_mpeg.set(True)
                            self.on_only_mpeg()
                    self.refresh_start_btn()
                elif kind == "row":
                    _, iid, text, tag = msg
                    if self.tv.exists(iid):
                        self.tv.set(iid, "status", text)
                        if tag:
                            self.tv.item(iid, tags=(tag,))
                elif kind == "focus":
                    if self.tv.exists(msg[1]):
                        self.tv.see(msg[1])
                elif kind == "cur_name":
                    self.v_cur_name.set(msg[1])
                elif kind == "cur":
                    self.pb_cur["value"] = msg[1]
                    self.v_cur_info.set(msg[2])
                elif kind == "total":
                    self.pb_total["value"] = msg[1]
                    self.v_total_info.set(msg[2])
                elif kind == "finished":
                    self.running = False
                    self.btn_stop.configure(state="disabled")
                    self.pb_total["value"] = 100 if not self.stop_flag else self.pb_total["value"]
                    self.v_total_info.set(msg[1])
                    self.v_cur_name.set(T("当前：已结束"))
                    self._append_log(msg[1])
                    self.refresh_start_btn()
                    for d in msg[2]:
                        self._append_log(T("文件保存在：") + d)
                    self.show_done(msg[1], msg[2])
        except queue.Empty:
            pass
        # 列表内容变了（加了文件、状态更新、清空）就重新算列宽，决定要不要显示左右滚动条
        sig = tuple((len(tv.get_children()), tuple(tv.set(i, "status") for i in tv.get_children()))
                    for tv in (self.tv, self.m_tv))
        if sig != getattr(self, "_fit_sig", None):
            self._fit_sig = sig
            self.fit_tree(self.tv)
            self.fit_tree(self.m_tv)
        self.root.after(100, self.poll)

    def on_close(self):
        if self.running or self.m_running:
            if not messagebox.askyesno(T("退出"), T("还在转换中，确定要退出吗？没转完的文件会被删掉")):
                return
            self.stop()
            self.m_stop()
            time.sleep(0.5)
        if self.settings_dirty():
            ans = messagebox.askyesnocancel(T("保存设置"), T("设置有改动还没保存，退出前要保存吗？"))
            if ans is None:
                return
            if ans:
                self.save_cfg()
        self.root.destroy()


def run():
    # 后台线程里的错误也要报告出来
    threading.excepthook = lambda a: report_crash(
        "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)), T("后台任务出错"))
    root = None
    try:
        if os.name == "nt":  # 高分屏下字体不发虚
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        try:
            root = cfg.TkinterDnD.Tk() if cfg.HAS_DND else tk.Tk()
        except Exception:  # 拖放插件出问题时，退回普通窗口
            cfg.HAS_DND = False
            if tk._default_root is not None:
                try:
                    tk._default_root.destroy()
                except Exception:
                    pass
            root = tk.Tk()
        root.report_callback_exception = lambda et, ev, tb: report_crash(
            "".join(traceback.format_exception(et, ev, tb)), T("运行出错"))
        App(root)

        def to_front():  # 双击打开时把窗口提到最前面
            try:
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
                root.after(300, lambda: root.attributes("-topmost", False))
                root.focus_force()
            except tk.TclError:
                pass
        root.after(150, to_front)
        root.mainloop()
    except Exception:
        report_crash(traceback.format_exc(), T("启动失败"))
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass

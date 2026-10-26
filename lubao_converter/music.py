# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
音乐转换页：选音乐 → 选输出格式和音质 → 转换到原文件所在文件夹的 output 目录。
保留歌名、歌手、专辑等信息，目标格式支持的话把封面也一起带过去；原文件不会被删除。
音乐软件的加密格式（网易云 .ncm、QQ 音乐 .mflac 等）受版权保护，本软件不做解密，只在列表里说明。
"""
import os
import time
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import config as cfg
from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数
from .widgets import RoundButton


def is_lossless(codec):
    return bool(codec) and (codec in LOSSLESS_CODECS or codec.startswith("pcm_") or codec.startswith("dsd_"))


def codec_family(codec):
    if not codec:
        return ""
    return "pcm" if codec.startswith("pcm_") else codec


def audio_codec_name(c):
    if not c:
        return "?"
    if c.startswith("pcm_"):
        return "PCM"
    if c.startswith("dsd_"):
        return "DSD"
    return {"mp3": "MP3", "flac": "FLAC", "aac": "AAC", "alac": "ALAC", "vorbis": "Vorbis", "opus": "Opus",
            "wmav2": "WMA", "wmav1": "WMA", "ape": "APE", "wavpack": "WavPack", "ac3": "AC3", "eac3": "E-AC3",
            "dts": "DTS", "tta": "TTA", "tak": "TAK", "amr_nb": "AMR", "amr_wb": "AMR", "mp2": "MP2"}.get(c, c.upper())


class MusicMixin:
    """音乐转换页面和它的转换逻辑。"""

    def init_music(self):
        self.m_items = []
        self.m_running = self.m_scanning = self.m_stop_flag = False
        self.m_proc = None
        self.v_m_path = tk.StringVar()
        self.v_m_fmt = tk.StringVar(value=AUDIO_OUT[0]["name"])
        self.v_m_rate = tk.StringVar(value="")
        self.v_m_sr = tk.StringVar(value="")
        self.v_m_desc = tk.StringVar(value="")
        self.v_m_info = tk.StringVar(value="")
        self.v_m_cur_name = tk.StringVar(value=T("当前：等待开始"))
        self.v_m_cur_info = tk.StringVar(value="")
        self.v_m_total_info = tk.StringVar(value=T("总进度：0/0"))
        self.ffmpeg_ok = False
        self.m_out_dir = None  # 用户指定的音乐输出文件夹；None = 默认（音乐旁边的 output）
        self.v_m_out_info = tk.StringVar(value=T("默认：音乐旁边的 output 文件夹（选的是文件夹时，就是那个文件夹里的 output）"))

    # ---------- 界面 ----------
    def build_music_tab(self):
        t = self.tab_music
        bf = ttk.Frame(t)
        bf.pack(side="bottom", fill="x", pady=(10, 0))
        self.m_btn_start = RoundButton(bf, T("开始转换"), self.m_start, kind="accent", bg=C_BG, state="disabled",
                                       width=int(120 * cfg.SF))
        self.m_btn_start.pack(side="left")
        self.m_btn_stop = RoundButton(bf, T("停止"), self.m_stop, bg=C_BG, state="disabled", width=int(90 * cfg.SF))
        self.m_btn_stop.pack(side="left", padx=(10, 0))
        RoundButton(bf, T("打开输出文件夹"), self.m_open_output, bg=C_BG).pack(side="right")
        RoundButton(bf, T("清空列表"), self.m_clear, bg=C_BG).pack(side="right", padx=(0, 10))
        RoundButton(bf, T("移除选中"), self.m_remove_selected, bg=C_BG).pack(side="right", padx=(0, 10))

        body = ttk.Frame(t)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=5, uniform="mcols")
        body.columnconfigure(1, weight=6, uniform="mcols")
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ① 选择音乐
        o1, c1 = self.card(left, T("请选择需要转换的音乐"))
        o1.pack(fill="x")
        c1.columnconfigure(0, weight=1)
        ent = ttk.Entry(c1, textvariable=self.v_m_path, font=FONT)
        ent.grid(row=1, column=0, sticky="ew")
        ent.bind("<Return>", lambda e: self.m_scan([clean_path(self.v_m_path.get())]))
        bx = ttk.Frame(c1, style="Card.TFrame")
        bx.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for i, (txt, cmd) in enumerate(((T("读取路径"), lambda: self.m_scan([clean_path(self.v_m_path.get())])),
                                        (T("选择音乐"), self.m_pick_files), (T("选择文件夹"), self.m_pick_dir))):
            bx.columnconfigure(i, weight=1, uniform="mpick")
            RoundButton(bx, txt, cmd, bg=C_CARD).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
        hint = (T("可以直接把音乐或文件夹拖进来；也能从 mp4、mkv 等视频里直接提取音轨") if cfg.HAS_DND else
                T("可以把路径粘贴到输入框后按回车；也能从 mp4、mkv 等视频里直接提取音轨"))
        self.wrap_label(c1, hint).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        # ② 输出格式
        o2, c2 = self.card(left, T("输出格式"))
        o2.pack(fill="x", pady=(10, 0))
        c2.columnconfigure(1, weight=1)
        ttk.Label(c2, text=T("格式"), style="Key.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        self.m_cb_fmt = ttk.Combobox(c2, textvariable=self.v_m_fmt, values=[f["name"] for f in AUDIO_OUT],
                                     state="readonly", font=FONT_BOLD, width=28)
        self.m_cb_fmt.grid(row=1, column=1, sticky="w")
        self.m_cb_fmt.bind("<<ComboboxSelected>>", lambda e: self.m_on_fmt())
        ttk.Label(c2, text=T("音质"), style="Key.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=(8, 0))
        self.m_cb_rate = ttk.Combobox(c2, textvariable=self.v_m_rate, state="readonly", font=FONT_BOLD, width=28)
        self.m_cb_rate.grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(c2, text=T("采样率"), style="Key.TLabel").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=(8, 0))
        self.m_cb_sr = ttk.Combobox(c2, textvariable=self.v_m_sr, state="readonly", font=FONT_BOLD, width=28)
        self.m_cb_sr.grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.wrap_label(c2, textvariable=self.v_m_desc).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.wrap_label(c2, T("会保留歌名、歌手、专辑等信息，格式支持的话封面也一起带过去；原文件不会删除")).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(c2, text=T("输出位置"), style="Key.TLabel").grid(row=6, column=0, sticky="nw", padx=(0, 16), pady=(10, 0))
        self.wrap_label(c2, textvariable=self.v_m_out_info, style="Card.TLabel").grid(
            row=6, column=1, sticky="ew", pady=(10, 0))
        mb_ = ttk.Frame(c2, style="Card.TFrame")
        mb_.grid(row=7, column=1, sticky="w", pady=(6, 0))
        RoundButton(mb_, T("指定输出文件夹"), lambda: self.pick_out_dir(music=True), bg=C_CARD).pack(side="left")
        RoundButton(mb_, T("恢复默认"), lambda: self.reset_out_dir(music=True), bg=C_CARD).pack(side="left", padx=(8, 0))

        # ③ 关于加密格式
        o3, c3 = self.card(left, T("关于音乐软件的加密格式"))
        o3.pack(fill="both", expand=True, pady=(10, 0))  # 拉伸到底，和右边进度那块的底边对齐
        c3.columnconfigure(0, weight=1)
        self.wrap_label(c3, T("网易云的 .ncm、QQ 音乐的 .mflac / .mgg / .qmc、酷狗的 .kgm、酷我的 .kwm 等，是音乐平台为了保护"
                            "版权加密过的文件，本软件不能转换。想要能自由转换的音乐，可以在音乐软件里下载普通的 mp3 / flac "
                            "版本，或者使用自己的 CD、无加密的正版音乐。"), style="Card.TLabel").grid(row=1, column=0, sticky="ew")

        # ④ 进度（右栏底部）
        o5, c5 = self.card(right)
        o5.pack(side="bottom", fill="x", pady=(10, 0))
        c5.columnconfigure(0, weight=1)
        ttk.Label(c5, textvariable=self.v_m_cur_name, style="Key.TLabel").grid(row=0, column=0, sticky="w")
        self.wrap_label(c5, textvariable=self.v_m_cur_info).grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.m_pb_cur = ttk.Progressbar(c5, maximum=100)
        self.m_pb_cur.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(c5, textvariable=self.v_m_total_info, style="Key.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.m_pb_total = ttk.Progressbar(c5, maximum=100)
        self.m_pb_total.grid(row=4, column=0, sticky="ew", pady=(4, 0))

        # ⑤ 音乐列表
        o4, c4 = self.card(right)
        o4.pack(fill="both", expand=True)
        c4.columnconfigure(0, weight=1)
        c4.rowconfigure(1, weight=1)
        self.wrap_label(c4, textvariable=self.v_m_info, style="Info.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        cols = ("name", "codec", "dur", "size", "status")
        tv = ttk.Treeview(c4, columns=cols, show="headings", selectmode="extended", height=4)
        for c, txt, w, mw, anc in (("name", T("文件名"), 200, 160, "w"), ("codec", T("编码"), 80, 70, "center"),
                                   ("dur", T("时长"), 70, 60, "center"), ("size", T("大小"), 80, 70, "center"),
                                   ("status", T("状态"), 220, 180, "w")):
            tv.heading(c, text=txt, anchor=anc)
            tv.column(c, width=int(w * cfg.SF), minwidth=int(mw * cfg.SF), anchor=anc,
                      stretch=(c in ("name", "status")))
        self.tree_scroll(c4, tv, fit={"name": int(160 * cfg.SF), "status": int(180 * cfg.SF)})
        tv.tag_configure("skip", foreground=C_MUTED)
        tv.tag_configure("ok", foreground=C_OK)
        tv.tag_configure("bad", foreground=C_BAD)
        tv.tag_configure("lock", foreground=C_BAD)
        self.m_tv = tv
        self.m_on_fmt()

    def m_fmt_spec(self):
        name = self.v_m_fmt.get()
        return next((f for f in AUDIO_OUT if f["name"] == name), AUDIO_OUT[0])

    def m_on_fmt(self):
        """换了输出格式：更新音质选项和说明。"""
        spec = self.m_fmt_spec()
        if spec["rates"]:
            # 第一项（默认）：和原音乐一样——按原文件的码率挑，不低于原来的码率，音质不打折
            labels = [T("和原音乐一样（推荐）")] + \
                     ["{} kbps{}".format(r[:-1], T("（最高）") if i == 0 else "") for i, r in enumerate(spec["rates"])]
            self.m_cb_rate.configure(values=labels, state="readonly")
            if self.v_m_rate.get() not in labels:
                self.v_m_rate.set(labels[0])
        else:
            self.m_cb_rate.configure(values=[T("无损（和原文件一样）")], state="disabled")
            self.v_m_rate.set(T("无损（和原文件一样）"))
        if spec["srs"]:
            labels = [T("和原音乐一样（推荐）")] + [fmt_sr(x) for x in spec["srs"]]
            self.m_cb_sr.configure(values=labels, state="readonly")
            if self.v_m_sr.get() not in labels:
                self.v_m_sr.set(labels[0])
        else:  # OPUS 只有 48 kHz 一种
            only = T("{}（这个格式只支持这一种）").format(fmt_sr(spec["sr_ok"][0]))
            self.m_cb_sr.configure(values=[only], state="disabled")
            self.v_m_sr.set(only)
        self.v_m_desc.set(spec["desc"])

    def m_rate(self):
        spec = self.m_fmt_spec()
        if not spec["rates"]:
            return ""
        if self.v_m_rate.get() == T("和原音乐一样（推荐）"):
            return "auto"
        txt = self.v_m_rate.get().split()[0] if self.v_m_rate.get() else ""
        return txt + "k" if txt + "k" in spec["rates"] else spec["rates"][0]

    def m_sr(self):
        """选的采样率；0 = 和原音乐一样。"""
        spec = self.m_fmt_spec()
        return next((x for x in spec["srs"] if fmt_sr(x) == self.v_m_sr.get()), 0)

    def m_refresh_btns(self):
        ok = self.ffmpeg_ok and not self.m_running and not self.m_scanning and bool(self.m_items)
        self.m_btn_start.configure(state="normal" if ok else "disabled")

    # ---------- 选择 / 扫描 ----------
    def m_pick_files(self):
        exts = " ".join("*" + e for e in sorted(AUDIO_IN_EXTS | set(ENCRYPTED_EXTS)))
        ps = filedialog.askopenfilenames(title=T("选择音乐"), filetypes=[(T("音乐文件"), exts), (T("所有文件"), "*.*")])
        if ps:
            self.m_scan(list(ps))

    def m_pick_dir(self):
        p = filedialog.askdirectory(title=T("选择音乐文件夹"))
        if p:
            self.m_scan([p])

    def m_scan(self, paths):
        if self.m_running or self.m_scanning:
            return
        paths = [os.path.normpath(p) for p in paths if p]
        if not paths:
            return
        self.v_m_path.set(paths[0] if len(paths) == 1 else T("已选择 {} 个文件").format(len(paths)))
        self.m_clear()
        self.m_scanning = True
        self.m_refresh_btns()
        self.v_m_info.set(T("正在读取音乐信息..."))
        known = AUDIO_IN_EXTS | set(ENCRYPTED_EXTS)

        def job():
            files = []
            for p in paths:
                if os.path.isdir(p):
                    out = os.path.join(os.path.abspath(p), "output")
                    for x in sorted(os.listdir(p)):
                        f = os.path.join(p, x)
                        if os.path.isfile(f) and os.path.splitext(x)[1].lower() in known:
                            files.append((f, out))
                elif os.path.isfile(p):
                    files.append((p, os.path.join(os.path.dirname(os.path.abspath(p)), "output")))
                else:
                    self.log(T("找不到：") + p)
            if not files:
                self.post("m_scan_done", T("没找到音乐文件哦～"))
                return
            for i, (f, out) in enumerate(files):
                ext = os.path.splitext(f)[1].lower()
                try:
                    size = os.path.getsize(f)
                except OSError:
                    size = 0
                if ext in ENCRYPTED_EXTS:
                    item = dict(path=f, out=out, size=size, locked=ENCRYPTED_EXTS[ext], dur=0.0, acodec=None)
                else:
                    item = dict(path=f, out=out, size=size, locked=None, **self.eng.probe_audio(f))
                self.post("m_add", item)
                self.post("m_scan_prog", i + 1, len(files))
            self.post("m_scan_done", None)
        threading.Thread(target=job, daemon=True).start()

    def m_clear(self):
        if self.m_running:
            return
        self.m_items = []
        self.m_tv.delete(*self.m_tv.get_children())
        self.v_m_info.set("")
        self.m_refresh_btns()

    def m_remove_selected(self):
        if self.m_running:
            return
        sel = set(self.m_tv.selection())
        for iid in sel:
            self.m_tv.delete(iid)
        self.m_items = [it for it in self.m_items if it["iid"] not in sel]
        self.m_update_info()
        self.m_refresh_btns()

    def m_update_info(self):
        n = len(self.m_items)
        locked = sum(1 for it in self.m_items if it["locked"])
        noaudio = sum(1 for it in self.m_items if not it["locked"] and not it["acodec"])
        if not n:
            self.v_m_info.set("")
            return
        msg = T("共 {} 个文件").format(n)
        if locked:
            msg += T("，其中 {} 个是音乐软件的加密格式，不能转换").format(locked)
        if noaudio:
            msg += T("，{} 个读不到音轨").format(noaudio)
        self.v_m_info.set(msg)

    def m_open_output(self):
        if self.m_out_dir and os.path.isdir(self.m_out_dir):
            self.open_folder(self.m_out_dir)
            return
        target = next((it["out"] for it in self.m_items if os.path.isdir(it["out"])), None)
        if not target:
            messagebox.showinfo(T("提示"), T("还没有输出文件夹哦，转换开始后才会创建～"))
            return
        self.open_folder(target)

    # ---------- 开始 / 停止 ----------
    def m_start(self):
        if self.m_running or not self.m_items:
            return
        if not self.ffmpeg_ok:
            messagebox.showwarning(T("还不能转换"), T("还没检测到可用的 ffmpeg，请先到「设置」里检查～"))
            return
        spec, rate, sr = self.m_fmt_spec(), self.m_rate(), self.m_sr()
        jobs = []
        for it in self.m_items:
            iid = it["iid"]
            same_ext = os.path.splitext(it["path"])[1].lower().lstrip(".") == spec["ext"]
            if it["locked"]:
                self.m_set(iid, T("跳过：{}加密格式，不能转换").format(it["locked"]), "lock")
            elif not it["acodec"]:
                self.m_set(iid, T("跳过：读不到音轨"), "skip")
            elif same_ext and codec_family(it["acodec"]) in spec["family"] and sr in (0, it.get("sr")):
                # 同一种格式、也不改采样率：转了也没意义（指定了别的采样率时照常转换）
                self.m_set(iid, T("跳过：已经是 {} 了").format(spec["name"]), "skip")
            else:
                self.m_set(iid, T("等待中"), "")
                jobs.append(it)
        if not jobs:
            messagebox.showinfo(T("提示"), T("列表里没有需要转换的音乐哦～"))
            return
        self.m_running, self.m_stop_flag = True, False
        self.m_btn_stop.configure(state="normal")
        self.m_refresh_btns()
        self.m_pb_cur["value"] = self.m_pb_total["value"] = 0
        self.log(T("开始转换音乐：{} 个，输出 {}{}").format(len(jobs), spec["name"], T("，") + self.v_m_rate.get() if rate else "")
                 + T("，采样率：{}").format(self.v_m_sr.get()))
        if self.m_out_dir:
            self.log(T("这次输出到：{}").format(self.m_out_dir))
        threading.Thread(target=self.m_worker, args=(jobs, spec, rate, self.m_out_dir, sr), daemon=True).start()

    def m_stop(self):
        if not self.m_running:
            return
        self.m_stop_flag = True
        self.m_btn_stop.configure(state="disabled")
        p = self.m_proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def m_set(self, iid, text, tag=None):
        if self.m_tv.exists(iid):
            self.m_tv.set(iid, "status", text)
            if tag is not None:
                self.m_tv.item(iid, tags=(tag,) if tag else ())

    def m_worker(self, jobs, spec, rate, out_dir=None, sr=0):
        n, ok, fail = len(jobs), 0, 0
        saved_dirs = []  # 这一轮实际保存到了哪些文件夹
        t0 = time.time()
        used_names = set()
        for k, it in enumerate(jobs, 1):
            if self.m_stop_flag:
                break
            iid, src = it["iid"], it["path"]
            stem, src_ext = os.path.splitext(os.path.basename(src))
            name = stem + "." + spec["ext"]
            out = out_dir or it["out"]  # 指定了输出文件夹就用它，否则用音乐旁边的 output
            if os.path.normcase(os.path.join(out, name)) in used_names:
                name = "{}_{}.{}".format(stem, src_ext.lstrip(".").lower(), spec["ext"])
            dst = os.path.join(out, name)
            used_names.add(os.path.normcase(dst))
            if os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src):
                self.log(T("输出文件夹里已经有同名文件，直接覆盖：{}").format(dst))
            if os.path.abspath(dst) == os.path.abspath(src):
                self.post("m_row", iid, T("跳过：输出会覆盖原文件"), "skip")
                continue
            try:
                os.makedirs(out, exist_ok=True)
            except OSError as e:
                self.post("m_row", iid, T("失败：无法创建输出文件夹"), "bad")
                self.log(T("无法创建文件夹 {}：{}").format(out, e))
                fail += 1
                continue
            cmd = self.eng.build_audio(src, dst, it, spec["key"], rate, sr)
            self.post("m_row", iid, T("转换中..."), None)
            self.post("m_cur_name", T("当前 [{}/{}]：{}").format(k, n, os.path.basename(src)))
            note = ""
            lossy_up = not is_lossless(it["acodec"]) and not spec["rates"]
            if lossy_up:
                note = T("（原文件是有损的，转成无损只会变大，音质不会变好）")
            out_sr = self.eng.pick_sr(spec, it, sr)
            detail = ", ".join(x for x in (self.eng.pick_rate(spec, it, rate),
                                           fmt_sr(out_sr) if out_sr else "") if x)
            if out_sr and it.get("sr") and out_sr > it["sr"]:
                note += T("（原文件只有 {}，提高采样率不会让音质变好）").format(fmt_sr(it["sr"]))
            self.log(T("[{}/{}] 音乐 {} -> {}  {} {} -> {} {}{}").format(
                k, n, os.path.basename(src), name, audio_codec_name(it["acodec"]),
                fmt_sr(it["sr"]) if it.get("sr") else "", spec["name"], detail, note))
            start = time.time()
            rc, err = self.m_run(cmd, it["dur"], k, n)
            if self.m_stop_flag:
                remove(dst)
                self.post("m_row", iid, T("已停止，删掉了没转完的文件"), "skip")
                break
            good, why = (self.eng.verify_audio(dst, it["dur"]) if rc == 0 and os.path.isfile(dst)
                         else (False, ""))
            if not good:
                remove(dst)
                fail += 1
                short = err.strip().splitlines()[-1] if err.strip() else (why or T("转出来的文件不完整"))
                self.post("m_row", iid, T("失败：") + short[:60], "bad")
                self.log(T("音乐转换失败：{}\n{}").format(os.path.basename(src), err.strip()[-600:]))
                continue
            ok += 1
            status = T("完成 {}，{} -> {}").format(fmt_t(time.time() - start), fmt_size(it["size"]),
                                               fmt_size(os.path.getsize(dst)))
            if lossy_up:
                status += T("（有损转无损，音质不会变好）")
            self.post("m_row", iid, status, "ok")
            self.log(T("已保存到：{}").format(dst))
            if out not in saved_dirs:
                saved_dirs.append(out)
        summary = T("音乐转换完成 {} 个，失败 {} 个，总耗时 {}").format(ok, fail, fmt_t(time.time() - t0))
        if self.m_stop_flag:
            summary = T("已停止。") + summary
        self.post("m_done", summary, saved_dirs)

    def m_run(self, cmd, dur, k, n):
        err = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                    creationflags=NO_WINDOW, universal_newlines=True, encoding="utf-8", errors="ignore")
        except OSError as e:
            return 1, str(e)
        self.m_proc = proc
        start, cur, speed = time.time(), 0.0, "-"
        for line in proc.stdout:
            key, _, v = line.strip().partition("=")
            if key in ("out_time_us", "out_time_ms"):
                try:
                    cur = max(cur, int(v) / 1e6)
                except ValueError:
                    pass
            elif key == "speed":
                speed = v.strip()
            elif key == "progress":
                p = 1.0 if v == "end" else (min(cur / dur, 1.0) if dur > 0 else 0.0)
                self.post("m_cur", p * 100, T("{:.1f}%    速度 {}    已用 {}").format(p * 100, speed, fmt_t(time.time() - start)))
                self.post("m_total", ((k - 1) + p) / n * 100, T("总进度：{}/{}").format(k - 1, n))
        proc.wait()
        self.m_proc = None
        err.seek(0)
        msg = err.read().decode("utf-8", "ignore")
        err.close()
        return proc.returncode, msg

    # ---------- 消息（在 App.poll 里调用） ----------
    def m_handle(self, msg):
        kind = msg[0]
        if kind == "m_add":
            it = msg[1]
            if it["locked"]:
                codec, status, tags = T("加密"), T("{}加密格式，不能转换").format(it["locked"]), ("lock",)
            else:
                codec, status, tags = audio_codec_name(it["acodec"]), "", ()
            iid = self.m_tv.insert("", "end", values=(
                os.path.basename(it["path"]), codec, fmt_t(it["dur"]) if it["dur"] else "—",
                fmt_size(it["size"]), status), tags=tags)
            it["iid"] = iid
            self.m_items.append(it)
        elif kind == "m_scan_prog":
            self.v_m_info.set(T("正在读取音乐信息... {}/{}").format(msg[1], msg[2]))
        elif kind == "m_scan_done":
            self.m_scanning = False
            if msg[1]:
                self.v_m_info.set(msg[1])
            else:
                self.m_update_info()
            self.m_refresh_btns()
        elif kind == "m_row":
            self.m_set(msg[1], msg[2], msg[3])
            if msg[2] == T("转换中...") and self.m_tv.exists(msg[1]):
                self.m_tv.see(msg[1])
        elif kind == "m_cur_name":
            self.v_m_cur_name.set(msg[1])
        elif kind == "m_cur":
            self.m_pb_cur["value"] = msg[1]
            self.v_m_cur_info.set(msg[2])
        elif kind == "m_total":
            self.m_pb_total["value"] = msg[1]
            self.v_m_total_info.set(msg[2])
        elif kind == "m_done":
            self.m_running = False
            self.m_btn_stop.configure(state="disabled")
            if not self.m_stop_flag:
                self.m_pb_total["value"] = 100
            self.v_m_total_info.set(msg[1])
            self.v_m_cur_name.set(T("当前：已结束"))
            self._append_log(msg[1])
            self.m_refresh_btns()
            for d in msg[2]:
                self._append_log(T("文件保存在：") + d)
            self.show_done(msg[1], msg[2])

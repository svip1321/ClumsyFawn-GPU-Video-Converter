# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
主界面布局：顶部头像和选项卡、转换页、日志页、设置页。
"""
import os
import webbrowser
import tkinter as tk
from tkinter import ttk

from . import config as cfg
from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数
from .widgets import RoundButton, bind_wrap, auto_set
from .i18n import ready_langs


class LayoutMixin:
    """搭建主窗口里的各个页面。"""

    def build_ui(self):
        r = self.root
        r.title(T("小鹿包的 GPU 音视频转换器"))
        cfg.SF = max(float(r.tk.call("tk", "scaling")) / 1.3333, 1.0)  # 高分屏放大系数
        # 窗口 16:9；屏幕放不下时按屏幕大小等比例缩小
        w = min(int(1280 * cfg.SF), r.winfo_screenwidth() - 40)
        h = w * 9 // 16
        if h > r.winfo_screenheight() - 90:
            h = r.winfo_screenheight() - 90
            w = h * 16 // 9
        r.geometry("{}x{}".format(w, h))
        r.minsize(min(int(1120 * cfg.SF), w), min(int(630 * cfg.SF), h))
        # 启动时默认最大化（铺满屏幕，保留标题栏和任务栏）；点「还原」时回到上面算好的 16:9 大小
        try:
            r.state("zoomed")
        except tk.TclError:
            try:
                r.attributes("-zoomed", True)  # Linux
            except tk.TclError:
                pass
        r.configure(bg=C_BG)
        dark_titlebar(r)  # 深色模式时标题栏也变深色
        self.setup_style()
        self.load_avatar()

        # 顶部：圆形头像 + 标题 + 选项卡按钮
        head = ttk.Frame(r, padding=(16, 12, 16, 4))
        head.pack(fill="x")
        if self.avatar:
            tk.Label(head, image=self.avatar, bg=C_BG, bd=0).pack(side="left")
        tbox = ttk.Frame(head)
        tbox.pack(side="left", padx=(10, 0))
        ttk.Label(tbox, text=T("小鹿包的 GPU 音视频转换器"), style="AppTitle.TLabel").pack(anchor="w")
        ttk.Label(tbox, text=T("by 粗糙的鹿包"), style="AppSub.TLabel").pack(anchor="w")
        self.tab_btns = {}
        tabbar = ttk.Frame(head)
        tabbar.pack(side="right")

        nb = ttk.Notebook(r, style="Hidden.TNotebook")
        self.nb = nb
        self.tab_convert = ttk.Frame(nb, padding=(16, 8, 16, 8))
        self.tab_music = ttk.Frame(nb, padding=(16, 8, 16, 8))
        self.tab_log = ttk.Frame(nb, padding=(16, 8, 16, 8))
        self.tab_set = ttk.Frame(nb, padding=(16, 8, 4, 8))
        for frame, name in ((self.tab_convert, T("视频转换")), (self.tab_music, T("音乐转换")),
                            (self.tab_log, T("日志")), (self.tab_set, T("设置"))):
            nb.add(frame, text=name)
            b = RoundButton(tabbar, name, lambda f=frame: self.nb.select(f), kind="tab", bg=C_BG,
                            width=int(96 * cfg.SF))
            b.pack(side="left", padx=(8, 0))
            self.tab_btns[str(frame)] = b

        # 底部版权
        foot = ttk.Frame(r, padding=(16, 0, 16, 8))
        foot.pack(side="bottom", fill="x")
        # 从右往左：X 账号（可以点）· 禁止商用 · 版权
        xl = tk.Label(foot, text="X @svip1321", fg=C_ACCENT, bg=C_BG, cursor="hand2", font=FONT_SMALL + ("underline",))
        xl.pack(side="right")
        xl.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_X_URL))
        ttk.Label(foot, text=T("Copyright © 2026 粗糙的鹿包  ·  All Rights Reserved") + "  ·  ", style="Foot.TLabel").pack(side="right")
        tk.Label(foot, text=T("禁止商用"), fg=C_BAD, bg=C_BG, font=FONT_SMALL + ("bold",)).pack(side="left")
        nb.pack(fill="both", expand=True)

        self.build_convert_tab()
        self.build_music_tab()
        self.build_log_tab()
        self.build_set_tab()
        self.refresh_tabs()

        if cfg.HAS_DND:
            r.drop_target_register(cfg.DND_FILES)
            r.dnd_bind("<<Drop>>", self.on_drop)

    def load_avatar(self):
        """从 assets 文件夹加载圆形头像，按屏幕缩放挑最合适的尺寸。窗口图标用单独的 ico.png（不用头像）。"""
        self.avatar = self.avatar_big = None
        sizes = [k for k in AVATAR_SIZES if asset_ok("avatar_%d.png" % k)]  # 被换掉的头像（SHA256 不对）不用
        try:
            if sizes:
                pic = lambda k: tk.PhotoImage(master=self.root, file=os.path.join(ASSET_DIR, "avatar_%d.png" % k))
                self.avatar = pic(min(sizes, key=lambda k: abs(k - 48 * cfg.SF)))
                self.avatar_big = pic(min(sizes, key=lambda k: abs(k - 88 * cfg.SF)))
        except Exception:
            pass
        try:  # 软件图标：assets\ico.png（没有或者被换掉了就用系统默认图标）
            if not asset_ok(ICON_PNG):
                raise OSError(ICON_PNG)
            icon = tk.PhotoImage(master=self.root, file=os.path.join(ASSET_DIR, ICON_PNG))
            k = max(1, icon.width() // 64)  # 大图缩小一点再交给系统，任务栏图标更清楚
            self._icons = [icon.subsample(k, k) if k > 1 else icon]
            self.root.iconphoto(True, *self._icons)
        except Exception:
            pass

    def refresh_tabs(self):
        cur = self.nb.select()
        for key, b in self.tab_btns.items():
            b.set_selected(key == cur)

    def build_convert_tab(self):
        t = self.tab_convert

        # GPU 没就绪时显示的提示条。外面套一个盒子：出现 / 消失时只改盒子的高度，做出 Q 弹的动画
        self.banner_box = tk.Frame(t, bg=C_BG, height=0, bd=0, highlightthickness=0)
        self.banner_box.pack_propagate(False)
        self.gpu_banner = tk.Label(self.banner_box, text="", bg=C_BANNER, fg="white", anchor="w", justify="left",
                                   padx=12, pady=8, font=FONT_BOLD, width=1)
        self.gpu_banner.place(x=0, y=0, relwidth=1)
        bind_wrap(self.gpu_banner, 24)
        # 窗口变宽变窄、文字换行变了时，提示条的高度跟着变（动画进行中不打扰）
        self.gpu_banner.bind("<Configure>", lambda e: self._banner_fit(), add="+")

        # 底部按钮先固定住
        bf = ttk.Frame(t)
        bf.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_start = RoundButton(bf, T("开始转换"), self.start, kind="accent", bg=C_BG, state="disabled",
                                     width=int(120 * cfg.SF))
        self.btn_start.pack(side="left")
        self.btn_stop = RoundButton(bf, T("停止"), self.stop, bg=C_BG, state="disabled", width=int(90 * cfg.SF))
        self.btn_stop.pack(side="left", padx=(10, 0))
        RoundButton(bf, T("打开输出文件夹"), self.open_output, bg=C_BG).pack(side="right")
        RoundButton(bf, T("清空列表"), self.clear_list, bg=C_BG).pack(side="right", padx=(0, 10))
        RoundButton(bf, T("移除选中"), self.remove_selected, bg=C_BG).pack(side="right", padx=(0, 10))

        # 主体：左右两栏（16:9 宽屏）
        body = ttk.Frame(t)
        body.pack(fill="both", expand=True)
        self.top_row = body  # 警告条显示在它上面
        body.columnconfigure(0, weight=5, uniform="cols")
        body.columnconfigure(1, weight=6, uniform="cols")
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---------- 左栏 ----------
        # ① 选择视频
        o1, c1 = self.card(left, T("请选择需要转换的视频"))
        o1.pack(fill="x")
        c1.columnconfigure(0, weight=1)
        ent = ttk.Entry(c1, textvariable=self.v_path, font=FONT)
        ent.grid(row=1, column=0, columnspan=3, sticky="ew")
        ent.bind("<Return>", lambda e: self.scan([clean_path(self.v_path.get())]))
        bx = ttk.Frame(c1, style="Card.TFrame")
        bx.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for i, (txt, cmd) in enumerate(((T("读取路径"), lambda: self.scan([clean_path(self.v_path.get())])),
                                        (T("选择视频"), self.pick_files), (T("选择文件夹"), self.pick_dir))):
            bx.columnconfigure(i, weight=1, uniform="pick")
            RoundButton(bx, txt, cmd, bg=C_CARD).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
        hint = (T("可以直接把视频或文件夹拖进窗口，也可以把路径粘贴到输入框后按回车") if cfg.HAS_DND else
                T("可以把路径粘贴到输入框后按回车。小提示：pip install tkinterdnd2 后，还能直接把视频拖进窗口"))
        self.wrap_label(c1, hint).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # ② 格式转换
        oa, ca = self.card(left, T("格式转换"))
        oa.pack(fill="x", pady=(10, 0))
        ca.columnconfigure(2, weight=1)
        ttk.Label(ca, text=T("目标格式"), style="Key.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        self.cb_target = ttk.Combobox(ca, textvariable=self.v_target, values=TARGETS, width=9, state="readonly",
                                      font=FONT_BOLD)
        self.cb_target.grid(row=1, column=1, sticky="w")
        self.lbl_target_hint = self.wrap_label(ca, textvariable=self.v_target_hint)
        self.lbl_target_hint.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # ③ 格式纠正
        ob, cb0 = self.card(left, T("格式纠正"))
        ob.pack(fill="both", expand=True, pady=(10, 0))  # 拉伸到底，和右边进度那块的底边对齐
        cb0.columnconfigure(0, weight=1)
        cb0.rowconfigure(1, weight=1)
        # 内容放进可以上下滚动的区域：窗口放不下时滚动查看，不改变窗口大小
        sh, cb = self.scroll_area(cb0, bg=C_CARD, style="Card.TFrame")
        sh.grid(row=1, column=0, sticky="nsew")
        cb.columnconfigure(0, weight=1)
        self.wrap_buttons(cb, "Fix.TCheckbutton", pad=70)
        ttk.Checkbutton(cb, text=T("启用文件夹视频格式纠正"), variable=self.v_only_mpeg, style="Fix.TCheckbutton",
                        command=self.on_only_mpeg).grid(row=1, column=0, sticky="w")
        ind = int(16 * cfg.SF) + 8  # 和勾选框文字对齐的缩进
        self.wrap_label(cb, T("把兼容性差的视频纠正成手机、电视、电脑都能正常播放的 mp4；下面没勾选的问题不会处理")).grid(
            row=2, column=0, sticky="ew", padx=(ind, 0))
        for i, (var, title, desc) in enumerate((
                (self.v_fix_mpeg, T("纠正 MPEG 编码（MPEG-1 / 2 / 4）"),
                 T("很老的编码：同样画质文件大好几倍，很多手机、电视、剪辑软件放不了")),
                (self.v_fix_av1, T("纠正 AV1 编码（注意：不是 .avi 文件）"),
                 T("很新的编码：老手机、老电脑、部分电视没有硬件解码，会卡顿甚至放不了")),
                (self.v_fix_audio, T("纠正苹果设备没声音的 mp4（音频纠正）"),
                 T("声音是 MP3、OPUS、FLAC 等编码时，Windows 能放，iPhone / iPad / Mac 却没声音。纠正时画面原样复制不动，"
                   "只把这条声音换成苹果支持的 AAC（320k 最高码率，原采样率和声道不变，听不出区别）")))):
            ttk.Checkbutton(cb, text=title, variable=var, command=self.on_fix_change, style="Fix.TCheckbutton").grid(
                row=3 + i * 2, column=0, sticky="w", padx=(ind, 0), pady=(6, 0))
            self.wrap_label(cb, desc).grid(row=4 + i * 2, column=0, sticky="ew", padx=(ind * 2, 0))

        # ---------- 右栏 ----------
        # ④ 通用设置
        oc, cc = self.card(right, T("通用设置"))
        oc.pack(fill="x")
        cc.columnconfigure(1, weight=1)
        ttk.Label(cc, text=T("编码方式"), style="Key.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        self.lbl_enc_info = self.wrap_label(cc, textvariable=self.v_enc_info, style="Key.TLabel")
        self.lbl_enc_info.grid(row=1, column=1, sticky="ew")
        ttk.Label(cc, text=T("原视频"), style="Key.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=(8, 0))
        self.lbl_del_info = self.wrap_label(cc, textvariable=self.v_del_info, style="Key.TLabel")
        self.lbl_del_info.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        RoundButton(cc, T("去设置修改"), lambda: self.nb.select(self.tab_set), bg=C_CARD).grid(
            row=1, column=2, rowspan=2, sticky="e", padx=(10, 0))
        ttk.Label(cc, text=T("输出位置"), style="Key.TLabel").grid(row=3, column=0, sticky="nw", padx=(0, 16), pady=(8, 0))
        self.wrap_label(cc, textvariable=self.v_out_info, style="Card.TLabel").grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        ob_ = ttk.Frame(cc, style="Card.TFrame")
        ob_.grid(row=4, column=1, columnspan=2, sticky="w", pady=(6, 0))
        RoundButton(ob_, T("指定输出文件夹"), self.pick_out_dir, bg=C_CARD).pack(side="left")
        RoundButton(ob_, T("恢复默认"), self.reset_out_dir, bg=C_CARD).pack(side="left", padx=(8, 0))

        # ⑥ 进度（先固定在右栏底部）
        o4, c4 = self.card(right)
        o4.pack(side="bottom", fill="x", pady=(10, 0))
        c4.columnconfigure(0, weight=1)
        ttk.Label(c4, textvariable=self.v_cur_name, style="Key.TLabel").grid(row=0, column=0, sticky="w")
        self.lbl_cur_info = self.wrap_label(c4, textvariable=self.v_cur_info)
        self.lbl_cur_info.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.pb_cur = ttk.Progressbar(c4, maximum=100)
        self.pb_cur.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(c4, textvariable=self.v_total_info, style="Key.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.pb_total = ttk.Progressbar(c4, maximum=100)
        self.pb_total.grid(row=4, column=0, sticky="ew", pady=(4, 0))

        # ⑤ 视频列表（占满剩下的高度）
        o3, c3 = self.card(right)
        o3.pack(fill="both", expand=True, pady=(10, 0))
        c3.columnconfigure(0, weight=1)
        c3.rowconfigure(1, weight=1)
        self.wrap_label(c3, textvariable=self.v_mpeg_info, style="Info.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        cols = ("name", "codec", "size", "status")
        tv = ttk.Treeview(c3, columns=cols, show="headings", selectmode="extended", height=4)
        # 文件名、状态两列有最小宽度：窗口放不下时出现左右滚动条，长的文件名和状态也能完整看到
        for c, txt, w, mw, anc in (("name", T("文件名"), 200, 160, "w"), ("codec", T("编码"), 110, 90, "center"),
                                   ("size", T("大小"), 80, 70, "center"), ("status", T("状态"), 240, 200, "w")):
            tv.heading(c, text=txt, anchor=anc)
            tv.column(c, width=int(w * cfg.SF), minwidth=int(mw * cfg.SF), anchor=anc,
                      stretch=(c in ("name", "status")))
        # 文件名、状态两列会按最长的文字自动变宽：放不下时才出现左右滚动条
        self.tree_scroll(c3, tv, fit={"name": int(160 * cfg.SF), "status": int(200 * cfg.SF)})
        tv.tag_configure("mpeg", foreground=C_INFO)
        tv.tag_configure("skip", foreground=C_MUTED)
        tv.tag_configure("ok", foreground=C_OK)
        tv.tag_configure("bad", foreground=C_BAD)
        self.tv = tv

    def build_log_tab(self):
        t = self.tab_log
        bf = ttk.Frame(t)
        bf.pack(side="bottom", fill="x", pady=(12, 0))
        RoundButton(bf, T("清空日志"), self.clear_log, bg=C_BG).pack(side="right")
        o, c = self.card(t, T("运行日志"))
        o.pack(fill="both", expand=True)
        c.columnconfigure(0, weight=1)
        c.rowconfigure(1, weight=1)
        self.log_box = tk.Text(c, wrap="word", height=10, state="disabled", relief="flat", bd=0,
                               bg=C_LOG, fg=C_TEXT, insertbackground=C_TEXT, selectbackground=C_SEL,
                               selectforeground=C_TEXT, padx=10, pady=8, font=FONT_MONO,
                               highlightthickness=1, highlightbackground=C_BORDER)
        self.log_box.grid(row=1, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(c, orient="vertical", command=self.log_box.yview)  # 和其他页面同一种滚动条，日志多了才出现
        lsb.grid(row=1, column=1, sticky="ns")
        lsb.grid_remove()
        self.log_box.configure(yscrollcommand=auto_set(lsb, lsb.grid, lsb.grid_remove))

    def build_set_tab(self):
        holder, t = self.scroll_area(self.tab_set)
        holder.pack(fill="both", expand=True)

        # 用户界面（语言）
        o0, c = self.card(t, T("用户界面"))
        o0.pack(fill="x", pady=(0, 12))
        c.columnconfigure(4, weight=1)
        ttk.Label(c, text=T("语言") + " / Language", style="Key.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        ttk.Combobox(c, textvariable=self.v_lang, values=[n for _, n in ready_langs()], state="readonly",
                     font=FONT_BOLD, width=16).grid(row=1, column=1, sticky="w")
        # 外观（右边原来空着的地方）：浅色 / 深色 / 跟随系统
        ttk.Label(c, text=T("外观"), style="Key.TLabel").grid(row=1, column=2, sticky="w", padx=(40, 16))
        ttk.Combobox(c, textvariable=self.v_theme, values=[self.theme_names()[k] for k in THEMES], state="readonly",
                     font=FONT_BOLD, width=12).grid(row=1, column=3, sticky="w")
        self.wrap_label(c, T("切换语言或外观并保存设置后，重启软件才会生效")).grid(row=1, column=4, sticky="ew", padx=(12, 0))

        # ffmpeg 与画质
        o1, c = self.card(t, T("转换设置"))
        o1.pack(fill="x")
        c.columnconfigure(1, weight=1)
        ttk.Label(c, text=T("ffmpeg 路径"), style="Key.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        ttk.Entry(c, textvariable=self.v_ffmpeg, font=FONT).grid(row=1, column=1, sticky="ew")
        RoundButton(c, T("浏览"), self.pick_ffmpeg, bg=C_CARD, width=int(70 * cfg.SF)).grid(
            row=1, column=2, sticky="ew", padx=(10, 0))
        self.btn_ff = RoundButton(c, T("检测 ffmpeg"), lambda: self.check_ffmpeg(manual=True), bg=C_CARD)
        self.btn_ff.grid(row=1, column=3, sticky="ew", padx=(8, 0))
        self.lbl_ff = self.wrap_label(c, textvariable=self.v_ff)
        self.lbl_ff.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(6, 0))
        hl = ttk.Frame(c, style="Card.TFrame")
        hl.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(2, 14))
        hl.columnconfigure(0, weight=1)
        self.wrap_label(hl, T("已加进环境变量就填 ffmpeg；否则填完整路径，例如 C:\\ffmpeg\\bin\\ffmpeg.exe")).grid(
            row=0, column=0, sticky="ew")
        self.link(hl, T("还没装 ffmpeg？查看安装方法"), self.show_ffmpeg_help).grid(row=0, column=1, sticky="e", padx=(10, 0))

        ttk.Label(c, text=T("画质（CQ）"), style="Key.TLabel").grid(row=4, column=0, sticky="w", padx=(0, 16))
        fr = ttk.Frame(c, style="Card.TFrame")
        fr.grid(row=4, column=1, columnspan=3, sticky="w")
        ttk.Spinbox(fr, from_=10, to=35, textvariable=self.v_cq, width=6, font=FONT_BOLD).pack(side="left")
        ttk.Label(fr, text=T("所有目标格式通用"), style="Sub.TLabel").pack(side="left", padx=(12, 0))
        self.wrap_label(c, T("数字越小画质越好、文件越大。19 接近无损（默认），23 体积大约减半，肉眼基本看不出差别。"
                           ".mp4 / .mkv / .mov / .ts / .m4v 文件用 HEVC 编码，.avi / .flv 文件用 H.264 编码，"
                           "同样的数字画质一样，只是 H.264 的文件会大一些")).grid(
            row=5, column=1, columnspan=3, sticky="ew", pady=(6, 0))

        # 原视频处理
        o2, c = self.card(t, T("原视频处理方式"))
        o2.pack(fill="x", pady=(12, 0))
        c.columnconfigure(0, weight=1)
        opts = (("keep", T("保留原视频（不删除）")),
                ("trash", T("放进回收站（推荐，删错了还能找回来）")),
                ("delete", T("永久删除（无法找回，最省空间）")))
        for i, (val, txt) in enumerate(opts, 1):
            rb = ttk.Radiobutton(c, text=txt, value=val, variable=self.v_del_mode, style="Del.TRadiobutton")
            rb.grid(row=i, column=0, sticky="w")
            if val == "trash" and not TRASH_OK:
                rb.configure(state="disabled", text=txt + T("  —— 需要先 pip install send2trash"))
        self.wrap_buttons(c, "Del.TRadiobutton")
        self.wrap_label(c, T("只会处理转换成功、并且检查能正常播放的视频；转换失败或检查没通过的原视频一定会保留")).grid(
            row=4, column=0, sticky="ew", pady=(6, 0))

        # 编码方式（左） + 投喂鹿包（右，放在原来空着的那块地方）
        row3 = ttk.Frame(t)
        row3.pack(fill="x", pady=(12, 0), before=o2)  # 放在「原视频处理方式」上面
        row3.columnconfigure(0, weight=3, uniform="r3")
        row3.columnconfigure(1, weight=2, uniform="r3")

        o3, c = self.card(row3, T("编码方式（显卡加速）"))
        o3.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        c.columnconfigure(0, weight=1)
        self.backend_radios = {}
        choices = [("auto", T("自动（推荐：按 NVIDIA → AMD → Intel 的顺序挑能用的显卡）"))] + \
                  [(b["id"], b["name"]) for b in BACKENDS]
        for i, (bid, txt) in enumerate(choices, 1):
            rb = ttk.Radiobutton(c, text=txt, value=bid, variable=self.v_backend, style="Enc.TRadiobutton")
            rb.grid(row=i, column=0, sticky="w")
            self.backend_radios[bid] = (rb, txt)
        self.wrap_buttons(c, "Enc.TRadiobutton")
        self.wrap_label(c, T("显卡加速比 CPU 快很多倍；CPU 只在电脑没有可用显卡时用，转换会慢一些，但画质设置一样有效")).grid(
            row=len(choices) + 1, column=0, sticky="ew", pady=(4, 10))
        gf = ttk.Frame(c, style="Card.TFrame")
        gf.grid(row=len(choices) + 2, column=0, sticky="ew")
        gf.columnconfigure(1, weight=1)
        self.btn_gpu = RoundButton(gf, T("重新检测"), lambda: self.check_gpu(manual=True), bg=C_CARD)
        self.btn_gpu.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        self.gpu_box = ttk.Frame(gf, style="Card.TFrame")  # 检测结果：每种编码方式一行，能用绿色、没检测到红色
        self.gpu_box.grid(row=0, column=1, sticky="ew", pady=(4, 0))
        self.gpu_box.columnconfigure(0, weight=1)
        self.set_gpu_lines([(self.v_gpu.get(), "Sub.TLabel")])

        # 投喂鹿包：独立卡片，内容居中
        o4 = tk.Frame(row3, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        o4.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        o4.columnconfigure(0, weight=1)
        o4.rowconfigure(0, weight=1)
        box = ttk.Frame(o4, style="Card.TFrame", padding=(20, 16))
        box.grid(row=0, column=0)  # 不贴边 = 在卡片里上下左右都居中
        box.columnconfigure(0, weight=1)
        if self.avatar_big:
            tk.Label(box, image=self.avatar_big, bg=C_CARD, bd=0).grid(row=0, column=0, pady=(0, 10))
        ttk.Label(box, text=T("投喂鹿包"), style="AppTitle.TLabel", background=C_CARD).grid(row=1, column=0)
        msg = ttk.Label(box, text=T("觉得好用的话，可以请鹿包喝杯奶茶～\n投喂完全随心意，不投喂也能一直免费用哦"),
                        style="Sub.TLabel", justify="center", anchor="center")
        msg.grid(row=2, column=0, pady=(6, 14))
        RoundButton(box, T("投喂鹿包 ♥"), self.show_feed, kind="accent", bg=C_CARD, width=int(180 * cfg.SF)).grid(
            row=3, column=0)

        bf = ttk.Frame(t)
        bf.pack(fill="x", pady=(14, 4))
        RoundButton(bf, T("保存设置"), self.apply_settings, kind="accent", bg=C_BG, width=int(120 * cfg.SF)).pack(side="left")

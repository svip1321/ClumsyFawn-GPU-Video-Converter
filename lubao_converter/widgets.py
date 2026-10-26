# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
自定义控件和界面小部件：圆角按钮、蓝灰色勾选框、自动换行、卡片、滚动区域、整体样式。
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import config as cfg
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数


def make_indicator(kind, size, master=None):
    """画勾选框/单选框图片。右边留 8px 空白当作和文字的间距。"""
    def mix(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))

    def cover(d):  # 距离 -> 覆盖率，做简单抗锯齿
        return min(max(0.5 - d, 0.0), 1.0)

    def seg(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5

    gap = 8
    n, c = size, (size - 1) / 2.0
    on, dis = kind.endswith("_on"), kind.endswith("_dis")
    edge = C_IND_DIS_EDGE if dis else (C_ACCENT if on else C_IND_EDGE)
    fill = C_IND_DIS_FILL if dis else (C_ACCENT if on and kind.startswith("chk") else C_IND_FILL)
    bw = max(1.2, size / 12.0)
    rows = []
    for y in range(n):
        row = []
        for x in range(n):
            if kind.startswith("chk"):
                r = size * 0.24
                qx = max(abs(x - c) - (c - 0.5 - r), 0.0)
                qy = max(abs(y - c) - (c - 0.5 - r), 0.0)
                d = (qx * qx + qy * qy) ** 0.5 - r          # 圆角矩形的有向距离
                col = mix(C_CARD, edge, cover(d))
                col = mix(col, fill, cover(d + bw))
                if on:
                    u, v = x / float(n - 1), y / float(n - 1)
                    dd = min(seg(u, v, 0.26, 0.52, 0.43, 0.69), seg(u, v, 0.43, 0.69, 0.75, 0.33)) * (n - 1)
                    col = mix(col, "#ffffff", cover(dd - size * 0.07))
            else:
                R = c - 0.5
                d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
                col = mix(C_CARD, edge, cover(d - R))
                col = mix(col, fill, cover(d - R + bw))
                if on:
                    col = mix(col, C_ACCENT, cover(d - size * 0.24))
            row.append(col)
        row += [C_CARD] * gap
        rows.append("{" + " ".join(row) + "}")
    img = tk.PhotoImage(master=master, width=n + gap, height=n)
    img.put(" ".join(rows))
    return img


def auto_set(sb, show, hide):
    """滚动条只在内容溢出时显示：返回给 xscrollcommand / yscrollcommand 用的函数。"""
    def setter(lo, hi):
        sb.set(lo, hi)
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            if sb.winfo_ismapped():
                hide()
        elif not sb.winfo_ismapped():
            show()
    return setter


def debounce(widget, name, ms, fn):
    """连续触发时只在最后一次之后 ms 毫秒执行一次（最大化 / 还原时窗口大小会连着变好多次）。"""
    job = getattr(widget, name, None)
    if job:
        try:
            widget.after_cancel(job)
        except tk.TclError:
            pass

    def run():
        setattr(widget, name, None)
        try:
            fn()
        except tk.TclError:  # 控件已经关掉了
            pass
    setattr(widget, name, widget.after(ms, run))


def bind_wrap(label, pad=4):
    """让文字按控件的实际宽度自动换行；宽度变化不到 2 像素就不更新，避免来回抖动。
    窗口大小连续变化时（最大化 / 还原）等停下来再统一换行，不然几十个文字一起反复重排，界面会闪黑块。"""
    def apply():
        wl = max(label.winfo_width() - pad, 60)
        if abs(getattr(label, "_wl", 0) - wl) >= 2:
            label._wl = wl
            label.configure(wraplength=wl)
    label.bind("<Configure>", lambda e: debounce(label, "_wrap_job", 30, apply), add="+")


class RoundButton(tk.Canvas):
    """自己画的圆角按钮：高度统一、有边框、鼠标悬停变色、按下时平滑缩小再弹回。"""
    COLORS = {
        #          底色       悬停       按下       边框       悬停边框   文字
        "normal": (C_CARD, C_BTN_HOV, C_BTN_PRS, C_BTN_LINE, C_ACCENT, C_TEXT),
        "accent": (C_ACCENT, C_ACCENT_D, C_ACC_PRS, C_ACCENT, C_ACCENT_D, "#ffffff"),
        "tab": (C_TAB, C_TAB_HOV, C_TAB_PRS, C_TAB, C_TAB_HOV, C_TAB_TXT),
    }

    def __init__(self, parent, text, command=None, kind="normal", bg=C_BG, width=None, state="normal"):
        self.text, self.command, self.kind, self.state = text, command, kind, state
        self.selected = self.hover = self.pressed = False
        self.scale, self.target, self._anim = 1.0, 1.0, None
        self.font = tkfont.Font(font=FONT_BOLD)
        h = int(round(36 * cfg.SF))
        w = max(width or 0, self.font.measure(text) + int(36 * cfg.SF))
        tk.Canvas.__init__(self, parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0,
                           cursor="hand2" if state == "normal" else "arrow")
        self._size = None
        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False, target=1.0))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    # 兼容 ttk.Button 的 configure(state=..., text=...)
    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if "state" in kw:
            self.state = kw.pop("state")
            tk.Canvas.configure(self, cursor="hand2" if self.state == "normal" else "arrow")
        if "text" in kw:
            self.text = kw.pop("text")
        if kw:
            tk.Canvas.configure(self, **kw)
        self.redraw()
    config = configure

    def _on_resize(self, e):
        if (e.width, e.height) != self._size:  # 尺寸没变就不重画
            self._size = (e.width, e.height)
            self.redraw()

    def set_selected(self, sel):
        self.selected = sel
        self.redraw()

    def _set(self, **kw):
        for k, v in kw.items():
            if k == "target":
                self._animate(v)
            else:
                setattr(self, k, v)
        self.redraw()

    def _press(self, e):
        if self.state != "normal":
            return
        self.pressed = True
        self._animate(0.92)

    def _release(self, e):
        was = self.pressed
        self.pressed = False
        self._animate(1.0)
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        if was and inside and self.state == "normal" and self.command:
            self.after(90, self.command)  # 等弹回动画走一半再执行，手感更自然

    def _animate(self, target):
        self.target = target
        if self._anim is None:
            self._step()

    def _step(self):
        diff = self.target - self.scale
        if abs(diff) < 0.004:
            self.scale, self._anim = self.target, None
            self.redraw()
            return
        self.scale += diff * 0.35
        self.redraw()
        self._anim = self.after(12, self._step)

    def redraw(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = int(self["width"]), int(self["height"])
        base, hov, prs, line, hline, fg = self.COLORS[self.kind]
        if self.kind == "tab" and self.selected:
            base, hov, prs, line, hline, fg = C_ACCENT, C_ACCENT, C_ACCENT_D, C_ACCENT, C_ACCENT, "#ffffff"
        if self.state != "normal":
            if self.kind == "accent":
                fill, outline, fg = C_ACC_DIS, C_ACC_DIS, "#ffffff" if not DARK else C_DIS_FG
            else:
                fill, outline, fg = C_DIS_FILL, C_DIS_LINE, C_DIS_FG
        elif self.pressed:
            fill, outline = prs, hline
        elif self.hover:
            fill, outline = hov, hline
        else:
            fill, outline = base, line
        s = self.scale
        dx, dy = (1 - s) * w / 2.0, (1 - s) * h / 2.0
        x1, y1, x2, y2 = dx + 1, dy + 1, w - dx - 2, h - dy - 2
        r = min((y2 - y1) / 2.0, 10 * cfg.SF)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=1)
        self.create_text(w / 2.0, h / 2.0, text=self.text, fill=fg, font=self.font)


class WidgetMixin:
    """App 用到的界面小工具（样式、卡片、换行文字、链接、滚动区域）。"""

    def setup_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")  # clam 主题可以自定义颜色，各系统显示一致
        except tk.TclError:
            pass
        st.configure(".", background=C_BG, foreground=C_TEXT, font=FONT, bordercolor=C_BORDER,
                     lightcolor=C_BORDER, darkcolor=C_BORDER, focuscolor=C_ACCENT)
        st.configure("TFrame", background=C_BG)
        st.configure("Card.TFrame", background=C_CARD)
        st.configure("TLabel", background=C_BG)
        st.configure("Card.TLabel", background=C_CARD)
        st.configure("Key.TLabel", background=C_CARD, font=FONT_BOLD)
        st.configure("Sub.TLabel", background=C_CARD, foreground=C_SUB)
        st.configure("Title.TLabel", background=C_CARD, font=FONT_TITLE)
        st.configure("Info.TLabel", background=C_CARD, foreground=C_INFO, font=FONT_BOLD)
        st.configure("Ok.TLabel", background=C_CARD, foreground=C_OK, font=FONT_BOLD)
        st.configure("Bad.TLabel", background=C_CARD, foreground=C_BAD, font=FONT_BOLD)
        st.configure("AppTitle.TLabel", background=C_BG, font=FONT_BIG)
        st.configure("AppSub.TLabel", background=C_BG, foreground=C_INFO, font=FONT_BOLD)
        st.configure("Foot.TLabel", background=C_BG, foreground=C_FOOT, font=FONT_SMALL)

        # 隐藏 Notebook 自带的选项卡，用顶部自己画的按钮切换
        st.layout("Hidden.TNotebook.Tab", [])
        st.configure("Hidden.TNotebook", background=C_BG, borderwidth=0, padding=0, tabmargins=0)

        sel = dict(selectbackground=C_SEL, selectforeground=C_TEXT, insertcolor=C_TEXT, foreground=C_TEXT)
        st.configure("TEntry", fieldbackground=C_FIELD, padding=6, **sel)
        st.configure("TCombobox", fieldbackground=C_FIELD, background=C_CARD, padding=5, arrowsize=14,
                     arrowcolor=C_SUB, **sel)
        st.map("TCombobox", fieldbackground=[("readonly", C_FIELD), ("disabled", C_BG)],
               foreground=[("disabled", C_SUB)], selectbackground=[("readonly", C_FIELD)],
               selectforeground=[("readonly", C_TEXT)], background=[("active", C_BTN_HOV)])
        st.configure("TSpinbox", fieldbackground=C_FIELD, background=C_CARD, padding=5, arrowsize=12,
                     arrowcolor=C_SUB, **sel)
        # 下拉框弹出的选项列表（它是普通 Listbox，要单独设颜色）
        for k, v in (("background", C_FIELD), ("foreground", C_TEXT), ("selectBackground", C_ACCENT),
                     ("selectForeground", "#ffffff")):
            self.root.option_add("*TCombobox*Listbox." + k, v)

        # 自己画的蓝灰色勾选框 / 单选框（带抗锯齿，跟随高分屏缩放）
        size = max(14, int(round(16 * cfg.SF)))
        self._imgs = {k: make_indicator(k, size, self.root) for k in
                      ("chk_off", "chk_on", "chk_dis", "rad_off", "rad_on", "rad_dis")}
        im = self._imgs
        st.element_create("Pink.Checkbutton.indicator", "image", im["chk_off"],
                          ("disabled", im["chk_dis"]), ("selected", im["chk_on"]))
        st.element_create("Pink.Radiobutton.indicator", "image", im["rad_off"],
                          ("disabled", im["rad_dis"]), ("selected", im["rad_on"]))
        for w, ind in (("TCheckbutton", "Pink.Checkbutton.indicator"), ("TRadiobutton", "Pink.Radiobutton.indicator")):
            base = w[1:]
            st.layout(w, [(base + ".padding", {"sticky": "nswe", "children": [
                (ind, {"side": "left", "sticky": ""}),
                (base + ".focus", {"side": "left", "sticky": "w", "children": [
                    (base + ".label", {"sticky": "nswe"})]})]})])
            st.configure(w, background=C_CARD, padding=(0, 4), focuscolor=C_CARD, font=FONT_BOLD)
            st.map(w, background=[("active", C_CARD)], foreground=[("disabled", C_DIS_TXT)])

        st.configure("Treeview", background=C_FIELD, fieldbackground=C_FIELD, foreground=C_TEXT,
                     rowheight=int(30 * cfg.SF), borderwidth=0)
        st.map("Treeview", background=[("selected", C_SEL)], foreground=[("selected", C_TEXT)])
        st.configure("Treeview.Heading", background=C_HEAD, foreground=C_TEXT, font=FONT_BOLD, relief="flat",
                     padding=(6, 6))
        st.map("Treeview.Heading", background=[("active", C_TAB)])
        st.configure("Horizontal.TProgressbar", troughcolor=C_TROUGH, background=C_ACCENT,
                     bordercolor=C_TROUGH, lightcolor=C_ACCENT, darkcolor=C_ACCENT, thickness=int(10 * cfg.SF))
        # 上下、左右滚动条统一成同一种浅灰蓝色，鼠标放上去稍微变深
        for sb_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(sb_style, background=C_TAB, troughcolor=C_CARD, arrowsize=12,
                         bordercolor=C_CARD, lightcolor=C_TAB, darkcolor=C_TAB, arrowcolor=C_SUB)
            hov = [("pressed", C_SB_PRS), ("active", C_SB_HOV)]
            st.map(sb_style, background=hov, lightcolor=hov, darkcolor=hov)

    def wrap_buttons(self, container, style, pad=40):
        """让 container 里用了 style 样式的单选框 / 勾选框文字按容器宽度自动换行（长语言不会被截断）。"""
        st = ttk.Style()

        def apply():
            w = max(container.winfo_width() - int(pad * cfg.SF), 120)
            if getattr(container, "_btn_wl", 0) != w:
                container._btn_wl = w
                st.configure(style, wraplength=w)
        container.bind("<Configure>", lambda e: debounce(container, "_btn_job", 30, apply), add="+")

    def card(self, parent, title=None):
        """白色卡片：外面一圈浅灰边框，里面是内容区。"""
        outer = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        inner = ttk.Frame(outer, style="Card.TFrame", padding=(16, 10))
        inner.pack(fill="both", expand=True)
        if title:
            ttk.Label(inner, text=title, style="Title.TLabel").grid(row=0, column=0, columnspan=10, sticky="w",
                                                                    pady=(0, 6))
        return outer, inner

    def wrap_label(self, parent, text="", textvariable=None, style="Sub.TLabel"):
        """会根据宽度自动换行的文字。"""
        kw = {"textvariable": textvariable} if textvariable is not None else {"text": text}
        # width=1：文字本身不去撑宽度，宽度只由布局决定，再按实际宽度换行，避免"换行↔布局"死循环
        lbl = ttk.Label(parent, style=style, justify="left", anchor="w", width=1, **kw)
        bind_wrap(lbl)
        return lbl

    def link(self, parent, text, command, bg=C_CARD):
        """可以点击的蓝色链接文字。"""
        lbl = tk.Label(parent, text=text, fg=C_INFO, bg=bg, cursor="hand2",
                       font=FONT_BOLD + ("underline",))
        lbl.bind("<Button-1>", lambda e: command())
        return lbl

    def fit_tree(self, tv):
        """按列表里最长的文件名 / 状态调整列宽：放得下就不出现左右滚动条，文字比列表宽时才出现。"""
        base = getattr(tv, "_fit_base", None)
        if not base:
            return
        if not hasattr(self, "_tree_font"):
            self._tree_font = tkfont.Font(font=FONT)
        kids = tv.get_children()
        want = {}
        for col, mw in base.items():
            need = max([self._tree_font.measure(tv.set(i, col)) for i in kids] + [0]) + int(24 * cfg.SF)
            want[col] = max(mw, need)
        # 列表比内容宽时，多出来的宽度都给最后一列（状态），正好铺满，不会出现多余的滚动条
        fixed = sum(int(tv.column(c, "width")) for c in tv["columns"] if c not in want)
        spare = tv.winfo_width() - 4 - fixed - sum(want.values())
        last = list(want)[-1]
        for col, w in want.items():
            width = w + (spare if col == last and spare > 0 else 0)
            if int(tv.column(col, "width")) != width or int(tv.column(col, "minwidth")) != w:
                tv.column(col, minwidth=w, width=width, stretch=False)

    def tree_scroll(self, parent, tv, row=1, fit=None):
        """给列表加上下、左右两个滚动条（列宽加起来比窗口宽时就能左右拖）；按住 Shift 滚鼠标滚轮也能左右滚。"""
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tv.xview)

        # 内容放得下就藏起滚动条，放不下（溢出）才显示
        tv.configure(yscrollcommand=auto_set(vsb, vsb.grid, vsb.grid_remove),
                     xscrollcommand=auto_set(hsb, hsb.grid, hsb.grid_remove))
        tv.grid(row=row, column=0, sticky="nsew")
        vsb.grid(row=row, column=1, sticky="ns")
        hsb.grid(row=row + 1, column=0, sticky="ew")
        vsb.grid_remove()
        hsb.grid_remove()
        tv._fit_base = fit or {}  # {列名: 最小宽度}：这些列会随内容自动变宽
        if fit:
            tv.bind("<Configure>", lambda e: debounce(tv, "_fit_job", 60, lambda: self.fit_tree(tv)), add="+")

        def hwheel(e):
            tv.xview_scroll(-3 if (e.num == 4 or e.delta > 0) else 3, "units")
            return "break"
        tv.bind("<Shift-MouseWheel>", hwheel)
        tv.bind("<Shift-Button-4>", hwheel)
        tv.bind("<Shift-Button-5>", hwheel)

    def scroll_area(self, parent, bg=C_BG, style=None):
        """可以上下滚动的区域，返回 (外框, 放内容的 Frame)。内容比区域高时才出现滚动条。"""
        holder = ttk.Frame(parent, style=style) if style else ttk.Frame(parent)
        # height=1：不让画布去撑高外面的布局，高度只由外面分到多少决定
        cv = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0, height=1)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(cv, padding=(0, 0, 12, 0), style=style) if style else ttk.Frame(cv, padding=(0, 0, 12, 0))
        win_id = cv.create_window(0, 0, window=body, anchor="nw")

        def sync(e=None):
            cv.configure(scrollregion=cv.bbox("all"))
            need = body.winfo_reqheight() > cv.winfo_height() + 1
            if need and not vsb.winfo_ismapped():
                vsb.pack(side="right", fill="y")
            elif not need and vsb.winfo_ismapped():
                vsb.pack_forget()
                cv.yview_moveto(0)
        body.bind("<Configure>", lambda e: debounce(body, "_sync_job", 40, sync))
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(win_id, width=e.width),
                                          debounce(cv, "_sync_job", 40, sync)))

        def wheel(e):
            if not vsb.winfo_ismapped():
                return
            cv.yview_scroll(-2 if (e.num == 4 or e.delta > 0) else 2, "units")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            holder.bind_all(seq, lambda e: wheel(e) if str(e.widget).startswith(str(holder)) else None, add="+")
        return holder, body

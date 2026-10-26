# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
多语言：代码里所有给人看的文字都写成 T("简体中文原文")，运行时按所选语言查表替换。
语言文件放在 lubao_converter/lang/<语言代码>.json，内容是 {"简体中文原文": "翻译"}。
查不到翻译时显示简体中文原文，所以漏翻也不会报错（检查工具 check_lang.py 会把漏翻找出来）。
切换语言后需要重启软件才生效。
"""
import os
import json

# (语言代码, 用这种语言自己写的名字)
LANGS = [
    ("zh_CN", "简体中文"),
    ("zh_TW", "繁體中文"),
    ("en", "English"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("ru", "Русский"),
    ("pt", "Português"),
]
LANG_CODES = [c for c, _ in LANGS]
LANG_NAMES = dict(LANGS)
SOURCE_LANG = "zh_CN"  # 代码里写的就是简体中文
LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")

_table = {}
current = SOURCE_LANG


def detect_system_lang():
    """按系统语言挑一个默认语言；挑不到就用英文。"""
    code = ""
    if os.name == "nt":
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary = lcid & 0x3FF  # 低 10 位是主语言
            code = {0x04: "zh", 0x09: "en", 0x11: "ja", 0x12: "ko", 0x0A: "es", 0x0C: "fr",
                    0x07: "de", 0x19: "ru", 0x16: "pt"}.get(primary, "")
            if code == "zh":  # 台湾、香港、澳门用繁体
                code = "zh_TW" if lcid in (0x0404, 0x0C04, 0x1404) else "zh_CN"
        except Exception:
            code = ""
    if not code:
        try:
            import locale
            loc = (locale.getdefaultlocale()[0] or "").replace("-", "_")
        except Exception:
            loc = ""
        if loc.startswith("zh"):
            code = "zh_TW" if any(x in loc for x in ("TW", "HK", "MO", "Hant")) else "zh_CN"
        else:
            code = loc.split("_")[0]
    return code if code in LANG_CODES else "en"


def setup(lang):
    """载入语言文件。语言代码不认识时用英文。"""
    global current, _table
    if lang not in LANG_CODES:
        lang = "en"
    current = lang
    _table = {}
    if lang != SOURCE_LANG:
        try:
            with open(os.path.join(LANG_DIR, lang + ".json"), "r", encoding="utf-8") as f:
                _table = {k: v for k, v in json.load(f).items() if isinstance(v, str) and v}
        except Exception:
            _table = {}
    return current


def ready_langs():
    """翻译完成（至少 95% 的条目已翻译）的语言，才放进设置页的语言下拉框；没翻完的先不显示。"""
    out = []
    for code, name in LANGS:
        if code == SOURCE_LANG:
            out.append((code, name))
            continue
        try:
            with open(os.path.join(LANG_DIR, code + ".json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            # 繁体中文、日语里有些条目本来就和简体原文写法一样，只要填了就算翻译过
            same_ok = code in ("zh_TW", "ja")
            done = sum(1 for k, v in data.items() if isinstance(v, str) and v and (v != k or same_ok))
            if data and done >= len(data) * 0.95:
                out.append((code, name))
        except Exception:
            pass
    return out


def T(text):
    """把简体中文原文换成当前语言；查不到就原样返回。需要填数字等内容时：T("共 {} 个").format(n)"""
    return _table.get(text, text)

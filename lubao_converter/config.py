# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
配置：路径、颜色、字体、格式常量等，所有模块共用。
"""

import hashlib
import os
import sys

try:  # 可选：pip install tkinterdnd2 后支持拖入
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False

PKG_DIR = os.path.dirname(os.path.abspath(__file__))       # lubao_converter 文件夹
if getattr(sys, "frozen", False):                           # 打包成 exe 运行时
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))  # exe 所在文件夹
else:
    APP_DIR = os.path.dirname(PKG_DIR)                      # main.pyw 所在文件夹
ASSET_DIR = os.path.join(PKG_DIR, "assets")                 # 头像、收款码图片
CFG_PATH = os.path.join(APP_DIR, "gpu_video_converter_gui.json")
LOG_PATH = os.path.join(APP_DIR, "gpu_video_converter_error.log")  # 出错时把详细信息写在这里
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # 调用 ffmpeg 时不弹黑框

# 语言：启动时就要定下来（下面的常量文字和字体都跟着语言走），所以在这里读设置文件
from .i18n import T, setup as _setup_lang, detect_system_lang, LANGS, LANG_CODES, LANG_NAMES  # LANGS 等给其他模块用（from .config import *）


def _saved(key):
    try:
        import json
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get(key)
    except Exception:
        return None


def _saved_lang():
    return _saved("lang")


LANG = _setup_lang(_saved_lang() or detect_system_lang())

# 外观：浅色 / 深色 / 跟随系统。和语言一样启动时就定下来（所有颜色都跟着变），切换后重启生效
THEMES = ["light", "dark", "system"]


def system_dark():
    """系统是不是深色模式（Windows 看「应用模式」，Mac 看「外观」）。"""
    try:
        if os.name == "nt":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if sys.platform == "darwin":
            import subprocess
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
            return "dark" in r.stdout.lower()
    except Exception:
        pass
    return False


THEME = _saved("theme") if _saved("theme") in THEMES else "light"
DARK = THEME == "dark" or (THEME == "system" and system_dark())

# 界面配色（浅色 / 深色两套，名字一样，代码里直接用 C_xxx）
_LIGHT = dict(
    BG="#f2f4f7", CARD="#ffffff", TAB="#e6e9ee", TEXT="#2b2d33", SUB="#8a8f99", BORDER="#e2e4e9",
    ACCENT="#4a6a8f", ACCENT_D="#3a5675", ACC_PRS="#2e4660", ACC_DIS="#b9c5d4", INFO="#3a5675",
    OK="#2e9b62", BAD="#d93025", BANNER="#d93025",
    FIELD="#ffffff", MUTED="#a0a4ab", FOOT="#a3a8b1", DIS_TXT="#b8bcc4", SEL="#e2e9f2", HEAD="#f7f8fa",
    TROUGH="#eceef2", LOG="#fafbfc", SB_HOV="#d3d7de", SB_PRS="#c9ced6",
    BTN_HOV="#f1f4f8", BTN_PRS="#e3e9f1", BTN_LINE="#d3d7de", TAB_HOV="#dfe2e8", TAB_PRS="#d4d8df", TAB_TXT="#6f7480",
    DIS_FILL="#eef0f3", DIS_LINE="#e2e4e9", DIS_FG="#b5bac3",
    IND_EDGE="#b9bec8", IND_FILL="#ffffff", IND_DIS_EDGE="#d9dce2", IND_DIS_FILL="#f3f4f7")
_DARK = dict(
    BG="#1c1f24", CARD="#262a30", TAB="#30353d", TEXT="#e4e6ea", SUB="#9aa1ab", BORDER="#363b43",
    ACCENT="#5579a3", ACCENT_D="#6889b0", ACC_PRS="#46698f", ACC_DIS="#3a4757", INFO="#8fb0d6",
    OK="#4cc38a", BAD="#ff6b5e", BANNER="#b9372c",
    FIELD="#1e2227", MUTED="#6d737d", FOOT="#6d737d", DIS_TXT="#5d636c", SEL="#34465a", HEAD="#2d3239",
    TROUGH="#1e2227", LOG="#1e2227", SB_HOV="#4a515b", SB_PRS="#565e69",
    BTN_HOV="#2f343c", BTN_PRS="#373d46", BTN_LINE="#424852", TAB_HOV="#3a4049", TAB_PRS="#434a54", TAB_TXT="#aab0b9",
    DIS_FILL="#2a2e34", DIS_LINE="#33383f", DIS_FG="#5d636c",
    IND_EDGE="#6a717c", IND_FILL="#1e2227", IND_DIS_EDGE="#3a3f47", IND_DIS_FILL="#2a2e34")
for _k, _v in (_DARK if DARK else _LIGHT).items():
    globals()["C_" + _k] = _v
# 字体按语言挑：每种文字用系统里最清楚好看的那款
if os.name == "nt":
    _FAM = {"zh_CN": "Microsoft YaHei UI", "zh_TW": "Microsoft JhengHei UI", "ja": "Yu Gothic UI",
            "ko": "Malgun Gothic"}.get(LANG, "Segoe UI")
    _SZ, FONT_MONO = 10, ("Consolas", 10)
elif sys.platform == "darwin":
    _FAM = {"zh_CN": "PingFang SC", "zh_TW": "PingFang TC", "ja": "Hiragino Sans",
            "ko": "Apple SD Gothic Neo"}.get(LANG, "Helvetica Neue")
    _SZ, FONT_MONO = 13, ("Menlo", 12)
else:
    _FAM, _SZ, FONT_MONO = "TkDefaultFont", 10, ("TkFixedFont", 10)
FONT, FONT_BOLD = (_FAM, _SZ), (_FAM, _SZ, "bold")
FONT_TITLE, FONT_BIG, FONT_SMALL = (_FAM, _SZ + 1, "bold"), (_FAM, _SZ + 3, "bold"), (_FAM, _SZ - 1)
SF = 1.0  # 高分屏放大系数，启动时计算

# 视频格式
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".m2ts", ".mts", ".wmv",
              ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".rmvb", ".vob", ".f4v"}
TARGETS = ["mp4", "mkv", "mov", "avi", "flv", "ts", "m4v"]
HEVC_TARGETS = ("mp4", "m4v", "mov", "mkv", "ts")
MPEG_CODECS = {"mpeg1video": "MPEG-1", "mpeg2video": "MPEG-2", "mpeg4": "MPEG-4"}
AV1_CODECS = {"av1": "AV1"}  # 太新的编码，老设备放不了，也是格式纠正的对象
# 苹果设备（iPhone / iPad / Mac）在 mp4 里能放出声音的音频编码；不在这里面的（MP3、OPUS、FLAC、PCM 等）苹果上会没声音
APPLE_AUDIO = {"aac", "alac", "ac3", "eac3"}
AUDIO_FIX_EXTS = (".mp4", ".m4v")  # 音频纠正只看这些文件
# mp4 里不放 MP3：Windows 能放，但苹果设备经常没声音，所以遇到 MP3 会转成 AAC
MP4_AUDIO = {"aac", "ac3", "eac3", "alac"}
AUDIO_OK = {  # 各容器能直接复制的音频编码，None = 全都行
    "mp4": MP4_AUDIO, "m4v": MP4_AUDIO,
    "mov": MP4_AUDIO | {"mp3", "pcm_s16le", "pcm_s24le", "pcm_s16be", "pcm_s24be"},
    "mkv": None,
    "avi": {"mp3", "ac3", "pcm_s16le"},
    "flv": {"aac", "mp3"},
    "ts": {"aac", "mp3", "ac3", "eac3", "mp2"},
}

FFMPEG_DL_URL = "https://www.gyan.dev/ffmpeg/builds/"     # FFmpeg 官网推荐的 Windows 版本
FFMPEG_HOME_URL = "https://ffmpeg.org/download.html"
AUTHOR_X_URL = "https://x.com/svip1321"                  # 作者的 X（原 Twitter）账号     # FFmpeg 官网下载页

DEL_TEXT = {"keep": T("保留原视频（不删除）"),
            "trash": T("转完一个、检查能正常播放后，把原视频放进回收站"),
            "delete": T("转完一个、检查能正常播放后，永久删除原视频（无法找回）")}

AVATAR_SIZES = (32, 48, 64, 72, 96, 128)  # assets 里头像的几种尺寸（圆形，圆外透明）
ICON_PNG = "ico.png"  # 软件图标（窗口左上角、任务栏、exe），放在 assets 里，建议 512x512
# 头像和图标的 SHA256「指纹」：被删掉或换成别的图片（哪怕名字一样），指纹都会对不上，一律当作文件缺失
# 以后自己换了头像 / 图标，要把这里的值改成新文件的 SHA256（PowerShell：Get-FileHash 文件名）
ASSET_SHA256 = {
    "avatar_32.png": "16e61a4f80e9e9fd95ab2c9ad07fd9b858c03d79e1f617dddb583d2aa53cd2aa",
    "avatar_48.png": "bfb850ce32ecdcc1c152011dc0257f7c1fc98a9b008a562c90248724b0301130",
    "avatar_64.png": "b285f01fba325f84317e2d0739e0521b05c949f874de9d8787ba3e1133e4fd4a",
    "avatar_72.png": "b29233b930ed9bc1ace2c380ac6d6686941b3a0660cea543856fa9f0f8756af4",
    "avatar_96.png": "f350aa3cdd77b3d1e2abff167db25e19af3d86da5df06fd1a124511189949782",
    "avatar_128.png": "56cd38f4f4e6dbbbe15c3c6b786aeec84574932de0ad5142688e6141fa543083",
    "ico.png": "9585c2d9b26c414386f825fc805b5cb1740394ce95195bbe9eedd1009c04d157",
}


def asset_ok(name):
    """assets 里的这张图片是不是原装的：文件存在，而且 SHA256 和上面记下的一样。"""
    try:
        with open(os.path.join(ASSET_DIR, name), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() == ASSET_SHA256.get(name)
    except OSError:
        return False


# 编码方式（按这个顺序检测；"自动" 会在三种显卡里挑第一个能用的）
# opts 里是几套候选参数，检测时从上往下试，第一套能用的就用它（兼容新老版本 ffmpeg）；{q} 换成画质数字
BACKENDS = [
    {"id": "nvenc", "name": T("NVIDIA 显卡（NVENC）"), "short": "NVIDIA", "gpu": True,
     "h264": "h264_nvenc", "hevc": "hevc_nvenc", "pix8": "yuv420p", "pix10": "p010le",
     "opts": {"h264": [["-preset", "p6", "-rc", "vbr", "-cq", "{q}", "-b:v", "0"],
                       ["-preset", "slow", "-rc", "vbr", "-cq", "{q}", "-b:v", "0"]],
              "hevc": [["-preset", "p6", "-rc", "vbr", "-cq", "{q}", "-b:v", "0"],
                       ["-preset", "slow", "-rc", "vbr", "-cq", "{q}", "-b:v", "0"]]}},
    {"id": "amf", "name": T("AMD 显卡（AMF）"), "short": "AMD", "gpu": True,
     "h264": "h264_amf", "hevc": "hevc_amf", "pix8": "nv12", "pix10": "p010le",
     "opts": {"h264": [["-quality", "quality", "-rc", "cqp", "-qp_i", "{q}", "-qp_p", "{q}", "-qp_b", "{q}"],
                       ["-rc", "cqp", "-qp_i", "{q}", "-qp_p", "{q}"]],
              "hevc": [["-quality", "quality", "-rc", "cqp", "-qp_i", "{q}", "-qp_p", "{q}"],
                       ["-rc", "cqp", "-qp_i", "{q}", "-qp_p", "{q}"]]}},
    {"id": "qsv", "name": T("Intel 核显（QSV）"), "short": "Intel", "gpu": True,
     "h264": "h264_qsv", "hevc": "hevc_qsv", "pix8": "nv12", "pix10": "p010le",
     "opts": {"h264": [["-preset", "slow", "-global_quality", "{q}"], ["-global_quality", "{q}"], ["-q:v", "{q}"]],
              "hevc": [["-preset", "slow", "-global_quality", "{q}"], ["-global_quality", "{q}"], ["-q:v", "{q}"]]}},
    {"id": "cpu", "name": T("CPU（不用显卡）"), "short": "CPU", "gpu": False,
     "h264": "libx264", "hevc": "libx265", "pix8": "yuv420p", "pix10": "yuv420p10le",
     "opts": {"h264": [["-preset", "medium", "-crf", "{q}"]],
              "hevc": [["-preset", "medium", "-crf", "{q}", "-x265-params", "log-level=error"]]}},
]
BACKEND_BY_ID = {b["id"]: b for b in BACKENDS}
BACKEND_CHOICES = ["auto"] + [b["id"] for b in BACKENDS]


# ============================== 音乐转换 ==============================
# 能读取的音乐格式（也能从常见视频里直接提取音轨）
AUDIO_IN_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma", ".ape", ".wv",
                 ".aiff", ".aif", ".aifc", ".alac", ".dsf", ".dff", ".amr", ".ac3", ".dts", ".mka", ".tta",
                 ".tak", ".caf", ".mpc", ".mp2", ".m4b", ".spx", ".au",
                 ".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".ts", ".m4v", ".wmv", ".mpg", ".mpeg"}
# 音乐软件的加密格式：受版权保护，本软件不做解密，只认出来并说明
ENCRYPTED_EXTS = {
    ".ncm": T("网易云音乐"), ".uc": T("网易云音乐缓存"),
    ".qmc0": T("QQ 音乐"), ".qmc2": T("QQ 音乐"), ".qmc3": T("QQ 音乐"), ".qmcflac": T("QQ 音乐"), ".qmcogg": T("QQ 音乐"),
    ".mflac": T("QQ 音乐"), ".mflac0": T("QQ 音乐"), ".mgg": T("QQ 音乐"), ".mgg1": T("QQ 音乐"), ".mmp4": T("QQ 音乐"),
    ".tkm": T("QQ 音乐"), ".bkcmp3": T("QQ 音乐"), ".bkcflac": T("QQ 音乐"),
    ".kgm": T("酷狗音乐"), ".kgma": T("酷狗音乐"), ".vpr": T("酷狗音乐"),
    ".kwm": T("酷我音乐"), ".xm": T("虾米音乐"), ".mg3d": T("咪咕音乐"),
}
LOSSLESS_CODECS = {"flac", "alac", "ape", "wavpack", "tta", "tak", "mlp", "truehd"}  # 加上 pcm_* / dsd_*

# 输出格式：ext 扩展名，codec 编码参数，rates 可选码率（空 = 无损），cover 能不能带封面
AUDIO_OUT = [
    {"key": "mp3", "srs": [48000, 44100, 32000], "sr_ok": (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000), "name": "MP3", "ext": "mp3", "codec": ["-c:a", "libmp3lame"], "rates": ["320k", "256k", "192k", "128k"],
     "cover": True, "family": {"mp3"},
     "desc": T("最通用：手机、车载、播放器、网页全都能放；320k 的听感和无损非常接近")},
    {"key": "flac", "srs": [192000, 96000, 48000, 44100], "sr_ok": None, "name": T("FLAC（无损）"), "ext": "flac", "codec": ["-c:a", "flac", "-compression_level", "8"], "rates": [],
     "cover": True, "family": {"flac"},
     "desc": T("无损压缩：音质和原文件完全一样，体积大约是 WAV 的一半，大部分播放器都支持")},
    {"key": "wav", "srs": [192000, 96000, 48000, 44100], "sr_ok": None, "name": T("WAV（无损不压缩）"), "ext": "wav", "codec": [], "rates": [], "cover": False, "family": {"pcm"},
     "desc": T("无损不压缩：音质完全一样，但体积很大，适合剪辑、录音软件；不能带封面")},
    {"key": "m4a", "srs": [96000, 48000, 44100], "sr_ok": (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000), "name": T("M4A（AAC）"), "ext": "m4a", "codec": ["-c:a", "aac"], "rates": ["320k", "256k", "192k", "128k"],
     "cover": True, "family": {"aac"},
     "desc": T("AAC 编码：苹果设备首选，同样码率比 MP3 音质更好一点，安卓和电脑也都能放")},
    {"key": "alac", "srs": [192000, 96000, 48000, 44100], "sr_ok": None, "name": T("M4A（ALAC 苹果无损）"), "ext": "m4a", "codec": ["-c:a", "alac"], "rates": [], "cover": True,
     "family": {"alac"}, "desc": T("苹果无损：音质和原文件一样，iPhone、Mac 的音乐 App 原生支持")},
    {"key": "ogg", "srs": [48000, 44100], "sr_ok": None, "name": T("OGG（Vorbis）"), "ext": "ogg", "codec": ["-c:a", "libvorbis"], "rates": ["320k", "256k", "192k", "128k"],
     "cover": False, "family": {"vorbis"},
     "desc": T("开源免费的编码，很多游戏和安卓 App 在用；苹果设备支持比较差")},
    {"key": "opus", "srs": [], "sr_ok": (48000,), "name": "OPUS", "ext": "opus", "codec": ["-c:a", "libopus"], "rates": ["256k", "192k", "160k", "128k", "96k"],
     "cover": False, "family": {"opus"},
     "desc": T("很新的高效编码：低码率下音质最好，适合语音和网络传输；一些老设备放不了")},
    {"key": "wma", "srs": [48000, 44100], "sr_ok": (8000, 11025, 16000, 22050, 32000, 44100, 48000), "name": "WMA", "ext": "wma", "codec": ["-c:a", "wmav2"], "rates": ["192k", "160k", "128k"], "cover": False,
     "family": {"wmav2", "wmav1"}, "desc": T("微软的老格式：只建议给老的 Windows 设备用，其他设备支持一般")},
    {"key": "aiff", "srs": [192000, 96000, 48000, 44100], "sr_ok": None, "name": T("AIFF（无损不压缩）"), "ext": "aiff", "codec": [], "rates": [], "cover": False, "family": {"pcm"},
     "desc": T("苹果的无损不压缩格式，和 WAV 类似，Mac 上的专业软件常用")},
]
AUDIO_OUT_BY_KEY = {f["key"]: f for f in AUDIO_OUT}


def fit_sr(spec, sr):
    """目标格式支持原采样率就保持原样；不支持就换成不超过原采样率的最高一档（原采样率读不到时返回 0 = 交给 ffmpeg）。"""
    ok = spec["sr_ok"]
    if not sr or ok is None or sr in ok:
        return sr
    lower = [x for x in ok if x <= sr]
    return max(lower) if lower else min(ok)


def fmt_sr(sr):
    """44100 -> 44.1 kHz"""
    return "{:g} kHz".format(sr / 1000.0)


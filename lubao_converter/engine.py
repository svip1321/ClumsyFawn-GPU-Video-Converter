# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
转换核心：检测 ffmpeg 和编码方式（NVIDIA / AMD / Intel / CPU）、读取视频信息、拼 ffmpeg 命令、检查新视频能否播放。
"""
import os
import re
import json
import subprocess

from .i18n import T     # 多语言：T("中文原文") 会换成当前语言
from .config import *  # 颜色、字体、常量
from .utils import *   # 小工具函数


# 在 .avi / .flv 这类没有好用索引的文件里跳转时，解码器会打印的提示：不代表文件坏了
SEEK_NOISE = ("co located POCs unavailable", "mmco: unref short failure", "reference picture missing",
              "Missing reference picture", "number of reference frames", "non-existing PPS", "no frame!",
              "decode_slice_header error", "Could not find ref with POC")


class Engine:
    def __init__(self, ffmpeg="ffmpeg"):
        self.ffmpeg = ffmpeg or "ffmpeg"
        self.found = {}      # 检测结果：编码方式 id -> {"h264": 参数或None, "hevc": 参数或None, "hevc10": bool}
        self.detected = False
        self.active = None   # 当前使用的编码方式 id
        self.extra = {}      # cuda 解码、帧率参数写法等
        self.models = {}     # 显卡 / CPU 型号：编码方式 id -> 型号名，例如 "nvenc": "NVIDIA GeForce RTX 3060 Laptop GPU"
        self.proc = None

    @property
    def ffprobe(self):
        d, b = os.path.split(self.ffmpeg)
        return os.path.join(d, b.replace("ffmpeg", "ffprobe")) if d else "ffprobe"

    def run(self, cmd):
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=NO_WINDOW)
            return (r.returncode == 0, r.stdout.decode("utf-8", "ignore"),
                    r.stderr.decode("utf-8", "ignore"))
        except (FileNotFoundError, OSError):
            return False, "", ""

    def enc_works(self, enc, opts, pix):
        """用一小段黑色测试画面试编码，能成功就说明这个编码器在这台电脑上真的能用。"""
        args = [x.replace("{q}", "23") for x in opts]
        ok, _, _ = self.run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                             "-i", "color=black:s=320x240:d=0.2", "-pix_fmt", pix,
                             "-c:v", enc] + args + ["-f", "null", "-"])
        return ok

    def check_ffmpeg(self):
        """检测 ffmpeg 和 ffprobe 能不能用，返回 (是否可用, 说明文字)。
        路径填的是 ffmpeg 但系统里找不到时，会再找软件旁边的 ffmpeg.exe（方便打包成 exe 时一起带上）。"""
        ok, ver, _ = self.run([self.ffmpeg, "-hide_banner", "-version"])
        if (not ok or not ver) and self.ffmpeg == "ffmpeg":
            exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            for cand in (os.path.join(APP_DIR, exe), os.path.join(APP_DIR, "ffmpeg", "bin", exe),
                         os.path.join(APP_DIR, "bin", exe)):
                if os.path.isfile(cand):
                    self.ffmpeg = cand
                    ok, ver, _ = self.run([self.ffmpeg, "-hide_banner", "-version"])
                    break
        if not ok or not ver:
            return False, T("找不到 ffmpeg（当前填写：{}）").format(self.ffmpeg)
        ok2, _, _ = self.run([self.ffprobe, "-hide_banner", "-version"])
        if not ok2:
            return False, T("找到了 ffmpeg，但同一个文件夹里没有 ffprobe（当前：{}）").format(self.ffprobe)
        return True, ver.splitlines()[0]

    def detect_backend(self, be):
        """检测一种编码方式：H.264 / HEVC / HEVC 10bit 各自能不能用。"""
        res = {"h264": None, "hevc": None, "hevc10": False}
        for codec in ("h264", "hevc"):
            for opts in be["opts"][codec]:
                if self.enc_works(be[codec], opts, be["pix8"]):
                    res[codec] = opts
                    break
        if res["hevc"]:
            res["hevc10"] = self.enc_works(be["hevc"], res["hevc"], be["pix10"])
        return res if (res["h264"] or res["hevc"]) else None

    def status_text(self, bid):
        """只有状态部分，例如：可用（H.264 / HEVC / HEVC 10bit）"""
        r = self.found.get(bid)
        if not r:
            return T("没检测到")
        parts = (["H.264"] if r["h264"] else []) + (["HEVC"] if r["hevc"] else []) + \
                (["HEVC 10bit"] if r["hevc10"] else [])
        return T("可用（{}）").format(" / ".join(parts))

    def describe(self, bid):
        """例如：NVIDIA 显卡（NVENC）：可用（H.264 / HEVC / HEVC 10bit）"""
        return T("{}：{}").format(BACKEND_BY_ID[bid]["name"], self.status_text(bid))

    def detect_models(self):
        """读出电脑里的显卡和 CPU 型号，按厂商对应到编码方式上。读不到也没关系，界面上就只显示编码方式的名字。"""
        gpus, cpu = [], ""
        if os.name == "nt":
            ok, out, _ = self.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                   "(Get-CimInstance Win32_VideoController).Name; '@@CPU@@'; "
                                   "(Get-CimInstance Win32_Processor).Name"])
            if ok and "@@CPU@@" in out:
                g, c = out.split("@@CPU@@", 1)
                gpus = [x.strip() for x in g.splitlines() if x.strip()]
                cpu = next((x.strip() for x in c.splitlines() if x.strip()), "")
            else:  # 老系统没有 Get-CimInstance 时用 wmic
                _, out, _ = self.run(["wmic", "path", "win32_VideoController", "get", "name"])
                gpus = [x.strip() for x in out.splitlines()[1:] if x.strip()]
                _, out, _ = self.run(["wmic", "cpu", "get", "name"])
                cpu = next((x.strip() for x in out.splitlines()[1:] if x.strip()), "")
        else:
            _, out, _ = self.run(["lspci"])
            gpus = [x.split(": ", 1)[-1] for x in out.splitlines() if "VGA" in x or "3D controller" in x]
            try:
                with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as f:
                    cpu = next((l.split(":", 1)[1].strip() for l in f if l.startswith("model name")), "")
            except OSError:
                pass
        ok, out, _ = self.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])  # N 卡的名字最准
        nv = next((x.strip() for x in out.splitlines() if x.strip()), "") if ok else ""
        models = {}
        for bid, keys in (("nvenc", ("nvidia",)), ("amf", ("amd", "radeon")), ("qsv", ("intel",))):
            name = next((g for g in gpus if any(k in g.lower() for k in keys)), "")
            if bid == "nvenc" and nv:
                name = nv if nv.lower().startswith("nvidia") else "NVIDIA " + nv
            if name:
                models[bid] = " ".join(name.split())
        if cpu:
            models["cpu"] = " ".join(cpu.split())
        self.models = models
        return models

    def model_text(self, bid):
        """给人看的"型号 + 编码方式"，例如：NVIDIA GeForce RTX 3060 Laptop GPU（NVENC）；读不到型号就用编码方式的名字。"""
        tag = {"nvenc": "NVENC", "amf": "AMF", "qsv": "QSV"}.get(bid)
        m = self.models.get(bid)
        if not m:
            return BACKEND_BY_ID[bid]["name"]
        return T("{}（{}）").format(m, tag) if tag else T("CPU：{}").format(m)

    def pick(self, pref):
        """按用户的选择定下当前用哪种编码方式；"auto" 时按 NVIDIA → AMD → Intel 挑第一个能用的显卡。"""
        if pref == "auto":
            self.active = next((b["id"] for b in BACKENDS if b["gpu"] and b["id"] in self.found), None)
        else:
            self.active = pref if pref in self.found else None
        return self.active

    def check(self):
        """检测 ffmpeg 和所有编码方式，返回 (有没有能用的编码方式, 说明文字)。"""
        self.found, self.detected, self.active = {}, False, None
        ok, first = self.check_ffmpeg()
        if not ok:
            return False, "NO_FFMPEG:" + first
        for be in BACKENDS:
            r = self.detect_backend(be)
            if r:
                self.found[be["id"]] = r
        _, hw, _ = self.run([self.ffmpeg, "-hide_banner", "-hwaccels"])
        self.extra["cuda"] = "cuda" in hw.split()
        _, h, _ = self.run([self.ffmpeg, "-hide_banner", "-h", "long"])
        self.extra["fps"] = ["-fps_mode", "passthrough"] if "-fps_mode" in h else ["-vsync", "passthrough"]
        try:
            self.detect_models()
        except Exception:
            self.models = {}
        self.detected = True
        lines = [first] + [self.describe(b["id"]) for b in BACKENDS]
        return bool(self.found), "\n".join(lines)

    def probe(self, path):
        info = {"dur": 0.0, "pix": "", "vcodec": "?", "acodec": None, "fps": 0.0, "n_audio": 0,
                "acodecs": [], "achs": []}  # 每条音轨的编码和声道数
        ok, out, _ = self.run([self.ffprobe, "-v", "error", "-show_entries",
                               "format=duration:stream=codec_type,codec_name,pix_fmt,avg_frame_rate,r_frame_rate,channels",
                               "-of", "json", path])
        if not ok:
            return info
        try:
            data = json.loads(out)
        except ValueError:
            return info
        got_v = False
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and not got_v:
                info["vcodec"], info["pix"], got_v = s.get("codec_name", "?"), s.get("pix_fmt", ""), True
                for key in ("avg_frame_rate", "r_frame_rate"):
                    try:
                        a, b = s.get(key, "0/1").split("/")
                        if float(b) > 0 and float(a) > 0:
                            info["fps"] = float(a) / float(b)
                            break
                    except (ValueError, ZeroDivisionError):
                        pass
            elif s.get("codec_type") == "audio":
                info["n_audio"] += 1
                info["acodecs"].append(s.get("codec_name") or "?")
                info["achs"].append(int(s.get("channels") or 2))
                if info["acodec"] is None:  # 记第一条音轨的编码，用来判断能不能原样复制
                    info["acodec"] = s.get("codec_name")
        try:
            info["dur"] = float(data.get("format", {}).get("duration", 0))
        except (TypeError, ValueError):
            pass
        return info

    def video_args(self, info, target, cq):
        """按当前编码方式决定视频用 HEVC 还是 H.264，返回 (编码, 编码器名, ffmpeg 视频参数)。"""
        be = BACKEND_BY_ID[self.active]
        r = self.found[self.active]
        ten_bit = bool(re.search(r"1[02](le|be)?$", info["pix"]))
        can_hevc = r["hevc"] and target in HEVC_TARGETS  # .avi / .flv 文件装不了 HEVC
        if ten_bit and can_hevc and r["hevc10"]:
            codec, pix = "hevc", be["pix10"]              # 10bit 源保留色深
        elif can_hevc or not r["h264"]:
            codec, pix = "hevc", be["pix8"]               # 默认 HEVC
        else:
            codec, pix = "h264", be["pix8"]
        args = ["-c:v", be[codec]] + [x.replace("{q}", str(cq)) for x in r[codec]] + ["-pix_fmt", pix]
        return codec, be[codec], args

    def hw_decode(self):
        """N 卡顺便用显卡解码；其他编码方式用 CPU 解码（解码很轻，主要的活是编码）。"""
        return ["-hwaccel", "cuda"] if self.active == "nvenc" and self.extra.get("cuda") else []

    # ---------- 音乐 ----------
    def probe_audio(self, path):
        """读取音乐信息：时长、编码、采样率、位深、码率、有没有封面。"""
        info = {"dur": 0.0, "acodec": None, "sr": 0, "ch": 0, "bits": 16, "bitrate": 0, "cover": None}
        ok, out, _ = self.run([self.ffprobe, "-v", "error", "-show_entries",
                               "format=duration,bit_rate:stream=index,codec_type,codec_name,sample_rate,channels,"
                               "bits_per_raw_sample,bits_per_sample,sample_fmt,bit_rate:stream_disposition=attached_pic",
                               "-of", "json", path])
        if not ok:
            return info
        try:
            data = json.loads(out)
        except ValueError:
            return info
        for st in data.get("streams", []):
            if st.get("codec_type") == "audio" and info["acodec"] is None:
                info["acodec"] = st.get("codec_name")
                info["sr"] = int(st.get("sample_rate") or 0)
                info["ch"] = int(st.get("channels") or 0)
                bits = int(st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0)
                if not bits:
                    fmt = st.get("sample_fmt", "")
                    bits = 24 if fmt.startswith("s32") else 16
                info["bits"] = bits
                info["bitrate"] = int(st.get("bit_rate") or 0)
            elif st.get("codec_type") == "video" and (st.get("disposition") or {}).get("attached_pic") \
                    and info["cover"] is None:
                info["cover"] = st.get("index")                   # 封面图在第几条流
        fmt = data.get("format", {})
        try:
            info["dur"] = float(fmt.get("duration") or 0)
        except (TypeError, ValueError):
            pass
        if not info["bitrate"]:
            try:
                info["bitrate"] = int(fmt.get("bit_rate") or 0)
            except (TypeError, ValueError):
                pass
        return info

    @staticmethod
    def pick_rate(spec, info, rate):
        """rate="auto"（和原音乐一样）时：挑不低于原文件码率的最小一档；原文件是无损或读不到码率时用最高档。"""
        if rate != "auto" or not spec["rates"]:
            return rate
        src = info.get("bitrate", 0) // 1000
        rates = sorted(spec["rates"], key=lambda r: int(r[:-1]))
        c = info.get("acodec") or ""
        if not src or c in LOSSLESS_CODECS or c.startswith(("pcm_", "dsd_")):
            return rates[-1]
        return next((r for r in rates if int(r[:-1]) >= src * 0.95), rates[-1])

    @staticmethod
    def pick_sr(spec, info, sr):
        """sr=0（和原音乐一样）时按原采样率；目标格式不支持原采样率时自动换成最接近的一档。"""
        return fit_sr(spec, sr or info.get("sr", 0))

    def build_audio(self, src, dst, info, fmt_key, rate, sr=0):
        """拼音乐转换命令：保留歌名/歌手等信息；目标格式支持的话把封面也带过去。
        rate：码率（"auto" = 跟原音乐差不多）；sr：采样率（0 = 和原音乐一样）。"""
        spec = AUDIO_OUT_BY_KEY[fmt_key]
        rate = self.pick_rate(spec, info, rate)
        out_sr = self.pick_sr(spec, info, sr)
        hi = info.get("bits", 16) > 16                            # 24bit 等高位深的无损源
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-nostats", "-progress", "pipe:1",
               "-i", src, "-map", "0:a:0"]
        if spec["cover"] and info.get("cover") is not None:
            cmd += ["-map", "0:%d" % info["cover"], "-c:v", "copy", "-disposition:v:0", "attached_pic"]
        cmd += ["-map_metadata", "0"]
        if fmt_key == "wav":
            cmd += ["-c:a", "pcm_s24le" if hi else "pcm_s16le"]
        elif fmt_key == "aiff":
            cmd += ["-c:a", "pcm_s24be" if hi else "pcm_s16be"]
        else:
            cmd += spec["codec"]
            if fmt_key == "flac":
                cmd += ["-sample_fmt", "s32" if hi else "s16"]
            elif fmt_key == "alac":
                cmd += ["-sample_fmt", "s32p" if hi else "s16p"]
            if spec["rates"]:
                cmd += ["-b:a", rate if rate in spec["rates"] else spec["rates"][0]]
        if out_sr and out_sr != info.get("sr"):
            cmd += ["-ar", str(out_sr)]
        if fmt_key == "mp3":
            cmd += ["-id3v2_version", "3"]                        # Windows 资源管理器能直接看到歌名、封面
        return cmd + [dst]

    @staticmethod
    def can_remux(info, target):
        """H.264 / HEVC 本来就是兼容性好的编码：只换文件格式时直接复制视频流，不重新编码（画质 100% 不变，很快）。
        .avi 例外：这种老格式记录不了 H.264 双向参考帧需要的时间信息，原样复制进去容易出问题，所以一律重新编码。"""
        vc = info.get("vcodec")
        if target == "avi":
            return False
        return vc == "h264" or (vc == "hevc" and target in HEVC_TARGETS)

    @staticmethod
    def aac_bitrate(ch):
        """转 AAC 时用的码率：双声道 320k（AAC 的最高常用档，听感和原来没有区别），多声道按每声道 96k 往上加。"""
        return "%dk" % max(320, 96 * (ch or 2))

    @staticmethod
    def apple_silent(info):
        """mp4 里有苹果设备放不出声音的音轨（MP3、OPUS、FLAC、PCM 等）就返回这些编码，没有就返回空列表。"""
        return [a for a in (info.get("acodecs") or []) if a not in APPLE_AUDIO]

    def build(self, src, dst, info, target, cq, remux=False):
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-nostats", "-progress", "pipe:1"]
        if remux:
            codec, venc = info["vcodec"], "copy"
            cmd += ["-i", src, "-map", "0:V:0", "-map", "0:a?", "-c:v", "copy"]
        else:
            codec, venc, vargs = self.video_args(info, target, cq)
            cmd += self.hw_decode()
            fps = self.extra.get("fps", [])
            if target == "avi":  # avi 只能存固定帧率，passthrough 会在结尾多出一帧；cfr 按原帧率原样输出
                fps = [x.replace("passthrough", "cfr") for x in fps]
            cmd += ["-i", src, "-map", "0:V:0", "-map", "0:a?"] + vargs + fps
        if codec == "hevc" and target in ("mp4", "m4v", "mov"):
            cmd += ["-tag:v", "hvc1"]
        # 每条音轨单独决定：目标格式装得下就原样复制（音质 100% 不变），装不下才转码
        allowed = AUDIO_OK[target]
        acodecs = info.get("acodecs") or ([info["acodec"]] if info.get("acodec") else [])
        achs = info.get("achs") or [2] * len(acodecs)
        notes = []
        for i, a in enumerate(acodecs):
            if allowed is None or a in allowed:
                cmd += ["-c:a:%d" % i, "copy"]
                notes.append(T("{}（原样复制）").format(a))
            elif target == "avi":
                cmd += ["-c:a:%d" % i, "libmp3lame", "-b:a:%d" % i, "320k"]
                notes.append("{} -> mp3 320k".format(a))
            else:
                br = self.aac_bitrate(achs[i] if i < len(achs) else 2)
                cmd += ["-c:a:%d" % i, "aac", "-b:a:%d" % i, br]
                notes.append("{} -> aac {}".format(a, br))
        anote = " / ".join(notes) if notes else T("无音轨")
        if target in ("mp4", "m4v", "mov"):
            cmd += ["-movflags", "+faststart"]
        if target == "m4v":
            cmd += ["-f", "mp4"]  # .m4v 就是 mp4；ffmpeg 默认的 iPod 模式不支持 HEVC，所以按普通 mp4 来写
        return cmd + [dst], venc, anote

    def decode_count(self, dst, start, length, video=True):
        """从 start 秒开始解码 length 秒（None = 到结尾），返回 (成功?, 解码到的帧数或秒数, 报错行)。"""
        seek = ["-ss", "{:.2f}".format(start)] if start > 0 else []   # 开头直接从头解码，不跳转
        dur = ["-t", "{:.2f}".format(length)] if length else []
        maps = ["-map", "0:V:0", "-map", "0:a?"] if video else ["-map", "0:a:0"]
        ok, out, err = self.run([self.ffmpeg, "-hide_banner", "-v", "error", "-nostdin"] + seek + ["-i", dst] + dur +
                                maps + ["-f", "null", "-", "-nostats", "-progress", "pipe:1"])
        frames, secs = 0, 0.0
        for line in out.splitlines():
            k, _, v = line.partition("=")
            try:
                if k == "frame":
                    frames = max(frames, int(v))
                elif k in ("out_time_us", "out_time_ms"):
                    secs = max(secs, int(v) / 1e6)
            except ValueError:
                pass
        return ok, (frames if video else secs), err

    def verify(self, dst, src_dur):
        """检查新视频能否正常播放：有视频流、时长一致，开头/中间/结尾都真的能解码出足够的画面。
        （只看时长不够：被截断的文件头部可能还写着完整时长）"""
        info = self.probe(dst)
        if info["vcodec"] == "?":
            return False, T("读不到视频流")
        if src_dur > 0 and abs(info["dur"] - src_dur) > max(1.0, src_dur * 0.01):
            return False, T("时长不一致（原 {} / 新 {}）").format(fmt_t(src_dur), fmt_t(info["dur"]))
        d = info["dur"] or src_dur
        fps = info.get("fps") or 0
        if d < 12:
            points = [(0.0, None, d)]                                   # 短视频：从头到尾完整解码
        else:
            points = [(0.0, 3.0, 3.0), (d / 2, 3.0, 3.0), (max(d - 4, 0), 3.0, min(3.0, d - max(d - 4, 0)))]
        for t, length, span in points:
            ok, frames, err = self.decode_count(dst, t, length)
            # 只有跳转之后才忽略跳转引起的提示；从开头解码时任何报错都算
            real = [ln for ln in err.splitlines() if ln.strip() and not (t > 0 and any(x in ln for x in SEEK_NOISE))]
            if not ok or real:
                return False, T("{} 附近解码出错").format(fmt_t(t))
            need = max(1, int(span * fps * 0.8)) if fps else 1
            if frames < need:
                return False, T("{} 附近画面不完整（只解出 {} 帧）").format(fmt_t(t), frames)
        return True, ""

    def verify_audio(self, dst, src_dur):
        """检查转出来的音乐：从头到尾完整解码一遍（音频解码很快），时长要和原文件一致、不能有报错。"""
        info = self.probe_audio(dst)
        if not info["acodec"]:
            return False, T("读不到音轨")
        if src_dur > 0 and abs(info["dur"] - src_dur) > max(1.0, src_dur * 0.01):
            return False, T("时长不一致（原 {} / 新 {}）").format(fmt_t(src_dur), fmt_t(info["dur"]))
        ok, secs, err = self.decode_count(dst, 0, None, video=False)
        if not ok or err.strip():
            return False, T("解码出错")
        if src_dur > 0 and secs < src_dur - max(1.0, src_dur * 0.01):
            return False, T("只能播放到 {}，文件不完整").format(fmt_t(secs))
        return True, ""

# 小鹿包的 GPU 音视频转换器

![禁止商用](https://img.shields.io/badge/%E7%A6%81%E6%AD%A2%E5%95%86%E7%94%A8-Non--Commercial-d93025?style=for-the-badge)
![源码公开](https://img.shields.io/badge/%E6%BA%90%E7%A0%81%E5%85%AC%E5%BC%80-Source%20Available-4a6a8f?style=for-the-badge)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-4a6a8f?style=for-the-badge)

> ⚠️ **禁止商用 / Non-Commercial Only**
> 本项目源码公开，仅限个人学习、研究和非商业使用。**未经作者书面同意，禁止任何商业用途**（出售、付费服务、公司营利使用、广告引流等）。详见 [LICENSE.txt](LICENSE.txt)。
> The source code is public for personal, non-commercial use only. **Commercial use is prohibited** without the author's written permission. See [LICENSE.txt](LICENSE.txt).

**Copyright © 2026 粗糙的鹿包 (Clumsy Fawn)** · 联系作者 / Contact: [X (Twitter) @svip1321](https://x.com/svip1321)

---

## 这是什么

一个带图形界面的视频 / 音乐格式转换器，基于 FFmpeg，支持显卡加速。

- **视频转换**：mp4 / mkv / mov / avi / flv / ts / m4v 互转。H.264 / HEVC 视频只换文件格式、不重新编码，画质完全不变；其他编码用显卡重新编码成 HEVC。分辨率、画面比例、帧率保持原样，音频能原样复制就原样复制
- **格式纠正**：把兼容性差的 MPEG（太老）和 AV1（太新）编码视频，换成兼容性更好的 HEVC / H.264
- **音乐转换**：MP3 / FLAC / WAV / M4A（AAC、ALAC）/ OGG / OPUS / WMA / AIFF 互转，保留歌名、歌手、封面，也能从视频里提取音轨
- **显卡加速**：自动检测 NVIDIA（NVENC）/ AMD（AMF）/ Intel（QSV），都没有时可以用 CPU
- **安全**：每个文件转完都会实际解码开头、中间、结尾检查能否正常播放，检查通过才会按设置处理原文件
- **多语言**：简体中文、繁體中文、English、日本語、한국어、Español、Français、Deutsch、Русский、Português

> 音乐软件的加密格式（网易云 .ncm、QQ 音乐 .mflac / .mgg 等）受版权保护，本软件不做解密。

## 怎么运行

1. 安装 Python 3.8 或更高版本
2. 准备 FFmpeg：放在项目的 `FFMPEG\bin\` 里（需要 `ffmpeg.exe` 和 `ffprobe.exe`），或者加进系统环境变量
3. 双击 `main.pyw`

可选：`pip install tkinterdnd2`（拖入文件）、`pip install send2trash`（删除原文件时放进回收站）

## 下载打包好的 exe可执行程序

下载Releases页面的对应版本解压后双击 ClumsyFawnGPUConverter.exe 就能用（产品名：鹿包的GPU格式转换 / Clumsy Fawn GPU Converter，版本 1.0.0）。

为了尽量不被杀毒软件误报，脚本会在单独的干净环境里打包、用文件夹模式、不压缩不加密，并写入完整的作者和版本信息（`version_info.txt`）。没有代码签名证书时仍可能被个别杀毒软件误报，可以把 exe 提交给厂商申诉，脚本结束时会列出申诉地址。

## 改代码后检查多语言

所有给人看的文字都要写成 `T("简体中文原文")`，翻译放在 `lubao_converter/lang/` 里。改完代码运行：

```
py check_lang.py
```

它会找出忘了包 `T()` 的文字、每种语言漏翻的条目，以及 `{}` 占位符不一致的地方。

## 文件结构

```
main.pyw                启动入口
check_lang.py           多语言检查工具
build_exe.bat           打包成 exe
version_info.txt        exe 的版本信息（作者、版本号、版权）
LICENSE.txt             许可协议（禁止商用）
lubao_converter/
    config.py           配置：路径、颜色、字体、格式常量
    i18n.py             多语言
    utils.py            小工具：格式化、回收站、错误报告
    engine.py           转换核心：检测 ffmpeg / 显卡、拼命令、检查新文件
    widgets.py          自定义控件：圆角按钮、勾选框、卡片、整体样式
    layout.py           主界面：视频转换页、日志页、设置页
    music.py            音乐转换页
    dialogs.py          弹窗：ffmpeg 安装指引、投喂鹿包、提示条
    app.py              主程序：扫描、开始/停止转换、后台线程
    lang/               语言文件
    qr_data.py          内置的投喂收款码（属于作者个人，请勿修改）
    assets/             头像（avatar_*.png）、软件图标（ico.png，512x512）（属于作者个人，不得用于其他项目）
```

## 第三方组件

本软件调用 [FFmpeg](https://ffmpeg.org) 完成转换。FFmpeg 不属于本项目，遵循它自己的许可证（见 `FFMPEG/LICENSE` 和 <https://ffmpeg.org/legal.html>）。如果你把 FFmpeg 和本软件一起分发，请同时遵守 FFmpeg 的许可证要求。

## 许可

[LICENSE.txt](LICENSE.txt) —— 仅限非商业使用，商用请先联系作者：[X @svip1321](https://x.com/svip1321)

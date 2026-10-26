# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
小鹿包的 GPU 音视频转换器 —— 双击这个文件启动
Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn)

文件结构：
  main.pyw                    启动入口（就是这个文件）
  lubao_converter/
      config.py               配置：路径、颜色、字体、格式常量
      utils.py                小工具：格式化、回收站、错误报告
      engine.py               转换核心：检测 ffmpeg/GPU、拼命令、检查新视频
      widgets.py              自定义控件：圆角按钮、勾选框、卡片、整体样式
      layout.py               主界面：头像、选项卡、转换页、日志页、设置页
      dialogs.py              弹窗：ffmpeg 安装指引、投喂鹿包、提示条
      app.py                  主程序：扫描、开始/停止转换、后台线程
      assets/                 头像和收款码图片
"""
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def fallback_error(detail):
    """连程序模块都没加载起来时用的报错（比如文件缺了）。"""
    log = os.path.join(HERE, "gpu_video_converter_error.log")
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write("\n[{}] Python {}\n{}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0], detail))
    except Exception:
        pass
    last = detail.strip().splitlines()[-1] if detail.strip() else "未知错误"
    msg = "呜…程序启动失败了 >_<\n\n{}\n\n详细信息已保存到：\n{}\n\n请确认 lubao_converter 文件夹和 main.pyw 放在一起".format(last, log)
    # 缺了程序文件时，直接说清楚缺的是哪个
    names = ("__init__", "app", "config", "i18n", "utils", "engine", "widgets", "layout", "music", "dialogs")
    lost = [n + ".py" for n in names if not os.path.isfile(os.path.join(HERE, "lubao_converter", n + ".py"))]
    if lost:
        msg = ("呜…程序启动失败了 >_<\n\n缺失文件：{}\n（在 lubao_converter 文件夹里），软件无法运行。\n\n"
               "请重新下载完整的软件，或者从备份里把文件放回去。\n\nMissing files: {}").format(
            "、".join(lost), ", ".join(lost))
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "启动失败", 0x10 | 0x40000)
        else:
            print(msg, file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from lubao_converter.app import run
    except Exception:
        fallback_error(traceback.format_exc())
    else:
        run()

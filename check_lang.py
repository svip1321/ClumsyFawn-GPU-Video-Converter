# -*- coding: utf-8 -*-
# Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
# 仅限个人非商业使用，禁止商用（详见 LICENSE.txt）
# Non-commercial use only. Commercial use is prohibited. See LICENSE.txt
"""
多语言检查工具 —— 每次改完代码都运行一下：  py check_lang.py
检查内容：
  1. 代码里给人看的中文有没有忘了包 T("...")（没包的话切换语言后还会显示中文）
  2. 每种语言的翻译文件有没有漏翻的条目、有没有已经用不到的旧条目
  3. 翻译里的 {} 占位符和原文是否一致（不一致运行时会出错）
  4. 外语翻译里有没有残留中文（多半是忘了翻）
加 --fix 会把漏掉的条目先用简体中文原文补进语言文件（方便接着翻译），并删掉用不到的旧条目。
全部通过时返回 0，有问题时返回 1。
"""
import ast
import glob
import json
import os
import re
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "lubao_converter")
LANG_DIR = os.path.join(PKG, "lang")
sys.path.insert(0, HERE)
from lubao_converter.i18n import LANG_CODES, SOURCE_LANG  # noqa: E402

CJK = re.compile(r"[　-〿一-鿿＀-￯]")
HAN = re.compile(r"[一-鿿]")
SKIP_FILES = {"i18n.py"}           # 语言名称本身（日本語、한국어……）不翻译
ALLOW_HAN = {"zh_TW", "ja"}        # 这些语言里出现汉字是正常的
KEEP_NAMES = ("粗糙的鹿包",)        # 作者署名，所有语言都保持原样
# 日语里本来就和简体中文写法一样的条目（汉字 + 全角标点），不算漏翻
SAME_OK = {"ja": {"CPU：{}", "M4A（AAC）", "OGG（Vorbis）", "{}（{}）", "{}：{}", "停止", "警告：", "（最高）"}}


def scan_code():
    """返回 (所有 T() 里的原文集合, 没包 T() 的中文列表)。"""
    keys, unwrapped = set(), []
    for path in sorted(glob.glob(os.path.join(PKG, "*.py"))):
        name = os.path.basename(path)
        if name in SKIP_FILES:
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        doc, parent = set(), {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and \
                    isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
                doc.add(id(n.body[0].value))
            for c in ast.iter_child_nodes(n):
                parent[id(c)] = n
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "T":
                if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    keys.add(n.args[0].value)
                else:
                    unwrapped.append((name, n.lineno, "T() 里不是固定的文字，检查不到它的翻译"))
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and CJK.search(n.value) and id(n) not in doc:
                p = parent.get(id(n))
                if not (isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id == "T"):
                    unwrapped.append((name, n.lineno, n.value[:40]))
    return keys, unwrapped


def _strip_names(text):
    """去掉作者署名等不需要翻译的名字（这些名字在所有语言里都保持原样）。"""
    for name in KEEP_NAMES:
        text = text.replace(name, "")
    return text


def placeholders(text):
    """取出 {} 占位符（按顺序），例如 ['', ':.1f', 'name']。"""
    out = []
    try:
        for _, field, spec, _ in string.Formatter().parse(text):
            if field is not None:
                out.append(field + (":" + spec if spec else ""))
    except ValueError:
        out.append("<格式错误>")
    return out


def main():
    fix = "--fix" in sys.argv
    keys, unwrapped = scan_code()
    problems = 0
    print("代码里共有 {} 条要翻译的文字".format(len(keys)))
    if unwrapped:
        problems += len(unwrapped)
        print("\n[!] 下面这些中文没有包 T()，切换语言后还会显示中文：")
        for f, line, text in unwrapped:
            print("    {}:{}  {}".format(f, line, text))
    for code in LANG_CODES:
        path = os.path.join(LANG_DIR, code + ".json")
        try:
            data = json.load(open(path, encoding="utf-8"))
        except FileNotFoundError:
            data = {}
            print("\n[{}] 还没有语言文件".format(code))
        except ValueError as e:
            problems += 1
            print("\n[{}] 语言文件格式坏了：{}".format(code, e))
            continue
        missing = sorted(k for k in keys if k not in data or not str(data.get(k, "")).strip())
        # 外语里和简体原文一模一样（而且原文有中文）= 其实没翻；繁体中文有些词本来就相同，不算
        same = sorted(k for k in keys if k in data and data[k] == k and CJK.search(_strip_names(k))
                      and code not in (SOURCE_LANG, "zh_TW") and k not in missing
                      and k not in SAME_OK.get(code, ()))
        unused = sorted(k for k in data if k not in keys)
        bad_ph, left_cn = [], []
        for k in keys & set(data):
            v = data[k]
            if sorted(placeholders(k)) != sorted(placeholders(v)) or placeholders(k) != placeholders(v) and \
                    any(p == "" or p.startswith(":") for p in placeholders(k)):
                bad_ph.append(k)
            vv = v
            for name in KEEP_NAMES:
                vv = vv.replace(name, "")
            if code != SOURCE_LANG and code not in ALLOW_HAN and HAN.search(vv):
                left_cn.append(k)
        left_cn = [k for k in left_cn if k not in same]
        issues = len(missing) + len(same) + len(bad_ph) + len(left_cn)
        status = "全部通过" if not issues and not unused else ""
        print("\n[{}] 已翻译 {}/{} {}".format(code, len(keys) - len(missing) - len(same), len(keys), status))
        for title, items in (("漏翻", missing), ("还是简体中文原文", same), ("占位符 {} 不一致", bad_ph),
                             ("翻译里还有中文", left_cn),
                             ("用不到的旧条目（可删）", unused)):
            if items:
                print("    {} {} 条：".format(title, len(items)))
                for k in items[:8]:
                    print("      - {}".format(k.replace("\n", "\\n")[:60]))
                if len(items) > 8:
                    print("      ……还有 {} 条".format(len(items) - 8))
        problems += issues
        if fix:
            new = {k: data.get(k, "") for k in sorted(keys)}  # 只补空位，不拿原文去填外语
            if code == SOURCE_LANG:
                new = {k: k for k in sorted(keys)}
            os.makedirs(LANG_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(new, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.write("\n")
    print("\n" + ("全部语言检查通过 ✓" if not problems else "一共发现 {} 个问题，请修改后再检查".format(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

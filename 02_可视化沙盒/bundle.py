# -*- coding: utf-8 -*-
"""把 index.html + font_data.js + replay_data.js 打包成一个自包含的 HTML 单文件。

用途：发给导师/同行时只需传一个 .html，双击即可全离线打开（像素字体与 24 组
回放数据均已内嵌，不依赖网络、不依赖同目录其他文件）。

用法：
    python bundle.py                    # 输出 疏散沙盒-单文件版.html
    python bundle.py --out 某某.html
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        sys.exit(f"缺少文件: {p}")
    with open(p, encoding="utf-8") as f:
        return f.read()


def inline(html, js):
    """把 js 内嵌进 <script> 标签；对 </script> 做转义以防提前闭合。"""
    safe = js.replace("</script>", "<\\/script>")
    return "<script>\n" + safe + "\n</script>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="疏散沙盒-单文件版.html")
    args = ap.parse_args()

    html = read("index.html")
    font = read("font_data.js")
    data = read("replay_data.js")

    # 1) 字体
    pat_font = r'<script src="font_data\.js"></script>'
    if not re.search(pat_font, html):
        sys.exit("index.html 中未找到 font_data.js 引用")
    html = re.sub(pat_font, lambda m: inline("", font), html)

    # 2) 回放数据
    pat_data = r'<script src="replay_data\.js"></script>'
    if not re.search(pat_data, html):
        sys.exit("index.html 中未找到 replay_data.js 引用")
    html = re.sub(pat_data, lambda m: inline("", data), html)

    for name in ('studio_data.js', 'pixel-world.js', 'scene-effects.js', 'agent-narrative.js', 'studio.js', 'settings-ui.js'):
        html = html.replace('<script src="'+name+'"></script>', inline('', read(name)))
    html = html.replace('<link rel="stylesheet" href="studio.css">', '<style>'+read('studio.css')+'</style>')

    # 3) 移除其它外部引用（应已无）
    left = re.findall(r'<script[^>]*src="([^"]+)"', html) + \
        re.findall(r'<link[^>]*href="([^"]+)"', html)
    if left:
        print("警告：仍存在外部引用 ->", left)

    out = os.path.join(HERE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"输出: {out}  ({os.path.getsize(out)/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()

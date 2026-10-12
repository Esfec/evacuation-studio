# -*- coding: utf-8 -*-
"""
build_font.py — 生成像素字体子集(供 index.html 内嵌使用)

字体: Fusion Pixel Font 12px Proportional SC (OFL-1.1)
来源: npm @fontsource/fusion-pixel-12px-proportional-sc

用法:
  python build_font.py                 # 生成 font_subset.css (含 base64 内联 woff2)
  python build_font.py --woff2-only    # 只输出 font_subset.woff2
"""
import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_FILE = None

# 界面里会出现的固定文案(提取自 index.html 的 UI 字符串)
UI_TEXT = """
像素疏散小镇 LLM-Agent 消防疏散沙盒 博物馆 火灾 设计筛选 回放 运行 策略 设计 条件 种子
起火点 时间轴 播放 暂停 重播 重来 速度 倍速 活动中 已逃出 遇难 力竭 逃出率 决策事件流 详情
恐慌 体力 健康 房间 风险 烟雾 占用 容量 状态 封闭 烧毁 不可通行 死角 出口 防火门 紧急通道
主大厅 过厅 展室 教室 中走廊 印象展区 北侧廊 临时展厅 庭院 储藏室 西展区 员工出口 后走廊
当前人员 类型 认知型 感知型 跟随型 受训员工 综合判断 普通访客 依赖显著线索 从众 参考人群流向
图例 火焰 密度 场景 新增通道 排队 拥堵 决策理由 历史记录 无可见路径 体力不支 停留 通道
目标已满 移动 迷失 规则评估最优 规则识别出口 风险评估 最短路 随机游走 局部 全局
滚轮缩放 拖拽平移 点击小人查看详情 双击复位 可拖入文件 对比条形 切运行 全部 剩余 条
导入成功 失败 加载中 请选择 小人 房间 之 想前往 但通道拥堵 极度恐慌 本能冲向人群 完全失去判断
尚未 未找到数据 请先运行导出器 秒 分钟 小时 第 步 共 人员疏散 热力 烟雾蔓延 通道容量
语义拓扑 仅供研究展示 并非计算流体力学模拟或合规工具 一跳 回合 同步移动 气泡 显示 思考过程
展厅 走廊 院落 花园 中庭 中厅 门厅 展柜 装置 幕墙 标识 照明 布展 后勤 装修
排队等待 通道饱和 火灾 蔓延 危险 安全 撤离 逃生 逃生出口 安全出口 侧门 员工 楼梯 扶梯
统计 指标 总体 平均 累计 暴露 折返 次数 调用 模型 温度 并发
开始 结束 清空 复位 视角 跟随 追踪 关闭 打开 展开 收起 更多 全部 仅活动 仅遇难
ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789
!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~ 。，、；：？！“”‘’（）《》【】—…·×÷±°№㎡
↑↓←→↔★☆■□▲▼●○◆◇✓✗√∞§¶
"""


def find_font_file():
    """在 npm 包缓存或本地查找 Fusion Pixel 字体 woff2"""
    cands = []
    pat = os.path.join(HERE, "font", "*.woff2")
    cands += glob.glob(pat)
    # npm 全局缓存
    npm_cache = os.path.join(os.path.expanduser("~"), "AppData", "Local", "npm-cache")
    if os.path.isdir(npm_cache):
        cands += glob.glob(os.path.join(npm_cache, "_cacache", "**", "*fusion-pixel*.woff2"), recursive=True)
    cands += glob.glob(os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "fontpkg",
                                    "**", "*.woff2"), recursive=True)
    cands = [c for c in cands if os.path.getsize(c) > 200000]
    return sorted(cands, key=os.path.getsize, reverse=True)[0] if cands else None


def gb2312_level1():
    """GB2312 一级字库(3755 个常用汉字), 避免导入新运行/LLM reasoning 时缺字"""
    out = []
    for hi in range(0xB0, 0xD8):          # 一级汉字区
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return "".join(out)


def collect_chars():
    chars = set(UI_TEXT) | set(gb2312_level1())
    # 回放数据里的动态文本(房间名/描述/决策理由/推理)
    for f in ("replay_data.js", "replay_data.json"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="ignore") as fh:
                chars |= set(fh.read())
    return "".join(sorted(c for c in chars if ord(c) > 31))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--woff2-only", action="store_true")
    ap.add_argument("--font", default=None)
    args = ap.parse_args()

    src = args.font or find_font_file()
    if not src:
        print("未找到 Fusion Pixel 字体 woff2。")
        print("请先下载: npm pack @fontsource/fusion-pixel-12px-proportional-sc")
        print("解压后把 files/*.woff2 放到 ./font/ 目录, 或用 --font 指定路径。")
        sys.exit(1)

    chars = collect_chars()
    out_woff2 = os.path.join(HERE, "font_subset.woff2")
    cmd = [sys.executable, "-m", "fontTools.subset", src,
           "--text=" + chars, "--flavor=woff2",
           "--layout-features=", "--no-hinting", "--desubroutinize",
           "--output-file=" + out_woff2, "--drop-tables+=DSIG"]
    subprocess.run(cmd, check=True)
    size = os.path.getsize(out_woff2)
    print(f"子集字符数: {len(chars)}  输出: {out_woff2} ({size/1024:.1f} KB)")

    if not args.woff2_only:
        b64 = base64.b64encode(open(out_woff2, "rb").read()).decode()
        css = ("/* Fusion Pixel Font 12px Proportional SC (OFL-1.1) 子集, 由 build_font.py 生成 */\n"
               "@font-face{\n"
               "  font-family:'FusionPixel';\n"
               "  src:url(data:font/woff2;base64," + b64 + ") format('woff2');\n"
               "  font-weight:400; font-style:normal; font-display:swap;\n"
               "}\n")
        out_css = os.path.join(HERE, "font_subset.css")
        with open(out_css, "w", encoding="utf-8") as f:
            f.write(css)
        print(f"输出: {out_css} ({os.path.getsize(out_css)/1024:.1f} KB)")
        # JS 版: 运行时注入 <style>, data URL 方式不受 file:// 的字体跨域限制
        out_js = os.path.join(HERE, "font_data.js")
        with open(out_js, "w", encoding="utf-8") as f:
            f.write("window.FONT_CSS = " + json.dumps(css) + ";\n")
        print(f"输出: {out_js} ({os.path.getsize(out_js)/1024:.1f} KB)")


if __name__ == "__main__":
    main()

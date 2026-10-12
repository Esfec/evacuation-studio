"""analysis.py — 群体行为分析渲染模块"""

_AC = {"Cognitive": "#3B82F6", "Perceptual": "#F59E0B", "Follower": "#EF4444"}
_MODE_C = {
    "LLM_API":      "#8B5CF6",
    "Panic_Follow": "#EF4444",
    "Rule":         "#3B82F6",
    "Rule_Fallback":"#F59E0B",
    "Mock":         "#6B7280",
    "Baseline_Rule":"#10B981",
}


def _x(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _line_chart(series, W, H, title, y_max=1.0, y_fmt="{:.1f}", xs=None):
    """
    通用 SVG 折线图。
    series: [(values_list, color, label), ...]
    """
    PL, PR, PT, PB = 40, 14, 30, 26
    cw = W - PL - PR
    ch = H - PT - PB
    y_max = y_max if y_max > 0 else 1.0

    out = [
        f'<svg width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="#0D1019" rx="5"/>',
        f'<text x="{W//2}" y="18" text-anchor="middle" font-size="11" '
        f'fill="#7B93B8" font-family="Arial">{_x(title)}</text>',
    ]

    # 横向网格线 + Y 轴标签
    for i in range(5):
        frac = i / 4
        py   = int(PT + ch * (1 - frac))
        out.append(f'<line x1="{PL}" y1="{py}" x2="{W - PR}" y2="{py}" '
                   f'stroke="#161D2F" stroke-width="1"/>')
        out.append(f'<text x="{PL - 4}" y="{py + 4}" text-anchor="end" '
                   f'font-size="9" fill="#2E3D52" font-family="monospace">'
                   f'{y_fmt.format(frac * y_max)}</text>')

    # 左侧轴线
    out.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT + ch}" '
               f'stroke="#161D2F" stroke-width="1"/>')

    # 数据折线
    for vals, color, lbl in series:
        n = len(vals)
        if n < 2:
            continue
        pts = " ".join(
            f"{PL + i / (n - 1) * cw:.1f},"
            f"{PT + ch * (1 - min(1.0, max(0.0, v / y_max))):.1f}"
            for i, v in enumerate(vals)
        )
        out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                   f'stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>')

    # X 轴标签
    if xs and len(xs) >= 2:
        n   = len(xs)
        stp = max(1, n // 5)
        for i in range(0, n, stp):
            x = PL + i / (n - 1) * cw
            out.append(f'<text x="{x:.1f}" y="{H - 3}" text-anchor="middle" '
                       f'font-size="9" fill="#2E3D52" font-family="monospace">{xs[i]}</text>')

    # 图例（折线段 + 文字）
    lx = PL + 6
    for vals, color, lbl in series:
        out.append(f'<line x1="{lx}" y1="{PT - 9}" x2="{lx + 12}" y2="{PT - 9}" '
                   f'stroke="{color}" stroke-width="2"/>')
        out.append(f'<text x="{lx + 16}" y="{PT - 5}" font-size="9" '
                   f'fill="{color}" font-family="Arial">{_x(lbl)}</text>')
        lx += len(lbl) * 6 + 30

    out.append('</svg>')
    return "\n".join(out)


def build_analysis_html(eng, step):
    """生成群体行为分析 HTML 报告"""
    step_stats = getattr(eng, 'step_stats', [])
    agents = eng.agents
    nodes  = eng.nodes
    logs   = eng.logs
    cot    = eng.cot_logs
    types  = ["Cognitive", "Perceptual", "Follower"]

    _placeholder = ('<div style="color:#2E3D52;text-align:center;'
                    'padding:55px 0;font-size:11px">运行仿真后显示</div>')

    # ──────────────────────────────────────
    # 1. 最终状态统计（KPI）
    # ──────────────────────────────────────
    fin = {}
    for t in types:
        ta  = [a for a in agents if a['type'] == t]
        n   = len(ta) or 1
        esc = [a for a in ta if a['status'] == 'Escaped']
        # 平均逃生步数 = history 长度 - 1（初始节点不算移动）
        avg_steps = (sum(len(a['history']) - 1 for a in esc) / len(esc)
                     if esc else 0.0)
        fin[t] = {
            'total':      len(ta),
            'escaped':    len(esc),
            'dead':       sum(1 for a in ta if a['status'] == 'Dead'),
            'active':     sum(1 for a in ta if a['status'] == 'Active'),
            'esc_rate':   len(esc) / n,
            'avg_panic':  sum(a['panic_level'] for a in ta) / n,
            'avg_steps':  avg_steps,
        }

    # ──────────────────────────────────────
    # 2. 时序图（恐慌演化 + 逃生进度）
    # ──────────────────────────────────────
    has_ts = len(step_stats) >= 2

    if has_ts:
        xs = [s['step'] for s in step_stats]

        def _ts(key):
            return [s.get(key, 0) for s in step_stats]

        panic_chart = _line_chart(
            [(_ts('avg_panic_Cognitive'),  "#3B82F6", "认知型"),
             (_ts('avg_panic_Perceptual'), "#F59E0B", "感知型"),
             (_ts('avg_panic_Follower'),   "#EF4444", "跟随型")],
            W=510, H=200, title="平均恐慌值演化",
            y_max=1.0, xs=xs,
        )
        max_esc = max(
            max(_ts('escaped_Cognitive')  or [0]),
            max(_ts('escaped_Perceptual') or [0]),
            max(_ts('escaped_Follower')   or [0]),
            1,
        )
        esc_chart = _line_chart(
            [(_ts('escaped_Cognitive'),  "#3B82F6", "认知型"),
             (_ts('escaped_Perceptual'), "#F59E0B", "感知型"),
             (_ts('escaped_Follower'),   "#EF4444", "跟随型")],
            W=510, H=200, title="逃生累积人数",
            y_max=max_esc, y_fmt="{:.0f}", xs=xs,
        )
    else:
        panic_chart = esc_chart = _placeholder

    # ──────────────────────────────────────
    # 3. 决策模式分布柱状图
    # ──────────────────────────────────────
    mc = {t: {} for t in types}
    for lg in cot:
        t = lg.get('agent_type', '')
        m = lg.get('decision_mode', '')
        if t in mc:
            mc[t][m] = mc[t].get(m, 0) + 1

    main_modes = ["LLM_API", "Panic_Follow", "Rule", "Rule_Fallback", "Mock"]
    present    = [m for m in main_modes
                  if any(mc[t].get(m, 0) > 0 for t in types)]

    BCW, BCH       = 480, 210
    BPL, BPR       = 40, 14
    BPT, BPB       = 30, 62
    bcw = BCW - BPL - BPR
    bch = BCH - BPT - BPB
    max_mc = max((mc[t].get(m, 0) for t in types for m in present), default=1)
    n_m    = max(len(present), 1)
    grp_w  = bcw / 3
    b_w    = grp_w * 0.75 / n_m

    bp = [
        f'<svg width="{BCW}" height="{BCH}">',
        f'<rect width="{BCW}" height="{BCH}" fill="#0D1019" rx="5"/>',
        f'<text x="{BCW // 2}" y="18" text-anchor="middle" font-size="11" '
        f'fill="#7B93B8" font-family="Arial">决策模式分布对比</text>',
    ]

    for i in range(4):
        frac = i / 3
        py   = int(BPT + bch * (1 - frac))
        bp.append(f'<line x1="{BPL}" y1="{py}" x2="{BCW - BPR}" y2="{py}" '
                  f'stroke="#161D2F" stroke-width="1"/>')
        bp.append(f'<text x="{BPL - 4}" y="{py + 4}" text-anchor="end" '
                  f'font-size="9" fill="#2E3D52">{int(frac * max_mc)}</text>')

    for ti, t in enumerate(types):
        gx = BPL + ti * grp_w + grp_w * 0.12
        for mi, m in enumerate(present):
            cnt = mc[t].get(m, 0)
            bh  = int(cnt / max_mc * bch) if max_mc else 0
            bx  = gx + mi * b_w
            by  = BPT + bch - bh
            col = _MODE_C.get(m, '#888')
            bp.append(f'<rect x="{bx:.1f}" y="{by}" width="{b_w * 0.85:.1f}" '
                      f'height="{max(0, bh)}" fill="{col}" opacity="0.85" rx="2"/>')
            if bh > 14:
                bp.append(f'<text x="{bx + b_w * 0.42:.1f}" y="{by + bh - 3}" '
                          f'text-anchor="middle" font-size="8" fill="white">{cnt}</text>')
        lbx = BPL + ti * grp_w + grp_w / 2
        bp.append(f'<text x="{lbx:.1f}" y="{BCH - BPB + 17}" text-anchor="middle" '
                  f'font-size="10" fill="{_AC[t]}" font-family="Arial">{t}</text>')

    # 图例
    lx = BPL
    for m in present:
        col = _MODE_C.get(m, '#888')
        bp.append(f'<rect x="{lx}" y="{BCH - 12}" width="8" height="8" '
                  f'fill="{col}" rx="1"/>')
        bp.append(f'<text x="{lx + 11}" y="{BCH - 4}" font-size="9" '
                  f'fill="#2E3D52" font-family="monospace">{m}</text>')
        lx += len(m) * 6.2 + 20
    bp.append('</svg>')
    mode_chart = "\n".join(bp)

    # ──────────────────────────────────────
    # 4. 节点访问热度
    # ──────────────────────────────────────
    nv = {}
    for lg in logs:
        nd = lg.get('To', '')
        if nd:
            nv[nd] = nv.get(nd, 0) + 1
    max_nv = max(nv.values(), default=1)

    nt_col = {
        'exit': '#22C55E', 'stairs': '#CA8A04', 'fire': '#DC2626',
        'corridor': '#3B82F6', 'room': '#7C3AED', 'deadend': '#F59E0B',
        'door': '#2563EB', 'hall': '#6366F1',
    }
    nr_html = ""
    for nid, cnt in sorted(nv.items(), key=lambda x: -x[1])[:14]:
        nd  = nodes.get(nid, {})
        nm  = _x(nd.get('name', nid))
        tc  = nt_col.get(nd.get('type', ''), '#6B7280')
        pct = int(cnt / max_nv * 100)
        nr_html += (
            f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0;'
            f'border-bottom:1px solid #0D1019">'
            f'<span style="min-width:30px;color:#2E3D52;font-family:monospace;font-size:10px">{nid}</span>'
            f'<span style="min-width:68px;font-size:10px;color:#4B5E7A;'
            f'overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{nm}</span>'
            f'<div style="flex:1;height:10px;background:#111520;border-radius:2px">'
            f'<div style="height:100%;width:{pct}%;background:{tc}33;'
            f'border-right:2px solid {tc};border-radius:2px"></div></div>'
            f'<span style="min-width:28px;text-align:right;font-family:monospace;'
            f'font-size:10px;color:{tc}">{cnt}</span>'
            f'</div>'
        )

    # ──────────────────────────────────────
    # 5. 恐慌程度分布（低/中/高）
    # ──────────────────────────────────────
    brk      = {t: [0, 0, 0] for t in types}
    brk_cols = ["#22C55E", "#F59E0B", "#EF4444"]
    brk_lbls = ["低恐慌 <0.3", "中恐慌 0.3-0.65", "高恐慌 >0.65"]

    for a in agents:
        t, p = a['type'], a['panic_level']
        if t in brk:
            brk[t][0 if p < 0.3 else (1 if p < 0.65 else 2)] += 1

    pb_html = ""
    for t in types:
        tot  = sum(brk[t]) or 1
        segs = "".join(
            f'<div title="{brk_lbls[i]}: {brk[t][i]}人" '
            f'style="height:100%;width:{brk[t][i] / tot * 100:.0f}%;'
            f'background:{c};display:inline-block"></div>'
            for i, c in enumerate(brk_cols)
            if brk[t][i] > 0
        )
        pb_html += (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
            f'<span style="color:{_AC[t]};font-size:10px;min-width:90px">{t}</span>'
            f'<div style="flex:1;height:14px;background:#111520;border-radius:3px;'
            f'overflow:hidden;display:flex">{segs}</div>'
            f'<span style="font-size:10px;color:#EF4444;min-width:60px;text-align:right">'
            f'{brk[t][2]} 人极度恐慌</span>'
            f'</div>'
        )

    # ──────────────────────────────────────
    # 6. KPI 卡片
    # ──────────────────────────────────────
    kpi_html = ""
    for t in types:
        s  = fin[t]
        ac = _AC[t]
        kpi_html += f"""
        <div style="background:#0D1019;border:1px solid #1C2535;border-radius:6px;
                    padding:12px;border-top:2px solid {ac}">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:10px">
            <span style="color:{ac};font-size:12px;font-weight:bold">{t}</span>
            <span style="font-size:22px;color:#22C55E;font-weight:bold">
              {s['esc_rate']:.0%}
            </span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);
                      gap:4px;text-align:center">
            <div>
              <div style="color:#22C55E;font-size:16px;font-weight:bold">{s['escaped']}</div>
              <div style="font-size:9px;color:#2E3D52;margin-top:2px">逃生</div>
            </div>
            <div>
              <div style="color:#EF4444;font-size:16px;font-weight:bold">{s['dead']}</div>
              <div style="font-size:9px;color:#2E3D52;margin-top:2px">遇难</div>
            </div>
            <div>
              <div style="color:#F59E0B;font-size:16px;font-weight:bold">{s['avg_panic']:.2f}</div>
              <div style="font-size:9px;color:#2E3D52;margin-top:2px">均恐慌</div>
            </div>
            <div>
              <div style="color:#7B93B8;font-size:16px;font-weight:bold">{s['avg_steps']:.1f}</div>
              <div style="font-size:9px;color:#2E3D52;margin-top:2px">均步数</div>
            </div>
          </div>
        </div>"""

    brk_legend = "".join(
        f'<span style="display:flex;align-items:center;gap:4px;font-size:10px;color:{c}">'
        f'■ {l}</span>'
        for c, l in zip(brk_cols, brk_lbls)
    )

    return f"""<!DOCTYPE html><html>
<head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#090B13;color:#7B93B8;font-family:Arial,sans-serif;
      padding:14px;font-size:12px}}
.title{{font-size:12px;color:#526280;letter-spacing:2px;margin-bottom:12px;
        padding-bottom:8px;border-bottom:1px solid #1C2535}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}}
.panel{{background:#0D1019;border:1px solid #1C2535;border-radius:6px;padding:10px}}
.pt{{font-size:10px;color:#2E3D52;letter-spacing:2px;text-transform:uppercase;
     margin-bottom:8px;border-bottom:1px solid #161B29;padding-bottom:5px}}
</style>
</head>
<body>

<div class="title">📈 GROUP BEHAVIOR ANALYSIS — STEP {step:03d}</div>

<div class="g3">{kpi_html}</div>

<div class="g2">
  <div class="panel">
    <div class="pt">📉 恐慌演化</div>
    {panic_chart}
  </div>
  <div class="panel">
    <div class="pt">🏃 逃生累积进度</div>
    {esc_chart}
  </div>
</div>

<div class="g2">
  <div class="panel">
    <div class="pt">🎛 决策模式分布</div>
    {mode_chart if present else _placeholder}
  </div>
  <div class="panel">
    <div class="pt">🗺 节点访问热度 TOP14</div>
    <div style="max-height:200px;overflow-y:auto">
      {nr_html or _placeholder}
    </div>
  </div>
</div>

<div class="panel">
  <div class="pt">😱 恐慌程度分布</div>
  {pb_html or _placeholder}
  <div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">
    {brk_legend}
  </div>
</div>

</body></html>"""
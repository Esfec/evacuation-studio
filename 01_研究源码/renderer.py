"""renderer.py — Streamlit HTML Renderer
Replaces the original pygame-based version.
Exports:
  build_topology_html(eng, step)       -> Light topology view
  build_dark_topology_html(eng, step)  -> Dark main view (tab1 primary view)
  build_floorplan_html(eng, step)      -> Floor plan (same as dark view)
"""
import math

# ── Node grid coordinates (col, row), col=4 is empty column gap ──────────────
GRID = {
    "N15": (0, 0), "N17": (1, 0), "N01": (2, 0), "N03": (3, 0),
    "N02": (5, 0), "N07": (6, 0),
    "N04": (0, 1), "N06": (1, 1), "N05": (2, 1),
    "N13": (5, 1), "N08": (6, 1), "N18": (7, 1),
    "N11": (0, 2), "N10": (1, 2), "N09": (2, 2),
    "N14": (5, 2), "N16": (6, 2),
    "N12": (1, 3),
}

CELL_W, CELL_H = 120, 110
OX, OY         = 70,  65
NODE_R         = 28

# ── Node colors ───────────────────────────────────────────────────────────────
_NC_DARK = {
    "fire": "#DC2626", "exit": "#16A34A",  "stairs":   "#CA8A04",
    "door": "#2563EB", "deadend": "#6B7280",
    "corridor": "#3B82F6", "room": "#7C3AED", "hall": "#6366F1",
}
_NC_LIGHT = {
    "fire": "#EF4444", "exit": "#22C55E",  "stairs":   "#EAB308",
    "door": "#60A5FA", "deadend": "#9CA3AF",
    "corridor": "#93C5FD", "room": "#C4B5FD", "hall": "#A5B4FC",
}
_AC = {"Cognitive": "#3B82F6", "Perceptual": "#F59E0B", "Follower": "#EF4444"}
_SD = {"Open": "#22C55E", "Risky": "#F59E0B", "Blocked": "#EF4444"}


# ── Utility functions ─────────────────────────────────────────────────────────

def _gp(nid):
    col, row = GRID.get(nid, (0, 0))
    return OX + col * CELL_W, OY + row * CELL_H

def _dedup(edges):
    seen, out = set(), []
    for e in edges:
        k = tuple(sorted([e["source"], e["target"]]))
        if k not in seen:
            seen.add(k); out.append(e)
    return out

def _amap(eng):
    m = {}
    for a in eng.agents:
        m.setdefault(a["current_node"], []).append(a)
    return m

def _esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _edge_stroke(risk, dark):
    if risk > 0.7:  return "#EF4444"
    if risk > 0.4:  return "#F97316"
    if risk > 0.15: return "#EAB308"
    return "#2D3748" if dark else "#CBD5E1"

def _place_agents(p, x, y, agents_here):
    """Draw agent dots inside node circles."""
    n = len(agents_here)
    for i, a in enumerate(agents_here[:12]):
        angle = i / max(n, 1) * 2 * math.pi - math.pi / 2
        sx = a.get("_slot_x", 0.0)
        sy = a.get("_slot_y", 0.0)
        r_off = NODE_R * 0.65
        ax = int(x + r_off * math.cos(angle + sx))
        ay = int(y + r_off * math.sin(angle + sy))
        dx, dy = ax - x, ay - y
        d = math.sqrt(dx*dx + dy*dy) or 1
        mr = NODE_R - 5
        if d > mr:
            ax = x + int(dx / d * mr)
            ay = y + int(dy / d * mr)
        ac  = _AC.get(a["type"], "#888")
        op  = "0.4" if a["status"] == "Exhausted" else "1"
        p.append(f'<circle cx="{ax}" cy="{ay}" r="4" fill="{ac}" '
                 f'stroke="#0B0D15" stroke-width="1" opacity="{op}"/>')


# ══════════════════════════════════════════════════════════════════════════════
#  Light Topology View
# ══════════════════════════════════════════════════════════════════════════════

def build_topology_html(eng, step):
    nodes = eng.nodes
    edges = _dedup(eng.edges)
    am    = _amap(eng)
    stats = eng.get_statistics()

    max_col = max(c for c, _ in GRID.values())
    max_row = max(r for _, r in GRID.values())
    W = OX * 2 + max_col * CELL_W + 40
    H = OY * 2 + max_row * CELL_H + 50

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
         f'<rect width="{W}" height="{H}" fill="#F8FAFC" rx="6"/>']

    # Grid dots
    for c in range(max_col + 2):
        for r in range(max_row + 2):
            p.append(f'<circle cx="{OX+c*CELL_W}" cy="{OY+r*CELL_H}" r="2" fill="#E2E8F0"/>')

    # Edges
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in GRID or t not in GRID: continue
        x1, y1 = _gp(s); x2, y2 = _gp(t)
        r  = max(nodes.get(s,{}).get("risk_level",0), nodes.get(t,{}).get("risk_level",0))
        sc = _edge_stroke(r, False)
        mx, my = (x1+x2)//2, (y1+y2)//2
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{sc}" stroke-width="2"/>')
        p.append(f'<rect x="{mx-11}" y="{my-8}" width="22" height="16" rx="3" fill="white" stroke="{sc}"/>')
        p.append(f'<text x="{mx}" y="{my+4}" text-anchor="middle" font-size="10" '
                 f'fill="#64748B" font-family="Arial">{e["dist"]}</text>')

    # Nodes
    for nid, node in nodes.items():
        if nid not in GRID: continue
        x, y   = _gp(nid)
        ntype  = node.get("type", "room")
        risk   = node.get("risk_level", 0)
        status = node.get("status", "Open")
        bc     = _NC_LIGHT.get(ntype, "#94A3B8")

        if risk > 0.4:
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R+10}" '
                     f'fill="rgba(239,68,68,{risk*0.25:.2f})"/>')
        p.append(f'<circle cx="{x+2}" cy="{y+3}" r="{NODE_R}" fill="rgba(0,0,0,0.12)"/>')
        p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" fill="{bc}"/>')
        if risk > 0.2:
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" '
                     f'fill="rgba(239,68,68,{min(0.6, risk*0.6):.2f})"/>')

        rim = "#EF4444" if status == "Blocked" else "white"
        rw  = 3        if status == "Blocked" else 2
        p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" fill="none" '
                 f'stroke="{rim}" stroke-width="{rw}"/>')

        if node.get("is_dead_end") or ntype == "deadend":
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R-8}" fill="none" '
                     f'stroke="white" stroke-width="1.5" opacity="0.6"/>')

        # ── Fix 3: When type=="fire", status dot should not show green "Open" ──
        _ds = "Risky" if ntype == "fire" and status == "Open" else status  # <- Fix
        sc2 = _SD.get(_ds)
        if sc2:
            sx = x + int(NODE_R*0.7); sy = y - int(NODE_R*0.7)
            p.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{sc2}" stroke="white" stroke-width="1"/>')

        p.append(f'<text x="{x}" y="{y-NODE_R-13}" text-anchor="middle" '
                 f'font-size="10" fill="#94A3B8" font-family="monospace">{nid}</text>')
        name = _esc(node.get("name", nid))
        p.append(f'<text x="{x}" y="{y+NODE_R+16}" text-anchor="middle" '
                 f'font-size="11" font-weight="bold" fill="#1E293B" font-family="Arial">{name}</text>')

        cnt = node.get("current_count", 0)
        if cnt > 0:
            p.append(f'<text x="{x}" y="{y+4}" text-anchor="middle" '
                     f'font-size="12" font-weight="bold" fill="white" font-family="Arial">{cnt}</text>')

        ah = [a for a in am.get(nid, []) if a["status"] in ("Active", "Exhausted")]
        for i, a in enumerate(ah[:8]):
            angle = i / max(len(ah), 1) * 2 * math.pi - math.pi/2
            ax = int(x + NODE_R*0.62*math.cos(angle))
            ay = int(y + NODE_R*0.62*math.sin(angle))
            p.append(f'<circle cx="{ax}" cy="{ay}" r="4" fill="{_AC.get(a["type"],"#888")}" '
                     f'stroke="white" stroke-width="1.5"/>')

    p.append('</svg>')
    svg = "\n".join(p)

    s = stats
    return f"""<!DOCTYPE html><html>
<head><meta charset="utf-8">
<style>
body{{margin:0;padding:10px;background:#F8FAFC;font-family:Arial,sans-serif;}}
h3{{margin:0 0 8px 0;font-size:13px;color:#64748B;}}
.chips{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;}}
.chip{{padding:3px 10px;border-radius:16px;font-size:12px;font-weight:bold;}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;}}
.li{{display:inline-flex;align-items:center;gap:4px;font-size:11px;color:#64748B;}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;}}
</style></head>
<body>
<h3>🔗 Topology — Step {step}</h3>
<div class="chips">
  <span class="chip" style="background:#DBEAFE;color:#1D4ED8">Active {s["active"]}</span>
  <span class="chip" style="background:#DCFCE7;color:#166534">Escaped ✅ {s["escaped"]}</span>
  <span class="chip" style="background:#F1F5F9;color:#475569">Dead 💀 {s["dead"]}</span>
  <span class="chip" style="background:#FEF3C7;color:#92400E">Panic {s["avg_panic"]:.2f}</span>
  <span style="font-size:12px;color:#CBD5E1">Total {s["total"]}</span>
</div>
<div style="overflow-x:auto">{svg}</div>
<div class="legend">
  <span class="li"><span class="dot" style="background:#EF4444"></span>Fire</span>
  <span class="li"><span class="dot" style="background:#22C55E"></span>Exit</span>
  <span class="li"><span class="dot" style="background:#EAB308"></span>Stairs</span>
  <span class="li"><span class="dot" style="background:#93C5FD"></span>Corridor</span>
  <span class="li"><span class="dot" style="background:#C4B5FD"></span>Gallery</span>
  <span class="li"><span class="dot" style="background:#9CA3AF"></span>Dead End</span>
  <span style="color:#CBD5E1">│</span>
  <span class="li"><span class="dot" style="background:#3B82F6"></span>Cognitive</span>
  <span class="li"><span class="dot" style="background:#F59E0B"></span>Perceptual</span>
  <span class="li"><span class="dot" style="background:#EF4444"></span>Follower</span>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  Dark Topology Main View (tab1, height=1020)
# ══════════════════════════════════════════════════════════════════════════════

def build_dark_topology_html(eng, step):
    nodes = eng.nodes
    edges = _dedup(eng.edges)
    am    = _amap(eng)
    stats = eng.get_statistics()

    max_col = max(c for c, _ in GRID.values())
    max_row = max(r for _, r in GRID.values())
    W = OX * 2 + max_col * CELL_W + 40
    H = OY * 2 + max_row * CELL_H + 55

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
         """<defs>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="fire" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur stdDeviation="7" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>""",
         f'<rect width="{W}" height="{H}" fill="#0B0D15"/>']

    for c in range(max_col + 2):
        for r in range(max_row + 2):
            p.append(f'<circle cx="{OX+c*CELL_W}" cy="{OY+r*CELL_H}" r="1.5" fill="#191E2E"/>')

    # Edges
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in GRID or t not in GRID: continue
        x1, y1 = _gp(s); x2, y2 = _gp(t)
        r  = max(nodes.get(s,{}).get("risk_level",0), nodes.get(t,{}).get("risk_level",0))
        sc = _edge_stroke(r, True)
        sw = 2 if r > 0.4 else 1.5
        mx, my = (x1+x2)//2, (y1+y2)//2
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{sc}" stroke-width="{sw}" opacity="0.75"/>')
        p.append(f'<rect x="{mx-11}" y="{my-8}" width="22" height="16" rx="3" '
                 f'fill="#0D1019" stroke="{sc}" opacity="0.7"/>')
        p.append(f'<text x="{mx}" y="{my+4}" text-anchor="middle" font-size="10" '
                 f'fill="#3D4F6A" font-family="monospace">{e["dist"]}</text>')

    # Nodes
    for nid, node in nodes.items():
        if nid not in GRID: continue
        x, y   = _gp(nid)
        ntype  = node.get("type", "room")
        risk   = node.get("risk_level", 0)
        smoke  = node.get("smoke_density", 0)
        status = node.get("status", "Open")
        bc     = _NC_DARK.get(ntype, "#6B7280")

        # ── Fire node type=="fire" should also trigger flame glow, not dependent on risk threshold ──
        if risk > 0.5 or ntype == "fire":                          # <- Fix
            fa = min(0.55, max(0.25, (risk - 0.5) * 1.2))         # <- Fix
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R+16}" '
                     f'fill="rgba(220,38,38,{fa:.2f})" filter="url(#fire)"/>')

        p.append(f'<circle cx="{x+2}" cy="{y+4}" r="{NODE_R}" fill="rgba(0,0,0,0.55)"/>')

        if status == "Blocked" or risk > 0.85:
            fill = "#7F1D1D"
        elif risk > 0.6:
            fill = "#92400E"
        else:
            fill = bc
        p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" fill="{fill}" filter="url(#glow)"/>')

        if smoke > 0.25:
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" '
                     f'fill="rgba(71,85,105,{min(0.65, smoke*0.75):.2f})"/>')

        rim = "#EF4444" if (status == "Blocked" or risk > 0.7 or ntype == "fire") else bc  # <- Fix
        p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R}" fill="none" '
                 f'stroke="{rim}" stroke-width="1.5" opacity="0.8"/>')

        if node.get("is_dead_end") or ntype == "deadend":
            p.append(f'<circle cx="{x}" cy="{y}" r="{NODE_R-8}" fill="none" '
                     f'stroke="{bc}" stroke-width="1.5" opacity="0.4"/>')

        # ── Fix 3: When type=="fire", status dot should not show green "Open" ──
        _ds = "Risky" if ntype == "fire" and status == "Open" else status  # <- Fix
        sc2 = _SD.get(_ds)
        if sc2:
            sx = x + int(NODE_R*0.70); sy = y - int(NODE_R*0.70)
            p.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{sc2}"/>')

        p.append(f'<text x="{x}" y="{y-NODE_R-14}" text-anchor="middle" '
                 f'font-size="10" fill="#2E3D52" font-family="monospace">{nid}</text>')
        nc   = "#C8D6E8" if risk < 0.5 else "#FCA5A5"
        name = _esc(node.get("name", nid))
        p.append(f'<text x="{x}" y="{y+NODE_R+16}" text-anchor="middle" '
                 f'font-size="11" font-weight="bold" fill="{nc}" font-family="Arial">{name}</text>')
        if risk > 0.05:
            rc = "#F87171" if risk > 0.5 else "#FCD34D"
            p.append(f'<text x="{x}" y="{y+NODE_R+29}" text-anchor="middle" '
                     f'font-size="9" fill="{rc}" font-family="monospace">{risk:.0%}</text>')

        ah = [a for a in am.get(nid, []) if a["status"] in ("Active", "Exhausted")]
        if ah:
            p.append(f'<circle cx="{x}" cy="{y}" r="13" fill="rgba(0,0,0,0.55)"/>')
            p.append(f'<text x="{x}" y="{y+4}" text-anchor="middle" '
                     f'font-size="12" font-weight="bold" fill="white" font-family="monospace">{len(ah)}</text>')
            _place_agents(p, x, y, ah)

    p.append('</svg>')
    svg = "\n".join(p)

    # Event log
    evs = getattr(eng, "step_event_log", [])[-15:]
    ev_html = ("".join(f'<div class="ev">{_esc(e)}</div>' for e in evs)
               or '<div style="color:#2D3D52;font-size:10px;padding:4px 0">(No events yet)</div>')

    # Type statistics table
    ts  = stats.get("type_stats", {})
    tbl = ""
    for t, d in ts.items():
        ac   = _AC.get(t, "#888")
        surv = f"{d['escaped']/d['total']*100:.0f}%" if d["total"] else "—"
        tbl += (f'<tr>'
                f'<td><span class="badge" style="background:{ac}22;color:{ac};">{t}</span></td>'
                f'<td>{d["total"]}</td>'
                f'<td style="color:#22C55E">{d["escaped"]}</td>'
                f'<td style="color:#6B7280">{d["dead"]}</td>'
                f'<td>{surv}</td>'
                f'<td style="color:#F59E0B">{d["avg_panic"]:.2f}</td>'
                f'</tr>')

    # Node risk list
    node_rows = ""
    for nid in sorted(nodes.keys()):
        if nid not in GRID: continue
        nd  = nodes[nid]
        r   = nd.get("risk_level", 0)
        st  = nd.get("status", "Open")
        rc  = "#EF4444" if r > 0.5 else ("#F59E0B" if r > 0.2 else "#22C55E")
        stc = {"Blocked":"#EF4444","Risky":"#F59E0B","Open":"#22C55E"}.get(st, "#6B7280")
        node_rows += (f'<div class="ng-row">'
                      f'<span class="ng-id">{nid}</span>'
                      f'<span class="ng-name">{_esc(nd.get("name",""))}</span>'
                      f'<span style="color:{rc}">{r:.0%}</span>'
                      f'<span style="color:{stc}">{st}</span>'
                      f'</div>')

    s = stats
    return f"""<!DOCTYPE html><html>
<head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#090B13;color:#7B93B8;font-family:"Courier New",monospace;padding:12px;font-size:12px;}}
.topbar{{display:flex;align-items:center;justify-content:space-between;padding-bottom:10px;
  border-bottom:1px solid #1C2535;margin-bottom:10px;flex-wrap:wrap;gap:8px;}}
.title{{font-size:13px;color:#526280;letter-spacing:2px;}}
.step{{font-size:24px;color:#3B82F6;font-weight:bold;}}
.kpi{{display:flex;gap:16px;}}
.kv{{font-size:18px;font-weight:bold;display:block;}}
.kl{{font-size:9px;color:#2E3D52;letter-spacing:1px;}}
.main{{display:flex;gap:12px;align-items:flex-start;}}
.svg-wrap{{overflow-x:auto;flex-shrink:0;}}
.sidebar{{display:flex;flex-direction:column;gap:10px;min-width:230px;flex:1;}}
.panel{{background:#0D1019;border:1px solid #1C2535;border-radius:6px;padding:10px;}}
.pt{{font-size:10px;color:#2E3D52;letter-spacing:2px;text-transform:uppercase;
  margin-bottom:6px;border-bottom:1px solid #161B29;padding-bottom:5px;}}
.events{{max-height:200px;overflow-y:auto;}}
.ev{{font-size:10px;color:#3D5070;padding:2px 0;border-bottom:1px solid #111520;}}
table{{width:100%;border-collapse:collapse;font-size:10px;}}
th{{color:#2E3D52;font-weight:normal;text-align:left;padding:3px 5px;border-bottom:1px solid #161B29;}}
td{{padding:3px 5px;border-bottom:1px solid #0D1019;}}
.badge{{padding:1px 7px;border-radius:8px;font-size:10px;}}
.ng-row{{display:flex;justify-content:space-between;padding:2px 0;
  border-bottom:1px solid #0D1019;font-size:10px;}}
.ng-id{{color:#2E3D52;min-width:32px;}}
.ng-name{{color:#4B5E7A;flex:1;margin:0 6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.ng-status{{max-height:240px;overflow-y:auto;}}
.legend{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;}}
.li{{display:inline-flex;align-items:center;gap:4px;font-size:10px;color:#2E3D52;}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
</style>
</head>
<body>
<div class="topbar">
  <div class="title">🔥 MUSEUM FIRE EVACUATION</div>
  <div style="display:flex;align-items:baseline;gap:6px;">
    <span style="font-size:10px;color:#2E3D52;">STEP</span>
    <span class="step">{step:03d}</span>
  </div>
  <div class="kpi">
    <div><span class="kv" style="color:#3B82F6">{s["active"]}</span><span class="kl">ACTIVE</span></div>
    <div><span class="kv" style="color:#22C55E">{s["escaped"]}</span><span class="kl">ESCAPED</span></div>
    <div><span class="kv" style="color:#6B7280">{s["dead"]}</span><span class="kl">DEAD</span></div>
    <div><span class="kv" style="color:#F59E0B">{s["avg_panic"]:.2f}</span><span class="kl">PANIC</span></div>
    <div><span class="kv" style="color:#7B93B8">{s["total"]}</span><span class="kl">TOTAL</span></div>
  </div>
</div>

<div class="main">
  <div class="svg-wrap">
    {svg}
    <div class="legend">
      <span class="li"><span class="dot" style="background:#DC2626"></span>Fire</span>
      <span class="li"><span class="dot" style="background:#16A34A"></span>Exit</span>
      <span class="li"><span class="dot" style="background:#CA8A04"></span>Stairs</span>
      <span class="li"><span class="dot" style="background:#2563EB"></span>Door</span>
      <span class="li"><span class="dot" style="background:#3B82F6"></span>Corridor</span>
      <span class="li"><span class="dot" style="background:#7C3AED"></span>Gallery</span>
      <span class="li"><span class="dot" style="background:#6B7280"></span>Dead End</span>
      <span style="color:#161B29">│</span>
      <span class="li"><span class="dot" style="background:#3B82F6"></span>Cognitive</span>
      <span class="li"><span class="dot" style="background:#F59E0B"></span>Perceptual</span>
      <span class="li"><span class="dot" style="background:#EF4444"></span>Follower</span>
      <span style="color:#161B29">│</span>
      <span class="li"><span class="dot" style="background:#22C55E"></span>Open</span>
      <span class="li"><span class="dot" style="background:#F59E0B"></span>Risky</span>
      <span class="li"><span class="dot" style="background:#EF4444"></span>Blocked</span>
    </div>
  </div>

  <div class="sidebar">
    <div class="panel">
      <div class="pt">📊 Agent Statistics</div>
      <table>
        <tr><th>Type</th><th>Total</th><th>Escaped</th><th>Dead</th><th>Survival</th><th>Panic</th></tr>
        {tbl if tbl else '<tr><td colspan="6" style="color:#2E3D52;padding:6px">Available after init</td></tr>'}
      </table>
    </div>
    <div class="panel">
      <div class="pt">📋 Step {step} Events</div>
      <div class="events">{ev_html}</div>
    </div>
    <div class="panel">
      <div class="pt">🗺️ Node Risk</div>
      <div class="ng-status">
        {node_rows if node_rows else '<div style="color:#2E3D52;font-size:10px;padding:4px">Available after init</div>'}
      </div>
    </div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  Floor Plan View (same as dark topology view)
# ══════════════════════════════════════════════════════════════════════════════

def build_floorplan_html(eng, step):
    """Floor plan view; current implementation is identical to the dark topology view."""
    return build_dark_topology_html(eng, step)
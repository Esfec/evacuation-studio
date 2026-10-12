"""renderer_3d.py — Three.js 3D 建筑模型渲染器"""
import json
from config import (
    ROOM_LAYOUT, CORRIDOR_PATHS, TYPE_CFG, STATUS_COLOR,
    STEP_SECONDS, GRID_W, GRID_H,
)

ROOM_HEIGHT_3D = {
    "fire": 3.0, "corridor": 1.8, "hall": 4.0, "room": 2.5,
    "door": 1.5, "stairs": 3.5, "exit": 2.0, "deadend": 2.5,
}
ROOM_COLOR_3D = {
    "fire": "#EF4444", "corridor": "#60A5FA", "hall": "#818CF8",
    "room": "#22D3EE", "door": "#A78BFA", "stairs": "#2DD4BF",
    "exit": "#4ADE80", "deadend": "#FBBF24",
}
ACCENT_COLOR_3D = {
    "fire": "#DC2626", "corridor": "#2563EB", "hall": "#4F46E5",
    "room": "#0891B2", "door": "#7C3AED", "stairs": "#0D9488",
    "exit": "#16A34A", "deadend": "#D97706",
}


def build_3d_html(engine, step, height=620):
    rooms = []
    for nid, (col, row, w, h, label, rtype) in ROOM_LAYOUT.items():
        node = engine.nodes.get(nid, {})
        rooms.append({
            "id": nid, "col": col, "row": row, "w": w, "h": h,
            "label": label.replace("\n", " "), "type": rtype,
            "h3d": ROOM_HEIGHT_3D.get(rtype, 2.0),
            "color": ROOM_COLOR_3D.get(rtype, "#94A3B8"),
            "accent": ACCENT_COLOR_3D.get(rtype, "#64748B"),
            "risk": round(node.get("risk_level", 0), 3),
            "smoke": round(node.get("smoke_density", 0), 3),
            "count": node.get("current_count", 0),
            "cap": node.get("capacity", 60),
            "status": node.get("status", "Open"),
        })

    corridors = []
    for (src, tgt), wpts in CORRIDOR_PATHS.items():
        sl, tl = ROOM_LAYOUT.get(src), ROOM_LAYOUT.get(tgt)
        if sl and tl:
            corridors.append({
                "sx": sl[0] + sl[2] / 2, "sz": sl[1] + sl[3] / 2,
                "tx": tl[0] + tl[2] / 2, "tz": tl[1] + tl[3] / 2,
            })

    agents_list = []
    for a in engine.agents:
        layout = ROOM_LAYOUT.get(a["current_node"])
        if not layout:
            continue
        col, row, w, h = layout[0], layout[1], layout[2], layout[3]
        cfg = TYPE_CFG[a["type"]]
        color = STATUS_COLOR.get(a["status"]) or cfg["color"]
        agents_list.append({
            "id": a["id"], "type": a["type"], "status": a["status"],
            "x": round(col + w / 2 + a["_slot_x"] * (w - 0.5), 2),
            "z": round(row + h / 2 + a["_slot_y"] * (h - 0.5), 2),
            "color": color, "panic": round(a["panic_level"], 2),
            "shape": cfg["shape"],
        })

    stats = engine.get_statistics()
    elapsed = step * STEP_SECONDS
    rj = json.dumps(rooms, ensure_ascii=False)
    cj = json.dumps(corridors, ensure_ascii=False)
    aj = json.dumps(agents_list, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f172a;overflow:hidden;font-family:Inter,system-ui,sans-serif}}
#c{{width:100%;height:{height}px;position:relative}}
canvas{{display:block}}
#hud{{position:absolute;top:10px;left:10px;background:rgba(15,23,42,.88);color:#e2e8f0;
  padding:10px 16px;border-radius:8px;font-size:12px;pointer-events:none;
  border:1px solid rgba(255,255,255,.08)}}
#hud b{{color:#fff;font-size:14px}}
#hud .s{{color:#94a3b8;margin-top:2px}}
#tip{{position:absolute;display:none;pointer-events:none;background:rgba(15,23,42,.92);
  color:#e2e8f0;padding:8px 12px;border-radius:6px;font-size:11px;max-width:230px;
  border:1px solid rgba(255,255,255,.12);box-shadow:0 4px 16px rgba(0,0,0,.4);z-index:10}}
#leg{{position:absolute;bottom:8px;left:8px;background:rgba(15,23,42,.85);color:#94a3b8;
  padding:6px 12px;border-radius:6px;font-size:10px;pointer-events:none;
  border:1px solid rgba(255,255,255,.06)}}
#leg i{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:3px;
  vertical-align:middle}}
#leg span{{margin-right:8px}}
#ctrl{{position:absolute;bottom:8px;right:8px;background:rgba(15,23,42,.6);color:#475569;
  padding:4px 8px;border-radius:4px;font-size:9px;pointer-events:none}}
</style>
</head>
<body>
<div id="c">
  <div id="hud">
    <b>🔥 博物馆疏散 3D</b> &nbsp;Step {step:03d}<br>
    <div class="s">⏱{elapsed}s &nbsp;
      <span style="color:#16a34a">✅{stats["escaped"]}</span>&nbsp;
      <span style="color:#dc2626">💀{stats["dead"]}</span>&nbsp;
      <span style="color:#3b82f6">🟢{stats["active"]}</span>
    </div>
  </div>
  <div id="tip"></div>
  <div id="leg">
    <span><i style="background:#2563eb"></i>认知</span>
    <span><i style="background:#d97706"></i>感知</span>
    <span><i style="background:#dc2626"></i>跟随</span>
    <span style="color:#475569">│</span>
    <span><i style="background:#4ade80"></i>出口</span>
    <span><i style="background:#ef4444"></i>火源</span>
    <span><i style="background:#fbbf24"></i>死胡同</span>
  </div>
  <div id="ctrl">🖱 左键旋转 · 右键平移 · 滚轮缩放</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
(function(){{
const R={rj};
const CO={cj};
const AG={aj};
const GW={GRID_W},GH={GRID_H},OX=GW/2,OZ=GH/2;

const ct=document.getElementById('c');
const W=ct.clientWidth,H={height};

const sc=new THREE.Scene();
sc.background=new THREE.Color(0x0f172a);
sc.fog=new THREE.FogExp2(0x0f172a,0.008);

const cam=new THREE.PerspectiveCamera(45,W/H,0.1,200);
cam.position.set(16,22,24);

const rn=new THREE.WebGLRenderer({{antialias:true}});
rn.setSize(W,H);
rn.setPixelRatio(Math.min(window.devicePixelRatio,2));
rn.shadowMap.enabled=true;
rn.shadowMap.type=THREE.PCFSoftShadowMap;
rn.toneMapping=THREE.ACESFilmicToneMapping;
rn.toneMappingExposure=1.2;
ct.appendChild(rn.domElement);

// Lights
sc.add(new THREE.AmbientLight(0x8090b0,0.5));
sc.add(new THREE.HemisphereLight(0x7ec8e3,0x3d2b1f,0.35));
const dl=new THREE.DirectionalLight(0xfff0dd,0.9);
dl.position.set(12,25,8);dl.castShadow=true;
dl.shadow.mapSize.set(2048,2048);
const scc=dl.shadow.camera;
scc.left=-22;scc.right=22;scc.top=22;scc.bottom=-22;scc.near=0.5;scc.far=60;
sc.add(dl);

// Floor
const flm=new THREE.MeshStandardMaterial({{color:0x1a2236,roughness:0.95}});
const fl=new THREE.Mesh(new THREE.PlaneGeometry(34,34),flm);
fl.rotation.x=-Math.PI/2;fl.position.y=-0.02;fl.receiveShadow=true;sc.add(fl);
sc.add(new THREE.GridHelper(34,34,0x2d3a50,0x1e293b));

function hc(hex){{return new THREE.Color(hex)}}
function rr(ctx,x,y,w,h,r){{
  ctx.beginPath();ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();
}}

// ── Rooms ──
const rmA=[],rg=new THREE.Group();
R.forEach(r=>{{
  const x=r.col+r.w/2-OX, z=r.row+r.h/2-OZ;
  const h3=r.h3d*(r.status==='Blocked'&&r.type!=='fire'?0.4:1);

  const g=new THREE.BoxGeometry(r.w*0.94,h3,r.h*0.94);
  const bc=hc(r.color);
  if(r.risk>0.1) bc.lerp(new THREE.Color(0xef4444),r.risk*0.6);
  if(r.status==='Blocked') bc.multiplyScalar(0.35);
  const mt=new THREE.MeshStandardMaterial({{
    color:bc,roughness:0.55,metalness:0.08,
    transparent:true,opacity:r.status==='Blocked'?0.45:0.88}});
  const ms=new THREE.Mesh(g,mt);
  ms.position.set(x,h3/2,z);ms.castShadow=true;ms.receiveShadow=true;
  ms.userData={{tp:'room',d:r}};rg.add(ms);rmA.push(ms);

  // Edges
  const eg=new THREE.EdgesGeometry(g);
  const em=new THREE.LineBasicMaterial({{
    color:r.status==='Blocked'?0x7f1d1d:0x3f4f6a,transparent:true,opacity:0.5}});
  const el=new THREE.LineSegments(eg,em);el.position.copy(ms.position);rg.add(el);

  // Top accent strip
  const ag2=new THREE.BoxGeometry(r.w*0.94,0.12,r.h*0.94);
  const ac2=hc(r.accent);
  const am2=new THREE.MeshStandardMaterial({{color:ac2,emissive:ac2,
    emissiveIntensity:r.type==='exit'?0.5:r.type==='fire'?0.9:0.12,roughness:0.3}});
  const amh=new THREE.Mesh(ag2,am2);amh.position.set(x,h3+0.06,z);rg.add(amh);

  // Exit glow ring
  if(r.type==='exit'){{
    const rg2=new THREE.RingGeometry(Math.max(r.w,r.h)*.52,Math.max(r.w,r.h)*.62,32);
    const rm2=new THREE.MeshBasicMaterial({{color:0x22c55e,transparent:true,opacity:0.35,
      side:THREE.DoubleSide}});
    const rms=new THREE.Mesh(rg2,rm2);rms.rotation.x=-Math.PI/2;rms.position.set(x,0.03,z);
    rms.userData._p=true;rg.add(rms);
  }}

  // Fire point light
  if(r.type==='fire'&&r.risk>0.2){{
    const pl=new THREE.PointLight(0xff4500,r.risk*2.5,10);
    pl.position.set(x,h3+1.5,z);rg.add(pl);
  }}

  // Smoke cloud
  if(r.smoke>0.1){{
    const sg2=new THREE.BoxGeometry(r.w*0.88,1.2,r.h*0.88);
    const sm2=new THREE.MeshBasicMaterial({{color:0x64748b,transparent:true,
      opacity:r.smoke*0.3}});
    const smh=new THREE.Mesh(sg2,sm2);smh.position.set(x,h3+0.7,z);
    smh.userData._sk=r.smoke*0.3;smh.userData._s=true;rg.add(smh);
  }}

  // Count badge
  if(r.count>0){{
    const cv=document.createElement('canvas');cv.width=64;cv.height=32;
    const cx=cv.getContext('2d');
    const ratio=r.count/Math.max(r.cap,1);
    cx.fillStyle=ratio>0.7?'#dc2626':ratio>0.4?'#f59e0b':'#16a34a';
    rr(cx,4,2,56,28,6);cx.fill();
    cx.fillStyle='#fff';cx.font='bold 18px monospace';
    cx.textAlign='center';cx.textBaseline='middle';
    cx.fillText(''+r.count,32,16);
    const tx=new THREE.CanvasTexture(cv);
    const sp=new THREE.Sprite(new THREE.SpriteMaterial({{map:tx,transparent:true}}));
    sp.scale.set(1,0.5,1);sp.position.set(x+r.w*0.32,h3+0.7,z+r.h*0.28);rg.add(sp);
  }}

  // Label
  const lc=document.createElement('canvas');lc.width=512;lc.height=96;
  const lx=lc.getContext('2d');
  lx.fillStyle='rgba(15,23,42,0.78)';rr(lx,4,4,504,88,10);lx.fill();
  lx.fillStyle='#e2e8f0';
  lx.font="bold 30px 'PingFang SC','Microsoft YaHei',sans-serif";
  lx.textAlign='center';lx.textBaseline='middle';
  const lb=r.label.length>10?r.label.substring(0,10)+'…':r.label;
  lx.fillText(lb,256,36);
  lx.fillStyle='#64748b';lx.font='22px monospace';
  lx.fillText(r.id,256,72);
  const lt=new THREE.CanvasTexture(lc);
  const ls=new THREE.Sprite(new THREE.SpriteMaterial({{map:lt,transparent:true,opacity:0.9}}));
  ls.scale.set(3.6,0.7,1);ls.position.set(x,h3+1.6,z);rg.add(ls);
}});
sc.add(rg);

// ── Corridors ──
CO.forEach(c=>{{
  const pts=[new THREE.Vector3(c.sx-OX,0.08,c.sz-OZ),
             new THREE.Vector3(c.tx-OX,0.08,c.tz-OZ)];
  const lg=new THREE.BufferGeometry().setFromPoints(pts);
  const lm=new THREE.LineDashedMaterial({{color:0xf59e0b,dashSize:0.3,gapSize:0.2,
    transparent:true,opacity:0.45}});
  const ln=new THREE.Line(lg,lm);ln.computeLineDistances();sc.add(ln);
  const mid=new THREE.Vector3((c.sx+c.tx)/2-OX,0.12,(c.sz+c.tz)/2-OZ);
  const dot=new THREE.Mesh(new THREE.SphereGeometry(0.1,8,6),
    new THREE.MeshBasicMaterial({{color:0xf59e0b}}));
  dot.position.copy(mid);sc.add(dot);
}});

// ── Agents ──
const agA=[];
AG.forEach(a=>{{
  const ax=a.x-OX, az=a.z-OZ;
  if(a.status==='Dead'){{
    const xm=new THREE.MeshBasicMaterial({{color:0x6b7280}});
    const g1=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.06,0.06),xm);g1.rotation.y=Math.PI/4;
    const g2=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.06,0.06),xm);g2.rotation.y=-Math.PI/4;
    const xg=new THREE.Group();xg.add(g1,g2);xg.position.set(ax,0.1,az);sc.add(xg);return;
  }}
  if(a.status==='Escaped'){{
    const gm=new THREE.MeshStandardMaterial({{color:0x16a34a,emissive:0x16a34a,
      emissiveIntensity:0.3}});
    const mesh=new THREE.Mesh(new THREE.SphereGeometry(0.22,10,10),gm);
    mesh.position.set(ax,0.25,az);mesh.userData={{tp:'agent',d:a}};sc.add(mesh);agA.push(mesh);
    return;
  }}
  let geo;
  const clr=hc(a.color);
  if(a.shape==='diamond') geo=new THREE.OctahedronGeometry(0.28);
  else if(a.shape==='circle') geo=new THREE.SphereGeometry(0.22,10,10);
  else geo=new THREE.BoxGeometry(0.3,0.3,0.3);
  const mat=new THREE.MeshStandardMaterial({{
    color:clr,emissive:clr,emissiveIntensity:0.15,roughness:0.4,metalness:0.25}});
  const mesh=new THREE.Mesh(geo,mat);
  mesh.position.set(ax,0.45,az);mesh.castShadow=true;
  mesh.userData={{tp:'agent',d:a}};sc.add(mesh);agA.push(mesh);

  if(a.panic>0.3){{
    const pg=new THREE.RingGeometry(0.22,0.32,12);
    const pm=new THREE.MeshBasicMaterial({{color:0xef4444,transparent:true,
      opacity:a.panic*0.55,side:THREE.DoubleSide}});
    const pr=new THREE.Mesh(pg,pm);pr.rotation.x=-Math.PI/2;
    pr.position.set(ax,0.04,az);sc.add(pr);
  }}
}});

// ── Controls ──
const ctrl=new THREE.OrbitControls(cam,rn.domElement);
ctrl.enableDamping=true;ctrl.dampingFactor=0.08;
ctrl.maxPolarAngle=Math.PI/2.15;ctrl.minDistance=5;ctrl.maxDistance=45;
ctrl.target.set(0,1,0);

// ── Tooltip ──
const rc=new THREE.Raycaster();
const mv=new THREE.Vector2();
const tip=document.getElementById('tip');
ct.addEventListener('mousemove',function(e){{
  const b=rn.domElement.getBoundingClientRect();
  mv.x=((e.clientX-b.left)/b.width)*2-1;
  mv.y=-((e.clientY-b.top)/b.height)*2+1;
  rc.setFromCamera(mv,cam);
  const hits=rc.intersectObjects(rmA.concat(agA));
  if(hits.length>0){{
    const u=hits[0].object.userData;
    if(u.tp==='room'){{
      const d=u.d;
      tip.innerHTML='<b>'+d.label+'</b> ('+d.id+')<br>'+
        '类型: '+d.type+' | 状态: '+d.status+'<br>'+
        '人数: '+d.count+'/'+d.cap+'<br>'+
        '风险: '+(d.risk*100).toFixed(0)+'% | 烟雾: '+(d.smoke*100).toFixed(0)+'%';
      tip.style.display='block';
    }}else if(u.tp==='agent'){{
      const d=u.d;
      tip.innerHTML='<b>'+d.id+'</b> ('+d.type+')<br>'+
        '状态: '+d.status+' | 恐慌: '+(d.panic*100).toFixed(0)+'%';
      tip.style.display='block';
    }}
    tip.style.left=(e.clientX-b.left+15)+'px';
    tip.style.top=(e.clientY-b.top-10)+'px';
  }}else{{tip.style.display='none'}}
}});

// ── Animate ──
let t=0;
function anim(){{
  requestAnimationFrame(anim);
  t+=0.016;
  ctrl.update();
  rg.children.forEach(function(ch){{
    if(ch.userData._p) ch.material.opacity=0.2+Math.sin(t*3)*0.2;
    if(ch.userData._s) ch.material.opacity=ch.userData._sk*(0.85+Math.sin(t*0.7)*0.15);
  }});
  agA.forEach(function(m,i){{
    if(m.userData.d&&m.userData.d.status==='Active'){{
      m.position.y=0.45+Math.sin(t*2+i*0.7)*0.04;
      m.rotation.y+=0.008;
    }}
  }});
  rn.render(sc,cam);
}}
anim();

window.addEventListener('resize',function(){{
  var w=ct.clientWidth;
  cam.aspect=w/{height};cam.updateProjectionMatrix();
  rn.setSize(w,{height});
}});
}})();
</script>
</body>
</html>"""
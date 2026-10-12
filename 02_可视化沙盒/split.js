'use strict';
// Synchronized split view (museum-ui-1.7). Presentation only: draws two recorded runs
// that differ only in design_id at the same step index with the same camera. The
// renderer is reused by swapping the per-run view state; no simulation state is touched.
(()=>{
const DESIGN={D0:'D0 原始方案',D1:'D1 N06↔N10 容量 ×2',D2:'D2 新增 N06↔N08 连廊'};
let on=false,showDeaths=true,partner=null,saved=null,lastIndex=-1;
const side={A:{},B:{}};
const KEYS=['run','index','frameBefore','staticCanvas','staticKey','selected','selectedRoom','fxFrame','fxElapsed','fxLast','hitAgents','transform'];
// Top-level `let` bindings from studio.js are shared through the global lexical scope.
const get=()=>({run,index,frameBefore,staticCanvas,staticKey,selected,selectedRoom,fxFrame,fxElapsed,fxLast,hitAgents,transform});
function put(s){({run,index,frameBefore,staticCanvas,staticKey,selected,selectedRoom,fxFrame,fxElapsed,fxLast,hitAgents,transform}=s)}

stage.insertAdjacentHTML('beforeend',`<div id="splitUI" class="split-ui" hidden><div class="split-tag split-a"><b id="splitNameA"></b><span id="splitStatA"></span></div><div class="split-delta"><span id="splitDelta"></span><button id="splitDeaths" class="on" title="显示每个房间的遇难人数">遇难点</button><button id="splitStats" title="终局数值对照">数值</button><button id="splitClose" title="退出分屏">×</button></div><div class="split-tag split-b"><select id="splitPartner" aria-label="对照方案"></select><span id="splitStatB"></span></div><i class="split-divider"></i></div>`);

function candidates(r){const key=comparisonKey(r);let c=runs.filter(x=>x!==r&&x.config.design_id!==r.config.design_id&&comparisonKey(x)===key);
  if(!c.length)c=runs.filter(x=>x!==r&&x.config.design_id!==r.config.design_id&&x.source===r.source&&x.config.policy_id===r.config.policy_id&&x.config.condition_id===r.config.condition_id&&x.config.seed===r.config.seed&&(x.config.fire_origin||'N01')===(r.config.fire_origin||'N01'));return c}
function pick(r){const c=candidates(r);const want=r.config.design_id==='D0'?'D2':'D0';return c.find(x=>x.config.design_id===want)||c[0]||null}
function diffEdges(a,b){const ea=new Map(a.topology.edges.map(e=>[[e.source,e.target].sort().join('-'),e.capacity_per_step||4]));const out=[];const seen=new Set();
  for(const e of b.topology.edges){const k=[e.source,e.target].sort().join('-');if(seen.has(k)||!ROUTES[k])continue;seen.add(k);if(!ea.has(k))out.push({k,kind:'new'});else if((e.capacity_per_step||4)>ea.get(k))out.push({k,kind:'wide',cap:e.capacity_per_step})}return out}
function counts(r,i){const f=r.snapshots[Math.min(i,r.snapshots.length-1)];return f.counts}

function fillPartners(){const c=candidates(saved?side.A.run||run:run);$('splitPartner').innerHTML=c.map(r=>`<option value="${runs.indexOf(r)}">${esc(DESIGN[r.config.design_id]||r.config.design_id)}</option>`).join('');if(partner)$('splitPartner').value=runs.indexOf(partner)}
function initB(){side.B={run:partner,index:0,frameBefore:null,staticCanvas:null,staticKey:'',selected:'',selectedRoom:'',fxFrame:null,fxElapsed:0,fxLast:0,hitAgents:[],transform:{scale:1,x:0,y:0}};lastIndex=-1}

function start(){if(on||!run)return;if(window.__tour&&document.body.classList.contains('touring'))window.__tour.stop();partner=pick(run);if(!partner){toast('没有找到同条件（策略、火情、seed、画像相同）的其他方案录制，无法分屏。');return}
  on=true;saved={show:document.body.classList.contains('show-mode'),bubbleMode,selected};document.body.classList.add('show-mode','split');$('showMode').textContent='▣ 研究模式';bubbleMode=0;selected='';$('compare').classList.add('on');
  initB();fillPartners();$('splitUI').hidden=false;sync()}
function stop(){if(!on)return;on=false;document.body.classList.remove('split');if(!saved.show){document.body.classList.remove('show-mode');$('showMode').textContent='▣ 展示模式'}bubbleMode=saved.bubbleMode;selected=saved.selected;$('compare').classList.remove('on');$('splitUI').hidden=true;staticKey='';detail()}

function sync(){if(!on)return;const a=run,b=partner,ca=counts(a,index),cb=counts(b,index),n=a.snapshots[0].agents.length,d=cb.escaped-ca.escaped,dd=cb.dead-ca.dead;
  $('splitNameA').textContent=DESIGN[a.config.design_id]||a.config.design_id;
  $('splitStatA').innerHTML=`已疏散 <b>${ca.escaped}</b> · 遇难 <b>${ca.dead}</b>`;$('splitStatB').innerHTML=`已疏散 <b>${cb.escaped}</b> · 遇难 <b>${cb.dead}</b>`;
  const ia=Math.min(index,a.snapshots.length-1),ib=Math.min(index,b.snapshots.length-1);
  $('splitDelta').innerHTML=`STEP ${String(a.snapshots[ia].completed_steps).padStart(2,'0')}${ib<index?` <small>(${b.config.design_id} 已于第 ${b.snapshots.at(-1).completed_steps} 步结束)</small>`:''}<br>${b.config.design_id} − ${a.config.design_id}：疏散 <em class="${d>0?'up':d<0?'down':''}">${d>0?'+':''}${d}</em> · 遇难 <em class="${dd<0?'up':dd>0?'down':''}">${dd>0?'+':''}${dd}</em> <small>/ ${n} 人 · 单次录制</small>${geo(a.snapshots[ia],b.snapshots[ib],b.config.design_id,a.config.design_id)}`}
function geo(fa,fb,nb,na){const da=deaths(fa),db=deaths(fb),ids=[...new Set([...Object.keys(da),...Object.keys(db)])].map(id=>({id,d:(db[id]||0)-(da[id]||0)})).filter(x=>x.d).sort((x,y)=>Math.abs(y.d)-Math.abs(x.d)).slice(0,4);
  return ids.length?`<br><small>遇难地点变化（${nb} 相对 ${na}）：</small>${ids.map(x=>`${x.id} <em class="${x.d<0?'up':'down'}">${x.d>0?'+':''}${x.d}</em>`).join(' · ')}`:''}

function deaths(f){const o={};for(const a of f.agents)if(a.status==='Dead')o[a.node]=(o[a.node]||0)+1;return o}
// Recorded final-death locations per room: the paper's 'failure geography' made visible.
function deathBadges(f){const d=deaths(f);ctx.save();ctx.translate(transform.x,transform.y);ctx.scale(transform.scale,transform.scale*YR);
  for(const [id,n] of Object.entries(d)){const r=ROOMS[id];if(!r)continue;const x=r[0]+r[2]-40,y=r[1]+20;rect(ctx,x-2,y-2,40,22,'#5e1f14');rect(ctx,x,y,36,18,'#c0462c');text(ctx,'✕ '+n,x+18,y+14,13,'#fff3e0','center')}
  ctx.restore()}
function midpoint(pts){const L=pts.slice(1).map((p,i)=>Math.hypot(p[0]-pts[i][0],p[1]-pts[i][1]));let d=L.reduce((a,b)=>a+b,0)/2;for(let i=0;i<L.length;i++){if(d<=L[i]){const k=L[i]?d/L[i]:0;return[pts[i][0]+(pts[i+1][0]-pts[i][0])*k,pts[i][1]+(pts[i+1][1]-pts[i][1])*k]}d-=L[i]}return pts[0]}
function highlight(now,diffs){if(!diffs.length)return;ctx.save();ctx.translate(transform.x,transform.y);ctx.scale(transform.scale,transform.scale*YR);const pulse=effectsMode===0?.55+.45*Math.sin(now/260):1;
  for(const d of diffs){const r=ROUTES[d.k];ctx.save();ctx.globalAlpha=.35*pulse;line(ctx,r.points,22,d.kind==='new'?'#f2c14e':'#7fb2d9');ctx.globalAlpha=1;ctx.setLineDash([10,7]);line(ctx,r.points,4,d.kind==='new'?'#b87a14':'#3f78a8');ctx.restore();
    const m=midpoint(r.points);const label=d.kind==='new'?'新增连廊':`容量 ×${Math.round((d.cap||8)/4)}`;
    rect(ctx,m[0]-34,m[1]-14,68,22,'#fff3c8');rect(ctx,m[0]-34,m[1]-14,68,3,d.kind==='new'?'#b87a14':'#3f78a8');text(ctx,label,m[0],m[1]+3,12,'#6a4614','center')}
  ctx.restore()}

const baseDraw=draw;
draw=function(now){if(!on||!partner)return baseDraw(now);
  const fullW=cw,half=Math.floor(fullW/2);
  if(index!==lastIndex){const prevB=lastIndex<0?null:partner.snapshots[Math.min(lastIndex,partner.snapshots.length-1)];side.B.frameBefore=prevB;side.B.index=Math.min(index,partner.snapshots.length-1);lastIndex=index;sync()}
  ctx.clearRect(0,0,fullW,ch);
  // Centre both buildings in the band between the name tags and the comparison panel.
  const tag=document.querySelector('.split-tag'),panel=document.querySelector('.split-delta'),top=tag?tag.offsetTop+tag.offsetHeight:0,bottom=panel?panel.offsetTop:ch,fullH=ch,band=Math.max(200,bottom-top);
  ctx.save();ctx.translate(0,top-40);ch=band+80;window.__labelShort=Math.min((half-35)/W,(ch-85)/(H*YR))*zoom<.62;
  // Left: the selected run, with its own view state as studio.js keeps it.
  ctx.save();ctx.beginPath();ctx.rect(0,0,half,ch);ctx.clip();cw=half;baseDraw(now);if(showDeaths)deathBadges(frame());ctx.restore();
  side.A=get();
  // Right: the partner run at the same step index and camera.
  put({...side.A,...side.B});ctx.save();ctx.translate(half,0);ctx.beginPath();ctx.rect(0,0,fullW-half,ch);ctx.clip();cw=fullW-half;baseDraw(now);highlight(now,diffEdges(side.A.run,partner));if(showDeaths)deathBadges(frame());ctx.restore();
  const g=get();for(const k of ['frameBefore','staticCanvas','staticKey','fxFrame','fxElapsed','fxLast'])side.B[k]=g[k];
  ctx.restore();ch=fullH;window.__labelShort=false;put(side.A);cw=fullW;hitAgents=[];
};
// In split view a click selects nothing (two maps share one canvas); dragging still pans both.
stage.addEventListener('pointerup',()=>{if(on&&pointer&&!pointer.moved)pointer=null},{capture:true});

const oldCompare=$('compare').onclick;$('compare').title='分屏对照：同条件不同方案同步回放';
$('compare').onclick=()=>{on?stop():start();$('compare').blur()};$('splitClose').onclick=stop;$('splitDeaths').onclick=()=>{showDeaths=!showDeaths;$('splitDeaths').classList.toggle('on',showDeaths)};$('splitStats').onclick=()=>oldCompare&&oldCompare();
$('splitPartner').onchange=e=>{partner=runs[+e.target.value];initB();sync()};
$('runSelect').addEventListener('change',()=>{if(!on)return;const p=pick(run);if(!p){stop();toast('当前录制没有同条件的对照方案，已退出分屏。');return}partner=p;initB();fillPartners();sync()});
window.__split={start,stop,get on(){return on},get partner(){return partner}};
})();

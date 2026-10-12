'use strict';
// Guided tour (museum-ui-1.7). Presentation only: every chapter is selected from the
// loaded recording and every sentence is filled from recorded fields. Nothing here is
// fed back into the simulation, and narration is labelled as front-end synthesis.
(()=>{
const TYPE_SHORT={Cognitive:'认知型',Perceptual:'感知型',Follower:'跟随型'};
const ease=(a,b,k)=>a+(b-a)*k;
let on=false,chapters=[],ci=0,saved=null,timer=null,typing=null,cam={zoom:1,x:W/2,y:H/2,agent:''},full='';
const name=id=>(nodeMeta(id).name||id);
const roomLabel=id=>`${id} ${name(id)}`;

document.querySelector('.header-actions').insertAdjacentHTML('afterbegin','<button id="tourStart" class="tour-start" title="自动导览当前录制（← → 切换，Esc 退出）">★ 导览</button>');
stage.insertAdjacentHTML('beforeend',`<div id="tourTitle" class="tour-title" hidden><div class="tour-title-card"><small>QIMU MUSEUM · EVACUATION STORY</small><h2 class="pixel" id="tourHeadline">栖木博物馆的疏散</h2><p id="tourTitleSub"></p><button id="tourGo" class="primary">▶ 开始导览</button><span class="tour-hint">→ / Enter 下一幕 · ← 上一幕 · Esc 退出</span></div></div>
<div id="tourRibbon" class="tour-ribbon" hidden></div>
<div id="tourBox" class="tour-box" hidden role="dialog" aria-live="polite"><canvas id="tourPortrait" width="88" height="96" aria-hidden="true"></canvas><div class="tour-main"><div class="tour-name"><b id="tourName"></b><span id="tourRole"></span></div><div id="tourText" class="tour-text"></div><div id="tourMeta" class="tour-meta"></div></div><div class="tour-nav"><span id="tourCount"></span><button id="tourPrev" aria-label="上一幕">◀</button><button id="tourNext" aria-label="下一幕">▶</button><button id="tourExit" aria-label="退出导览">×</button></div><i class="tour-caret">▼</i></div>`);

function stepOf(f){return f.completed_steps||0}
function pathOf(S,id,upto){const out=[];for(let i=0;i<=upto&&i<S.length;i++){const a=S[i].agents.find(q=>q.id===id);if(a&&out.at(-1)!==a.node)out.push(a.node)}return out}
function narr(a){try{return agentNarrative(a,null,name)}catch(e){return{text:a.summary||'',label:'原始记录'}}}

function build(){
  const S=run.snapshots,first=S[0],last=S.at(-1),cfg=run.config,out=[];
  const count=t=>first.agents.filter(a=>a.type===t).length;
  const rooms=new Set(first.agents.map(a=>a.node)).size;
  const policy=POLICIES[cfg.policy_id]||cfg.policy_id;
  out.push({kind:'title',title:'序',from:0,to:0,cam:{zoom:1}});
  out.push({title:'开馆',speaker:'讲解员',role:'导览旁白',portrait:'guide',from:0,to:0,cam:{zoom:.82},
    text:`这是一层的 18 个空间。录制开始时，${first.agents.length} 人分散在 ${rooms} 个房间：认知型 ${count('Cognitive')} 人、感知型 ${count('Perceptual')} 人、跟随型 ${count('Follower')} 人。脚下的色环就是类型。`,
    meta:`每人只能感知自己所在房间连通的门洞；每步最多走一跳，标称 ${cfg.step_seconds||5} 秒。决策策略：${policy}。`});
  // Fire: first step at which the configured origin (or any room) is recorded at high risk.
  const origin=cfg.fire_origin||'N01';let k=S.findIndex(f=>f.nodes.some(n=>n.id===origin&&n.risk>=.5));if(k<0)k=S.findIndex(f=>f.nodes.some(n=>n.risk>=.5));
  if(k>=0){let to=S.findIndex((f,i)=>i>k&&f.nodes.filter(n=>n.risk>=.5).length>=3);if(to<0)to=k+5;to=Math.min(S.length-1,to,k+6);const f=S[to],smoky=f.nodes.filter(n=>n.smoke>=.1).length,hot=f.nodes.filter(n=>n.risk>=.5),o=S[k].nodes.find(n=>n.id===origin);
    out.push({title:'起火',speaker:'讲解员',role:'导览旁白',portrait:'guide',from:k,to,room:origin,cam:{zoom:1.45,room:origin},
      text:`起火点在 ${roomLabel(origin)}。${stepOf(S[k])?`第 ${stepOf(S[k])} 步`:'录制开始时'}，这里的记录风险已达 ${(o?.risk??0).toFixed(2)}；到第 ${stepOf(f)} 步，${smoky} 个空间明显进烟（浓度 ≥ 0.1），高风险空间增加到 ${hot.length} 个：${hot.map(n=>name(n.id)).join('、')}。`,
      meta:'火焰与烟团是记录中 risk / smoke 字段的图示，传播沿拓扑跳数计时，不是物理燃烧模型。'})}
  // A Cognitive occupant who escaped earliest.
  const escStep=id=>S.findIndex(f=>f.agents.find(a=>a.id===id)?.status==='Escaped');
  const cogs=first.agents.filter(a=>a.type==='Cognitive').map(a=>({id:a.id,e:escStep(a.id)})).filter(x=>x.e>0).sort((a,b)=>a.e-b.e);
  if(cogs.length){const {id,e}=cogs[0],before=S[Math.max(0,e-1)].agents.find(a=>a.id===id),done=S[e].agents.find(a=>a.id===id),path=pathOf(S,id,e);
    out.push({title:'认得路的人',speaker:id,role:'认知型 · 受训员工',portrait:before,agent:id,from:Math.max(0,e-3),to:e,cam:{zoom:2.1,agent:id},
      text:`${narr(before).text}`,
      meta:`第 ${stepOf(S[e])} 步抵达 ${roomLabel(done.node)}。路径：${path.join(' → ')}。（${narr(before).label}）`})}
  // A Follower: most queue steps; else one who did not escape; else any.
  const fol=first.agents.filter(a=>a.type==='Follower').map(a=>{let q=0,firstQ=-1;S.forEach((f,i)=>{const x=f.agents.find(b=>b.id===a.id);if(x&&['EDGE_QUEUE','NODE_FULL'].includes(x.action)){q++;if(firstQ<0)firstQ=i}});const end=last.agents.find(b=>b.id===a.id);return{id:a.id,q,firstQ,end}});
  let pick=fol.filter(x=>x.q>0).sort((a,b)=>b.q-a.q)[0]||fol.find(x=>x.end?.status!=='Escaped')||fol[0];
  if(pick){let at=pick.firstQ>=0?pick.firstQ:S.findIndex(f=>f.agents.find(a=>a.id===pick.id)?.status!=='Active');if(at<0)at=Math.min(S.length-1,6);
    const a=S[at].agents.find(b=>b.id===pick.id),end=pick.end,fate=end?STATUS[end.status]||end.status:'';
    out.push({title:'跟着人群走',speaker:pick.id,role:'跟随型 · 访客',portrait:a,agent:pick.id,from:Math.max(0,at-2),to:at,cam:{zoom:2.1,agent:pick.id},
      text:`${narr(a).text}`,
      meta:`${pick.q?`整段录制中排队 ${pick.q} 步。`:''}最终状态：${fate}${end?.status==='Escaped'?'':'，停在 '+roomLabel(end.node)}。路径：${pathOf(S,pick.id,S.length-1).join(' → ')}。（${narr(a).label}）`})}
  // Bottleneck: step and link with the largest recorded queue.
  let best=null;S.forEach((f,i)=>(f.edges||[]).forEach(e=>{const q=(e.edge_queue||0)+(e.node_full||0);if(q>0&&(!best||q>best.q))best={i,e,q}}));
  if(best){const {i,e}=best;out.push({title:'门口的队伍',speaker:'讲解员',role:'导览旁白',portrait:'guide',from:Math.max(0,i-1),to:i,room:e.source,cam:{zoom:1.9,room:e.source},
    text:`第 ${stepOf(S[i])} 步，${roomLabel(e.source)} → ${roomLabel(e.target)} 这道门：${e.proposals} 人同时想通过，每步容量 ${e.capacity_per_step}，${e.edge_queue} 人通道排队${e.node_full?`、${e.node_full} 人因目标满员等待`:''}。`,
    meta:'这正是设计方案要处理的位置：D1 加宽 N06↔N10，D2 新增 N06↔N08 连廊，可在“新建运行”或切换录制中对照。'})}
  // Finale summary.
  const by=t=>{const all=last.agents.filter(a=>a.type===t);return{n:all.length,e:all.filter(a=>a.status==='Escaped').length}};
  const flow={};S.forEach(f=>(f.edges||[]).forEach(e=>{const key=[e.source,e.target].sort().join(' ↔ ');flow[key]=(flow[key]||0)+(e.accepted||0)}));
  const busiest=Object.entries(flow).sort((a,b)=>b[1]-a[1])[0];const c=last.counts;
  const src=run.source==='archived'?'旧版录制':run.source==='live_llm'?'真实 API 记录':'本地策略录制';
  // Decision composition from recorded per-step modes: LLM adopted vs panic override vs rule fallback.
  const modes={};S.forEach(f=>f.agents.forEach(a=>{if(a.mode)modes[a.mode]=(modes[a.mode]||0)+1}));
  const llm=modes.LLM_API||0,panic=Object.entries(modes).filter(([k])=>k.startsWith('Panic')).reduce((s,[,v])=>s+v,0),fb=modes.Rule_Fallback||0,norm=Object.values(run.llm_protocol?.normalized||{}).reduce((a,b)=>a+b,0);
  const mix=llm?`<div class="tour-mix">决策构成：<b>LLM 采纳 ${llm}</b> · 恐慌机制改写 ${panic} · 规则兜底 ${fb}${norm?` · 目标名称规范化 ${norm}`:''}${run.llm_protocol?.feedback_retries?` · 纠错重试 ${run.llm_protocol.feedback_retries}`:''}</div>`:'';
  out.push({kind:'finale',title:'结算',speaker:'讲解员',role:'本局结算',portrait:'guide',from:S.length-1,to:S.length-1,cam:{zoom:.86},
    text:`<div class="tour-stats"><div><b>${c.escaped}</b><small>已疏散</small></div><div><b>${c.dead}</b><small>遇难</small></div><div><b>${c.exhausted||0}</b><small>体力耗尽</small></div><div><b>${c.active}</b><small>仍在馆内</small></div></div><div class="tour-types">${['Cognitive','Perceptual','Follower'].map(t=>{const v=by(t),p=v.n?Math.round(v.e/v.n*100):0;return`<div><span><i style="background:${COLORS[t]}"></i>${TYPE_SHORT[t]}</span><div class="tour-bar"><em style="width:${p}%;background:${COLORS[t]}"></em></div><span>${v.e}/${v.n}</span></div>`}).join('')}</div>${mix}`,
    html:true,meta:`共 ${stepOf(last)} 步 · ${fmt(last.sim_time_s)}${busiest?` · 累计通过最多的门：${busiest[0]}（${busiest[1]} 人次）`:''} · ${src} · ${cfg.design_id}/${cfg.condition_id} · seed ${cfg.seed}${run.fallback_count?` · 规则兜底 ${run.fallback_count}`:''}。导览文字由前端依据记录整理，不是模型内部推理。`});
  return out;
}

function drawPortrait(p){const c=$('tourPortrait'),g=c.getContext('2d');g.imageSmoothingEnabled=false;g.clearRect(0,0,c.width,c.height);g.fillStyle='#e9dcb5';g.fillRect(0,0,c.width,c.height);for(let y=0;y<c.height;y+=8){g.fillStyle=y%16?'#e2d3a8':'#eadfbd';g.fillRect(0,y,c.width,8)}
  if(p==='guide'){person(g,44,86,'Perceptual',0,'Active',3,1,'GUIDE');g.fillStyle='#3e6b55';g.fillRect(52,40,14,10);g.fillStyle='#f1e2a6';g.fillRect(55,43,8,4)}else if(p)person(g,44,86,p.type,0,p.status,3,1,p.id)}

function type(html,isHtml){clearInterval(typing);const el=$('tourText');full=html;if(isHtml||reducedMotion.matches){el.innerHTML=html;typing=null;return}let i=0;el.textContent='';typing=setInterval(()=>{i+=2;el.textContent=html.slice(0,i);if(i>=html.length){clearInterval(typing);typing=null}},26)}
function finishTyping(){if(!typing)return false;clearInterval(typing);typing=null;$('tourText').textContent=full;return true}

function play(c){clearInterval(timer);playing=false;follow=false;setIndex(c.from);let i=c.from;if(c.to>c.from)timer=setInterval(()=>{if(i>=c.to){clearInterval(timer);return}i++;setIndex(i,true)},950)}

function show(n){ci=Math.max(0,Math.min(chapters.length-1,n));const c=chapters[ci];
  $('tourTitle').hidden=c.kind!=='title';$('tourBox').hidden=c.kind==='title';$('tourRibbon').hidden=c.kind==='title';
  selectedRoom=c.room||'';if(c.agent){selected=c.agent;detail()}else selected='';
  cam={zoom:c.cam.zoom||1,room:c.cam.room||'',agent:c.cam.agent||''};
  play(c);if(c.kind==='title')return;
  $('tourBox').classList.toggle('finale',c.kind==='finale');
  $('tourRibbon').textContent=`第 ${ci} 幕 · ${c.title}`;$('tourName').textContent=c.speaker;$('tourRole').textContent=c.role;$('tourMeta').textContent=c.meta||'';$('tourCount').textContent=`${ci} / ${chapters.length-1}`;
  $('tourPrev').disabled=ci<=1;$('tourNext').textContent=ci===chapters.length-1?'↺':'▶';drawPortrait(c.portrait);type(c.text,c.html);
}
function next(){if(finishTyping())return;if(ci>=chapters.length-1){show(1);return}show(ci+1)}
function prev(){if(ci>1)show(ci-1)}

function start(){if(on||!run)return;if(window.__split?.on)window.__split.stop();on=true;
  saved={show:document.body.classList.contains('show-mode'),bubbleMode,index,selected,selectedRoom,zoom,pan:{...pan}};
  document.body.classList.add('show-mode','touring');$('showMode').textContent='▣ 研究模式';bubbleMode=0;
  chapters=build();const cfg=run.config;$('tourHeadline').textContent=`栖木博物馆的 ${Math.round(run.snapshots.at(-1).sim_time_s)} 秒`;$('tourTitleSub').textContent=`${cfg.design_id} / ${cfg.condition_id} · 起火点 ${cfg.fire_origin||'N01'} · ${run.snapshots[0].agents.length} 人 · ${POLICIES[cfg.policy_id]||cfg.policy_id}`;
  show(0);requestAnimationFrame(camLoop)}
function stop(){if(!on)return;on=false;clearInterval(timer);clearInterval(typing);['tourTitle','tourBox','tourRibbon'].forEach(id=>$(id).hidden=true);document.body.classList.remove('touring');
  if(!saved.show){document.body.classList.remove('show-mode');$('showMode').textContent='▣ 展示模式'}
  bubbleMode=saved.bubbleMode;selected=saved.selected;selectedRoom=saved.selectedRoom;zoom=saved.zoom;pan=saved.pan;setIndex(saved.index);detail()}

function camLoop(){if(!on)return;const base=Math.min((cw-35)/W,(ch-85)/(H*YR));let tx=W/2,ty=H/2;
  if(cam.agent){const h=hitAgents.find(a=>a.id===cam.agent);if(h){tx=h.x;ty=h.y}else{const a=frame()?.agents.find(a=>a.id===cam.agent);if(a){[tx,ty]=center(a.node)}}}else if(cam.room)[tx,ty]=center(cam.room);
  zoom=ease(zoom,cam.zoom,.06);const s=base*zoom,box=$('tourBox'),side=!box.hidden&&box.classList.contains('finale'),boxH=box.hidden||side?0:box.offsetHeight+24,boxW=side?box.offsetWidth+30:0,aimY=(ch-boxH)/2+10,aimX=(cw-boxW)/2;
  const px=(aimX-cw/2)+s*(W/2-tx),py=(aimY-ch/2)+s*YR*(H/2-ty)-8;
  pan={x:ease(pan.x,px,.07),y:ease(pan.y,py,.07)};requestAnimationFrame(camLoop)}

$('tourStart').onclick=()=>on?stop():start();$('tourGo').onclick=()=>show(1);$('tourNext').onclick=next;$('tourPrev').onclick=prev;$('tourExit').onclick=stop;$('tourBox').onclick=e=>{if(e.target.closest('button'))return;next()};
window.addEventListener('keydown',e=>{if(!on||document.querySelector('dialog[open]'))return;const k=e.code;if(['ArrowRight','Enter','Space','PageDown'].includes(k)){e.preventDefault();e.stopImmediatePropagation();chapters[ci].kind==='title'?show(1):next()}else if(['ArrowLeft','PageUp'].includes(k)){e.preventDefault();e.stopImmediatePropagation();prev()}else if(k==='Escape'){e.preventDefault();e.stopImmediatePropagation();stop()}},true);
// Re-select the run, restart the tour from the title.
$('runSelect').addEventListener('change',()=>{if(on){stop();}});
window.__tour={start,stop,next,prev,get chapters(){return chapters},get index(){return ci}};
})();

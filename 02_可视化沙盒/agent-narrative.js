'use strict';
// Presentation-only synthesis of recorded public inputs; never used for decisions.
function agentNarrative(a, latest, name=id=>id) {
  const context=latest?.context||a.context, obs=latest?.options||a.observation;
  const target=latest?.target||a.target, raw=latest?.summary||a.summary||'';
  const choice=obs?.find(o=>o.target_id===target), state=context?.state;
  const mode=latest?.mode||a.mode||'', model=mode==='LLM_API';
  const result={raw,model,label:model?'模型原始摘要':'记录综合解说',text:'',short:'',evidence:context,obs};
  if(latest?.pending){result.text='正在把这一刻的观察、身体状态和已有记忆交给模型；选择尚未返回。';result.short='正在观察，等待模型返回';return result}
  if(a.status==='Dead'){result.text='本步记录为遇难，已停止行动。此前的决策不代表现在仍在移动。';result.short='已停止行动';return result}
  if(a.status==='Escaped'){result.text=`已到达${name(a.node)}，本步记录为疏散完成。`;result.short='已抵达出口';return result}
  if(a.status==='Exhausted'){result.text=`体力已经耗尽，停在${name(a.node)}，目前不能继续移动。`;result.short='体力耗尽，无法继续移动';return result}
  if(!context){result.text=raw||'尚无决策记录，等待观察周围。';result.label='原始记录 · 上下文未记录';result.short=result.text;return result}
  if(a.action==='INITIAL'&&!latest?.summary){result.text=`目前在${name(a.node)}。还没有本步观察与决策，先等待疏散开始。`;result.short='等待疏散开始';return result}
  const facts=[];
  // Priority is determined by evidence, not random variation or invented personality.
  if(state?.health<65)facts.push(`身体已受损（健康 ${Math.round(state.health)}）`);
  else if(state?.stamina<35)facts.push(`剩余体力只有 ${Math.round(state.stamina)}`);
  else if(state?.panic)facts.push(state.panic);
  if(context.environment?.air)facts.push(context.environment.air);
  let sense='';
  if(choice){const dest=name(target);sense=choice.perception_source==='tactile'?`沿墙摸到了通向${dest}的门洞`:choice.perception_source==='memory'?`记得通向${dest}的门洞`:`能看见通向${dest}的方向`;
    if(choice.passable===false)sense+='，但记录显示它已关闭';
    else if(choice.is_exit)sense+='，观察中标明那里是出口';
    else if(choice.recent_flow>0)sense+=`，上一步有 ${choice.recent_flow} 人实际走向那里`;
    else if(choice.perception_source==='direct'&&choice.crowd_count>0)sense+=`，可见 ${choice.crowd_count} 人`;
  }else if(obs?.length===0)sense='这一刻没有记录到可选择的方向';
  const mem=context.memory||[],visited=target&&mem.includes(target);
  const memory=visited?`${name(target)}出现在近期路径里，${a.action==='MOVED'&&(!latest||latest.committed)?'这次是折返':'准备折返'}`:mem.length>1?`近期经过${name(mem.at(-2))}`:'';
  const pending=latest&&!latest.committed;
  let outcome=pending?(target?`准备走向${name(target)}，尚未结算`:'还没有确定方向'):
    a.action==='EDGE_QUEUE'?`想去${name(target)}，但通道本步名额用完了，仍在${name(a.node)}排队`:
    a.action==='NODE_FULL'?`${name(target)}暂时满员，仍在${name(a.node)}等候`:
    a.action==='MOVED'?`本步已走到${name(a.node)}`:
    target?`选择${name(target)}，本步仍停在${name(a.node)}`:`本步留在${name(a.node)}`;
  const setting=facts.length?facts.join('，')+'。':'';
  const observed=sense?sense+'。':'', remembered=memory?memory+'。':'';
  if(['EDGE_QUEUE','NODE_FULL'].includes(a.action))result.text=outcome+'。'+observed+setting+remembered;
  else if(choice?.perception_source==='memory')result.text=remembered+observed+setting+outcome+'。';
  else if(choice?.perception_source==='tactile')result.text=setting+observed+remembered+outcome+'。';
  else if(a.type==='Follower'&&choice?.recent_flow>0)result.text=observed+setting+remembered+outcome+'。';
  else result.text=setting+remembered+observed+outcome+'。';
  result.short=outcome;
  if(model&&raw)result.text=raw; // Preserve real model output exactly, with context separately inspectable.
  return result;
}
if(typeof module!=='undefined')module.exports={agentNarrative};

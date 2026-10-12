const {agentNarrative}=require('../agent-narrative.js');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const base={id:'F04',type:'Follower',node:'N04',from_node:'N04',target:'N06',status:'Active',action:'EDGE_QUEUE',mode:'Local_Rule',summary:'原始规则输出',context:{state:{health:100,stamina:70,panic:'保持冷静'},environment:{air:'可见烟雾',crowd:'人群稀疏'},memory:['N03','N04'],known_connections:['N06']},observation:[{target_id:'N06',passable:true,recent_flow:3,perception_source:'memory'}]};
let checks=[];function test(name,fn){fn();checks.push(name)}
test('Queue does not claim arrival',()=>{const n=agentNarrative(base);assert.match(n.text,/仍在N04排队/);assert.doesNotMatch(n.text,/已走到/);assert.match(n.text,/上一步有 3 人实际/)});
test('Memory is distinguished from direct sight',()=>{const n=agentNarrative(base);assert.match(n.text,/记得通向N06的门洞/);assert.doesNotMatch(n.text,/能看见通向N06/)});
test('Tactile search and low stamina use recorded facts',()=>{const a=structuredClone(base);a.context.state.stamina=12;a.observation[0].perception_source='tactile';const n=agentNarrative(a);assert.match(n.text,/沿墙摸到/);assert.match(n.text,/体力只有 12/)});
test('Pending request hides previous decision',()=>{const n=agentNarrative(base,{pending:true});assert.match(n.text,/选择尚未返回/);assert.doesNotMatch(n.text,/N06|排队/)});
test('Returned decision is not presented as settled movement',()=>{const n=agentNarrative({...base,action:'MOVED'},{summary:'new',target:'N06',committed:false});assert.match(n.text,/尚未结算/);assert.doesNotMatch(n.text,/本步已走到/)});
test('Actual model summary retained verbatim',()=>{const n=agentNarrative({...base,mode:'LLM_API',summary:'我记得那扇门，想先过去。'});assert.equal(n.text,'我记得那扇门，想先过去。');assert.equal(n.label,'模型原始摘要')});
test('Dead and escaped agents do not keep announcing decisions',()=>{assert.match(agentNarrative({...base,status:'Dead'}).text,/已停止行动/);assert.match(agentNarrative({...base,status:'Escaped'}).text,/疏散完成/)});
test('Legacy missing context is not invented',()=>{const n=agentNarrative({...base,context:null});assert.equal(n.text,base.summary);assert.match(n.label,/上下文未记录/)});
test('Queued return is an intention, completed return is an outcome',()=>{const a=structuredClone(base);a.context.memory=['N06','N04'];assert.match(agentNarrative(a).text,/准备折返/);a.action='MOVED';a.node='N06';assert.match(agentNarrative(a).text,/这次是折返/)});
test('Closed observation is never described as usable',()=>{const a=structuredClone(base);a.observation[0].passable=false;assert.match(agentNarrative(a).text,/已关闭/)});
test('Initial state does not imply an observation or action',()=>{assert.match(agentNarrative({...base,action:'INITIAL'}).text,/还没有本步观察与决策/)});
fs.writeFileSync(path.join(__dirname,'../../evidence/narrative-tests.json'),JSON.stringify({passed:checks.length,checks},null,2));
console.log(JSON.stringify({passed:checks.length}));

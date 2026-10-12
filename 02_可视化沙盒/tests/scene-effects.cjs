const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const fx=require('../scene-effects.js'),checks=[];
function test(name,f){f();checks.push(name)}
test('Smoke can arrive before high fire risk',()=>{const n=fx.levels({risk:.2,smoke:.65});assert.equal(n.fire,0);assert.equal(n.smoke,.65)});
test('Scenario closure alone creates neither smoke nor fire',()=>{const n=fx.levels({risk:0,smoke:0,status:'Blocked',blocked:true});assert.equal(n.fire,0);assert.equal(n.smoke,0);assert.equal(n.closed,true)});
test('Fire closure does not suppress recorded smoke and fire',()=>{const n=fx.levels({risk:1,smoke:1,status:'Blocked',blocked:false});assert.equal(n.fire,1);assert.equal(n.smoke,1)});
test('Increasing recorded risk increases visual fire intensity',()=>{assert.ok(fx.levels({risk:.95}).fire>fx.levels({risk:.55}).fire)});
test('Missing or invalid hazard fields do not invent fire',()=>{assert.equal(fx.levels({risk:NaN,smoke:Infinity}).fire,0);assert.equal(fx.levels({}).smoke,0)});
test('Renderer is clipped and never mutates input when visual time advances',()=>{const calls=[],g={save(){calls.push('save')},restore(){calls.push('restore')},beginPath(){},rect(...a){calls.push(a)},clip(){calls.push('clip')},fillRect(){},set fillStyle(c){}};const n=Object.freeze({id:'N04',risk:.8,smoke:.5}),r=Object.freeze([1,2,210,115]);fx.hazard(g,n,r,0);fx.hazard(g,n,r,999999);assert.equal(calls.filter(v=>v==='clip').length,2);assert.deepEqual(n,{id:'N04',risk:.8,smoke:.5});assert.equal(calls.at(-1),'restore')});
fs.writeFileSync(path.join(__dirname,'../../evidence/scene-effects-tests.json'),JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length}));

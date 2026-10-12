// Start this package's start.py first. STUDIO_URL can select an isolated test port.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||path.resolve(__dirname,'../02_可视化沙盒/node_modules/playwright'));
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),base=process.env.STUDIO_URL||'http://127.0.0.1:8765';
const report=process.env.BROWSER_REPORT||path.join(root,'evidence/generated/browser-package.json');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const errors=[],checks=[];
 const check=(name,ok)=>{assert.ok(ok,name);checks.push(name)};
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>window.__studio);await page.evaluate(()=>document.fonts.ready);
  check('All 30 labeled embedded recordings are available',await page.locator('#runSelect option').count()===30);
  check('Current context UI is served', (await (await page.request.get(base+'/api/meta')).json()).implementation==='studio-1.4-context-ui');
  check('1920 x 1080 research screen fits',await page.evaluate(()=>document.documentElement.scrollWidth<=1920&&document.documentElement.scrollHeight<=1080));
  check('All 18 museum spaces are rendered',await page.evaluate(()=>Object.keys(window.__studio.rooms).length===18));
  await page.click('#next');await page.waitForTimeout(100);
  check('Recorded timeline advances',await page.evaluate(()=>window.__studio.index===1));
  check('Agent bubble is populated',!!(await page.locator('#agentBubble').textContent()).trim());
  await page.click('#showMode');check('Presentation mode hides inspector',await page.locator('.inspector').isHidden());await page.click('#showMode');
  await page.setViewportSize({width:1440,height:810});
  check('1440 x 810 screen fits',await page.evaluate(()=>document.documentElement.scrollWidth<=1440&&document.documentElement.scrollHeight<=810));
  const initial=await page.request.post(base+'/api/runs',{data:{policy:'Local_Rule',design:'D0',condition:'C0',cognitive:2,perceptual:1,follower:1,steps:2,autoplay:true}});
  check('Packaged frontend service accepts a local run',initial.ok());
  const created=await initial.json();
  const id=created.id;
  check('Local run has an id',typeof id==='string'&&id.length===32);
  let replay;
  for(let i=0;i<100;i++){
   replay=await (await page.request.get(base+'/api/runs/'+id+'/replay')).json();
   if(['completed','failed'].includes(replay.status))break;
   await page.waitForTimeout(50);
  }
  check('Local run completes without fallback or paid calls',replay.status==='completed'&&replay.fallback_count===0&&replay.source==='live_local'&&!replay.events.some(e=>e.type==='api.started'));
  check('Two simulation steps produce initial plus two committed frames',replay.snapshots.length===3);
  const offline=await browser.newPage({viewport:{width:1440,height:810}});
  offline.on('pageerror',e=>errors.push(e.message));
  await offline.goto(pathToFileURL(path.join(root,'02_可视化沙盒/疏散沙盒-单文件版.html')).href);
  await offline.waitForFunction(()=>window.__studio);
  check('Relocated single-file page opens offline',await offline.locator('#runSelect option').count()===30);
  await offline.click('#next');check('Offline replay can advance',await offline.evaluate(()=>window.__studio.index===1));
  check('No browser JavaScript errors',errors.length===0);
  fs.mkdirSync(path.dirname(report),{recursive:true});
  fs.writeFileSync(report,JSON.stringify({passed:checks.length,checks,errors,paid_api_calls:0},null,2));
  console.log(JSON.stringify({passed:checks.length,errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

// Start live_server.py before running. Optional PLAYWRIGHT_MODULE uses an existing installation.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const base=path.resolve(__dirname,'..'), evidence=path.resolve(base,'../evidence');
fs.mkdirSync(evidence,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1920,height:1080}});
 // ResizeObserver clears the canvas; capture only after the next rendered frame.
 const capture=page.screenshot.bind(page);page.screenshot=async options=>{await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));return capture(options)};
 const errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
 const check=(name,condition)=>{assert.ok(condition,name);checks.push(name)};
 await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.__studio);await page.evaluate(()=>document.fonts.ready);
 check('30 recordings including 6 new examples',await page.locator('#runSelect option').count()===30);
 await page.click('#compare');check('Default comparison includes three matched designs',await page.locator('.compare-row').count()===3);await page.click('[data-close=infoDialog]');
 check('1920 x 1080 has no page overflow',await page.evaluate(()=>document.documentElement.scrollHeight<=1080&&document.documentElement.scrollWidth<=1920));
 await page.click('#next');await page.waitForTimeout(900);
 check('Recorded next frame advances one step',(await page.locator('#stepLabel').textContent()).includes('STEP 01'));
 check('Agent bubble contains state, observation, environment, memory',await page.locator('#agentBubble').evaluate(el=>['状态','观察','环境','记忆'].every(s=>el.textContent.includes(s))));
 await page.selectOption('#agentSelect','C02');check('Selecting an agent updates bubble',(await page.locator('#agentBubble').textContent()).includes('C02'));
 await page.click('#bubbles');check('Town bubble mode',await page.locator('#bubbles').textContent()==='气泡 · 小镇');
 await page.evaluate(()=>window.__studio.setIndex(3));await page.screenshot({path:path.join(evidence,'research-1920x1080.png')});
 await page.click('#showMode');check('Presentation hides inspector',await page.locator('.inspector').isHidden());await page.screenshot({path:path.join(evidence,'presentation-1920x1080.png')});await page.click('#showMode');
 await page.setViewportSize({width:1440,height:810});await page.waitForTimeout(150);check('1440 x 810 has no page overflow',await page.evaluate(()=>document.documentElement.scrollHeight<=810&&document.documentElement.scrollWidth<=1440));await page.screenshot({path:path.join(evidence,'research-1440x810.png')});
 await page.setViewportSize({width:1920,height:1080});
 // Validate that every rendered route is orthogonal and cannot cut through an unrelated room.
 const geometry=await page.evaluate(()=>{const s=window.__studio,errors=[];for(const [key,r] of Object.entries(s.routes)){for(let i=1;i<r.points.length;i++){const a=r.points[i-1],b=r.points[i];if(a[0]!==b[0]&&a[1]!==b[1])errors.push(key+': diagonal');for(const [id,room] of Object.entries(s.rooms)){if([r.a,r.b].includes(id))continue;const [x,y,w,h]=room;if(a[0]===b[0]&&a[0]>x&&a[0]<x+w&&Math.max(a[1],b[1])>y&&Math.min(a[1],b[1])<y+h)errors.push(key+': enters '+id);if(a[1]===b[1]&&a[1]>y&&a[1]<y+h&&Math.max(a[0],b[0])>x&&Math.min(a[0],b[0])<x+w)errors.push(key+': enters '+id)}}}return errors});check('Routes are orthogonal and avoid unrelated rooms',geometry.length===0);
 // Missing credentials must not launch a rule fallback labeled as LLM.
 const missing=await page.request.post('http://127.0.0.1:8765/api/runs',{data:{policy:'LLM_Agent',provider:'OpenAI'}});check('Missing key rejected with HTTP 400',missing.status()===400);
 await page.click('#newRun');await page.fill('[name=steps]','3');
 await page.fill('[name=cognitive]','2');await page.fill('[name=perceptual]','1');await page.fill('[name=follower]','1');
 await page.locator('.settings-section').nth(0).locator('summary').click();
 await page.selectOption('#fireOrigin','N06');await page.fill('[name=fire_rate]','0.08');await page.fill('[name=smoke_rate]','0.12');
 await page.locator('.settings-section').nth(1).locator('summary').click();await page.selectOption('#placementMode','positions');
 for(const [id,node] of Object.entries({C01:'N01',C02:'N03',P03:'N04',F04:'N17'}))await page.selectOption(`[data-agent-position=${id}]`,node);
 await page.locator('.settings-section').nth(3).locator('summary').click();await page.fill('[data-profile="0"][data-key="physical.stamina"]','75');await page.locator('[data-profile="0"][data-key="physical.stamina"]').blur();
 const configDownload=page.waitForEvent('download');await page.click('#saveSettings');await (await configDownload).saveAs(path.join(evidence,'ui-settings.json'));
 await page.screenshot({path:path.join(evidence,'parameter-editor.png')});
 await page.click('#createRun');await page.waitForFunction(()=>window.__studio.run?.source==='live_local');await page.waitForFunction(()=>window.__studio.run.snapshots.length===1);const id=await page.evaluate(()=>window.__studio.run.id);
 check('UI fire and smoke settings reach engine',await page.evaluate(()=>window.__studio.run.config.fire_origin==='N06'&&window.__studio.run.config.smoke_rate===.12));
 check('UI exact Agent positions honored',await page.evaluate(()=>JSON.stringify(Object.fromEntries(window.__studio.run.snapshots[0].agents.map(a=>[a.id,a.node])))===JSON.stringify({C01:'N01',C02:'N03',P03:'N04',F04:'N17'})));
 check('UI profile stamina honored',await page.evaluate(()=>window.__studio.run.snapshots[0].agents[0].stamina===75));
 await page.click('#next');await page.waitForFunction(()=>window.__studio.run.snapshots.length===2);await page.waitForTimeout(150);check('Live single step pauses after exactly one step',await page.evaluate(()=>window.__studio.run.snapshots.length===2));
 check('Committed decision is not labeled pending settlement',(await page.locator('#agentBubble').textContent()).includes('本步已结算'));
 const reconnect=await page.request.get(`http://127.0.0.1:8765/api/runs/${id}/replay`);const rr=await reconnect.json();const cursor=rr.events.at(-1).seq;
 await page.click('#play');await page.waitForFunction(()=>window.__studio.run.status==='completed');check('Live resume reaches declared step limit',await page.evaluate(()=>window.__studio.run.snapshots.at(-1).completed_steps===3));
 await page.click('#compare');check('Custom parameters exclude incompatible default recordings',await page.locator('.compare-row').count()===1);await page.click('[data-close=infoDialog]');
 const sse=await page.request.get(`http://127.0.0.1:8765/api/runs/${id}/events?after=${cursor}`);const events=(await sse.text()).split('\n').filter(l=>l.startsWith('data: ')).map(l=>JSON.parse(l.slice(6)));check('SSE cursor resumes without old events',events.length>0&&events[0].seq===cursor+1&&events.at(-1).type==='run.ended');
 const downloadPromise=page.waitForEvent('download');await page.click('#export');const dl=await downloadPromise;const downloaded=path.join(evidence,'browser-live-replay.json');await dl.saveAs(downloaded);const data=JSON.parse(fs.readFileSync(downloaded,'utf8'));check('Export has snapshots, events, hashes and no key',data.snapshots.length===4&&data.events.length>0&&!!data.provenance['engine.py']&&!JSON.stringify(data).includes('api_key'));
 await page.setInputFiles('#fileInput',downloaded);await page.waitForFunction(()=>window.__studio.run.id.includes('-import-'));check('Imported replay starts at initial frame',await page.evaluate(()=>window.__studio.index===0));
 await page.selectOption('#runSelect','5');await page.evaluate(()=>window.__studio.setIndex(4));await page.click('#heat');await page.click('#showMode');await page.screenshot({path:path.join(evidence,'D2-C1-bubbles.png')});
 const offline=await browser.newPage({viewport:{width:1440,height:810}});offline.on('pageerror',e=>errors.push(e.message));await offline.goto(pathToFileURL(path.join(base,'疏散沙盒-单文件版.html')).href);await offline.waitForFunction(()=>window.__studio);check('Single-file opens offline',await offline.locator('#runSelect option').count()===30);await offline.click('#next');check('Offline timeline works',(await offline.locator('#stepLabel').textContent()).includes('STEP 01'));
 check('No browser JavaScript errors',errors.length===0);
 fs.writeFileSync(path.join(evidence,'browser-tests.json'),JSON.stringify({checks,errors,geometry,passed:checks.length},null,2));
 console.log(JSON.stringify({passed:checks.length,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

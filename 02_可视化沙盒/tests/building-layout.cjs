const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1920,height:1080}}),checks=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.__studio);await page.evaluate(()=>document.fonts.ready);
 const geometry=await page.evaluate(()=>{
  const {rooms,routes}=window.__studio,issues=[];
  const inside=(p,id)=>{const [x,y,w,h]=rooms[id];return p[0]>=x&&p[0]<=x+w&&p[1]>=y&&p[1]<=y+h};
  const intersection=(a,b,c,d)=>{
   const av=a[0]===b[0],bv=c[0]===d[0],between=(n,v,w)=>n>=Math.min(v,w)&&n<=Math.max(v,w);
   if(av!==bv){const p=av?[a[0],c[1]]:[c[0],a[1]];return between(p[0],a[0],b[0])&&between(p[1],a[1],b[1])&&between(p[0],c[0],d[0])&&between(p[1],c[1],d[1])?[p]:[]}
   const fixed=av?0:1,vary=av?1:0;if(a[fixed]!==c[fixed])return[];
   const low=Math.max(Math.min(a[vary],b[vary]),Math.min(c[vary],d[vary])),high=Math.min(Math.max(a[vary],b[vary]),Math.max(c[vary],d[vary]));
   return low>high?[]:[low,(low+high)/2,high].map(n=>av?[a[0],n]:[n,a[1]]);
  };
  const all=Object.entries(routes);
  for(let i=0;i<all.length;i++)for(let j=i+1;j<all.length;j++){
   const [ki,a]=all[i],[kj,b]=all[j],common=[a.a,a.b].filter(id=>[b.a,b.b].includes(id));
   for(let ai=1;ai<a.points.length;ai++)for(let bi=1;bi<b.points.length;bi++)for(const p of intersection(a.points[ai-1],a.points[ai],b.points[bi-1],b.points[bi]))if(!common.some(id=>inside(p,id)))issues.push({routes:[ki,kj],point:p});
  }
  for(const [id,r] of Object.entries(rooms))if(r[0]<82||r[1]<78||r[0]+r[2]>1178||r[1]+r[3]>767)issues.push({room:id,outsideEnvelope:true});
  const actual=new Set(window.__studio.run.topology.edges.map(e=>[e.source,e.target].sort().join('-')));
  for(const id of actual)if(!routes[id])issues.push({missingRoute:id});
  return {issues,rooms:Object.keys(rooms).length,renderedEdges:all.length,baseEdges:actual.size};
 });
 assert.deepEqual(geometry.issues,[]);checks.push('No route intersections or shared passages outside their common modeled room, including D2');
 assert.equal(geometry.rooms,18);checks.push('All 18 spaces belong to one building envelope, with every model edge rendered');
 const evidence=path.resolve(__dirname,'../../evidence'),settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 await page.click('#showMode');await page.click('#bubbles');await page.click('#bubbles');await settle();
 // Initial floor plan: no narrative overlay obscures the architecture.
 await page.screenshot({path:path.join(evidence,'museum-building-overview.png')});
 await page.locator('#stage').screenshot({path:path.join(evidence,'museum-building-scene.png')});
 await page.selectOption('#runSelect','5');await page.evaluate(()=>window.__studio.setIndex(4));await settle();
 await page.screenshot({path:path.join(evidence,'museum-building-D2-C1.png')});checks.push('D2 perimeter connector and C1 closure render without crossing unrelated rooms');
 await page.click('#showMode');await page.setViewportSize({width:1440,height:810});await settle();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=1440&&document.documentElement.scrollHeight<=810));checks.push('Research layout fits 1440 x 810');
 await page.screenshot({path:path.join(evidence,'museum-building-research.png')});
 assert.equal(errors.length,0);checks.push('No JavaScript errors');
 fs.writeFileSync(path.join(evidence,'building-layout-tests.json'),JSON.stringify({passed:checks.length,checks,geometry,errors},null,2));console.log(JSON.stringify({passed:checks.length,geometry}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

'use strict';
// Purely visual. Room-level recorded risk/smoke are the only hazard intensity inputs.
const SceneEffects=(()=>{
 const clamp=v=>Number.isFinite(Number(v))?Math.max(0,Math.min(1,Number(v))):0;
 function levels(n){const risk=clamp(n.risk),smoke=clamp(n.smoke);return{risk,smoke,fire:risk>=.5?(risk-.4)/.6:0,closed:!!n.blocked||['Blocked','Deadly'].includes(n.status)}}
 function block(g,x,y,w,h,c){g.fillStyle=c;g.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h))}
 function seed(s){let h=13;for(const c of s)h=(h*31+c.charCodeAt(0))>>>0;h=Math.imul(h^(h>>>16),0x7feb352d);h=Math.imul(h^(h>>>15),0x846ca68b);return(h^(h>>>16))>>>0}
 function puff(g,x,y,w,h,c){block(g,x+w*.18,y,w*.64,h,c);block(g,x,y+h*.2,w,h*.6,c)}
 function hazard(g,n,r,time=0,simple=false){
  const {risk,smoke,fire}=levels(n),[x,y,w,h]=r;if(!smoke&&!fire)return;
  const salt=seed(n.id),t=time/1000;g.save();g.beginPath();g.rect(x+7,y+13,w-14,h-21);g.clip();
  // Scorch and glow grow with the recorded risk; no wall-clock spread model.
  if(fire){block(g,x+7,y+13,w-14,h-21,`rgba(170,77,39,${fire*.16})`);const count=simple?1:Math.max(1,Math.ceil(fire*7));
   for(let i=0;i<count;i++){const key=seed(n.id+':flame:'+i),xx=x+17+(key%Math.max(1,w-39)),yy=y+36+((key>>>5)%Math.max(1,h-55)),flicker=Math.sin(t*7+i*2)*2;
    const height=12+fire*19+flicker,wide=8+fire*6;
    puff(g,xx-wide-9,yy-8,wide*2+18,15,`rgba(249,164,52,${.1+fire*.12})`);
    block(g,xx-wide,yy-4,wide*2,7,'#664a3a77');
    block(g,xx-wide/2-3,yy-height*.63,wide+6,height*.63,'#b94f31');
    block(g,xx-wide/2,yy-height*.84,wide,height*.84,'#e57935');
    block(g,xx-2+flicker,yy-height,5,height*.6,'#f5aa46');
    block(g,xx-3,yy-height*.52,7,height*.52,'#ffcb68');block(g,xx-1,yy-height*.27,3,height*.27,'#ffefac');
    if(!simple){const rise=(t*14+i*9)%31;block(g,xx+Math.sin(t+i)*4,yy-height-rise,2,3,`rgba(255,194,102,${.75*(1-rise/31)})`)}
   }
  }
  if(smoke){block(g,x+7,y+13,w-14,h-21,`rgba(81,83,79,${smoke*.11})`);
   const count=simple?3:Math.ceil(smoke*13),width=26+smoke*38;
   for(let i=0;i<count;i++){const key=seed(n.id+':smoke:'+i),life=(t*.065+(key%997)/997)%1;
    const xx=x+8+((key%Math.max(1,w-25))+Math.sin(t*.42+i)*8),yy=y+h-12-life*(h-20),size=width*(.7+life*.6);
    // Pixel-step smoke, clipped to the recorded room; doors never invent extra smoke.
    const opacity=(.045+smoke*.075)*Math.sin(life*Math.PI);
    puff(g,xx-size*.5,yy-size*.22,size,size*.49,`rgba(77,83,80,${opacity})`);
    puff(g,xx-size*.35,yy-size*.3,size*.7,size*.27,`rgba(190,192,174,${opacity*.8})`);
   }
   // A shallow ceiling layer makes rising concentration visible without hiding sprites.
   block(g,x+7,y+13,w-14,Math.min(h*.35,15+smoke*25),`rgba(78,84,80,${smoke*.13})`);
  }
  g.restore();
 }
 function ambient(g,rooms,time=0){
  const t=time/1000,r=rooms.N12;if(r){const [x,y]=r;g.save();g.beginPath();g.rect(x+68,y+120,73,41);g.clip();for(let i=0;i<3;i++){const d=(t*8+i*13)%37;g.strokeStyle=`rgba(221,241,215,${.6*(1-d/40)})`;g.lineWidth=1;g.strokeRect(x+104-d*.7,y+140-d*.2,d*1.4,d*.4)}g.restore()}
  // Small specular glints on exhibition glass; position never implies an Agent action.
  for(const id of ['N03','N06','N13','N17']){const r=rooms[id];if(!r)continue;const [x,y,w,h]=r;const alpha=.22+.13*Math.sin(t*1.1+seed(id));block(g,x+w-39,y+h-32,10,1,`rgba(249,255,228,${alpha})`);block(g,x+w-35,y+h-35,1,7,`rgba(249,255,228,${alpha})`)}
 }
 return{levels,hazard,ambient};
})();
if(typeof module!=='undefined')module.exports=SceneEffects;

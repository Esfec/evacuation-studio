/* Original canvas artwork. Furniture and landscape are illustrative, not obstacles. */
'use strict';
const PixelWorld = (() => {
  const ink='#514f48', wood='#986344';
  const exhibits=[
    {node:'N03',x:210,y:266,title:'自然 · 时间的骨架',kind:'自然展厅',description:'骨架标本、岩层色彩与玻璃展柜构成自然主题展区。围栏与展签让参观动线更容易理解。'},
    {node:'N13',x:680,y:270,title:'器物 · 一只陶罐的故事',kind:'器物展厅',description:'中央展台陈列陶器，两侧小展柜呈现器物细节。暖色聚光照向展台，周围留出观看空间。'},
    {node:'N08',x:935,y:272,title:'形与光 · 雕塑特别展',kind:'临时展厅',description:'两组雕塑面对面布置，展台、画作与休息长凳组成安静的观看区域。'},
    {node:'N04',x:445,y:705,title:'把观察画下来',kind:'公共教育工作坊',description:'工作台、画材、黑板和图书架，用于展览导赏后的绘画与讨论活动。'},
    {node:'N01',x:150,y:378,title:'从这里认识博物馆',kind:'服务与导览',description:'服务台提供参观导览，折页架和座椅构成短暂停留的空间。'},
    {node:'N12',x:935,y:650,title:'光影庭院',kind:'中庭花园',description:'浅水池、雕塑、树荫与长凳构成建筑内部的露天庭院。水面波纹是场景装饰动效。'},
    {node:'N17',x:210,y:561,title:'窗外的风景',kind:'西翼画廊',description:'风景画与小型展柜沿墙布置，中央保留观看和通行空间。'},
    {node:'N06',x:445,y:557,title:'印象 · 光与色',kind:'绘画展区',description:'不同色调的画作、颜料样本与休息长凳呈现绘画展厅的日常功能。'}
  ];
  function roomDetails(g,n,r){const [x,y,w,h]=r;
    if(['N03','N06','N08','N13','N17'].includes(n.id)){
      // Ceiling rails, tiny warm spots and exhibit labels add museum-specific detail.
      rect(g,x+15,y+11,w-30,2,'#6d6552');
      for(const dx of [24,w-28]){rect(g,x+dx-3,y+12,7,4,'#615847');rect(g,x+dx-1,y+16,4,2,'#ffe6a0');for(let k=0;k<5;k++)rect(g,x+dx-k*3,y+19+k*5,4+k*6,5,`rgba(255,240,174,${.1-k*.013})`)}
      for(const dx of [19,w-44]){rect(g,x+dx,y+h-14,25,5,'#f8efd4');rect(g,x+dx+3,y+h-12,14,1,'#a69b7c')}
    }
    if(n.id==='N03'){for(const dx of [64,155]){rect(g,x+dx,y+102,3,15,'#817b67');rect(g,x+dx-2,y+116,7,3,'#6f715e');rect(g,x+dx-1,y+101,5,3,'#d7ba7b')}rect(g,x+67,y+105,88,2,'#976a55');rect(g,x+89,y+118,47,10,'#f5e8c5');text(g,'自然 · 标本',x+113,y+126,8,'#81745c','center')}
    if(n.id==='N13'){for(const dx of [75,142]){rect(g,x+dx,y+107,3,12,'#776f57');rect(g,x+dx-2,y+119,7,2,'#716954')}rect(g,x+78,y+110,64,2,'#9d7b54');rect(g,x+w/2-16,y+116,32,8,'#f1e2bd');text(g,'陶器',x+w/2,y+123,8,'#8b7353','center')}
    if(n.id==='N04'){for(const dx of [22,145])for(const dy of [52,85]){rect(g,x+dx+15,y+dy,12,7,'#fcf0c7');rect(g,x+dx+17,y+dy+2,5,3,'#86a494');rect(g,x+dx+30,y+dy,2,6,'#af6550');rect(g,x+dx+33,y+dy+1,2,5,'#758fa0')}rect(g,x+w/2-27,y+43,53,7,'#ede4c3');text(g,'观察 · 绘画 · 分享',x+w/2,y+49,8,'#82795b','center')}
    if(n.id==='N01'){rect(g,x+101,y+18,16,24,'#917957');for(let j=0;j<3;j++){rect(g,x+103+j*4,y+21,3,12,['#c08b67','#7d9d95','#d6bd7d'][j])}rect(g,x+17,y+35,80,4,'#ad8156');text(g,'INFORMATION',x+57,y+43,7,'#efdfb7','center')}
    if(n.id==='N12'){for(const [dx,dy] of [[35,99],[174,177]]){rect(g,x+dx,y+dy,3,14,'#807956');rect(g,x+dx-3,y+dy-5,9,7,'#d8d4a0');rect(g,x+dx-1,y+dy-3,5,4,'#fcf0b6')}}
    if(n.id==='N16'){rect(g,x+9,y+88,38,19,'#95734d');rect(g,x+12,y+90,31,13,'#ceae76');rect(g,x+18,y+92,18,8,'#ede2bb');text(g,'藏品',x+27,y+99,8,'#887252','center')}
  }
  function rug(g,x,y,w,h,c){rect(g,x,y,w,h,'#795845');rect(g,x+2,y+2,w-4,h-4,c);rect(g,x+5,y+5,w-10,h-10,'#ffffff15');for(let a=x+5;a<x+w-4;a+=8){rect(g,a,y+3,2,2,'#e9d3a0');rect(g,a,y+h-5,2,2,'#e9d3a0')}}
  function shelf(g,x,y,w=40){rect(g,x+3,y+4,w,24,'#59493f40');rect(g,x,y,w,24,wood);rect(g,x+3,y+3,w-6,16,'#54483e');for(let i=0;i<w-8;i+=5){const colors=['#789b9c','#dcab64','#b85d4a','#8c9e65','#e9d7ad'];rect(g,x+4+i,y+5+(i%3),3,11,colors[(i/5|0)%5])}rect(g,x,y+19,w,3,'#d3a878');rect(g,x,y,w,2,'#e4bc87')}
  function desk(g,x,y,w=28){rect(g,x+4,y+15,3,7,wood);rect(g,x+w-5,y+15,3,7,wood);rect(g,x+2,y+4,w,14,'#704e3f');rect(g,x,y,w,13,'#ce9a60');rect(g,x+2,y+2,w-4,2,'#ebbd7b');rect(g,x+5,y+4,10,6,'#f5e5b8');rect(g,x+7,y+6,6,1,'#a5a394')}
  function seat(g,x,y,c='#73969c'){rect(g,x+2,y+9,3,6,wood);rect(g,x+12,y+9,3,6,wood);rect(g,x,y,17,12,'#526668');rect(g,x+2,y+2,13,7,c);rect(g,x+2,y+10,13,3,'#abc1a8')}
  function statue(g,x,y){rect(g,x-10,y+3,24,5,'#574c3e30');rect(g,x-9,y-4,18,9,'#9eab9d');rect(g,x-7,y-6,14,4,'#e3e2ca');rect(g,x-3,y-23,7,17,'#cad6c8');rect(g,x-6,y-16,12,8,'#b6c6b7');rect(g,x-3,y-28,8,7,'#e0e4cb');rect(g,x-6,y-24,11,3,'#eef0d8')}
  function lamp(g,x,y){rect(g,x+3,y+2,12,4,'#53664530');rect(g,x,y-25,3,30,'#526454');rect(g,x-4,y-31,11,10,'#586850');rect(g,x-2,y-29,7,6,'#ffe6a6');rect(g,x-5,y-33,13,3,'#374f46')}
  function crate(g,x,y){rect(g,x+2,y+3,22,19,'#72553f');rect(g,x,y,22,18,'#b98b56');rect(g,x+2,y+2,18,2,'#e0b779');rect(g,x+3,y+5,16,8,'#9c713f');rect(g,x+3,y+5,3,9,'#c99b5e');rect(g,x+16,y+5,3,9,'#c99b5e')}
  function flowers(g,x,y,seed){for(let i=0;i<7;i++){const xx=x+(i*13)%35,yy=y+(i*7)%15;rect(g,xx,yy,2,5,'#54794c');rect(g,xx-2,yy-2,6,4,['#f5d376','#df8e81','#f8efd2'][ (i+seed)%3]);rect(g,xx,yy-1,2,2,'#b9854f')}}
  function canopy(g,x,y,seed=0){rect(g,x-23,y+2,51,9,'#4c774534');rect(g,x-4,y-16,8,25,'#8f6644');rect(g,x-2,y-15,2,22,'#c2985e');const c=seed%2?['#3f7554','#578b57','#77aa68','#a5c773']:['#466d56','#608252','#89a761','#b2c57c'];rect(g,x-21,y-47,42,30,c[0]);rect(g,x-29,y-40,57,20,c[0]);rect(g,x-23,y-45,45,21,c[1]);rect(g,x-17,y-57,34,26,c[1]);rect(g,x-14,y-59,26,17,c[2]);rect(g,x-24,y-36,14,8,c[2]);rect(g,x+5,y-40,16,9,c[2]);rect(g,x-8,y-56,12,5,c[3]);rect(g,x+8,y-27,12,4,c[1])}
  function panel(g,x,y,w,title,c='#5c8278'){rect(g,x+2,y+3,w,29,'#423f3530');rect(g,x,y,w,27,'#ebdfbc');rect(g,x+3,y+3,w-6,21,c);text(g,title,x+w/2,y+17,10,'#f8ecc9','center')}
  function pedestal(g,x,y,w,h){rect(g,x+3,y+5,w,h,'#493d3230');rect(g,x,y,w,h,'#a79c82');rect(g,x,y,w,h-5,'#f0e6cb');rect(g,x+3,y+3,w-6,1,'#fff7de')}
  function fossil(g,x,y){pedestal(g,x-43,y-8,90,27);rect(g,x-35,y-4,73,3,'#795e45');rect(g,x-27,y-17,49,5,'#e9d6a8');rect(g,x-21,y-20,38,4,'#ffedc1');for(let i=0;i<6;i++){rect(g,x-22+i*7,y-15,3,13-i%2*4,'#a38a62');rect(g,x-21+i*7,y-15,2,10-i%2*4,'#e5cda1')}rect(g,x+17,y-26,5,13,'#e3cda4');rect(g,x+20,y-29,18,9,'#f0dab1');rect(g,x+33,y-26,8,5,'#e4c799');rect(g,x+28,y-27,2,2,'#765c45');rect(g,x-37,y-12,17,4,'#d4bd91');rect(g,x-43,y-8,10,3,'#d4bd91');rect(g,x-13,y-4,3,15,'#c2aa82');rect(g,x+14,y-4,3,15,'#c2aa82')}
  function canvasArt(g,x,y,w=40,h=34,c='#658f94'){rect(g,x+2,y+3,w,h,'#55453350');rect(g,x,y,w,h,'#876442');rect(g,x+2,y+2,w-4,h-4,'#efd5a1');rect(g,x+5,y+5,w-10,h-10,c);rect(g,x+8,y+8,9,7,'#efcd86');rect(g,x+8,y+h-15,w-16,7,'#405e65');rect(g,x+17,y+h-22,13,12,'#97ad99');rect(g,x+w-16,y+10,6,12,'#bbd0b7')}
  function sculpture(g,x,y){pedestal(g,x-18,y+2,39,20);rect(g,x-8,y-23,17,27,'#c4beaa');rect(g,x-14,y-18,28,8,'#e5dfca');rect(g,x-3,y-36,10,12,'#e8e0c4');rect(g,x-7,y-29,16,8,'#f5ead0');rect(g,x-7,y-8,7,12,'#f0e7ce');rect(g,x+6,y-7,6,10,'#969f96')}
  function building(g){
    // One continuous exterior envelope; grey roof infill is not traversable space.
    rect(g,90,90,1096,683,'#4e635545');rect(g,82,78,1096,689,'#535b52');rect(g,87,83,1086,679,'#b5b5a2');
    for(let y=88;y<758;y+=12){rect(g,91,y,1078,1,'#969d90');for(let x=95;x<1168;x+=30)rect(g,x+(y%24?10:0),y,1,12,'#a0a694')}
    rect(g,82,78,1096,9,'#faf0d3');rect(g,82,87,1096,6,'#9d9074');rect(g,82,78,9,689,'#e8ddc0');rect(g,1169,78,9,689,'#7d826b');rect(g,82,757,1096,10,'#777b62');rect(g,85,757,1090,3,'#d4c7a2');
    // Roofed areas remain visually distinct from open exhibition rooms.
    for(const [x,y,w,h] of [[100,95,220,65],[1060,95,100,65],[1060,510,100,245]]){rect(g,x,y,w,h,'#708980');for(let yy=y+4;yy<y+h;yy+=9){rect(g,x,yy,w,2,'#8fa498');for(let xx=x+((yy%18)?8:0);xx<x+w;xx+=20)rect(g,xx,yy,1,9,'#59776e')}rect(g,x,y,w,3,'#b9c9b1')}
    text(g,'栖 木 博 物 馆',210,126,20,'#f8edce','center');text(g,'Q I M U   M U S E U M',210,147,9,'#cdddca','center');
    text(g,'附 属 屋 面',1110,619,10,'#d0dfc9','center');
    // Exterior glazing has sills and mullions, never an extra traversable door.
    for(const yy of [211,278,380,448,540,590]){rect(g,82,yy,7,25,'#384f50');rect(g,82,yy+2,5,21,'#a3c7be');rect(g,82,yy+12,7,2,'#f2e8c9')}
  }
  function draw(g){
    rect(g,0,0,W,H,'#c4cfb4');
    for(let y=0;y<H;y+=18)for(let x=0;x<W;x+=18){const h=hash(x+':'+y);if(h%7===0)rect(g,x+4,y+8,2,3,'#a5b895')}
    rect(g,66,64,1128,715,'#dad6bc');for(let xx=67;xx<1190;xx+=24)rect(g,xx,64,1,715,'#c5c6ae');for(let yy=64;yy<779;yy+=24)rect(g,66,yy,1128,1,'#c5c6ae');
    for(const [x,y] of [[38,161],[38,332],[38,523],[38,715],[1224,161],[1224,332],[1224,523],[1224,715]])canopy(g,x,y,hash(''+y));
    for(const [x,y] of [[96,44],[259,44],[963,44],[1100,44]])flowers(g,x,y,1);
    rect(g,476,27,310,29,'#7c856b');rect(g,479,30,304,23,'#faf1d7');text(g,'一 层  /  展 览 与 公 共 教 育',630,47,13,'#526754','center');
    building(g);
    const routes=activeRoutes();
    for(const r of routes){line(g,r.points,30,'#5f665a');line(g,r.points,24,'#d1c3a1');line(g,r.points,18,'#e3ddc8');}
    for(const n of run.topology.nodes){const [x,y,w,h]=ROOMS[n.id],garden=['N12','N15'].includes(n.id),exit=n.type==='exit',hall=['corridor','door'].includes(n.type);
      rect(g,x-3,y-4,w+6,h+8,ink);rect(g,x,y,w,h,'#d7bb87');
      g.save();g.beginPath();g.rect(x+5,y+7,w-10,h-12);g.clip();
      const floor=garden?'#8eb16d':hall?'#dedccc':n.id==='N08'?'#c89667':'#d9b37b';rect(g,x+5,y+7,w-10,h-12,floor);
      for(let yy=y+7;yy<y+h;yy+=garden?10:hall?18:9){for(let xx=x+5;xx<x+w;xx+=hall?20:32){if(garden){if(hash(xx+':'+yy)%3===0)rect(g,xx,yy,3,2,'#b8cc82')}else{rect(g,xx,yy,hall?20:32,1,hall?'#babcae':'#b28c5f');rect(g,xx+(yy%2)*12,yy,1,hall?18:9,hall?'#bdbead':'#c49a66');if(!hall)rect(g,xx+5,yy+3,11,1,'#edc98c55')}}}
      // Wall skirting and the shadow of the cutaway back wall.
      rect(g,x+5,y+7,w-10,15,'#594c4030');rect(g,x+5,y+7,4,h-14,'#594c4020');
      if(garden){rect(g,x+12,y+17,w-24,h-31,'#c7bc95');rect(g,x+26,y+29,w-52,h-55,'#8eac73');flowers(g,x+28,y+39,2);flowers(g,x+w-63,y+h-37,0);canopy(g,x+w-47,y+91,1);plant(g,x+23,y+h-24);if(n.id==='N12'){rect(g,x+58,y+110,93,64,'#707f70');rect(g,x+62,y+114,85,54,'#cdd6c0');rect(g,x+67,y+119,75,43,'#78aaa8');rect(g,x+74,y+128,54,2,'#bad5c2');rect(g,x+105,y+124,3,29,'#bbd8c6');statue(g,x+104,y+130);bench(g,x+23,y+h-26,48);bench(g,x+w-70,y+h-26,48);text(g,'露 天 中 庭',x+w/2,y+204,12,'#4c7255','center')}else bench(g,x+60,y+h-25,52)}
      else if(n.id==='N04'){panel(g,x+55,y+12,96,'公共教育 · 工作坊','#4b786a');for(const dx of [17,139])for(const dy of [48,81]){desk(g,x+dx,y+dy,43);seat(g,x+dx+8,y+dy+16,'#af835b')}shelf(g,x+76,y+h-28,54)}
      else if(n.id==='N16'){shelf(g,x+13,y+13,w-26);crate(g,x+12,y+48);crate(g,x+34,y+59);crate(g,x+w-33,y+h-29)}
      else if(n.id==='N01'){rug(g,x+39,y+39,w-78,h-63,'#ad776a');desk(g,x+17,y+16,80);rect(g,x+24,y+18,14,10,'#466c68');rect(g,x+26,y+19,10,6,'#9ec1b2');panel(g,x+w-101,y+13,81,'服务 · 导览');seat(g,x+17,y+h-28);seat(g,x+39,y+h-28);seat(g,x+w-40,y+h-28);plant(g,x+w-17,y+51);text(g,'MUSEUM',x+w/2,y+85,17,'#e9cfaa','center')}
      else if(!hall&&!exit){
        const theme={N03:['自然 · 时间','#718b82'],N06:['印象 · 光与色','#9e8864'],N08:['特别展 · 雕塑','#668e8d'],N13:['器物 · 记忆','#ae845b'],N17:['西翼 · 风景','#848095']}[n.id]||['展览','#758b78'];
        panel(g,x+w/2-49,y+13,98,theme[0],theme[1]);
        if(n.id==='N03'){canvasArt(g,x+15,y+15,32,32,'#a39574');canvasArt(g,x+w-46,y+15,32,32);fossil(g,x+w/2,y+89);caseProp(g,x+20,y+h-41);caseProp(g,x+w-48,y+h-41);bench(g,x+w/2-20,y+h-24,40)}
        else if(n.id==='N08'){rug(g,x+29,y+56,w-58,h-77,'#8ba59a');sculpture(g,x+48,y+105);sculpture(g,x+w-52,y+105);bench(g,x+w/2-20,y+h-25,40);canvasArt(g,x+15,y+16,27,30);canvasArt(g,x+w-43,y+16,27,30,'#b88669')}
        else if(n.id==='N06'||n.id==='N17'){canvasArt(g,x+14,y+16,33,31,'#729693');canvasArt(g,x+w-45,y+16,32,31,'#ad886d');caseProp(g,x+17,y+h-39);caseProp(g,x+w-44,y+h-39);bench(g,x+w/2-25,y+h-23,50)}
        else if(n.id==='N13'){for(const dx of [19,165]){caseProp(g,x+dx,y+55);caseProp(g,x+dx,y+99)}pedestal(g,x+w/2-24,y+68,48,38);rect(g,x+w/2-8,y+58,17,20,'#a66d4b');rect(g,x+w/2-12,y+61,24,8,'#ce985d');rect(g,x+w/2-5,y+54,11,5,'#6d7055');bench(g,x+w/2-20,y+h-23,40)}
      }else if(hall){rect(g,x+14,y+15,22,10,'#4b8270');text(g,'→',x+25,y+24,12,'#f5edcb','center');if(w>150){bench(g,x+w-66,y+14,32);plant(g,x+w-19,y+29)}if(n.id==='N09'){rect(g,x+12,y+h-27,9,17,'#ac5142');rect(g,x+15,y+h-30,4,4,'#526457')}if(n.id==='N02'){panel(g,x+w/2-46,y+14,92,'参观导览');for(const dx of [18,w-47])seat(g,x+dx,y+h-31);text(g,'← 自然展    器物展 →',x+w/2,y+h-17,10,'#7a8a75','center')}if(n.id==='N05'){panel(g,x+w/2-43,y+14,86,'中央交通厅');bench(g,x+17,y+h-26,50);bench(g,x+w-68,y+h-26,50)}if(n.id==='N07'){for(let dx=140;dx<w-90;dx+=100){canvasArt(g,x+dx,y+12,30,24);bench(g,x+dx+36,y+17,35)}text(g,'北 侧 画 廊',x+w/2,y+h-13,11,'#8b927d','center')}}
      roomDetails(g,n,[x,y,w,h]);g.restore();
      // Raised walls: warm plaster over stone, with crisp edge highlights.
      rect(g,x,y-2,w,7,'#f9e4b9');rect(g,x,y+5,w,5,'#b18e69');rect(g,x,y+10,w,2,'#8b7256');rect(g,x,y,5,h,'#ead4ac');rect(g,x+w-5,y,5,h,'#a38d69');rect(g,x,y+h-6,w,6,'#8a795c');rect(g,x,y+h-6,w,2,'#c6b08a');
      for(let xx=x+12;xx<x+w-8;xx+=22)rect(g,xx,y,1,5,'#d6c39c');
      for(const r of routes)if(r.a===n.id||r.b===n.id)for(const d of doorCuts(n.id,r)){if(d.vertical){rect(g,d.x-5,d.y-14,10,28,'#e4d0a5');rect(g,d.x-6,d.y-17,12,4,'#6b6150');rect(g,d.x-6,d.y+13,12,4,'#6b6150');rect(g,d.x-1,d.y-13,2,26,'#f7e4bb')}else{rect(g,d.x-14,d.y-6,28,18,'#e4d0a5');rect(g,d.x-17,d.y-5,4,16,'#79634a');rect(g,d.x+13,d.y-5,4,16,'#79634a');rect(g,d.x-13,d.y+3,26,2,'#f8e7bb')}}
      if(exit){rect(g,x+10,y+12,w-20,18,'#336f5e');rect(g,x+12,y+13,w-24,2,'#94c4a0');text(g,n.id==='N11'?'EXIT ↓':'EXIT →',x+w/2,y+25,13,'#ffffd8','center');plant(g,x+w-14,y+h-20);if(n.id==='N11'){rug(g,x+w/2-28,y+h-51,56,39,'#729482');rect(g,x+w/2-24,y+h-7,48,20,'#cfdfcc');rect(g,x+w/2-22,y+h-3,44,7,'#7daba3');rect(g,x+w/2-1,y+h-5,2,16,'#e8ead7');rect(g,x+w/2-29,y+h+13,58,4,'#e9dcc1')}else{rug(g,x+w-44,y+h/2-22,32,44,'#729482');rect(g,x+w-6,y+h/2-22,24,44,'#ccddce');rect(g,x+w-3,y+h/2-19,9,38,'#7daba3');rect(g,x+w-4,y+h/2,22,2,'#e8ead7');rect(g,x+w+18,y+h/2-26,6,52,'#e9dcc1')}}
    }
    if(run.config.design_id==='D2')text(g,'D2 · 新增外围连廊',955,787,10,'#3e624d','center');
  }
  return {draw,exhibits};
})();

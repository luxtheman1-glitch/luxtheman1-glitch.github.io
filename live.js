/* LUX//CLEARANCE live scanner v1.5 — hosted, in-stock + sold-by-Walmart only */
(()=>{
const REFRESH_MS=30*60*1000, FRESH_MS=15*60*1000, FETCH_GAP=1200;
let liveRunning=false,lastReq=0,lastLiveScan=0,paintTimer=null;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const num=v=>{const n=Number(String(v??'').replace(/[^0-9.]/g,''));return Number.isFinite(n)?n:0};
const txt=v=>String(v??'').replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/\\u002F/g,'/').replace(/\\\//g,'/').replace(/\s+/g,' ').trim();
const itemId=u=>String(u||'').match(/\/ip\/(?:[^/?#]+\/)?(\d{5,})/)?.[1]||String(u||'').match(/\/ip\/(\d{5,})/)?.[1]||'';
const status=(title,body)=>{const a=document.getElementById('scanTitle'),b=document.getElementById('scanText');if(a)a.textContent=title;if(b)b.textContent=body};
function throttleRender(){clearTimeout(paintTimer);paintTimer=setTimeout(()=>{try{saveState();render()}catch{}},180)}
async function proxyFetch(url,retry=true){
 const wait=Math.max(0,FETCH_GAP-(Date.now()-lastReq));if(wait)await sleep(wait);lastReq=Date.now();
 const targets=['https://r.jina.ai/http://'+url.replace(/^https?:\/\//,''),'https://r.jina.ai/https://'+url.replace(/^https?:\/\//,'')];
 let err;
 for(const target of targets){
  const c=new AbortController(),tm=setTimeout(()=>c.abort(),45000);
  try{const r=await fetch(target,{signal:c.signal,cache:'no-store'});if(r.status===429&&retry){clearTimeout(tm);await sleep(9000);return proxyFetch(url,false)}if(!r.ok)throw new Error('HTTP '+r.status);const s=await r.text();if(s&&s.length>300)return s;throw new Error('empty response')}catch(e){err=e}finally{clearTimeout(tm)}
 }
 throw err||new Error('Walmart feed unavailable');
}
function normalizeProductUrl(u){try{const x=new URL(txt(u));if(x.hostname!=='www.walmart.com'||!x.pathname.includes('/ip/'))return'';['athbdg','athcpid','athpgid','athcgid','athznid','athieid','athstid','athguid','athancid','athena','athbdg'].forEach(k=>x.searchParams.delete(k));return x.toString()}catch{return''}}
function extractCandidates(md){
 const out=new Map(),rx=/(https?:\/\/www\.walmart\.com\/ip\/[^\s)\]"'<>]+)/gi;let m;
 while((m=rx.exec(md))){const url=normalizeProductUrl(m[1]);if(!url)continue;const id=itemId(url);if(!id)continue;const block=md.slice(Math.max(0,m.index-1800),Math.min(md.length,m.index+2600));if(!/\bClearance\b/i.test(block))continue;if(/Out of stock/i.test(block)&&!/(Shipping|Pickup|Delivery|Add(?: to cart)?)/i.test(block))continue;out.set(id,{id,url})}
 return[...out.values()];
}
function discoverLanes(md){
 const out=[],seen=new Set(),rx=/(https?:\/\/www\.walmart\.com\/[^\s)\]"'<>]*clearance[^\s)\]"'<>]*)/gi;let m;
 while((m=rx.exec(md))){try{const u=new URL(txt(m[1]));if(u.hostname!=='www.walmart.com'||u.pathname.includes('/ip/'))continue;['page','affinityOverride','povid','athAsset','athbdg','athpgid','athcgid','athznid','athieid','athstid','athguid','athancid'].forEach(k=>u.searchParams.delete(k));const key=u.toString();if(seen.has(key))continue;seen.add(key);out.push({url:key,label:/\/mens?\//i.test(u.pathname)?'Men clearance':'Clearance lane',priority:/\/mens?\//i.test(u.pathname)?100:50})}catch{}}
 return out;
}
function pageUrl(base,page){const u=new URL(base);u.searchParams.delete('page');u.searchParams.delete('affinityOverride');if(page>1){u.searchParams.set('affinityOverride','default');u.searchParams.set('page',String(page))}return u.toString()}
function exactImage(md){const urls=[...String(md).matchAll(/https:\/\/i5\.walmartimages\.com\/[^\s)\]"'<>]+/gi)].map(m=>m[0].replace(/[),.]+$/,''));return urls.find(u=>!/logo|spark|walmartplus|banner/i.test(u))||''}
function exactName(md){return txt(md.match(/^#\s+([^\n]{3,300})$/m)?.[1]||md.match(/^##\s+([^\n]{3,300})$/m)?.[1]||'')}
function exactPrice(md){return num(md.match(/Current price is USD(?:\s+Now)?\s*\$([\d,.]+)/i)?.[1]||md.match(/current price(?:\s+Now)?\s*\$([\d,.]+)/i)?.[1]||md.match(/(?:^|\n)Now\s*\$([\d,.]+)/i)?.[1]||md.match(/Price when purchased online[\s\S]{0,500}?\$([\d,.]+)/i)?.[1])}
function exactWas(md,price){const w=num(md.match(/\bwas\s+\$([\d,.]+)/i)?.[1]);return w>price?w:null}
function walmartSeller(md){return /Sold and shipped by Walmart\.com/i.test(md)}
function purchasable(md){
 const add=/Add to cart/i.test(md)||/(Shipping|Pickup|Delivery)\s+(?:Arrives|As soon as|available|today|tomorrow)/i.test(md)||/How do you want your item\?/i.test(md);
 const hardOut=/^(?:Out of stock|This item is unavailable|Currently unavailable)$/im.test(md);
 return add&&!hardOut;
}
function ratingInfo(md){const rating=Number(md.match(/([0-5](?:\.\d)?)\s+out of 5 stars/i)?.[1]||0);const reviews=parseInt((md.match(/([\d,]+)\s+ratings/i)?.[1]||md.match(/([\d,]+)\s+reviews/i)?.[1]||'0').replace(/,/g,''),10)||0;return{rating,reviews}}
async function verifyCandidate(c,source){
 try{
  const md=await proxyFetch(c.url);
  if(!walmartSeller(md)||!purchasable(md))return null;
  const name=exactName(md),price=exactPrice(md);if(!name||!price)return null;
  const was=exactWas(md,price),im=exactImage(md),ri=ratingInfo(md);
  const p=finish({id:c.id,name,price,was,url:c.url,image:im,imageVerified:!!im,seller:'Walmart',stock:'in',source,verifiedAt:Date.now(),active:true,rating:ri.rating,reviews:ri.reviews});
  p.seller='Walmart';p.stock='in';p.active=true;p.verifiedAt=Date.now();return p;
 }catch{return null}
}
function mergeLive(p,scanId){
 const id=String(p.id),i=products.findIndex(x=>String(x.id)===id),old=i>=0?products[i]:null;
 const next={...old,...p,scanId,firstSeen:old?.firstSeen||Date.now(),history:[...(old?.history||[]),{t:Date.now(),p:+p.price}].slice(-120)};
 if(i>=0)products[i]=next;else products.push(next);throttleRender();
}
function enforceStrict(){
 const now=Date.now();products=products.map(p=>{const ok=p.seller==='Walmart'&&p.stock==='in'&&p.verifiedAt&&now-p.verifiedAt<=FRESH_MS;return ok?{...p,active:true}:{...p,active:false}});try{saveState();render()}catch{}
}
async function liveScan(){
 if(liveRunning)return;liveRunning=true;lastLiveScan=Date.now();enforceStrict();
 const scanId='live-'+Date.now();
 const queue=[
  {url:'https://www.walmart.com/browse/clothing/mens/clearance/5438_9360765_9658256',label:'Men clearance',priority:120},
  {url:'https://www.walmart.com/c/best-sellers/men-clothes-in-clearance',label:'Men clearance',priority:110},
  {url:'https://www.walmart.com/shop/deals/clearance',label:'All clearance',priority:100}
 ],queued=new Set(queue.map(x=>x.url)),seenItems=new Set(),verified=new Set();let pages=0,lanes=0;
 status('Live scan starting…','Checking Walmart clearance now. Only in-stock items sold by Walmart will appear.');
 try{
  while(queue.length){queue.sort((a,b)=>b.priority-a.priority);const lane=queue.shift();let page=1,stale=0,lastFp='';
   while(true){
    status('LIVE · scanning Walmart',`${lane.label} · page ${page} · ${verified.size} verified Walmart items live`);
    let md;try{md=await proxyFetch(pageUrl(lane.url,page))}catch{break}pages++;
    for(const l of discoverLanes(md)){if(!queued.has(l.url)){queued.add(l.url);queue.push(l)}}
    const batch=extractCandidates(md),ids=batch.map(x=>x.id),fp=ids.join(',');let fresh=0;
    for(const c of batch){if(seenItems.has(c.id))continue;seenItems.add(c.id);fresh++;const p=await verifyCandidate(c,lane.label);if(p){verified.add(String(p.id));mergeLive(p,scanId);status('LIVE · feed updating',`${verified.size} in-stock Walmart-sold clearance items verified · ${pages} pages scanned`)}}
    if(!batch.length||fp===lastFp||fresh===0)stale++;else stale=0;lastFp=fp;if(!batch.length||stale>=2)break;page++;
   }lanes++;
  }
  products=products.map(p=>p.scanId===scanId&&p.seller==='Walmart'&&p.stock==='in'?p:{...p,active:false});saveState();render();
  status('LIVE · up to date',`${verified.size} in-stock items sold by Walmart · ${pages} pages · ${lanes} clearance lanes. Auto-refreshes while open.`);
 }catch(e){status('Live scan interrupted',`Keeping only recently verified Walmart-sold, in-stock items. Retrying automatically. ${e?.message||''}`)}finally{liveRunning=false}
}
window.scanNow=liveScan;
window.LUXLiveScan=liveScan;
const oldFiltered=window.filtered;
window.filtered=function(){const a=oldFiltered();return a.filter(p=>p.seller==='Walmart'&&p.stock==='in'&&p.active!==false)};
window.addEventListener('load',()=>{setTimeout(liveScan,250);setInterval(()=>{if(!liveRunning&&Date.now()-lastLiveScan>=REFRESH_MS)liveScan()},60*1000)});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!liveRunning&&Date.now()-lastLiveScan>=REFRESH_MS)liveScan()});
})();
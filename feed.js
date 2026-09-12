/* LUX//CLEARANCE feed loader v3 — data comes from GitHub scanner, not the phone */
(()=>{
const POLL_MS=60*1000;
let loading=false;
function status(title,body){const a=document.getElementById('scanTitle'),b=document.getElementById('scanText');if(a)a.textContent=title;if(b)b.textContent=body}
function ageLabel(iso){if(!iso)return'waiting for first scan';const ms=Date.now()-Date.parse(iso);const m=Math.max(0,Math.floor(ms/60000));return m<1?'just now':m===1?'1 minute ago':`${m} minutes ago`}
async function loadFeed(manual=false){
 if(loading)return;loading=true;
 status(manual?'Refreshing live feed…':'Loading live feed…','Fetching the latest verified Walmart clearance catalog.');
 try{
  const r=await fetch(`./deals.json?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);
  const data=await r.json();const items=Array.isArray(data.items)?data.items:[];
  products=items.map(p=>({...p,active:true,stock:'in',seller:'Walmart',imageVerified:!!p.image,verifiedAt:Date.parse(data.updated_at)||Date.now()}));
  saveState();render();
  status(items.length?'LIVE FEED':'Scanner warming up',items.length?`${items.length.toLocaleString()} in-stock clearance items sold by Walmart · updated ${ageLabel(data.updated_at)}`:'GitHub scanner has not published its first verified catalog yet.');
 }catch(e){status('Feed unavailable',`Could not load deals.json: ${e.message}`)}finally{loading=false}
}
window.scanNow=()=>loadFeed(true);
window.addEventListener('load',()=>{loadFeed(false);setInterval(()=>loadFeed(false),POLL_MS)});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)loadFeed(false)});
})();

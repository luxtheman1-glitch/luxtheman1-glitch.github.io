const CATS=['For You','Men','Women','Kids','Clothing','Home','Kitchen','Kids & Toys','Beauty','Pets','Tools','Tech','Saved'];
let cat='For You',renderLimit=120;
let products=JSON.parse(localStorage.getItem('luxMobileProducts')||'[]');
let favs=new Set(JSON.parse(localStorage.getItem('luxMobileFavs')||'[]').map(String));

const money=n=>'$'+Number(n||0).toFixed(2);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#039;'}[m]));
const disc=p=>Number(p.discount)||((p.was&&p.was>p.price)?Math.round((1-p.price/p.was)*100):0);
const sav=p=>Number(p.save||p.savings)||((p.was&&p.was>p.price)?p.was-p.price:0);

function audience(p){
  if(p.audience)return p.audience;
  const s=[p.name,p.brand,p.category].join(' ').toLowerCase();
  if(/\b(girl|boy|kid|youth|child|toddler|baby)\b/.test(s))return'Kids';
  if(/\b(women|woman|womens|ladies)\b/.test(s))return'Women';
  if(/\b(men|mens|male|big men)\b/.test(s))return'Men';
  return'Unisex';
}
function score(p){return Number(p.score)||disc(p)||0}
function level(p){
  const d=disc(p),s=sav(p);
  if(d>=70||(p.price<=4&&d>=45)||s>=60)return'ABSURD';
  if(d>=45||(p.price<=10&&d>=30)||s>=25)return'STEAL';
  return'WORTH IT';
}
function saveState(){
  localStorage.setItem('luxMobileProducts',JSON.stringify(products));
  localStorage.setItem('luxMobileFavs',JSON.stringify([...favs]));
}
function chips(){
  const el=document.getElementById('chips');
  if(!el)return;
  el.innerHTML=CATS.map(c=>`<button class="chip ${c===cat?'on':''}" onclick="setCat('${c.replace(/'/g,"\\'")}')">${c==='For You'?'✦ ':''}${esc(c)}</button>`).join('');
}
function setCat(c){
  cat=c;renderLimit=120;chips();render();
  const target=document.getElementById('chips');
  if(target)window.scrollTo({top:Math.max(0,target.offsetTop-132),behavior:'smooth'});
}
function filtered(){
  const q=(document.getElementById('q')?.value||'').trim().toLowerCase();
  const max=+(document.getElementById('max')?.value||99999);
  let a=products.filter(p=>p.active!==false&&p.stock==='in'&&+p.price<=max&&/walmart/i.test(p.seller||'Walmart'));
  if(cat==='Saved')a=a.filter(p=>favs.has(String(p.id)));
  else if(['Men','Women','Kids'].includes(cat))a=a.filter(p=>audience(p)===cat);
  else if(cat!=='For You')a=a.filter(p=>(p.category||p.cat)===cat);
  if(q)a=a.filter(p=>[p.name,p.brand,p.category,audience(p)].join(' ').toLowerCase().includes(q));
  const so=document.getElementById('sort')?.value||'score';
  if(so==='score')a.sort((x,y)=>score(y)-score(x)||disc(y)-disc(x)||x.price-y.price);
  if(so==='discount')a.sort((x,y)=>disc(y)-disc(x)||sav(y)-sav(x));
  if(so==='save')a.sort((x,y)=>sav(y)-sav(x)||disc(y)-disc(x));
  if(so==='price')a.sort((x,y)=>x.price-y.price);
  if(so==='rating')a.sort((x,y)=>(Number(y.rating)||0)-(Number(x.rating)||0)||(Number(y.reviews)||0)-(Number(x.reviews)||0));
  return a;
}
function card(p){
  const l=level(p),d=disc(p),sv=sav(p),isFav=favs.has(String(p.id));
  const rating=p.rating?`<div class="rating"><span class="star">★</span><b>${Number(p.rating).toFixed(1)}</b><span>(${Number(p.reviews||0).toLocaleString()})</span></div>`:'';
  return `<article class="card">
    <div class="photo" onclick="openItem('${p.id}')">
      ${p.image?`<img loading="lazy" src="${esc(p.image)}" alt="${esc(p.name)}">`:`<div class="noimg"><b>LUX</b><span>Image unavailable</span></div>`}
      <span class="badge ${l==='ABSURD'?'absurd':l==='STEAL'?'steal':''}">${l}${d?' · '+d+'% OFF':''}</span>
      <button class="fav ${isFav?'on':''}" aria-label="${isFav?'Remove from saved':'Save deal'}" onclick="event.stopPropagation();toggleFav('${p.id}')">${isFav?'♥':'♡'}</button>
    </div>
    <div class="body">
      <div class="brandline"><span>Sold by Walmart</span><i></i><span class="stock">In stock</span></div>
      <div class="name" onclick="openItem('${p.id}')">${p.brand?`<span class="brand">${esc(p.brand)}</span> `:''}${esc(p.name)}</div>
      ${rating}
      <div class="priceRow"><span class="price">${money(p.price)}</span>${p.was?`<span class="was">${money(p.was)}</span>`:''}</div>
      <div class="dealMeta">${sv?`You save <b>${money(sv)}</b>`:'Live clearance price'}${d?` · ${d}% markdown`:''}</div>
      <div class="actions"><button onclick="openItem('${p.id}')">Quick view</button><a href="${esc(p.url)}" target="_blank" rel="noopener">Shop deal ↗</a></div>
    </div>
  </article>`;
}
function render(){
  const a=filtered(),shown=a.slice(0,renderLimit),grid=document.getElementById('grid');
  if(grid){
    grid.innerHTML=shown.length?shown.map(card).join(''):'<div class="empty"><b>No live deals match this filter.</b><span>Try another department, price range, or search.</span></div>';
    if(a.length>shown.length)grid.insertAdjacentHTML('beforeend',`<div class="loadmore"><button onclick="renderLimit+=120;render()">Load more deals</button><span>${shown.length.toLocaleString()} of ${a.length.toLocaleString()}</span></div>`);
  }
  const heading=document.getElementById('heading');
  if(heading)heading.textContent=cat==='For You'?'Recommended for you':cat;
  const meta=document.getElementById('meta');
  if(meta)meta.textContent=`${a.length.toLocaleString()} verified clearance deals`;
  const live=products.filter(p=>p.active!==false&&p.stock==='in'&&/walmart/i.test(p.seller||'Walmart'));
  const total=document.getElementById('total');if(total)total.textContent=live.length.toLocaleString();
  const menN=document.getElementById('menN');if(menN)menN.textContent=live.filter(p=>audience(p)==='Men').length.toLocaleString();
  const savedN=document.getElementById('savedN');if(savedN)savedN.textContent=favs.size.toLocaleString();
}
function toggleFav(id){
  id=String(id);favs.has(id)?favs.delete(id):favs.add(id);saveState();render();
}
function closeDetail(){document.getElementById('sheetBg')?.classList.remove('on')}
function openItem(id){
  const p=products.find(x=>String(x.id)===String(id)&&x.active!==false&&x.stock==='in');
  if(!p)return;
  const d=disc(p),sv=sav(p),isFav=favs.has(String(p.id));
  const detail=document.getElementById('detail');
  if(!detail)return;
  detail.innerHTML=`<div class="detailPic">${p.image?`<img src="${esc(p.image)}" alt="${esc(p.name)}">`:'<div class="noimg"><b>LUX</b><span>Image unavailable</span></div>'}</div>
    <div class="detailInfo">
      <div class="detailBadges"><span>${level(p)}</span><span>IN STOCK</span><span>SOLD BY WALMART</span></div>
      <div class="eyebrow">${esc(audience(p))} · ${esc(p.category||'Clearance')}</div>
      <h1>${p.brand?`<span>${esc(p.brand)}</span> `:''}${esc(p.name)}</h1>
      ${p.rating?`<div class="rating detailRating"><span class="star">★</span><b>${Number(p.rating).toFixed(1)}</b><span>${Number(p.reviews||0).toLocaleString()} ratings</span></div>`:''}
      <div class="detailPrice"><span class="bigPrice">${money(p.price)}</span>${p.was?`<span class="was">${money(p.was)}</span>`:''}</div>
      <div class="savingsPanel"><b>${d?`${d}% off`:level(p)}</b>${sv?`<span>You save ${money(sv)}</span>`:'<span>Verified live clearance price</span>'}</div>
      <div class="panel"><b>Lux verified feed</b><br>This item entered the feed only after Walmart marked it as clearance, in stock, and sold by Walmart.</div>
      <div class="detailBtns"><button onclick="toggleFav('${p.id}');openItem('${p.id}')">${isFav?'♥ Saved':'♡ Save deal'}</button><a href="${esc(p.url)}" target="_blank" rel="noopener">Shop at Walmart ↗</a></div>
    </div>`;
  document.getElementById('sheetBg')?.classList.add('on');
}
function initUI(){
  chips();render();
  document.getElementById('q')?.addEventListener('input',()=>{renderLimit=120;render()});
  document.getElementById('max')?.addEventListener('change',()=>{renderLimit=120;render()});
  document.getElementById('sort')?.addEventListener('change',()=>{renderLimit=120;render()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail()});
}

window.setCat=setCat;
window.toggleFav=toggleFav;
window.openItem=openItem;
window.closeDetail=closeDetail;
window.render=render;
window.saveState=saveState;
window.addEventListener('DOMContentLoaded',initUI);

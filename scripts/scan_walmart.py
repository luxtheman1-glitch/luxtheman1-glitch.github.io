#!/usr/bin/env python3
import json, re, time, html as htmlmod
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
import requests

BASE='https://www.walmart.com'
SEEDS=[
 'https://www.walmart.com/browse/clothing/mens/clearance/5438_9360765_9658256',
 'https://www.walmart.com/c/best-sellers/men-clothes-in-clearance',
 'https://www.walmart.com/shop/deals/clearance',
]
HEADERS={
 'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36',
 'Accept-Language':'en-US,en;q=0.9',
 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
S=requests.Session();S.headers.update(HEADERS)
WALMART_SELLERS={'walmart','walmart.com','walmart.com usa llc'}

def clean(s):
 s=htmlmod.unescape(str(s or ''))
 s=s.replace('\\u002F','/').replace('\\/','/').replace('\\u0026','&')
 try:s=bytes(s,'utf-8').decode('unicode_escape')
 except Exception:pass
 return re.sub(r'\s+',' ',s).strip()

def fetch(url):
 last=None
 for n in range(3):
  try:
   r=S.get(url,timeout=35,allow_redirects=True)
   print('GET',r.status_code,len(r.text),url,flush=True)
   if r.status_code==200 and len(r.text)>10000:return r.text
   last=RuntimeError(f'{r.status_code} {url}')
  except Exception as e:last=e
  time.sleep(2+n*3)
 raise last or RuntimeError('fetch failed')

def strip_tracking(url):
 try:
  u=urlparse(url)
  q=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k not in {'athbdg','athcpid','athpgid','athcgid','athznid','athieid','athstid','athguid','athancid','athena','povid'}]
  return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),''))
 except Exception:return url

def page_url(base,page):
 u=urlparse(base);q=dict(parse_qsl(u.query));q.pop('page',None);q.pop('affinityOverride',None)
 if page>1:q.update({'affinityOverride':'default','page':str(page)})
 return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),''))

def discover_lanes(doc):
 out=[];seen=set()
 for m in re.finditer(r'href=["\']([^"\']+)["\']',doc,re.I):
  raw=clean(m.group(1));low=raw.lower()
  if 'clearance' not in low or '/ip/' in low:continue
  u=strip_tracking(urljoin(BASE,raw))
  p=urlparse(u)
  if p.netloc not in {'www.walmart.com','walmart.com'}:continue
  if u not in seen:seen.add(u);out.append(u)
 return out

def pick(block,patterns):
 for pat in patterns:
  m=re.search(pat,block,re.I|re.S)
  if m:return clean(m.group(1))
 return ''

def num(s):
 try:return float(re.sub(r'[^0-9.]','',str(s)))
 except:return 0.0

def seller_ok(block):
 seller=pick(block,[r'"sellerName"\s*:\s*"([^"]+)"',r'"sellerDisplayName"\s*:\s*"([^"]+)"',r'"sellerTitle"\s*:\s*"([^"]+)"'])
 return seller.lower() in WALMART_SELLERS,seller

def stock_ok(block):
 positive=bool(re.search(r'"availabilityStatus"\s*:\s*"IN_STOCK"|"isOutOfStock"\s*:\s*false|"availability"\s*:\s*"IN_STOCK"',block,re.I))
 negative=bool(re.search(r'"availabilityStatus"\s*:\s*"OUT_OF_STOCK"|"isOutOfStock"\s*:\s*true|"availability"\s*:\s*"OUT_OF_STOCK"',block,re.I))
 return positive and not negative

def category(name):
 s=name.lower()
 if re.search(r'shirt|tee\b|dress|jeans|pants|shorts|hoodie|sweater|jacket|shoe|sneaker|pajama|apparel|fashion',s):return 'Clothing'
 if re.search(r'lego|toy\b|doll|barbie|game\b|puzzle|hot wheels',s):return 'Kids & Toys'
 if re.search(r'cookware|skillet|kitchen|blender|coffee|tumbler|bowl|plate',s):return 'Kitchen'
 if re.search(r'shampoo|hair|makeup|beauty|scrunchie|skincare',s):return 'Beauty'
 if re.search(r'dog|cat\b|pet\b|puppy|kitten',s):return 'Pets'
 if re.search(r'drill|saw\b|tool\b|vacuum|faucet|hart\b',s):return 'Tools'
 if re.search(r'laptop|phone|tv\b|earbud|headphone|charger|electronics',s):return 'Tech'
 if re.search(r'mattress|towel|pillow|blanket|lamp|decor|rug\b|bedding|furniture|storage|home\b',s):return 'Home'
 return 'Other'

def audience(name):
 s=name.lower()
 if re.search(r'\b(girl|boy|kid|youth|child|toddler|baby)\b',s):return 'Kids'
 if re.search(r'\b(women|woman|womens|ladies)\b',s):return 'Women'
 if re.search(r'\b(men|mens|male|big men)\b',s):return 'Men'
 return 'Unisex'

def extract_items(doc,source):
 ids=[(m.start(),m.group(1)) for m in re.finditer(r'"usItemId"\s*:\s*"(\d{5,})"',doc,re.I)]
 out={}
 for pos,item_id in ids:
  block=doc[max(0,pos-7000):min(len(doc),pos+18000)]
  if not re.search(r'clearance',block,re.I):continue
  ok,seller=seller_ok(block)
  if not ok or not stock_ok(block):continue
  name=pick(block,[r'"name"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',r'"productName"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"'])
  if len(name)<3:continue
  price=num(pick(block,[r'"currentPrice"\s*:\s*\{[^{}]{0,1200}?"price"\s*:\s*([0-9.]+)',r'"currentPrice"\s*:\s*([0-9.]+)',r'"price"\s*:\s*([0-9.]+)']))
  if price<=0:continue
  was=num(pick(block,[r'"wasPrice"\s*:\s*\{[^{}]{0,1000}?"price"\s*:\s*([0-9.]+)',r'"wasPrice"\s*:\s*([0-9.]+)']))
  if was<=price:was=None
  url=pick(block,[r'"canonicalUrl"\s*:\s*"([^"]+)"',r'"productPageUrl"\s*:\s*"([^"]+)"',r'"productUrl"\s*:\s*"([^"]+)"'])
  url=strip_tracking(urljoin(BASE,url)) if url else f'{BASE}/ip/{item_id}'
  image=pick(block,[r'"imageUrl"\s*:\s*"([^"]*walmartimages[^"]+)"',r'"thumbnailUrl"\s*:\s*"([^"]*walmartimages[^"]+)"'])
  rating=num(pick(block,[r'"averageRating"\s*:\s*([0-5](?:\.\d+)?)',r'"rating"\s*:\s*([0-5](?:\.\d+)?)']))
  reviews=int(num(pick(block,[r'"numberOfReviews"\s*:\s*([0-9]+)',r'"reviewCount"\s*:\s*([0-9]+)'])))
  discount=round((1-price/was)*100) if was else 0
  savings=round(was-price,2) if was else 0
  aud=audience(name);cat=category(name)
  score=discount + (22 if aud=='Men' else 0) + (5 if cat in {'Home','Kitchen','Tools','Tech','Pets'} else 0)
  out[item_id]={
   'id':item_id,'name':name,'price':price,'was':was,'url':url,'image':image,'imageVerified':bool(image),
   'seller':'Walmart','stock':'in','source':source,'rating':rating,'reviews':reviews,'discount':discount,'savings':savings,
   'category':cat,'audience':aud,'score':min(125,score),'active':True,
  }
 return out

def main():
 queue=list(SEEDS);queued=set(queue);products={};pages=0;lanes=0
 while queue:
  lane=queue.pop(0);lanes+=1;page=1;stale=0;prev=set()
  print('\nLANE',lane,flush=True)
  while True:
   try:doc=fetch(page_url(lane,page))
   except Exception as e:
    print('lane fetch failed',e,flush=True);break
   pages+=1
   if page==1:
    for u in discover_lanes(doc):
     if u not in queued:queued.add(u);queue.append(u)
   batch=extract_items(doc,lane);ids=set(batch)
   fresh=ids-prev
   for k,v in batch.items():products[k]=v
   print(' page',page,'batch',len(batch),'fresh',len(fresh),'total',len(products),flush=True)
   if not ids or ids==prev or not fresh:stale+=1
   else:stale=0
   if not ids or stale>=2:break
   prev=ids;page+=1;time.sleep(0.8)
 if not products:
  raise SystemExit('ERROR: scanner found zero verified in-stock Walmart-sold clearance items; refusing to overwrite deals.json')
 items=list(products.values())
 items.sort(key=lambda p:(-(p.get('score') or 0),p.get('price') or 0))
 data={
  'updated_at':datetime.now(timezone.utc).isoformat(),
  'count':len(items),
  'pages_scanned':pages,'lanes_scanned':lanes,
  'source':'GitHub Walmart clearance scanner',
  'filters':{'stock':'IN_STOCK','seller':'Walmart','clearance':True},
  'items':items,
 }
 with open('deals.json','w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
 print(f'WROTE {len(items)} items from {pages} pages / {lanes} lanes',flush=True)

if __name__=='__main__':main()

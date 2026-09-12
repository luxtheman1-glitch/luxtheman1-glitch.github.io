#!/usr/bin/env python3
import json,re,time,html as htmlmod
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse,parse_qsl,urlencode,urlunparse
import requests

BASE='https://www.walmart.com'
SEEDS=[
 'https://www.walmart.com/shop/deals/clearance',
 'https://www.walmart.com/shop/deals/clearance/clothing-and-accessories',
 'https://www.walmart.com/shop/deals/clearance/furniture',
 'https://www.walmart.com/browse/clothing/mens/clearance/5438_9360765_9658256',
 'https://www.walmart.com/c/best-sellers/men-clothes-in-clearance',
]
HEADERS={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36','Accept-Language':'en-US,en;q=0.9','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Referer':'https://www.walmart.com/'}
S=requests.Session();S.headers.update(HEADERS)
WALMART_SELLERS={'walmart','walmart.com','walmart.com usa llc'}

def clean(v): return re.sub(r'\s+',' ',htmlmod.unescape(str(v or '')).replace('\\u002F','/').replace('\\/','/')).strip()
def num(v):
 if isinstance(v,(int,float)): return float(v)
 try:return float(re.sub(r'[^0-9.]','',str(v)))
 except:return 0.0

def fetch(url):
 last=None
 for n in range(3):
  try:
   r=S.get(url,timeout=35,allow_redirects=True);print('GET',r.status_code,len(r.text),url,flush=True)
   if r.status_code==200 and len(r.text)>10000:return r.text
   last=RuntimeError(f'{r.status_code} {url}')
  except Exception as e:last=e
  time.sleep(2+n*2)
 raise last or RuntimeError('fetch failed')

def strip_tracking(url):
 try:
  u=urlparse(url);drop={'athbdg','athcpid','athpgid','athcgid','athznid','athieid','athstid','athguid','athancid','athena','povid'}
  q=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k not in drop]
  return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),''))
 except:return url

def page_url(base,page):
 u=urlparse(base);q=dict(parse_qsl(u.query));q.pop('page',None);q.pop('affinityOverride',None)
 if page>1:q['page']=str(page)
 return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),''))

def discover_lanes(doc):
 out=[];seen=set()
 for m in re.finditer(r'href=["\']([^"\']+)["\']',doc,re.I):
  raw=clean(m.group(1))
  if 'clearance' not in raw.lower() or '/ip/' in raw.lower():continue
  u=strip_tracking(urljoin(BASE,raw));p=urlparse(u)
  if p.netloc not in {'www.walmart.com','walmart.com'}:continue
  if u not in seen:seen.add(u);out.append(u)
 return out

def iter_json_roots(doc):
 for m in re.finditer(r'<script\b[^>]*>(.*?)</script>',doc,re.I|re.S):
  raw=htmlmod.unescape(m.group(1)).strip()
  if raw[:1] not in '[{':continue
  try:yield json.loads(raw)
  except:pass

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)

def is_clearance(d):
 badge=d.get('badge') if isinstance(d.get('badge'),dict) else {}
 if str(badge.get('key','')).upper()=='CLEARANCE':return True
 if str(d.get('flag','')).strip().lower()=='clearance':return True
 badges=d.get('badges') if isinstance(d.get('badges'),dict) else {}
 flags=badges.get('flags') if isinstance(badges.get('flags'),list) else []
 return any(isinstance(x,dict) and (str(x.get('key','')).upper()=='CLEARANCE' or str(x.get('text','')).lower()=='clearance') for x in flags)

def is_walmart_sold(d): return clean(d.get('sellerName')).lower() in WALMART_SELLERS

def is_in_stock(d):
 av=d.get('availabilityStatusV2') if isinstance(d.get('availabilityStatusV2'),dict) else {}
 return d.get('isOutOfStock') is False and str(av.get('value','')).upper()=='IN_STOCK'

def image_for(d):
 info=d.get('imageInfo') if isinstance(d.get('imageInfo'),dict) else {}
 u=clean(info.get('thumbnailUrl'))
 return u if 'walmartimages.com' in u else ''

def price_for(d): return num(d.get('price'))
def was_for(d,price):
 pi=d.get('priceInfo') if isinstance(d.get('priceInfo'),dict) else {}
 w=num(pi.get('wasPrice'))
 return w if w>price else None

def product_url(d,item_id):
 u=clean(d.get('canonicalUrl'))
 return strip_tracking(urljoin(BASE,u)) if '/ip/' in u else f'{BASE}/ip/{item_id}'

def category(name):
 s=name.lower()
 if re.search(r'shirt|tee\b|dress|jeans|pants|shorts|hoodie|sweater|jacket|shoe|sneaker|pajama|apparel|fashion|boxer|brief|underwear',s):return 'Clothing'
 if re.search(r'lego|toy\b|doll|barbie|game\b|puzzle|hot wheels|paint set',s):return 'Kids & Toys'
 if re.search(r'cookware|skillet|kitchen|blender|coffee|tumbler|bowl|plate|spatula|peeler',s):return 'Kitchen'
 if re.search(r'shampoo|hair|makeup|beauty|scrunchie|skincare',s):return 'Beauty'
 if re.search(r'dog|cat\b|pet\b|puppy|kitten',s):return 'Pets'
 if re.search(r'drill|saw\b|tool\b|vacuum|faucet|hart\b',s):return 'Tools'
 if re.search(r'laptop|phone|tv\b|earbud|headphone|charger|electronics|smartwatch',s):return 'Tech'
 if re.search(r'mattress|towel|pillow|blanket|lamp|decor|rug\b|bedding|furniture|storage|comforter|sofa',s):return 'Home'
 return 'Other'

def audience(name):
 s=name.lower()
 if re.search(r'\b(girl|boy|kid|youth|child|toddler|baby)\b',s):return 'Kids'
 if re.search(r'\b(women|woman|womens|ladies)\b',s):return 'Women'
 if re.search(r'\b(men|mens|male|big men)\b',s):return 'Men'
 return 'Unisex'

def build_product(d,source):
 # Only Walmart's actual Product object is eligible. Nested variant/swatch objects are ignored.
 if d.get('__typename')!='Product':return None
 item_id=str(d.get('usItemId') or '')
 name=clean(d.get('name'))
 if not item_id.isdigit() or len(item_id)<5 or len(name)<8:return None
 if not is_clearance(d) or not is_walmart_sold(d) or not is_in_stock(d):return None
 price=price_for(d)
 if price<=0:return None
 was=was_for(d,price);image=image_for(d);url=product_url(d,item_id)
 rating=num(d.get('averageRating'));reviews=int(num(d.get('numberOfReviews')))
 discount=round((1-price/was)*100) if was else 0;savings=round(was-price,2) if was else 0
 aud=audience(name);cat=category(name);score=discount+(22 if aud=='Men' else 0)+(5 if cat in {'Home','Kitchen','Tools','Tech','Pets'} else 0)
 return {'id':item_id,'name':name,'brand':clean(d.get('brand')),'price':price,'was':was,'url':url,'image':image,'imageVerified':bool(image),'seller':'Walmart','stock':'in','source':source,'rating':rating,'reviews':reviews,'discount':discount,'savings':savings,'category':cat,'audience':aud,'score':min(125,score),'active':True}

def extract_items(doc,source):
 out={};real=0
 for root in iter_json_roots(doc):
  for d in walk(root):
   if d.get('__typename')!='Product':continue
   real+=1;p=build_product(d,source)
   if p:out[p['id']]=p
 print(' real Product objects',real,'STRICT ACCEPTED',len(out),flush=True)
 return out

def main():
 queue=list(SEEDS);queued=set(queue);products={};pages=0;lanes=0
 while queue:
  lane=queue.pop(0);lanes+=1;page=1;prev=set()
  print('\nLANE',lane,flush=True)
  while True:
   try:doc=fetch(page_url(lane,page))
   except Exception as e:print('lane fetch failed',e,flush=True);break
   pages+=1
   if page==1:
    for u in discover_lanes(doc):
     if u not in queued:queued.add(u);queue.append(u)
   batch=extract_items(doc,lane);ids=set(batch);fresh=ids-prev
   products.update(batch);print(' page',page,'strict',len(batch),'fresh',len(fresh),'total',len(products),flush=True)
   # Walmart often returns a shell/block for deep pages. Stop cleanly instead of looping forever.
   if not ids or ids==prev or not fresh:break
   prev=ids;page+=1;time.sleep(1)
 if not products:raise SystemExit('ERROR: zero strict Walmart-sold, in-stock clearance products; refusing to publish')
 items=sorted(products.values(),key=lambda p:(-(p.get('score') or 0),p.get('price') or 0))
 data={'updated_at':datetime.now(timezone.utc).isoformat(),'count':len(items),'pages_scanned':pages,'lanes_scanned':lanes,'source':'GitHub Walmart clearance scanner','filters':{'stock':'IN_STOCK','seller':'Walmart','clearance':True},'items':items}
 with open('deals.json','w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
 print(f'WROTE {len(items)} STRICT items from {pages} pages / {lanes} lanes',flush=True)
 for p in items[:12]:print(' SAMPLE',p['id'],p['seller'],p['stock'],p['price'],p['name'][:100],flush=True)

if __name__=='__main__':main()

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
 'Referer':'https://www.walmart.com/',
}
S=requests.Session();S.headers.update(HEADERS)
WALMART_SELLERS={'walmart','walmart.com','walmart.com usa llc'}


def clean(s):
 s=htmlmod.unescape(str(s or ''))
 s=s.replace('\\u002F','/').replace('\\/','/').replace('\\u0026','&')
 return re.sub(r'\s+',' ',s).strip()


def num(v):
 if isinstance(v,(int,float)):return float(v)
 try:return float(re.sub(r'[^0-9.]','',str(v)))
 except:return 0.0


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
 if page>1:q['page']=str(page)
 return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),''))


def discover_lanes(doc):
 out=[];seen=set()
 for m in re.finditer(r'href=["\']([^"\']+)["\']',doc,re.I):
  raw=clean(m.group(1));low=raw.lower()
  if 'clearance' not in low or '/ip/' in low:continue
  u=strip_tracking(urljoin(BASE,raw));p=urlparse(u)
  if p.netloc not in {'www.walmart.com','walmart.com'}:continue
  if u not in seen:seen.add(u);out.append(u)
 return out


def iter_script_json(doc):
 parsed=0
 for m in re.finditer(r'<script\b[^>]*>(.*?)</script>',doc,re.I|re.S):
  raw=htmlmod.unescape(m.group(1)).strip()
  if not raw:continue
  candidates=[]
  if raw[:1] in '[{':candidates.append(raw)
  else:
   # Some Walmart state scripts assign JSON after '='.
   eq=raw.find('=')
   if eq>=0:
    tail=raw[eq+1:].strip().rstrip(';')
    if tail[:1] in '[{':candidates.append(tail)
  for c in candidates:
   try:
    obj=json.loads(c);parsed+=1;yield obj
   except Exception:pass
 print(' parsed JSON scripts',parsed,flush=True)


def walk(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values():yield from walk(v)
 elif isinstance(obj,list):
  for v in obj:yield from walk(v)


def values_for_keys(obj,keys):
 vals=[]
 def rec(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in keys and not isinstance(v,(dict,list)):vals.append(v)
    rec(v)
  elif isinstance(x,list):
   for v in x:rec(v)
 rec(obj);return vals


def first_scalar(obj,keys):
 vals=values_for_keys(obj,set(keys))
 for v in vals:
  if v not in (None,''):return v
 return None


def candidate_price(d):
 pi=d.get('priceInfo') if isinstance(d.get('priceInfo'),dict) else {}
 cp=pi.get('currentPrice')
 if isinstance(cp,dict):
  p=num(cp.get('price') or cp.get('priceString'))
  if p:return p
 p=num(cp)
 if p:return p
 cp=d.get('currentPrice')
 if isinstance(cp,dict):p=num(cp.get('price') or cp.get('priceString'))
 else:p=num(cp)
 if p:return p
 return 0.0


def candidate_was(d,price):
 pi=d.get('priceInfo') if isinstance(d.get('priceInfo'),dict) else {}
 wp=pi.get('wasPrice') or d.get('wasPrice')
 if isinstance(wp,dict):w=num(wp.get('price') or wp.get('priceString'))
 else:w=num(wp)
 return w if w>price else None


def seller_name(d):
 direct=d.get('sellerName') or d.get('sellerDisplayName') or d.get('sellerTitle')
 if direct:return clean(direct)
 vals=values_for_keys(d,{'sellerName','sellerDisplayName','sellerTitle'})
 return clean(vals[0]) if vals else ''


def stock_positive(d):
 statuses=[str(v).upper() for v in values_for_keys(d,{'availabilityStatus','availability'})]
 flags=values_for_keys(d,{'isOutOfStock'})
 if any(v is True for v in flags):return False
 return any(s=='IN_STOCK' or s.endswith(':IN_STOCK') for s in statuses) or any(v is False for v in flags)


def clearance_positive(d):
 if d.get('isClearance') is True:return True
 vals=values_for_keys(d,{'badge','badgeText','badgeLabel','specialOffer','specialOfferText','tag','label','type'})
 return any('clearance' in str(v).lower() for v in vals)


def image_url(d):
 vals=values_for_keys(d,{'imageUrl','thumbnailUrl','src','url'})
 for v in vals:
  s=clean(v)
  if 'walmartimages.com' in s and not re.search(r'logo|spark|banner',s,re.I):return s
 return ''


def product_url(d,item_id):
 for k in ('canonicalUrl','productPageUrl','productUrl','productHref'):
  v=d.get(k)
  if isinstance(v,str) and '/ip/' in v:return strip_tracking(urljoin(BASE,clean(v)))
 vals=values_for_keys(d,{'canonicalUrl','productPageUrl','productUrl','productHref'})
 for v in vals:
  s=clean(v)
  if '/ip/' in s:return strip_tracking(urljoin(BASE,s))
 return f'{BASE}/ip/{item_id}'


def category(name):
 s=name.lower()
 if re.search(r'shirt|tee\b|dress|jeans|pants|shorts|hoodie|sweater|jacket|shoe|sneaker|pajama|apparel|fashion|boxer|brief',s):return 'Clothing'
 if re.search(r'lego|toy\b|doll|barbie|game\b|puzzle|hot wheels',s):return 'Kids & Toys'
 if re.search(r'cookware|skillet|kitchen|blender|coffee|tumbler|bowl|plate',s):return 'Kitchen'
 if re.search(r'shampoo|hair|makeup|beauty|scrunchie|skincare',s):return 'Beauty'
 if re.search(r'dog|cat\b|pet\b|puppy|kitten',s):return 'Pets'
 if re.search(r'drill|saw\b|tool\b|vacuum|faucet|hart\b',s):return 'Tools'
 if re.search(r'laptop|phone|tv\b|earbud|headphone|charger|electronics|smartwatch',s):return 'Tech'
 if re.search(r'mattress|towel|pillow|blanket|lamp|decor|rug\b|bedding|furniture|storage|home\b',s):return 'Home'
 return 'Other'


def audience(name):
 s=name.lower()
 if re.search(r'\b(girl|boy|kid|youth|child|toddler|baby)\b',s):return 'Kids'
 if re.search(r'\b(women|woman|womens|ladies)\b',s):return 'Women'
 if re.search(r'\b(men|mens|male|big men)\b',s):return 'Men'
 return 'Unisex'


def build_product(d,source):
 item_id=str(d.get('usItemId') or '')
 if not item_id.isdigit() or len(item_id)<5:return None
 # Product name must be on the same Walmart product object, never borrowed from a neighbor/child object.
 name=d.get('name') or d.get('productName') or d.get('title')
 if not isinstance(name,str):return None
 name=clean(name)
 if len(name)<8 or name.lower() in {'fulfillment','flags','actual_color','color','size'}:return None
 seller=seller_name(d)
 if seller.lower() not in WALMART_SELLERS:return None
 if not stock_positive(d):return None
 if not clearance_positive(d):return None
 price=candidate_price(d)
 if price<=0:return None
 was=candidate_was(d,price)
 url=product_url(d,item_id);image=image_url(d)
 rating=num(first_scalar(d,{'averageRating','rating'}) or 0)
 reviews=int(num(first_scalar(d,{'numberOfReviews','reviewCount'}) or 0))
 discount=round((1-price/was)*100) if was else 0;savings=round(was-price,2) if was else 0
 aud=audience(name);cat=category(name);score=discount+(22 if aud=='Men' else 0)+(5 if cat in {'Home','Kitchen','Tools','Tech','Pets'} else 0)
 return {'id':item_id,'name':name,'price':price,'was':was,'url':url,'image':image,'imageVerified':bool(image),'seller':'Walmart','stock':'in','source':source,'rating':rating,'reviews':reviews,'discount':discount,'savings':savings,'category':cat,'audience':aud,'score':min(125,score),'active':True}


def extract_items(doc,source):
 out={};objects=0;with_id=0
 for root in iter_script_json(doc):
  for d in walk(root):
   objects+=1
   if 'usItemId' not in d:continue
   with_id+=1
   p=build_product(d,source)
   if p:out[p['id']]=p
 print(' structured objects',objects,'with usItemId',with_id,'accepted',len(out),flush=True)
 return out


def main():
 queue=list(SEEDS);queued=set(queue);products={};pages=0;lanes=0
 while queue:
  lane=queue.pop(0);lanes+=1;page=1;stale=0;prev=set()
  print('\nLANE',lane,flush=True)
  while True:
   try:doc=fetch(page_url(lane,page))
   except Exception as e:print('lane fetch failed',e,flush=True);break
   pages+=1
   if page==1:
    for u in discover_lanes(doc):
     if u not in queued:queued.add(u);queue.append(u)
   batch=extract_items(doc,lane);ids=set(batch);fresh=ids-prev
   products.update(batch)
   print(' page',page,'batch',len(batch),'fresh',len(fresh),'total',len(products),flush=True)
   if not ids or ids==prev or not fresh:stale+=1
   else:stale=0
   if not ids or stale>=2:break
   prev=ids;page+=1;time.sleep(0.8)
 if not products:raise SystemExit('ERROR: zero strict structured Walmart clearance products; refusing to overwrite deals.json')
 items=sorted(products.values(),key=lambda p:(-(p.get('score') or 0),p.get('price') or 0))
 data={'updated_at':datetime.now(timezone.utc).isoformat(),'count':len(items),'pages_scanned':pages,'lanes_scanned':lanes,'source':'GitHub Walmart clearance scanner','filters':{'stock':'IN_STOCK','seller':'Walmart','clearance':True},'items':items}
 with open('deals.json','w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
 print(f'WROTE {len(items)} strict items from {pages} pages / {lanes} lanes',flush=True)

if __name__=='__main__':main()

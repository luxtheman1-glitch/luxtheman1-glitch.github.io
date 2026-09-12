#!/usr/bin/env python3
import requests,re,json,html
u='https://www.walmart.com/shop/deals/clearance'
r=requests.get(u,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36','Accept-Language':'en-US,en;q=0.9'},timeout=40)
print('HTTP',r.status_code,'LEN',len(r.text))
roots=[]
for m in re.finditer(r'<script\b[^>]*>(.*?)</script>',r.text,re.I|re.S):
 s=html.unescape(m.group(1)).strip()
 if s[:1] not in '[{': continue
 try: roots.append(json.loads(s))
 except: pass
print('JSON ROOTS',len(roots))

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values(): yield from walk(v)
 elif isinstance(x,list):
  for v in x: yield from walk(v)

products=[]
for root in roots:
 for d in walk(root):
  if d.get('__typename')=='Product' and d.get('usItemId') and isinstance(d.get('name'),str): products.append(d)
print('REAL PRODUCT OBJECTS',len(products))

hits=[]
for d in products:
 blob=json.dumps(d,ensure_ascii=False)
 if 'clearance' in blob.lower(): hits.append(d)
print('PRODUCT OBJECTS CONTAINING CLEARANCE',len(hits))
for d in hits[:20]:
 print('\nITEM',d.get('usItemId'))
 print('NAME',d.get('name'))
 print('SELLER',d.get('sellerName'),'OUT',d.get('isOutOfStock'),'AVAILV2',d.get('availabilityStatusV2'))
 print('PRICE',d.get('price'),'PRICEINFO',json.dumps(d.get('priceInfo'),ensure_ascii=False)[:1200])
 print('BADGE',json.dumps(d.get('badge'),ensure_ascii=False)[:1000])
 print('BADGES',json.dumps(d.get('badges'),ensure_ascii=False)[:3500])
 print('FLAG',json.dumps(d.get('flag'),ensure_ascii=False)[:1000])
 print('SPECIALBUY',json.dumps(d.get('specialBuy'),ensure_ascii=False)[:1000])
 print('PROMO',json.dumps(d.get('promoDiscount'),ensure_ascii=False)[:1000])
 print('CANONICAL',d.get('canonicalUrl'))
 print('IMAGEINFO',json.dumps(d.get('imageInfo'),ensure_ascii=False)[:1000])
 # Print only paths/values that contain clearance so we can map exact marker.
 found=[]
 def paths(x,path=''):
  if isinstance(x,dict):
   for k,v in x.items(): paths(v,f'{path}.{k}' if path else k)
  elif isinstance(x,list):
   for i,v in enumerate(x): paths(v,f'{path}[{i}]')
  elif 'clearance' in str(x).lower(): found.append((path,x))
 paths(d)
 print('CLEARANCE PATHS',found[:30])

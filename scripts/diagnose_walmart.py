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

def collect(x,names,out=None):
 if out is None: out={k:[] for k in names}
 if isinstance(x,dict):
  for k,v in x.items():
   if k in out and not isinstance(v,(dict,list)) and len(out[k])<8: out[k].append(v)
   collect(v,names,out)
 elif isinstance(x,list):
  for v in x: collect(v,names,out)
 return out

names={'sellerName','sellerDisplayName','sellerTitle','availabilityStatus','availability','isOutOfStock','badge','badgeText','badgeLabel','isClearance','specialOffer','specialOfferText','currentPrice','wasPrice','price','canonicalUrl','productPageUrl','productUrl','imageUrl','thumbnailUrl','averageRating','numberOfReviews'}
shown=0
for root in roots:
 for d in walk(root):
  if 'usItemId' not in d: continue
  nm=d.get('name') or d.get('productName') or d.get('title')
  if not isinstance(nm,str) or len(nm)<8: continue
  print('\nITEM',d.get('usItemId'))
  print('NAME',nm[:240])
  print('DIRECT KEYS',sorted(d.keys()))
  vals=collect(d,names)
  for k,v in vals.items():
   if v: print(k,repr(v[:8]))
  print('SNIP',json.dumps(d,ensure_ascii=False)[:5000])
  shown+=1
  if shown>=6: raise SystemExit
print('SHOWN',shown)

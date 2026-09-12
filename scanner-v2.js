/* LUX//CLEARANCE scanner v2 — auto-start, live feed, Walmart-sold + in-stock only */
(() => {
  'use strict';

  const REFRESH_MS = 30 * 60 * 1000;
  const VERIFY_FRESH_MS = 15 * 60 * 1000;
  const REQUEST_GAP_MS = 700;
  const MAX_VERIFY_CONCURRENCY = 3;

  let running = false;
  let lastRequestAt = 0;
  let renderTimer = null;
  let lastCompletedAt = 0;

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = v => String(v ?? '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/\\u002F/g, '/')
    .replace(/\\\//g, '/')
    .replace(/\s+/g, ' ')
    .trim();
  const number = v => {
    const n = Number(String(v ?? '').replace(/[^0-9.]/g, ''));
    return Number.isFinite(n) ? n : 0;
  };

  function ui(title, body) {
    const a = document.getElementById('scanTitle');
    const b = document.getElementById('scanText');
    if (a) a.textContent = title;
    if (b) b.textContent = body;
  }

  function scanButton(disabled) {
    const btn = document.querySelector('.scanbar button');
    if (!btn) return;
    btn.disabled = !!disabled;
    btn.textContent = disabled ? '↻ Scanning…' : '↻ Rescan';
  }

  function renderSoon() {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(() => {
      try { saveState(); render(); } catch (e) { console.error('render failed', e); }
    }, 120);
  }

  async function proxyFetch(url, retry = true) {
    const wait = Math.max(0, REQUEST_GAP_MS - (Date.now() - lastRequestAt));
    if (wait) await sleep(wait);
    lastRequestAt = Date.now();

    const stripped = url.replace(/^https?:\/\//, '');
    const targets = [
      'https://r.jina.ai/http://' + stripped,
      'https://r.jina.ai/https://' + stripped
    ];

    let lastErr = null;
    for (const target of targets) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 40000);
      try {
        const res = await fetch(target, { signal: controller.signal, cache: 'no-store' });
        if (res.status === 429 && retry) {
          clearTimeout(timeout);
          await sleep(8000);
          return proxyFetch(url, false);
        }
        if (!res.ok) throw new Error('Proxy HTTP ' + res.status);
        const text = await res.text();
        if (text && text.length > 200) return text;
        throw new Error('Empty Walmart response');
      } catch (err) {
        lastErr = err;
      } finally {
        clearTimeout(timeout);
      }
    }
    throw lastErr || new Error('Walmart feed unavailable');
  }

  function normalizeWalmartUrl(raw) {
    let s = clean(raw).replace(/[),.;]+$/, '');
    if (s.startsWith('/')) s = 'https://www.walmart.com' + s;
    if (!/^https?:\/\/www\.walmart\.com\//i.test(s)) return '';
    try {
      const u = new URL(s);
      if (u.hostname !== 'www.walmart.com') return '';
      [
        'athbdg','athcpid','athpgid','athcgid','athznid','athieid','athstid',
        'athguid','athancid','athena','povid','athAsset'
      ].forEach(k => u.searchParams.delete(k));
      return u.toString();
    } catch {
      return '';
    }
  }

  function itemId(url) {
    const s = String(url || '');
    return s.match(/\/ip\/(?:[^/?#]+\/)?(\d{5,})/)?.[1]
      || s.match(/\/ip\/(\d{5,})/)?.[1]
      || '';
  }

  function productLinks(md) {
    const found = new Map();
    const patterns = [
      /\]\((https?:\/\/www\.walmart\.com\/ip\/[^\s)]+)\)/gi,
      /\]\((\/ip\/[^\s)]+)\)/gi,
      /(https?:\/\/www\.walmart\.com\/ip\/[^\s)\]"'<>]+)/gi,
      /(?:href=)?["'](\/ip\/[^"']+)["']/gi
    ];

    for (const rx of patterns) {
      let m;
      while ((m = rx.exec(md))) {
        const url = normalizeWalmartUrl(m[1]);
        const id = itemId(url);
        if (!url || !id) continue;

        const block = md.slice(Math.max(0, m.index - 2200), Math.min(md.length, m.index + 2800));
        if (!/\bClearance\b/i.test(block)) continue;
        if (/Out of stock/i.test(block) && !/(Add|Shipping|Pickup|Delivery)/i.test(block)) continue;

        found.set(id, { id, url });
      }
    }
    return [...found.values()];
  }

  function discoverLanes(md) {
    const found = new Map();
    const patterns = [
      /\]\((https?:\/\/www\.walmart\.com\/[^\s)]*clearance[^\s)]*)\)/gi,
      /\]\((\/[^\s)]*clearance[^\s)]*)\)/gi,
      /(https?:\/\/www\.walmart\.com\/[^\s)\]"'<>]*clearance[^\s)\]"'<>]*)/gi
    ];

    for (const rx of patterns) {
      let m;
      while ((m = rx.exec(md))) {
        const url = normalizeWalmartUrl(m[1]);
        if (!url || /\/ip\//i.test(url)) continue;
        try {
          const u = new URL(url);
          u.searchParams.delete('page');
          u.searchParams.delete('affinityOverride');
          const key = u.toString();
          const men = /men|mens|men's/i.test(key);
          found.set(key, { url: key, label: men ? "Men's clearance" : 'Clearance lane', priority: men ? 110 : 50 });
        } catch {}
      }
    }
    return [...found.values()];
  }

  function pageUrl(base, page) {
    const u = new URL(base);
    u.searchParams.delete('page');
    u.searchParams.delete('affinityOverride');
    if (page > 1) {
      u.searchParams.set('affinityOverride', 'default');
      u.searchParams.set('page', String(page));
    }
    return u.toString();
  }

  function isSoldByWalmart(md) {
    return /Sold\s+(?:and\s+shipped\s+)?by\s+Walmart(?:\.com)?/i.test(md)
      || /Sold by Walmart\.com/i.test(md);
  }

  function isPurchasable(md) {
    if (/\bOut of stock\b|Currently unavailable|This item is unavailable|Sold out/i.test(md)) return false;
    return /Add to cart/i.test(md)
      || /Shipping\s+(?:arrives|available)/i.test(md)
      || /Pickup\s+(?:as soon as|available|today|tomorrow)/i.test(md)
      || /Delivery\s+(?:as soon as|available|today|tomorrow)/i.test(md)
      || /How do you want your item\?/i.test(md);
  }

  function exactName(md) {
    const candidates = [
      md.match(/^#\s+([^\n]{3,350})$/m)?.[1],
      md.match(/^##\s+([^\n]{3,350})$/m)?.[1],
      md.match(/Title:\s*([^\n]{3,350})/i)?.[1]
    ];
    return clean(candidates.find(Boolean) || '');
  }

  function exactPrice(md) {
    const candidates = [
      md.match(/current price(?:\s+Now)?\s*\$([\d,.]+)/i)?.[1],
      md.match(/Current price is USD(?:\s+Now)?\s*\$([\d,.]+)/i)?.[1],
      md.match(/(?:^|\n)Now\s*\$([\d,.]+)/i)?.[1],
      md.match(/Price when purchased online[\s\S]{0,500}?\$([\d,.]+)/i)?.[1]
    ];
    return number(candidates.find(Boolean));
  }

  function exactWas(md, price) {
    const was = number(md.match(/\bWas\s*\$([\d,.]+)/i)?.[1]);
    return was > price ? was : null;
  }

  function exactImage(md) {
    const urls = [...String(md).matchAll(/https:\/\/i5\.walmartimages\.com\/[^\s)\]"'<>]+/gi)]
      .map(x => x[0].replace(/[),.;]+$/, ''));
    return urls.find(u => !/logo|spark|walmartplus|banner|icon/i.test(u)) || '';
  }

  function ratingInfo(md) {
    const rating = Number(md.match(/([0-5](?:\.\d)?)\s+out of 5 stars/i)?.[1] || 0);
    const reviewsRaw = md.match(/([\d,]+)\s+(?:ratings|reviews)/i)?.[1] || '0';
    return { rating, reviews: parseInt(reviewsRaw.replace(/,/g, ''), 10) || 0 };
  }

  async function verifyCandidate(candidate, source) {
    try {
      const md = await proxyFetch(candidate.url);
      if (!isSoldByWalmart(md)) return null;
      if (!isPurchasable(md)) return null;

      const name = exactName(md);
      const price = exactPrice(md);
      if (!name || !price) return null;

      const was = exactWas(md, price);
      const image = exactImage(md);
      const { rating, reviews } = ratingInfo(md);

      let p = {
        id: candidate.id,
        name,
        price,
        was,
        url: candidate.url,
        image,
        imageVerified: !!image,
        seller: 'Walmart',
        stock: 'in',
        source,
        verifiedAt: Date.now(),
        active: true,
        rating,
        reviews
      };
      try { p = finish(p); } catch {}
      p.seller = 'Walmart';
      p.stock = 'in';
      p.active = true;
      p.verifiedAt = Date.now();
      return p;
    } catch (err) {
      console.warn('verify failed', candidate.url, err);
      return null;
    }
  }

  function mergeVerified(p, scanId) {
    const id = String(p.id);
    const idx = products.findIndex(x => String(x.id) === id);
    const old = idx >= 0 ? products[idx] : null;
    const next = {
      ...old,
      ...p,
      scanId,
      firstSeen: old?.firstSeen || Date.now(),
      history: [...(old?.history || []), { t: Date.now(), p: +p.price }].slice(-120)
    };
    if (idx >= 0) products[idx] = next;
    else products.push(next);
    renderSoon();
  }

  function enforceStrict() {
    const now = Date.now();
    products = products.map(p => {
      const valid = p.seller === 'Walmart'
        && p.stock === 'in'
        && p.verifiedAt
        && (now - p.verifiedAt <= VERIFY_FRESH_MS);
      return valid ? { ...p, active: true } : { ...p, active: false };
    });
    try { saveState(); render(); } catch {}
  }

  async function verifyBatch(batch, source, scanId, verifiedSet, stats) {
    let cursor = 0;
    async function worker() {
      while (cursor < batch.length) {
        const i = cursor++;
        const candidate = batch[i];
        const p = await verifyCandidate(candidate, source);
        stats.checked++;
        if (p) {
          verifiedSet.add(String(p.id));
          mergeVerified(p, scanId);
          ui('LIVE · feed updating', `${verifiedSet.size} Walmart-sold, in-stock clearance items verified · ${stats.pages} pages scanned`);
        } else {
          ui('LIVE · verifying', `${stats.checked} products checked · ${verifiedSet.size} passed strict Walmart + stock rules`);
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(MAX_VERIFY_CONCURRENCY, batch.length || 1) }, worker));
  }

  async function liveScan() {
    if (running) return;
    running = true;
    scanButton(true);
    enforceStrict();

    const scanId = 'live-' + Date.now();
    const queue = [
      { url: 'https://www.walmart.com/browse/clothing/mens/clearance/5438_9360765_9658256', label: "Men's clearance", priority: 130 },
      { url: 'https://www.walmart.com/c/best-sellers/men-clothes-in-clearance', label: "Men's clearance", priority: 120 },
      { url: 'https://www.walmart.com/shop/deals/clearance', label: 'All clearance', priority: 100 }
    ];
    const queued = new Set(queue.map(x => x.url));
    const seenCandidates = new Set();
    const verified = new Set();
    const stats = { pages: 0, lanes: 0, checked: 0 };

    ui('LIVE · connecting to Walmart', 'Auto-scan started. Only in-stock items sold by Walmart will be shown.');

    try {
      while (queue.length) {
        queue.sort((a, b) => b.priority - a.priority);
        const lane = queue.shift();
        let page = 1;
        let stale = 0;
        let previousFingerprint = '';

        while (true) {
          ui('LIVE · scanning Walmart', `${lane.label} · page ${page} · ${verified.size} verified live deals`);

          let md;
          try {
            md = await proxyFetch(pageUrl(lane.url, page));
          } catch (err) {
            console.warn('lane fetch failed', lane.url, err);
            break;
          }
          stats.pages++;

          for (const discovered of discoverLanes(md)) {
            if (!queued.has(discovered.url)) {
              queued.add(discovered.url);
              queue.push(discovered);
            }
          }

          const allCandidates = productLinks(md);
          const batch = allCandidates.filter(c => {
            if (seenCandidates.has(c.id)) return false;
            seenCandidates.add(c.id);
            return true;
          });

          const fingerprint = allCandidates.map(x => x.id).join(',');
          if (!allCandidates.length || fingerprint === previousFingerprint || !batch.length) stale++;
          else stale = 0;
          previousFingerprint = fingerprint;

          if (batch.length) {
            await verifyBatch(batch, lane.label, scanId, verified, stats);
          }

          if (!allCandidates.length || stale >= 2) break;
          page++;
        }
        stats.lanes++;
      }

      products = products.map(p => {
        const keep = p.scanId === scanId && p.seller === 'Walmart' && p.stock === 'in';
        return keep ? { ...p, active: true } : { ...p, active: false };
      });
      saveState();
      render();
      lastCompletedAt = Date.now();

      if (verified.size) {
        ui('LIVE · scan complete', `${verified.size} verified in-stock Walmart-sold clearance items · ${stats.pages} pages · ${stats.lanes} lanes. Auto-refresh stays on.`);
      } else {
        ui('LIVE · no verified items yet', 'The scanner ran, but Walmart returned no products that passed both in-stock and sold-by-Walmart checks. Tap Rescan to retry.');
      }
    } catch (err) {
      console.error('live scan crashed', err);
      ui('LIVE · scan error', 'Walmart could not be read right now. Tap Rescan to retry.');
    } finally {
      running = false;
      scanButton(false);
    }
  }

  // Replace the legacy scanner with the strict live scanner.
  window.scanNow = liveScan;
  window.luxLiveScan = liveScan;

  function boot() {
    ui('LIVE · starting…', 'Opening the Walmart clearance feed now.');
    setTimeout(liveScan, 80);
    setInterval(() => {
      if (!running && Date.now() - lastCompletedAt >= REFRESH_MS) liveScan();
    }, 60 * 1000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && !running && Date.now() - lastCompletedAt >= REFRESH_MS) liveScan();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();

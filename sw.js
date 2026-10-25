// Pokémon Binder service worker: lets the binder install as an app and open with no connection.
// The server fills in the version below, so every new binder version gets fresh saved copies.
const VERSION = "__VERSION__";
const SHELL = "binder-shell-" + VERSION;   // the page, fonts and icons
const DATA = "binder-data";                 // the last binder data the phone saw (cards, prices, purchases)
const PICS = "binder-pics";                 // card pictures, logos and Pokémon art you've looked at
const MAX_PICS = 3000;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(["./", "fonts.css?v=1", "manifest.webmanifest", "icon-192.png", "icon-512.png", "favicon"]).catch(() => {})));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("binder-shell-") && k !== SHELL).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Ask the server first; if it can't be reached, answer from the saved copy and say so in a header.
async function networkFirst(req, cacheName, keyReq) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(keyReq || req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(keyReq || req);
    if (!hit) throw err;
    const h = new Headers(hit.headers); h.set("X-Binder-Saved", "1");
    return new Response(await hit.blob(), {status: hit.status, statusText: hit.statusText, headers: h});
  }
}
// Pictures rarely change: use the saved copy if there is one, otherwise download and keep it.
async function cacheFirst(req) {
  const cache = await caches.open(PICS);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) { cache.put(req, res.clone()); trimPics(cache); }
  return res;
}
let trimming = false;
async function trimPics(cache) {
  if (trimming) return; trimming = true;
  try { const keys = await cache.keys(); for (let i = 0; i < keys.length - MAX_PICS; i++) await cache.delete(keys[i]); }
  finally { trimming = false; }
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;                       // saving changes always goes straight to the server
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;             // other websites: leave alone
  const p = url.pathname;
  if (p.endsWith("/api/health") || p.includes("/api/update") || p.includes("/api/backup") || p.includes("/api/refresh") || p.includes("/api/status") || p.includes("/api/psa/")) return;
  if (req.mode === "navigate") { e.respondWith(networkFirst(req, SHELL, new Request("./"))); return; }
  if (p.includes("/api/")) { e.respondWith(networkFirst(req, DATA)); return; }
  if (/\/(img|photo)\//.test(p) || /\/(art|unown)\//.test(p) || /\/(logo|sprite)\.png$/.test(p)) { e.respondWith(cacheFirst(req)); return; }
  if (/(fonts\.css|manifest\.webmanifest|icon-\d+\.png|app-icon\.png|favicon)$/.test(p)) { e.respondWith(networkFirst(req, SHELL)); return; }
});

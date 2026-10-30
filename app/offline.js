// Connection dot, changes made offline, installing the app, other addresses.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- connection to the server (green/red dot) ----------
const standaloneApp = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone===true;
// Asks the server "are you there?" every 30 seconds while the page is on screen, when the phone's network
// changes, and when you tap Check connection. Green = it answered, red = it didn't.
const conn={ok:null, at:0};
function setConn(ok){
  const was=conn.ok;
  conn.ok=ok; conn.at=Date.now();
  document.body.classList.toggle("offline", !ok);
  if(ok && was===false){ warmCache(true); syncAsked=false; }
  if(ok && !syncAsked && pendingList().length) setTimeout(reviewSync, 600);
  pendUI();
  const tip = ok ? "Connected to "+srv() : "Can't reach "+srv();
  document.querySelectorAll(".conn").forEach(d=>{ d.classList.toggle("on",ok); d.classList.toggle("off",!ok); d.title=tip; d.setAttribute("aria-label",tip); });
  connRow();
}
function connRow(){
  if(!$("stConnT")) return;
  if(conn.ok===null){ $("stConnT").textContent="Checking…"; $("stConnS").textContent=""; return; }
  $("stConnT").textContent = conn.ok ? "Connected to "+srv() : "Can't reach "+srv();
  const secs=Math.round((Date.now()-conn.at)/1000);
  $("stConnS").textContent = "Checked "+(secs<5 ? "just now" : secs<60 ? secs+" seconds ago" : Math.round(secs/60)+" min ago")+" · "+location.host
    + (conn.ok ? "" : ". Check that "+srv()+" is on, and that Tailscale is on if you're away from home.");
}
let connBusy=null;
function checkConn(){
  if(connBusy) return connBusy;
  const once=()=>{ const ctl=new AbortController(), t=setTimeout(()=>ctl.abort(),6000);
    return fetch("api/health",{cache:"no-store",signal:ctl.signal}).then(r=>r.ok,()=>false).finally(()=>clearTimeout(t)); };
  // one missed answer while connected gets a second try 2 seconds later, so a hiccup doesn't flip to offline
  connBusy=once().then(ok=>ok || conn.ok!==true || !navigator.onLine ? ok : new Promise(res=>setTimeout(res,2000)).then(once))
    .then(ok=>setConn(ok)).finally(()=>{ connBusy=null; });
  return connBusy;
}
// Offline copies: the service worker answers from the phone's saved copy when the server can't be reached,
// and marks those answers. Seeing one (or a failed request) flips the dot to red right away.
{
  const realFetch=window.fetch.bind(window);
  window.fetch=(input, init)=>realFetch(input, init).then(r=>{
    if(r.headers && r.headers.get("X-Binder-Saved") && conn.ok!==false) setConn(false);
    return r;
  }, err=>{
    const u=String(input && input.url || input);
    if(/api\//.test(u) && !/api\/health/.test(u)) checkConn();
    throw err;
  });
}
// Keep a fresh saved copy of every binder on the phone (not just the ones you open), at most every 6 hours.
function warmCache(force){
  if(!("serviceWorker" in navigator) || !navigator.serviceWorker.controller || conn.ok===false) return;
  let last=0; try{ last=+localStorage.getItem("nd-warm")||0; }catch(_){}
  if(!force && Date.now()-last < 6*3600e3) return;
  try{ localStorage.setItem("nd-warm", String(Date.now())); }catch(_){}
  const get=u=>fetch(u,{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null);
  Promise.all([get("api/home"), get("api/sets"), get("api/settings"), get("api/show")]).then(([home, sets])=>{   // api/show: card show mode works with no signal
    const ids=new Set([...((home&&home.binders)||[]).map(b=>b.id), ...((sets&&sets.sets)||[]).map(b=>b.id)]);
    let chain=Promise.resolve();
    ids.forEach(id=>{ chain=chain.then(()=>get("api/set/"+encodeURIComponent(id)+"/state")); });
  });
}
setTimeout(()=>warmCache(false), 15000);
if(standaloneApp() && navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(()=>{});   // ask Android not to clear the saved copy
setInterval(()=>{ if(!document.hidden) checkConn(); else connRow(); },30000);
setInterval(connRow,10000);
document.addEventListener("visibilitychange",()=>{ if(!document.hidden) checkConn(); });
addEventListener("online",checkConn);
addEventListener("offline",()=>setConn(false));
$("stConnBtn").onclick=()=>{ $("stConnT").textContent="Checking…"; checkConn(); };
checkConn();

// ---------- changes made offline (the phone app) ----------
// With no connection the phone can only ADD: mark a card owned and/or log what you paid and who from.
// Those wait on the phone ("nd-pending"), are shown back to you when the connection returns, and are sent
// only after you tap Sync. Each purchase gets its own id, so a repeated send never adds it twice.
const isOffline = () => conn.ok===false;
function pendingList(){ try{ const v=JSON.parse(localStorage.getItem("nd-pending")||"[]"); return Array.isArray(v)?v:[]; }catch(_){ return []; } }
function setPending(list){ try{ list.length ? localStorage.setItem("nd-pending", JSON.stringify(list)) : localStorage.removeItem("nd-pending"); }catch(_){} pendUI(); }
const newId = () => (Date.now().toString(36)+Math.random().toString(36).slice(2,10)).toLowerCase();
function offlineSave(n, patch, done){
  const old=buys(n), list=Array.isArray(patch.purchases) ? patch.purchases : null;
  const key=b=>JSON.stringify({d:b.d||"",price:b.price==null?null:b.price,where:b.where||"",seller:b.seller||null});
  let added=null;
  if(list && Object.keys(patch).length===1 && list.length===old.length+1){
    const left=old.map(key);
    for(const b of list){ const i=left.indexOf(key(b)); if(i>=0) left.splice(i,1); else if(!added) added=b; else { added=null; break; } }
    if(left.length) added=null;
  }
  if(!added){ toast("Offline: you can mark a card owned and add a purchase. Other changes wait for a connection to "+srv()+"."); done&&done(false); return; }
  const c=state.cards.find(x=>x.n===n)||{};
  const purchase={...added, id:newId()};
  const pend=pendingList();
  pend.push({sid:state.sid, n, name:c.name||n, set:state.set.name||state.sid, at:new Date().toISOString(), purchase});
  setPending(pend);
  // show it right away, as if saved
  const next={...rec(n), purchases:[...old, purchase].sort((a,b)=>(a.d||"").localeCompare(b.d||""))}; next.qty=next.purchases.length;
  state.own[n]=next; render();
  if(state.open===n && $("dlg").open){ ownLine(n); drawBuys(n); condOptions(n); $("dQty").textContent=qty(n); $("dArt").classList.toggle("need",false); }
  if(state.view==="pages") drawPages(); if(state.view==="shop") drawShop();
  done&&done(true);
  $("sync").textContent=(c.name||"Card")+" saved on this phone. It syncs when you're back online.";
  if(state.open===n && $("dSaved")) $("dSaved").textContent="Saved on this phone · syncs when you're back online";
}
// Put waiting changes back on top of the binder after it reloads (offline, the saved copy doesn't have them).
function applyPending(sid){
  for(const p of pendingList()){
    if(p.sid!==sid) continue;
    const r=state.own[p.n]||{}, l=(r.purchases||[]).filter(b=>b && typeof b==="object");
    if(l.some(b=>b.id===p.purchase.id)) continue;
    const purchases=[...l, p.purchase].sort((a,b)=>(a.d||"").localeCompare(b.d||""));
    state.own[p.n]={...r, purchases, qty:purchases.length, ...(p.cond && !r.cond ? {cond:p.cond} : {})};
  }
}
function pendWords(p){
  const b=p.purchase, bits=[];
  if(b.price!=null) bits.push("paid "+money(b.price));
  if(p.cond) bits.push(p.cond);
  if(b.where) bits.push((b.price!=null?"at ":"from ")+b.where);
  if(b.seller && b.seller.h) bits.push((PLAT[b.seller.p]||{}).label ? PLAT[b.seller.p].label+" "+b.seller.h : b.seller.h);
  return bits.length ? bits.join(" · ") : b.had ? "already had" : "no price added";
}
function pendUI(){
  const n=pendingList().length;
  try{ if(navigator.setAppBadge) (n ? navigator.setAppBadge(n) : navigator.clearAppBadge()).catch(()=>{}); }catch(_){}   // number on the app icon
  document.querySelectorAll(".pendn").forEach(e=>{ e.textContent = n ? " · "+n+" change"+(n===1?"":"s")+" waiting" : ""; });
  if($("stPendRow")){ $("stPendRow").hidden=!n; $("stPendT").textContent=n+" change"+(n===1?"":"s")+" waiting to sync"; $("stPendBtn").disabled=isOffline(); }
  const ls=state.lastSync;
  if($("stUndoRow")){ const show=!!(ls && ls.count && !ls.undone); $("stUndoRow").hidden=!show;
    if(show) $("stUndoS").textContent=ls.count+" purchase"+(ls.count===1?"":"s")+" added "+when(ls.at)+". Undo takes out exactly those."; }
}
let syncAsked=false, syncBusy=false;
// The confirm screen: what was added on the phone, in plain words, before anything is sent.
async function reviewSync(){
  let pend=pendingList(); if(!pend.length || syncBusy || isOffline()) return;
  syncBusy=true;
  try{
    // if the server has a newer binder version, load it first (the waiting changes stay on the phone)
    try{ const h=await fetch("api/health",{cache:"no-store"}).then(r=>r.json()); if(state.pageVersion && h.version && h.version!==state.pageVersion){ reloadHome(); return; } }catch(_){}
    // what the server has now, so the list can say "adds another copy" when you already own one
    const have={};
    for(const sid of [...new Set(pend.map(p=>p.sid))]){
      try{ const s=await fetch("api/set/"+enc(sid)+"/state",{cache:"no-store"}).then(r=>r.ok?r.json():null); have[sid]=(s&&s.collection)||{}; }catch(_){ have[sid]={}; }
    }
    const ul=document.createElement("ul"), dropped=new Set(); ul.className="pend-list";
    const draw=()=>{ ul.replaceChildren(); pend.forEach((p,i)=>{
      const li=document.createElement("li"), l=document.createElement("div"); l.className="pl";
      const t=document.createElement("b"); t.textContent=p.name+" · "+p.set;
      const r=(have[p.sid]||{})[p.n], got=r && Array.isArray(r.purchases) ? r.purchases.filter(b=>b&&b.id!==p.purchase.id).length : 0;
      const d=document.createElement("span"); d.textContent=(got ? "Adds another copy (you have "+got+")" : "Now owned")+" · "+pendWords(p);
      l.append(t,d);
      const x=document.createElement("button"); x.type="button"; x.className="px"; x.textContent="×"; x.title="Don't send this one"; x.setAttribute("aria-label","Remove "+p.name+" from this sync");
      x.onclick=()=>{ dropped.add(p.purchase.id); pend.splice(i,1); draw(); if(!pend.length) $("cfOk").textContent="Done"; };
      li.append(l,x); ul.append(li); }); };
    draw();
    const ok=await askConfirm("Ready to sync", pend.length+" change"+(pend.length===1?"":"s")+" made on this phone while offline. Nothing is sent until you tap Sync. Prices update on their own.", "Sync", {safe:true, body:ul});
    syncAsked=true;
    if(!ok) return;   // "Cancel": everything stays on the phone as it was
    if(!pend.length){ setPending(pendingList().filter(q=>!dropped.has(q.purchase.id))); if(state.sid) loadState(); return; }
    const r=await fetch("api/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({changes:pend.map(p=>({sid:p.sid,n:p.n,purchase:p.purchase,cond:p.cond}))})});
    const j=await r.json();
    if(!r.ok) throw new Error(j.error||"Sync failed");
    const sent=new Set(pend.map(p=>p.purchase.id));
    setPending(pendingList().filter(q=>!sent.has(q.purchase.id) && !dropped.has(q.purchase.id)));
    if(j.applied) state.lastSync={at:j.at, count:j.applied, undone:""}; pendUI();
    if(state.sid) loadState();
    if(typeof loadHome==="function" && atHome()) loadHome();
    toast("Synced "+j.applied+" change"+(j.applied===1?"":"s")+" to "+srv()+".", j.applied ? "Undo" : null, j.applied ? undoSync : null);
  }catch(e){ toast((e&&e.message&&e.message!=="Failed to fetch") ? e.message+"." : "Couldn't sync. The changes are still saved on this phone."); }
  finally{ syncBusy=false; }
}
async function undoSync(){
  const ok=await askConfirm("Undo last sync?", "Takes out the purchases that sync added. Anything you changed since stays as it is.", "Undo sync", {safe:true});
  if(!ok) return;
  try{
    const r=await fetch("api/sync/undo",{method:"POST"}); const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't undo");
    if(state.lastSync) state.lastSync.undone=new Date().toISOString(); pendUI();
    if(state.sid) loadState();
    toast("Undid the last sync ("+j.removed+" purchase"+(j.removed===1?"":"s")+" taken out).");
  }catch(e){ toast(e.message+"."); }
}
$("stPendBtn").onclick=()=>{ $("settings").close(); reviewSync(); };
$("stUndoBtn").onclick=undoSync;
document.querySelectorAll(".syncline").forEach(el=>el.addEventListener("click",()=>{ if(pendingList().length && !isOffline()) reviewSync(); }));
fetch("api/version").then(r=>r.json()).then(v=>{ state.pageVersion=v.version||""; }).catch(()=>{});
pendUI();

// ---------- install as an app ----------
// Chrome offers "Install" once the binder is opened by a secure (https) address, like its Tailscale name.
let installPrompt=null;
const standalone = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone===true;
function appRow(){
  const s=$("stAppS"), b=$("stAppBtn"); if(!s) return;
  b.hidden=true;
  if(standalone()) s.textContent="Installed: you're using the app now.";
  else if(installPrompt){ s.textContent="Adds the binder to your home screen and opens it full screen, like any app."; b.hidden=false; }
  else if(!isSecureContext) s.textContent="Open the binder by its https address (like its Tailscale name ending in .ts.net) to install it. This address ("+location.host+") isn't a secure one.";
  else s.textContent="If no Install button shows here, use Chrome's ⋮ menu → Install app (or Add to Home screen).";
}
addEventListener("beforeinstallprompt",e=>{ e.preventDefault(); installPrompt=e; appRow(); });
addEventListener("appinstalled",()=>{ installPrompt=null; appRow(); toast("Installed. Open the binder from your home screen."); });
$("stAppBtn").onclick=async()=>{ if(!installPrompt) return; installPrompt.prompt(); try{ await installPrompt.userChoice; }catch(_){} installPrompt=null; appRow(); };
if("serviceWorker" in navigator && isSecureContext) navigator.serviceWorker.register("sw.js").catch(()=>{});
appRow();

// ---------- other addresses ----------
$("stHosts").addEventListener("change",()=>{
  const v=$("stHosts").value;
  fetch("api/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({otherHosts:v})})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; }))
    .then(()=>{ $("stHostsMsg").textContent="Saved."; getSlots(); })
    .catch(e=>{ $("stHostsMsg").textContent=e.message+"."; });
});

// Long-pressing a picture on a phone shouldn't open the browser's image menu (copy, save, share).
// Computers keep the normal right-click menu.
document.addEventListener("contextmenu",e=>{
  if(matchMedia("(pointer:coarse)").matches && e.target.closest("img, canvas, svg, .face, .pk, .bk, .vb-cover, .hm-card")) e.preventDefault();
},{capture:true});

// Press and hold a card (phones) to jump straight to a price site. Settings > Phone picks which one, or Nothing.
(()=>{
  // Phones only let a page open a new tab right after a finger lifts, so holding arms it (with a short buzz)
  // and lifting the finger opens the site.
  let t=0, x0=0, y0=0, armed=null, swallow=false;
  const target=el=>{
    const f=el.closest("#grid .face"); if(f){ const b=f.closest(".sleeve"); return b && cardLinks(b.dataset.n); }
    const p=el.closest("#pgView .pk"); if(p){ if(pg.arr) return null; const n=pageLayout().slots[+p.dataset.i]; return n ? cardLinks(n) : null; }
    const r=el.closest("#fdBody button"); if(r && r._c) return findLinks(r._c);
    return null;
  };
  const stop=()=>{ clearTimeout(t); t=0; };
  document.addEventListener("pointerdown",e=>{
    stop(); armed=null; swallow=false;
    if(e.pointerType!=="touch" || lpMode()==="off" || !e.target.closest) return;
    const el=e.target; if(!target(el)) return;
    x0=e.clientX; y0=e.clientY;
    t=setTimeout(()=>{
      t=0; const k=target(el), u=k && k[lpMode()]; if(!u) return;
      armed=u; swallow=true; if(navigator.vibrate) navigator.vibrate(15);
    },500);
  },{passive:true});
  document.addEventListener("pointermove",e=>{ if(t && Math.hypot(e.clientX-x0,e.clientY-y0)>10) stop(); },{passive:true});
  const lift=()=>{ stop(); if(armed){ const u=armed; armed=null; window.open(u,"_blank","noopener"); } };
  document.addEventListener("pointerup",lift,{capture:true});
  document.addEventListener("touchend",lift,{capture:true});
  ["pointercancel","scroll"].forEach(ev=>document.addEventListener(ev,()=>{ stop(); },{passive:true,capture:true}));
  // The finger lifting after a long press would also count as a tap, so swallow that one click.
  document.addEventListener("click",e=>{ if(swallow){ swallow=false; e.preventDefault(); e.stopPropagation(); } },{capture:true});
})();

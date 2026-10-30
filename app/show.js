// Home shelf, card show mode, the seller pop-up.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- home: a shelf of your binders ----------
// The home page shows each binder as a small cover (its cover Pokémon in the set's colors), how complete it is
// (hidden by the privacy button), Find a card, and the cards you got most recently.
// The home button at the top of a binder comes back here; the phone's back button works too.
let homeShown=false;   // set right away, even while the slide animation is still running
const atHome = () => homeShown;
// Smooth screen changes (the browser's View Transitions): a short slide between My binders and a binder,
// a quick fade between tabs. Skipped when the phone asks for less motion, or the browser can't do it.
let vtReady=false;   // no animation for the very first screen
function withTransition(kind, fn){
  if(!vtReady || !document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches || document.hidden){ fn(); return; }
  const root=document.documentElement; root.dataset.vt=kind;
  try{ const t=document.startViewTransition(fn); t.finished.finally(()=>{ if(root.dataset.vt===kind) delete root.dataset.vt; }); }
  catch(_){ delete root.dataset.vt; fn(); }
}
function showHome(){
  const was=homeShown; homeShown=true;
  if(drawerEl.open) drawerEl.close();
  const swap=()=>{ closeShow(); document.body.classList.add("at-home"); $("home").hidden=false; document.title="My binders";
    if(window.scrollY) window.scrollTo(0,0);   // only when needed: on phones this flashes the scroll bar
    drawHome(); };
  was ? swap() : withTransition("back", swap);
  loadHome(); homeJob();
}
// Price check progress on the home page, same as at the top of a binder. Checks every 3 seconds while one runs,
// otherwise every 30 seconds in case the daily refresh starts while you're here.
let homeTimer=null, homeRunning=false;
function homeJob(){
  clearTimeout(homeTimer); homeTimer=null;
  if(!atHome()) return;
  fetch("api/refresh").then(r=>r.json()).then(j=>{
    if(!atHome()) return;
    if(j.running){
      homeRunning=true;
      $("hmSync").textContent="Checking "+(j.name||"prices")+": card "+Math.min(j.done+1,j.total||1)+" of "+(j.total||"…");
      setBar($("hmBar"), j.done, j.total);
    } else if(homeRunning){
      homeRunning=false; hideBar($("hmBar"));
      $("hmSync").textContent=j.message||"Prices updated"; loadHome();
      setTimeout(()=>{ if(!homeRunning) $("hmSync").textContent="Saved on "+srv(); }, 8000);
    }
    homeTimer=setTimeout(homeJob, homeRunning?3000:30000);
  }).catch(()=>{ homeTimer=setTimeout(homeJob, 30000); });
}
function showBinder(){ if(!atHome() && !atShow()) return; homeShown=false;
  withTransition("forward", ()=>{ closeShow(); document.body.classList.remove("at-home"); $("home").hidden=true; if(window.scrollY) window.scrollTo(0,0); if(state.sid) header(); }); }
function goHome(){ if(location.hash) history.pushState(null,"",location.pathname+location.search); showHome(); }

// ---------- card show mode ----------
// One list of every card you still need from the binders you're working on, with a big "Got it" to log a buy.
// Works with no signal: the list comes from the saved copy, and buys wait on the phone like other offline changes.
const atShow = () => document.body.classList.contains("at-show");
let showData=null, showSort=["cheap","dear","set","page"].includes(recall("nd-show-sort")) ? recall("nd-show-sort") : "cheap", showLimit=150;
// Where a needed card sits in its binder's pages: the exact order this device last showed for that binder
// (saved when a binder opens or its pages change), else the server's saved layout.
function rememberSlots(){ try{ if(!state.sid) return; const L=pageLayout(); store("nd-slots-"+state.sid, JSON.stringify({pk:L.pk, s:L.slots})); }catch(_){} }
function pagePos(c){
  let saved=null; try{ saved=JSON.parse(recall("nd-slots-"+c.sid)||"null"); }catch(_){}
  const i=saved && Array.isArray(saved.s) ? saved.s.indexOf(c.n) : -1;
  if(i>=0) return {i, pk:saved.pk||9};
  const b=(showData.binders||[]).find(x=>x.id===c.sid);
  return {i:c.slot||0, pk:(b&&b.pk)||9};
}
function openShow(push=true){
  if(push && location.hash!=="#show") history.pushState(null,"","#show");
  if(drawerEl.open) drawerEl.close();
  if($("shows").open) $("shows").close();
  homeShown=false;
  document.body.classList.remove("at-home"); $("home").hidden=true;
  document.body.classList.add("at-show"); $("showView").hidden=false; document.title="Card show";
  if(window.scrollY) window.scrollTo(0,0);
  showLimit=150; drawShowView(); loadShow();
}
function closeShow(){ if(!atShow()) return; document.body.classList.remove("at-show"); $("showView").hidden=true; }
function loadShow(){
  return fetch("api/show").then(r=>r.ok?r.json():Promise.reject()).then(j=>{ showData=j; if(atShow()) drawShowView(); })
    .catch(()=>{ if(atShow() && !showData) drawShowView("Can't load the list. Open card show mode once while connected so it's saved on this phone."); });
}
const showBoughtLocal = () => pendingList().filter(p=>p.purchase && p.purchase.d===todayStr());
function showCards(){
  if(!showData) return [];
  const pend=new Set(pendingList().map(p=>p.sid+"|"+p.n));
  return showData.cards.filter(c=>!pend.has(c.sid+"|"+c.n) && !c.gone);
}
function showStale(c){
  if(!c.price) return "";
  if(c.src==="tcgdex") return "market price";
  if((c.src==="tcgplayer"||c.src==="pricecharting") && c.last){
    const d=(new Date(todayStr())-new Date(c.last.slice(0,10)+"T00:00:00"))/864e5;
    if(d>STALE_DAYS) return "last sold "+new Date(c.last.slice(0,10)+"T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
  }
  return "";
}
const showNum = c => c.pt && /^\d+$/.test(c.num||"") ? c.num+"/"+c.pt : (c.num||c.n);
function showThumb(c, box){   // the card number shows until (or unless) the picture loads over it
  box.replaceChildren(); const t=document.createElement("span"); t.textContent=showNum(c); box.append(t);
  if(c.custom) return;
  const im=document.createElement("img"); im.alt=""; im.loading="lazy"; im.decoding="async";
  im.onerror=()=>im.remove(); box.append(im);   // in the page right away: a lazy picture outside the page never loads
  im.src="set/"+enc(c.sid)+"/img/"+enc(c.n)+".png";
}
function zoomCard(c){   // the same full-screen picture as in card details
  if(c.custom) return;
  $("zoomImg").src="set/"+enc(c.sid)+"/img/"+enc(c.n)+".png?full=1"; $("zoomImg").alt=c.name; zoomFoil(c, c.sid); $("zoom").showModal();
}
function drawShowView(err){
  const list=$("swList"); list.replaceChildren();
  $("swSort").querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed", b.dataset.s===showSort || (b.dataset.s==="price" && /^(cheap|dear)$/.test(showSort))));
  $("swPriceBtn").textContent="Price "+(showSort==="dear"?"↓":"↑");
  $("swPriceBtn").setAttribute("aria-label", showSort==="dear" ? "Price, highest first. Tap for lowest first" : "Price, lowest first. Tap for highest first");
  if(!showData){
    const e=document.createElement("div"); e.className="sw-empty"; e.textContent=err||"Loading your needed cards…"; list.append(e);
    return;
  }
  const picked=showData.picked||[];
  const chips=$("swChips"); chips.replaceChildren();
  if(picked.length) for(const b of showData.binders){ const sp=document.createElement("span"); sp.textContent=b.name; chips.append(sp); }
  else { const sp=document.createElement("span"); sp.className="all"; sp.textContent="All binders"; chips.append(sp); }
  const ch=document.createElement("button"); ch.type="button"; ch.className="sw-change"; ch.textContent="Change"; ch.setAttribute("aria-label","Change which binders you're working on"); ch.onclick=openPick; chips.append(ch);
  let cards=showCards();
  $("swNeed").textContent=cards.length;
  $("swFin").textContent=money0(cards.reduce((a,c)=>a+(c.price||0),0));
  const loc=showBoughtLocal(), n=(showData.bought||0)+loc.length, spent=(showData.spent||0)+loc.reduce((a,p)=>a+(Number(p.purchase.price)||0),0);
  $("swSpent").textContent=money0(spent); $("swSpentL").textContent="Bought today"+(n?" · "+n:"");
  const q=$("swQ").value.trim().toLowerCase();
  if(q){
    const numQ=/^#?\d+[a-z]?(\/\d*)?$/i.test(q) ? normNum(q.replace(/^#/,"").split("/")[0]) : null;
    cards=cards.filter(c=> numQ!=null ? normNum(String(c.num||c.n).toLowerCase())===numQ : (c.name||"").toLowerCase().includes(q));
  }
  const byNum=(a,b)=>(parseInt(a.num,10)||0)-(parseInt(b.num,10)||0) || String(a.n).localeCompare(String(b.n));
  if(showSort==="dear") cards.sort((a,b)=>(b.price||0)-(a.price||0));
  else if(showSort==="page"){ const ord=showData.binders.map(b=>b.id); cards.forEach(c=>c._pos=pagePos(c)); cards.sort((a,b)=>ord.indexOf(a.sid)-ord.indexOf(b.sid) || a._pos.i-b._pos.i); }
  else if(showSort==="set"){ const ord=showData.binders.map(b=>b.id); cards.sort((a,b)=>ord.indexOf(a.sid)-ord.indexOf(b.sid) || byNum(a,b)); }
  else cards.sort((a,b)=>(a.price||1e9)-(b.price||1e9));
  if(!cards.length){
    const e=document.createElement("div"); e.className="sw-empty";
    e.textContent=q ? "No needed card matches that." : "Nothing left to buy in these binders. Nice!";
    list.append(e);
  }
  let anyStale=false;
  // By page / By binder: a heading over each page side (or binder) with how many cards are left there and what they cost
  const multi=showData.binders.length>1;
  const grpKey=c=> showSort==="page" ? c.sid+"|"+Math.floor(c._pos.i/c._pos.pk) : showSort==="set" ? c.sid : "";
  const grpName=c=> showSort==="page" ? (multi ? c.set+" · " : "")+sideName(Math.floor(c._pos.i/c._pos.pk)) : c.set;
  const grpTotals={}; if(showSort==="page"||showSort==="set") for(const c of cards){ const k=grpKey(c), t=grpTotals[k]||(grpTotals[k]={n:0,v:0}); t.n++; t.v+=c.price||0; }
  let lastGrp=null;
  for(const c of cards.slice(0, showLimit)){
    const k=grpKey(c);
    if(k && k!==lastGrp){
      lastGrp=k; const t=grpTotals[k];
      const h=document.createElement("div"); h.className="sw-grp";
      const hb=document.createElement("b"); hb.textContent=grpName(c);
      const hs=document.createElement("span"); hs.textContent=t.n+" left · "+money0(t.v);
      h.append(hb,hs); list.append(h);
    }
    const row=document.createElement("div"); row.className="sw-row";
    const th=document.createElement("button"); th.type="button"; th.className="th"; showThumb(c, th);
    th.setAttribute("aria-label","Show "+c.name+" bigger"); th.onclick=()=>zoomCard(c);
    const tx=document.createElement("div"); tx.className="tx";
    const b=document.createElement("b"); b.textContent=c.name;
    const sm=document.createElement("small"); sm.textContent=(showSort==="set"||(showSort==="page"&&!multi) ? "" : c.set+" · ")+showNum(c);
    const pr=document.createElement("span"); pr.className="price"; pr.textContent=c.price ? money(c.price) : "No price yet";
    const st=showStale(c); if(st){ const i=document.createElement("i"); i.textContent=st; pr.append(staleEl(st[0].toUpperCase()+st.slice(1)), i); anyStale=true; }
    tx.append(b,sm,pr); tx.onclick=()=>zoomCard(c);
    const got=document.createElement("button"); got.type="button"; got.className="btn primary got"; got.textContent="Got it";
    got.setAttribute("aria-label","Got "+c.name+", log what you paid");
    got.onclick=()=>openBuy(c);
    row.append(th,tx,got); list.append(row);
  }
  if(cards.length>showLimit){
    const more=document.createElement("button"); more.type="button"; more.className="btn sw-more"; more.textContent="Show "+Math.min(150,cards.length-showLimit)+" more";
    more.onclick=()=>{ showLimit+=150; drawShowView(); }; list.append(more);
  }
  $("swStaleKey").hidden=!anyStale;
  if(anyStale && !$("swStaleKey").firstElementChild.firstChild) $("swStaleKey").firstElementChild.innerHTML=STALE_SVG;
}
$("swSort").onclick=e=>{ const b=e.target.closest("button"); if(!b) return;
  showSort = b.dataset.s!=="price" ? b.dataset.s : showSort==="cheap" ? "dear" : "cheap";   // Price flips between lowest and highest first
  store("nd-show-sort",showSort); drawShowView(); };
$("swQ").oninput=()=>{ showLimit=150; drawShowView(); };
$("swBack").onclick=()=>{ showAdd(false); drawSets(); openDrawer(); loadSets().then(drawSets); };
$("drMode").onclick=e=>{ const b=e.target.closest("button"); if(!b) return;
  if(b.dataset.m==="show"){ if(atShow()) drawerEl.close(); else openShow(); }
  else { if(atShow()) goHome(); else drawerEl.close(); } };

// the buy sheet
let buyCard=null, buyCond="", buySeller=null;
const todayKey = k => { try{ const v=JSON.parse(localStorage.getItem(k)||"null"); return v && v.d===todayStr() ? v.v : null; }catch(_){ return null; } };
const setTodayKey = (k,v) => store(k, JSON.stringify({d:todayStr(), v}));
function sellerLabel(sel){ const P=PLAT[sel.p]; return (P ? P.label+" " : "")+(sel.p==="web" ? sel.h.replace(/^https?:\/\/(www\.)?/i,"").slice(0,32) : (["instagram","tiktok","x","venmo","linktree","beacons","stan"].includes(sel.p)?"@":sel.p==="cashapp"?"$":"")+sel.h); }
// What a vendor's QR code points to, as a seller: Venmo, Cash App, PayPal, social pages, or any website.
function parseVendorQr(text){
  const t=(text||"").trim(); if(!t) return null;
  let u=null; try{ u=new URL(/^[a-z][a-z0-9+.-]*:/i.test(t) ? t : "https://"+t); }catch(_){}
  if(!u || !/^https?:$/.test(u.protocol) || !/\./.test(u.hostname)) return {p:"shop", h:t.slice(0,100)};
  const host=u.hostname.replace(/^(www\.|m\.)/,"").toLowerCase(), seg=u.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const pick=(p,h)=>h ? {p, h:String(h).replace(/^[@$]+/,"").slice(0,100)} : {p:"web", h:u.href.slice(0,100)};
  if(host==="venmo.com") return seg[0]==="u" ? pick("venmo",seg[1]) : (seg[0] && !["code","pay","account"].includes(seg[0]) ? pick("venmo",seg[0]) : pick("web",""));
  if(host==="cash.app"||host==="cash.me") return pick("cashapp", (seg[0]||"").startsWith("$") ? seg[0] : "");
  if(host==="paypal.me") return pick("paypal", seg[0]);
  if(host==="paypal.com" && seg[0]==="paypalme") return pick("paypal", seg[1]);
  if(host==="instagram.com") return pick("instagram", seg[0]);
  if(host==="tiktok.com") return pick("tiktok", (seg[0]||"").startsWith("@") ? seg[0] : "");
  if(host==="facebook.com") return pick("facebook", seg[0]);
  if(host==="x.com"||host==="twitter.com") return pick("x", seg[0]);
  if(host==="whatnot.com" && seg[0]==="user") return pick("whatnot", seg[1]);
  if(host==="ebay.com" && seg[0]==="usr") return pick("ebay", seg[1]);
  if(host==="linktr.ee"||host==="linktree.com") return pick("linktree", seg[0]);
  if(host==="beacons.ai"||host==="beacons.page") return pick("beacons", seg[0]);
  if(host==="stan.store") return pick("stan", seg[0]);
  return pick("web","");
}
const SELLER_PLATS=["instagram","linktree","tiktok","facebook","x","whatnot","ebay","venmo","cashapp","paypal","beacons","stan","web","shop"];
// ---------- seller pop-up (card show mode and card details) ----------
// A search box over everyone you've bought from (most recent first), Scan vendor QR, and "Add as a new seller".
let slCb=null, slList=[], slCur=null;
function openSellerPicker(list, cur, cb){
  slList=list||[]; slCur=cur; slCb=cb;
  $("slQ").value=""; $("slMsg").textContent=""; drawSl(); $("selDlg").showModal(); drawPlatChips();
}
function slDone(sel){ $("selDlg").close(); const cb=slCb; slCb=null; if(cb) cb(sel); }
const sameSeller=(a,b)=>a && b && a.p===b.p && a.h.toLowerCase()===b.h.toLowerCase();
function slTyped(){   // what's in the search box, as a seller (a pasted link picks its own site)
  const q=$("slQ").value.trim(); if(!q) return null;
  if(/^https?:\/\/|\.(com|me|app|net|org|tv|ee|ai|store|page)\//i.test(q)){ const x=parseVendorQr(q); if(x && x.p!=="shop") return x; }
  const p=$("slPlat").value; return {p, h:cleanHandle(p,q).slice(0,100)};
}
function drawSl(){
  const q=$("slQ").value.trim(), ql=q.replace(/^[@$]+/,"").toLowerCase();
  const rows=ql ? slList.filter(x=>x.h.toLowerCase().includes(ql) || sellerLabel(x).toLowerCase().includes(ql)) : slList;
  $("slH").textContent=ql ? (rows.length ? "Sellers you've bought from" : "No past seller matches") : (slList.length ? "Recent" : "No past sellers yet");
  const box=$("slList"); box.replaceChildren(); box.hidden=!rows.length;
  for(const x of rows.slice(0,60)){
    const b=document.createElement("button"); b.type="button"; b.className="ui-row";
    const l=document.createElement("span"); l.className="ui-l"; const t=document.createElement("b"); t.textContent=sellerLabel(x);
    const m=document.createElement("small"); m.textContent=[x.n ? x.n+" buy"+(x.n===1?"":"s") : "Added today", x.last ? "last "+fmtDay(x.last) : ""].filter(Boolean).join(" · ");
    l.append(t,m); b.append(l);
    if(sameSeller(x,slCur)) b.setAttribute("aria-current","true");
    b.onclick=()=>slDone({p:x.p, h:x.h}); box.append(b);
  }
  // a new seller: shown when what you typed isn't already on the list
  const typed=slTyped(), isNew=!!(typed && typed.h && !slList.some(x=>sameSeller(x,typed)));
  $("slNew").hidden=!isNew;
  if(isNew){
    if($("slPlat").value!==typed.p && [...$("slPlat").options].some(o=>o.value===typed.p)){ $("slPlat").value=typed.p; drawPlatChips(); }
    $("slNewT").textContent="Add “"+sellerLabel(typed)+"” as a new seller";
    const P=PLAT[typed.p], href=P && P.url ? P.url(typed.h) : null;
    $("slNewLink").textContent=href ? "Links to "+href.replace(/^https?:\/\/(www\.)?/,"") : "";
  }
  $("slNone").hidden=!slCur;
}
for(const k of SELLER_PLATS){ const o=document.createElement("option"); o.value=k; o.textContent=PLAT[k].label; $("slPlat").append(o); }
$("slPlat").value=recall("nd-sel-plat")||"instagram";
// the site chips under the search box: pick where they sell before (or after) typing their name
function drawPlatChips(){
  const box=$("slPlats"), cur=$("slPlat").value;
  if(!box.childElementCount) for(const k of SELLER_PLATS){ const b=document.createElement("button"); b.type="button"; b.className="h-chip"; b.dataset.p=k; b.textContent=PLAT[k].label;
    b.onclick=()=>{ $("slPlat").value=k; store("nd-sel-plat",k); drawPlatChips(); drawSl(); $("slQ").focus(); }; box.append(b); }
  let on=null; for(const b of box.children){ const p=b.dataset.p===cur; b.setAttribute("aria-pressed", String(p)); if(p) on=b; }
  if(on){ const l=on.offsetLeft-box.offsetLeft; if(l<box.scrollLeft || l+on.offsetWidth>box.scrollLeft+box.clientWidth) box.scrollLeft=l-16; }
  $("slQ").placeholder="Search, or type their "+PLAT[cur].label+" name";
}
drawPlatChips();
$("slQ").oninput=drawSl;
$("slPlat").onchange=()=>{ store("nd-sel-plat",$("slPlat").value); drawSl(); };
$("slUse").onclick=()=>{ const x=slTyped(); if(x && x.h){ store("nd-sel-plat",x.p); slDone(x); } };
$("slQ").addEventListener("keydown",e=>{ if(e.key==="Enter" && !$("slNew").hidden){ e.preventDefault(); $("slUse").click(); } });
$("slNone").onclick=()=>slDone(null);
$("slClose").onclick=()=>$("selDlg").close();
$("selDlg").addEventListener("click",e=>{ if(e.target===$("selDlg")) $("selDlg").close(); });
$("slScan").onclick=()=>$("slQr").click();
$("slQr").onchange=async e=>{
  const f=e.target.files && e.target.files[0]; e.target.value=""; if(!f) return;
  const msg=$("slMsg");
  if(!("BarcodeDetector" in window)){ msg.textContent="This browser can't read QR codes. Chrome on Android can. Type their name instead."; return; }
  msg.textContent="Reading the code…";
  try{
    const img=await createImageBitmap(f);
    const codes=await new BarcodeDetector({formats:["qr_code"]}).detect(img);
    const sel=codes.length ? parseVendorQr(codes[0].rawValue) : null;
    if(!sel){ msg.textContent="No QR code found in that photo. Try again a little closer."; return; }
    slDone(sel);
  }catch(_){ msg.textContent="Couldn't read that photo. Try again, or type their name."; }
};

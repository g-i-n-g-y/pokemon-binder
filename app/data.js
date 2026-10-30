// Loading binder data, loading bars, price refresh, privacy mode, switching views.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- data ----------
function loadSets(){
  return fetch("api/sets").then(r=>r.json()).then(j=>{ state.sets=j.sets||[]; state.removed=j.removed||[]; state.keepDays=j.keepDays||30; }).catch(()=>{});
}
let loadSeq=0;
function openSet(sid){
  const fromHome=typeof atHome==="function" && atHome();
  if(sid && fromHome) showBinder();
  state.sid=sid; store("nd-set",sid||undefined);
  if(sid && location.hash!=="#"+sid) history[fromHome ? "pushState" : "replaceState"](null,"","#"+sid);   // from home: back returns home
  state.cards=[]; state.own={}; state.prices={}; state.info={}; state.updated=""; state.ready=false; state.layout=null; dexNumsFor=null;
  if(typeof pg!=="undefined"){ pg.at=-1; pg.sel=-1; pg.arr=false; } state.trends={}; state.histFirst=""; state.seriesCache={};
  if(sid && state.view!=="cards") setView("cards");   // a binder always opens on its Cards tab
  if(!sid){ state.set={name:"Pokémon Binder"}; header(); rarityOptions(); render(); $("sync").textContent="Open the menu to add your first set."; return Promise.resolve(); }
  state.set=(state.sets.find(s=>s.id===sid))||{name:sid}; header(); render();
  return loadState();
}
function loadState(){
  const sid=state.sid, seq=++loadSeq;
  state.loadErr="";
  return fetch("api/set/"+enc(sid)+"/state").then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't load"); return j; })).then(s=>{
    if(seq!==loadSeq) return;
    (s.cards||[]).forEach((c,i)=>{ if(c.extra) c.k=i; });
    state.set=s.set||state.set; state.cards=(s.cards||[]).slice().sort(byNum);
    state.layout=s.layout||null; dexNumsFor=null;
    state.own=s.collection||{};
    applyPending(sid);
    const pr=s.prices||{}; state.prices={}; for(const k in (pr.p||{})) state.prices[k]=[pr.p[k][0]];
    state.info=pr.info||{}; state.updated=pr.updated||"";
    state.slots=s.slots||DEFAULT_SLOTS;
    state.shop=s.shop||{};
    state.ready=true; header(); rarityOptions(); render(); renderView(); rememberSlots();
    fetch("api/set/"+enc(sid)+"/trends?today="+todayStr()).then(r=>r.json()).then(h=>{ if(seq!==loadSeq) return; state.trends=h.cards||{}; state.histFirst=h.first||""; state.seriesCache={}; render(); renderView(); }).catch(()=>{});
    if(!wasRunning){ $("sync").textContent="Saved on "+srv()+" · prices checked every night"; hideBar($("syncBar")); watchImages(); }
  }).catch(err=>{ if(seq===loadSeq){ state.ready=false; state.loadErr=(err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Can't reach "+srv()+". "+offlineHint(); render(); $("sync").textContent=(err&&err.message&&err.message!=="Failed to fetch" ? err.message : "Can't reach "+srv())+"."; } });
}

// ---------- loading bars ----------
function setBar(el, done, total){
  el.hidden=false; const i=el.firstElementChild;
  if(total>0){ const pct=Math.max(2,Math.min(100,done/total*100)); el.classList.remove("wait"); i.style.width=pct.toFixed(1)+"%"; el.setAttribute("aria-valuenow",Math.round(pct)); }
  else { el.classList.add("wait"); i.style.width=""; el.removeAttribute("aria-valuenow"); }
}
const hideBar = el => { el.hidden=true; el.classList.remove("wait"); el.firstElementChild.style.width="0"; };

// Card images download in the background after a set is added; show how far along it is.
let imgTimer=null, imgWatching=null;
function watchImages(){
  clearTimeout(imgTimer); const sid=state.sid; if(!sid) return;
  fetch("api/progress").then(r=>r.json()).then(p=>{
    if(sid!==state.sid) return;
    const im=(p.images||{})[sid];
    if(im){
      imgWatching=sid;
      if(!wasRunning){ $("sync").textContent="Downloading card pictures: "+(im.total ? Math.min(im.done+1,im.total)+" of "+im.total : "starting…"); setBar($("syncBar"), im.done, im.total); }
      imgTimer=setTimeout(watchImages,2500);
    } else if(imgWatching===sid){
      imgWatching=null; render();
      if(!wasRunning){ hideBar($("syncBar")); $("sync").textContent="Card pictures downloaded"; }
    }
  }).catch(()=>{});
}

// ---------- price refresh ----------
let wasRunning=false, pollTimer=null;
function showJob(j){
  if(j.running){
    wasRunning=true;
    $("refresh").disabled=true; $("refreshLbl").textContent="Refreshing…"; $("refresh").classList.add("busy");
    $("sync").textContent="Checking "+(j.name||"prices")+": card "+Math.min(j.done+1,j.total||1)+" of "+(j.total||"…");
    setBar($("syncBar"), j.done, j.total);
    if(!pollTimer) pollTimer=setTimeout(poll,3000);
  } else {
    $("refresh").disabled=false; $("refreshLbl").textContent="Refresh prices"; $("refresh").classList.remove("busy");
    if(wasRunning){ wasRunning=false; hideBar($("syncBar")); loadState().then(()=>{ $("sync").textContent=j.message||"Prices updated"; watchImages(); }); }
  }
}
function poll(){ pollTimer=null; fetch("api/refresh").then(r=>r.json()).then(showJob).catch(()=>{ pollTimer=setTimeout(poll,10000); }); }
$("refresh").onclick=async()=>{
  if(!state.sid) return;
  const name=state.set.name||"this binder", n=state.cards.length;
  const last=state.updated ? "Prices were last updated "+when(state.updated)+". " : "";
  const ok=await askConfirm("Refresh "+name+" prices?", last+"This checks recent sales for all "+n+" cards and takes about "+Math.max(1,Math.round(n*1.1/60))+" minute"+(Math.round(n*1.1/60)>1?"s":"")+". Prices also refresh by themselves once a day.", "Refresh", {safe:true});
  if(!ok) return;
  $("refresh").disabled=true;
  fetch("api/refresh",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({set:state.sid})}).then(r=>r.json()).then(showJob)
    .catch(()=>{ $("refresh").disabled=false; $("sync").textContent="Couldn't start a price check."; toast("Couldn't start the price check. "+offlineHint(), "Try again", ()=>$("refresh").click()); });
};

// ---------- privacy mode ----------
function setPrivate(on){
  if(on) document.documentElement.setAttribute("data-private",""); else document.documentElement.removeAttribute("data-private");
  store("nd-private", on?"on":undefined);
  $("privBtn").setAttribute("aria-pressed", on); $("stPriv").checked=on;
  for(const id of ["hmPriv","swPriv"]) if($(id)) $(id).setAttribute("aria-pressed", on);
  $("privBtn").title = on ? "Privacy mode is on. Tap to show your collection" : "Privacy mode: hide what you own and spent";
  if(on){
    if(PRIVATE_HIDES.includes(state.view)) setView("cards");
    if(state.filter!=="all"){ state.filter="all"; [...$("fOwn").children].forEach(x=>x.setAttribute("aria-pressed",x.dataset.v==="all")); }
  }
  render(); if(state.view==="pages") drawPages();
}
$("privBtn").onclick=()=>setPrivate(!isPrivate());
$("stPriv").onchange=e=>setPrivate(e.target.checked);

// ---------- views ----------
const PRIVATE_HIDES=["shop","upg","stats"];   // privacy mode keeps Cards and Pages (all in color, no prices or owned counts)
function setView(v){
  if(isPrivate() && PRIVATE_HIDES.includes(v)) v="cards";
  state.view=v; store("nd-view",v); $("binderMain").dataset.view=v;
  [...$("views").children].forEach(b=>b.setAttribute("aria-pressed",b.dataset.v===v));
  $("vCards").hidden=v!=="cards"; $("vPages").hidden=v!=="pages"; $("vShop").hidden=v!=="shop"; $("vUpg").hidden=v!=="upg"; $("vStats").hidden=v!=="stats";
  renderView();
}
// "How it works": a link at the bottom of each binder tab opens help for that tab first, then the general tips.
const HOW={
  cards:["Cards","Every card in the set: in color if you own it, grey if you still need it. Tap Need on a card to mark it owned. Tap the card itself to log what you paid, its condition, notes and photos. Use All, Owned and Need, the rarity list and the sort to narrow it down."],
  pages:["Pages","Lays the binder out like a real one. Pick 4, 9, 12 or 16 pockets a page and the order cards go in. Arrange lets you move cards: tap a card, then tap where it should go. All in color shows every card in color, owned or not."],
  shop:["Shopping list","The cards you still need. The running total shows what it costs to buy every card down to that row, and a budget highlights the rows it covers. Got it marks a card owned with today's date. Pick My order and drag the ⠿ handle to sort cards your own way."],
  upg:["Upgrades","Cards you own in a worn condition, and what a better copy costs now. Pick which conditions to upgrade from and the condition to upgrade to. Cards without a condition aren't listed: set it on a card's My copy tab."],
  stats:["Stats","What you've spent and what your cards are worth, across all your binders, with spending per month and every purchase you've logged. Biggest movers shows this binder's cards whose price changed the most."]
};
function openHow(){
  const [name,text]=HOW[state.view]||HOW.cards, B=$("howBody"); B.replaceChildren();
  const sec=(t,p)=>{ const h=document.createElement("h3"); h.textContent=t; const q=document.createElement("p"); q.textContent=p; B.append(h,q); };
  sec(name, text);
  sec("Everywhere", "Prices are averages of recent Unlimited sales (pick which ones per binder in Settings) and are checked automatically every night. Tap the home button at the top left to switch binders or add a new one. Everything saves on "+srv()+".");
  $("howDlg").showModal();
}
$("howBtn").onclick=openHow;
$("howClose").onclick=$("howDone").onclick=()=>$("howDlg").close();
$("howDlg").addEventListener("click",e=>{ if(e.target===$("howDlg")) $("howDlg").close(); });   // tap outside the window closes it
function renderView(){ if(state.view==="pages") drawPages(); else if(state.view==="shop") drawShop(); else if(state.view==="upg") drawUpg(); else if(state.view==="stats") loadStats(); }
$("views").addEventListener("click",e=>{ const b=e.target.closest("button"); if(b && b.dataset.v!==state.view) withTransition("fade", ()=>setView(b.dataset.v)); });

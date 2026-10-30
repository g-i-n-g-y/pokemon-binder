// The binder: header totals, the card grid, phone filters, custom cards.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- header + stats ----------
function header(){
  const s=state.set, name=s.name||"";
  const t=$("setTitle"); t.replaceChildren();
  const dex=isDex(state.sid), own=isOwn(state.sid), sp=$("sprite");
  sp.hidden=!dex; if(dex){ sp.src=base()+"/sprite.png"; sp.alt=name+" sprite"; sp.onerror=()=>{ sp.hidden=true; }; } else sp.removeAttribute("src");
  const parts=dex||own ? [name] : name.split(" "); const a=document.createElement("span"); a.className="l"; a.textContent=parts[0]||"";
  const b=document.createElement("span"); b.className="d"; b.textContent=parts.length>1 ? " "+parts.slice(1).join(" ") : "";
  t.append(a,b);
  const secret=state.cards.filter(isSecret).length;
  $("eyebrow").textContent=own
    ? ["My binder", "Unlimited", state.cards.filter(c=>!c.custom).length+" card"+(state.cards.filter(c=>!c.custom).length===1?"":"s")].join(" · ")
    : dex
    ? ["Master set", "#"+String(s.dex||state.sid.slice(4)).padStart(4,"0"), "all sets", "Unlimited", state.cards.filter(c=>!c.custom).length+" cards"].join(" · ")
    : [s.series, year(s.releaseDate), "Unlimited", (printed()||state.cards.length)+" cards"+(secret?" + "+secret+" secret":"")].filter(Boolean).join(" · ");
  const nCustom=state.cards.filter(c=>c.custom).length;
  if(nCustom){ $("eyebrow").append(" · "); $("eyebrow").append(customBadge(nCustom)); }
  gapNote(dex);
  $("fSort").options[0].textContent=dex ? "Sort: release date" : own ? "Sort: order added" : "Sort: set number";
  $("fQ").placeholder=matchMedia("(max-width:640px)").matches ? (own ? "Search name, set or number" : dex ? "Search set or number" : "Search name or number")
    : (own ? "Search name, set or number (80/111)" : dex ? "Search set or number (80/111)" : "Search name or number (1/105)");
  document.title=(name ? name+" · " : "")+"Pokémon Binder";
  fitTitle();
}
// Phones: long set names (like "Neo Revelation") shrink to fit beside the buttons, down to 18px,
// and only then wrap onto a second line instead of being cut off with "…".
function fitTitle(){
  const t=$("setTitle"); t.style.fontSize=""; t.classList.remove("two");
  if(!matchMedia("(max-width:640px)").matches || !t.textContent) return;
  let fs=parseFloat(getComputedStyle(t).fontSize)||22;
  while(t.scrollWidth>t.clientWidth+1 && fs>18){ fs-=1; t.style.fontSize=fs+"px"; }
  if(t.scrollWidth<=t.clientWidth+1) return;
  // still too long: two lines, a little bigger again, shrinking only if one word is too wide
  t.classList.add("two"); fs=20; t.style.fontSize=fs+"px";
  while((t.scrollWidth>t.clientWidth+1 || t.scrollHeight>t.clientHeight+2) && fs>14){ fs-=1; t.style.fontSize=fs+"px"; }
}
addEventListener("resize",()=>{ clearTimeout(fitTitle.t); fitTitle.t=setTimeout(fitTitle,120); });
try{ document.fonts.ready.then(()=>fitTitle()); }catch(_){}
// Flags binders whose card list may be incomplete. Set binders: numbers 1 to the printed
// total that the card database doesn't have. Master sets: always, since the database skips
// some promos, trainer kit and McDonald's cards.
function gapNote(dex){
  const el=$("gapNote"), eb=$("eyebrow");
  let msg="";
  if(dex && state.cards.length){
    msg="Some promo and trainer kit cards may be missing. Add them with Missing a card? at the end of the list.";
  } else if(!dex && printed() && state.cards.length){
    const have=new Set(state.cards.map(c=>numVal(c.n)).filter(n=>!n[0]).map(n=>n[1]));
    const miss=[]; for(let i=1;i<=printed();i++) if(!have.has(i)) miss.push(i);
    if(miss.length) msg="Card list may be incomplete: the card database is missing "+(miss.length===1?"card ":miss.length+" cards (")
      +miss.slice(0,8).map(i=>"#"+String(i).padStart(3,"0")).join(", ")+(miss.length>8?", …":"")+(miss.length===1?"":")")+" of "+printed()+".";
  }
  el.hidden=!msg; el.replaceChildren();
  if(msg){ const b=document.createElement("b"); b.textContent="* "; el.append(b, msg); eb.insertBefore(document.createTextNode(" *"), eb.querySelector(".cbadge") ? eb.lastChild.previousSibling : null); }
}
function stats(){
  let owned=0, value=0, paid=0, need=0, needN=0, full=0;
  for(const c of state.cards){
    const p=basePrice(c.n); full+=p;
    paid+=paidFor(c.n);
    if(qty(c.n)>0){ owned++; value+=priceOf(c.n)*qty(c.n); }
    else { need+=p; needN++; }
  }
  const total=state.cards.length||1;
  $("sOwned").textContent=owned+" / "+state.cards.length;
  $("sBar").style.width=(owned/total*100).toFixed(1)+"%";
  $("sPct").textContent=(owned/total*100).toFixed(0)+"%";
  $("sValue").textContent=money0(value);
  if(paid>0){ const g=value-paid; $("sGain").replaceChildren(); const s=document.createElement("span"); s.className=g>=0?"pos":"neg"; s.textContent=(g>=0?"+":"−")+money0(Math.abs(g)); $("sGain").append(s," vs. "+money0(paid)+" paid"); }
  else $("sGain").textContent="Add what you paid to see gain or loss";
  $("sNeed").textContent=money0(need);
  $("sNeedN").textContent=needN+" cards to go";
  $("sFull").textContent=money0(full);
  $("sUpd").textContent=state.updated ? "Prices as of "+when(state.updated) : "Prices load after the first price check";
}

// ---------- grid ----------
function rarityOptions(){
  const sel=$("fRar"); sel.replaceChildren(); const o=document.createElement("option"); o.value=""; o.textContent=isMulti(state.sid) ? "All sets" : "All rarities"; sel.append(o);
  sel.setAttribute("aria-label", isMulti(state.sid) ? "Set" : "Rarity");
  [...new Set(state.cards.map(cat))].forEach(r=>{ const x=document.createElement("option"); x.value=r; x.textContent=r; sel.append(x); });
  sel.value=""; state.rar="";
}
function render(){
  let list=state.cards.filter(c=>{
    if(state.filter==="own" && qty(c.n)===0) return false;
    if(state.filter==="need" && qty(c.n)>0) return false;
    if(state.rar && cat(c)!==state.rar) return false;
    if(state.q && !matchQ(c, state.q)) return false;
    return true;
  });
  if(state.sort==="hi") list.sort((a,b)=>priceOf(b.n)-priceOf(a.n));
  if(state.sort==="lo") list.sort((a,b)=>priceOf(a.n)-priceOf(b.n));
  if(state.sort==="gain"||state.sort==="drop"){   // cards without a change go last
    const pc=new Map(list.map(c=>{ const t=trend(c.n); return [c.n, t ? t.pct : null]; }));
    const dir=state.sort==="gain"?-1:1;
    list.sort((a,b)=>{ const x=pc.get(a.n), y=pc.get(b.n); if(x==null&&y==null) return 0; if(x==null) return 1; if(y==null) return -1; return dir*(x-y); });
  }
  const g=$("grid"); g.replaceChildren();
  g.removeAttribute("aria-busy");
  if(!list.length && !state.ready && state.sid && state.loadErr){ g.append(retryNote("Couldn't open this binder. "+state.loadErr, ()=>{ state.loadErr=""; render(); loadState(); })); }
  else if(!list.length && !state.ready && state.sid){   // still loading: grey card outlines where the cards will be
    g.setAttribute("aria-busy","true");
    const sr=document.createElement("p"); sr.className="sr-only"; sr.textContent="Loading cards…"; g.append(sr);
    for(let i=0;i<12;i++){ const k=document.createElement("div"); k.className="sleeve skel"; k.setAttribute("aria-hidden","true"); k.innerHTML='<span class="sk-art"></span><span class="sk-line"></span><span class="sk-line short"></span>'; g.append(k); }
  }
  else if(!list.length && state.cards.length){   // filters hide everything: say why, with a way back to all cards
    const owned=state.cards.filter(c=>qty(c.n)>0).length, only=!state.q && !state.rar;
    const text = only && state.filter==="own" && !owned ? "You haven't marked any cards owned here yet. Tap Need on a card to mark it owned."
      : only && state.filter==="need" && owned===state.cards.length ? "You own every card in this binder."
      : state.q ? "No cards match “"+state.q+"”."+(state.filter!=="all"||state.rar ? " Some filters are on too." : "")
      : "No cards match these filters.";
    g.append(emptyNote(text, only ? "Show all cards" : "Clear filters", clearFilters));
  }
  else if(!list.length){ const e=document.createElement("div"); e.className="empty"; e.textContent=state.ready ? (isOwn(state.sid) ? "This binder is empty. Add cards with Find a card." : "This set has no cards yet.") : "Loading cards…"; g.append(e); }
  let anyStale=false;
  for(const c of list){
    const b=document.createElement("div");
    b.className="sleeve"+(qty(c.n)>0?"":" need"); b.dataset.n=c.n;
    const f=document.createElement("div"); f.className="face "+(c.custom?"custom":tint(c));
    f.setAttribute("role","button"); f.tabIndex=0; f.setAttribute("aria-label",c.name+" "+label(c)+" details");
    if(c.custom){ const ct=document.createElement("span"); ct.className="ctag"; ct.textContent="Custom"; f.append(ct); }
    const no=document.createElement("div"); no.className="no"; no.textContent=label(c);
    const nm=document.createElement("div"); nm.className="nm"; nm.textContent=c.name;
    const r=document.createElement("div"); r.className="rar"; r.textContent=RSYM[c.rarity]||c.rarity||"";
    f.append(no,nm,r,cardImg(c));
    const m=document.createElement("div"); m.className="meta";
    const p=document.createElement("span"); p.className="price"; p.textContent=priceOf(c.n) ? money(priceOf(c.n)) : "–";
    const sw=staleWhy(c.n), tr=trend(c.n);
    if(sw){ p.append(staleEl(sw)); anyStale=true; }   // an old price's up/down arrow doesn't mean much, so the clock takes its place
    else if(tr && Math.abs(tr.pct)>=5) p.append(trendEl(tr,true));
    const t=document.createElement("button"); t.type="button"; t.className="tag"+(qty(c.n)>0?" own":"");
    t.textContent=qty(c.n)>0 ? (qty(c.n)>1?"Owned ×"+qty(c.n):"Owned") : "Need";
    t.title=qty(c.n)>0 ? "Tap to mark as needed" : "Tap to mark as owned";
    t.setAttribute("aria-label",(qty(c.n)>0?"Owned. Mark "+c.name+" as needed":"Needed. Mark "+c.name+" as owned"));
    m.append(p,t); b.append(f);
    if(c.set){ const ed=document.createElement("div"); ed.className="ed"; ed.textContent=c.set; ed.title=c.set+(showEd?" · Unlimited":""); b.append(ed); }
    else if(showEd){ const ed=document.createElement("div"); ed.className="ed"; ed.textContent="Unlimited"; b.append(ed); }
    b.append(m); g.append(b);
  }
  if(state.ready && state.sid && !state.q) g.append(missTile());
  $("staleKey").hidden=!anyStale;
  $("staleKeyT").textContent="Old price: the last sale was over 3 months ago, or there are no recent sales. Tap the card to see when it last sold.";
  $("count").textContent=list.length+" of "+state.cards.length+" cards";
  filterSummary(list.length);
  stats();
}
// ---------- phone filters panel ----------
// It drives the same controls as the desktop toolbar (fOwn, fRar, fSort), so both stay in sync.
const OWN_LABELS={all:"All",need:"Need",own:"Owned"};
function activeFilters(){ return (state.filter!=="all")+(!!state.rar)+(state.sort!=="num"); }
function filterSummary(shown){
  const parts=[]; if(state.filter!=="all") parts.push(OWN_LABELS[state.filter]); if(state.rar) parts.push(state.rar);
  if(state.sort!=="num") parts.push($("fSort").selectedOptions[0].textContent.replace(/^Sort: /,""));
  $("fSum").textContent=(parts.length?parts.join(" · ")+" · ":"")+shown+" of "+state.cards.length+" cards";
  const n=activeFilters(); let badge=$("fBtn").querySelector(".n");
  if(n){ if(!badge){ badge=document.createElement("span"); badge.className="n"; $("fBtn").append(badge); } badge.textContent=n; }
  else if(badge) badge.remove();
  $("fBtn").setAttribute("aria-label","Filters"+(n?" ("+n+" on)":""));
  if($("fsheet").open) drawFilterSheet(shown);
}
// An empty spot: what's going on, plus one button that gets you out of it.
function emptyNote(text, label, onClick){
  const d=document.createElement("div"); d.className="empty";
  const p=document.createElement("p"); p.textContent=text; d.append(p);
  if(label){ const b=document.createElement("button"); b.type="button"; b.className="btn"; b.textContent=label; b.onclick=onClick; d.append(b); }
  return d;
}
function clearFilters(){
  state.q=""; $("fQ").value=""; state.rar=""; $("fRar").value="";
  setOwnFilter("all");
}
function setOwnFilter(v){ state.filter=v; [...$("fOwn").children].forEach(x=>x.setAttribute("aria-pressed",x.dataset.v===v)); render(); }
function chip(label, on, fn){ const b=document.createElement("button"); b.type="button"; b.className="chip"; b.textContent=label; b.setAttribute("aria-pressed",on); b.onclick=fn; return b; }
function drawFilterSheet(shown){
  const own=$("fsOwn"); own.replaceChildren(...["all","need","own"].map(v=>{ const b=document.createElement("button"); b.type="button"; b.textContent=OWN_LABELS[v]; b.setAttribute("aria-pressed",state.filter===v); b.onclick=()=>setOwnFilter(v); return b; }));
  $("fsRarLbl").textContent=isMulti(state.sid) ? "Set" : "Rarity";
  $("fsRar").replaceChildren(...[...$("fRar").options].map(o=>chip(o.value ? o.textContent : "All", state.rar===o.value, ()=>{ $("fRar").value=o.value; state.rar=o.value; render(); })));
  $("fsSort").replaceChildren(...[...$("fSort").options].map(o=>chip(o.textContent.replace(/^Sort: /,"").replace(/^./,c=>c.toUpperCase()), state.sort===o.value, ()=>{ $("fSort").value=o.value; state.sort=o.value; render(); })));
  $("fsPeriod").replaceChildren(...PERIODS.map(([d,l])=>chip(l, state.period===d, ()=>setPeriod(d))));
  $("fsPeriodNote").textContent=periodNote(); $("fsPeriodNote").hidden=!$("fsPeriodNote").textContent;
  const n = shown ?? $("grid").querySelectorAll(".sleeve").length;
  $("fsGo").textContent="Show "+n+" card"+(n===1?"":"s");
}
const fsheet=$("fsheet");
$("fBtn").onclick=()=>{ drawFilterSheet(); fsheet.showModal(); requestAnimationFrame(()=>requestAnimationFrame(()=>fsheet.classList.add("in"))); };
function closeFilterSheet(){ if(!fsheet.open) return; fsheet.classList.remove("in"); setTimeout(()=>fsheet.close(), matchMedia("(prefers-reduced-motion: reduce)").matches?0:220); }
$("fsGo").onclick=closeFilterSheet;
fsheet.addEventListener("click",e=>{ if(e.target===fsheet) closeFilterSheet(); });
fsheet.addEventListener("cancel",e=>{ e.preventDefault(); closeFilterSheet(); });
// Swipe down to close. Dragging the top of the panel always works; dragging anywhere else works
// when the panel isn't scrolled. Blocking the browser's own handling stops pull-to-refresh.
(()=>{
  const sh=fsheet.querySelector(".sheet"); let y0=null, dy=0, t0=0, fromGrab=false;
  fsheet.addEventListener("touchstart",e=>{
    fromGrab=!!e.target.closest("#fsGrab");
    if(!fromGrab && sh.scrollTop>0){ y0=null; return; }
    y0=e.touches[0].clientY; dy=0; t0=Date.now();
  },{passive:true});
  fsheet.addEventListener("touchmove",e=>{
    if(y0==null) return;
    dy=e.touches[0].clientY-y0;
    if(dy<=0 && !fromGrab){ y0=null; fsheet.classList.remove("drag"); fsheet.style.transform=""; return; }   // scrolling up inside
    e.preventDefault();
    fsheet.classList.add("drag"); fsheet.style.transform="translateY("+Math.max(0,dy)+"px)";
  },{passive:false});
  fsheet.addEventListener("touchend",()=>{
    if(y0==null) return;
    const fast=dy>40 && (Date.now()-t0)<250;
    fsheet.classList.remove("drag"); fsheet.style.transform="";
    if(dy>90 || fast) closeFilterSheet();
    y0=null;
  });
})();
$("fsReset").onclick=()=>{ $("fRar").value=""; state.rar=""; $("fSort").value="num"; state.sort="num"; setOwnFilter("all"); };

$("fOwn").addEventListener("click",e=>{ const b=e.target.closest("button"); if(!b) return; state.filter=b.dataset.v; [...$("fOwn").children].forEach(x=>x.setAttribute("aria-pressed",x===b)); render(); });
$("fRar").addEventListener("change",e=>{state.rar=e.target.value;render();});
$("fSort").addEventListener("change",e=>{state.sort=e.target.value;render();});
$("fQ").addEventListener("input",e=>{state.q=e.target.value.trim().toLowerCase();render();});
$("grid").addEventListener("click",e=>{
  const b=e.target.closest(".sleeve"); if(!b) return;
  if(e.target.closest(".tag")){ quickToggle(b.dataset.n); return; }
  openCard(b.dataset.n);
});
$("grid").addEventListener("keydown",e=>{
  if((e.key==="Enter"||e.key===" ") && e.target.classList.contains("face")){ const b=e.target.closest(".sleeve"); if(b){ e.preventDefault(); openCard(b.dataset.n); } }
});
async function clearCard(n){
  const c=state.cards.find(x=>x.n===n); if(!c) return;
  if(isOffline()){ toast("Marking a card as needed waits for a connection to "+srv()+"."); return; }
  const k=qty(n);
  const ok=await askConfirm("Mark "+c.name+" as needed?", "This removes "+(k===1?"its purchase record":"all "+k+" purchase records")+" for this card, including dates, prices and sellers.", "Remove");
  if(!ok) return;
  saveCard(n,{purchases:[]}, done=>{ $("sync").textContent = done ? c.name+" marked as needed" : "Couldn't save. Check that "+srv()+" is online."; });
  if(state.open===n && $("dlg").open){ $("dQty").textContent=0; drawBuys(n); condOptions(n); $("dArt").classList.toggle("need",true); }
}
function quickToggle(n){
  if(isPrivate()) return;
  const c=state.cards.find(x=>x.n===n); if(!c) return;
  const owned=qty(n)>0;
  if(owned){ clearCard(n); return; }
  const list=[{d:todayStr(), price:null, where:""}];
  saveCard(n,{purchases:list}, ok=>{ $("sync").textContent = ok ? (owned ? c.name+" marked as needed" : c.name+" marked as owned today. Tap the card to add what you paid.") : "Couldn't save. Check that "+srv()+" is online."; });
  const t=document.querySelector('.sleeve[data-n="'+CSS.escape(n)+'"] .tag'); if(t) t.focus();
}

// ---------- custom cards ----------
const customOf = n => state.cards.find(c=>c.n===n && c.custom);
const PENCIL='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';
function customBadge(count){
  const b=document.createElement("span"); b.className="cbadge"; b.innerHTML=PENCIL;
  b.append(String(count)); b.title=count+" custom card"+(count===1?"":"s")+" in this binder";
  b.setAttribute("aria-label", b.title); return b;
}
function missTile(){
  const t=document.createElement("div"); t.className="miss";
  const dex=isDex(state.sid), who=dex ? (state.set.name||"").replace(/^#?\d+\s*/,"") : "";
  const own=isOwn(state.sid);
  const h=document.createElement("b"); h.textContent=own ? "Add cards" : dex&&who ? "Missing a "+who+" card?" : "Missing a card?";
  const p=document.createElement("div"); p.className="s";
  p.textContent=own ? "Find any card from any set and add it here." : dex ? "Find it in the card list, or add a custom card for promos and trainer kit cards the list doesn't have." : "Find it in the card list, or add a custom card for a promo or variant.";
  t.append(h,p);
  const fb=document.createElement("button"); fb.type="button"; fb.className="btn"; fb.textContent="Find a card"; fb.onclick=()=>openFind(own || !dex ? null : who); t.append(fb);
  // PokéCottage has every Gen 1 and 2 page (#1 to #251) so far; raise this as they add more.
  const dexNo=+(state.set.dex||String(state.sid).replace(/^dex-/,""));
  if(dex && who && dexNo>=1 && dexNo<=COTTAGE_MAX){ const a=document.createElement("a"); a.className="btn"; a.target="_blank"; a.rel="noopener"; a.href="https://pokecottage.com/pokemon-master-sets/"+cottageSlug(who); a.textContent="Check PokéCottage's "+who+" list ↗"; t.append(a); }
  const add=document.createElement("button"); add.type="button"; add.className="btn"; add.textContent="+ Custom card"; add.onclick=()=>openCustom(null);
  t.append(add); return t;
}
let editing=null;
function openCustom(n){
  const c=n ? customOf(n) : null; editing=c ? c.n : null;
  $("cTitle").textContent=c ? "Edit custom card" : "Add a card";
  $("cSave").textContent=c ? "Save changes" : "Add card";
  $("cName").value=c?c.name:""; $("cSet").value=c?c.set||"":(isMulti(state.sid)?"":(state.set.name||"")); $("cNum").value=c?c.num||"":"";
  $("cRar").value=c?c.rarity||"":""; $("cTcg").value=c&&c.tcg ? "https://www.tcgplayer.com/product/"+c.tcg : "";
  const man=c && (state.info[c.n]||{}).manual; $("cPrice").value=man ? man.toFixed(2) : "";
  $("cPic").value=""; $("cPicName").textContent=c ? "Optional. Choose a picture to replace this card's photo." : "Optional. A photo of the card becomes its picture.";
  $("cErr").textContent="";
  $("cdlg").showModal(); setTimeout(()=>$("cName").focus(),50);
}
$("cPic").onchange=e=>{ const f=e.target.files[0]; $("cPicName").textContent=f ? f.name : "Optional. A photo of the card becomes its picture."; };
$("cClose").onclick=$("cCancel").onclick=()=>$("cdlg").close();
$("cdlg").addEventListener("click",e=>{ if(e.target===$("cdlg")) $("cdlg").close(); });
$("cForm").onsubmit=async e=>{
  e.preventDefault();
  if(!$("cName").value.trim()){ $("cErr").textContent="Give the card a name."; $("cName").focus(); return; }
  const pic=$("cPic").files[0];
  if(pic && pic.size>15*1048576){ $("cErr").textContent="That picture is too big (15 MB max)."; return; }
  const body={name:$("cName").value, set:$("cSet").value, num:$("cNum").value, rarity:$("cRar").value, tcg:$("cTcg").value, price:$("cPrice").value};
  $("cSave").disabled=true; $("cErr").textContent="Saving…";
  try{
    const url="api/set/"+enc(state.sid)+"/custom"+(editing?"/"+enc(editing):"");
    const r=await fetch(url,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't save");
    if(pic){
      const up=await fetch("api/set/"+enc(state.sid)+"/photo/"+enc(j.n),{method:"POST",headers:{"Content-Type":pic.type||"image/jpeg"},body:pic});
      if(!up.ok){ const uj=await up.json().catch(()=>({})); throw new Error("The card was saved, but the picture didn't upload"+(uj.error?" ("+uj.error+")":"")+". Try adding it again from the card."); }
    }
    $("cErr").textContent=""; $("cdlg").close();
    $("sync").textContent=(editing?"Saved changes to ":"Added ")+j.name+(body.tcg&&!editing?". Its price fills in on the next price check.":".");
    await loadState(); loadSets().then(()=>{ if($("drawer").open) drawSets(); });
    if(editing && state.open===j.n && $("dlg").open) openCard(j.n);
  }catch(err){ $("cErr").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message : "Couldn't save. Check that "+srv()+" is online."; }
  finally{ $("cSave").disabled=false; }
};
$("dCEdit").onclick=()=>{ if(state.open) openCustom(state.open); };
$("dCDel").onclick=async()=>{
  const c=customOf(state.open); if(!c) return;
  const extra = qty(c.n)>0 ? " Your "+qty(c.n)+" cop"+(qty(c.n)===1?"y":"ies")+", purchases and photos for it are deleted too." : "";
  const ok=await askConfirm("Delete this custom card?", c.name+(c.set?" · "+c.set:""), "Delete",
    {body:Object.assign(document.createElement("div"),{className:"note",textContent:"It's removed from this binder."+extra+" Backups you already have still include it."})});
  if(!ok) return;
  const r=await fetch("api/set/"+enc(state.sid)+"/custom/"+enc(c.n),{method:"DELETE"}).catch(()=>null);
  if(!r || !r.ok){ $("dSaved").textContent="Couldn't delete. Check that "+srv()+" is online."; return; }
  $("dlg").close(); $("sync").textContent="Deleted "+c.name+".";
  await loadState(); loadSets();
};

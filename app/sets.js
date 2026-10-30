// The sets menu, reordering binders, adding a Pokémon binder.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- set menu ----------
// The all-binders summary uses the same block as the summary at the top of the page, two figures per row.
function drawAllSum(){
  const box=$("allSum"), withT=state.sets.filter(s=>s.totals);
  box.hidden = withT.length<2; box.replaceChildren(); if(box.hidden) return;
  const T=withT.reduce((a,s)=>{ for(const k in s.totals) a[k]=(a[k]||0)+s.totals[k]; return a; },{});
  const h=document.createElement("h3"); h.className="ui-h"; h.textContent="All "+withT.length+" binders";
  const g=document.createElement("div"); g.className="stats two";
  const cell=(k,v,...sub)=>{ const d=document.createElement("div"); d.className="stat";
    const a=document.createElement("span"); a.className="k"; a.textContent=k;
    const b=document.createElement("span"); b.className="v"; b.textContent=v;
    const e=document.createElement("span"); e.className="s"; e.append(...sub);
    d.append(a,b,e); g.append(d); };
  const pct=Math.round(T.owned/Math.max(1,T.count)*100);
  const bar=document.createElement("span"); bar.className="bar"; const bi=document.createElement("i"); bi.style.width=pct+"%"; bar.append(bi);
  cell("Cards owned", T.owned+" / "+T.count, bar, pct+"%");
  let gain=["Add what you paid to see gain"];
  if(T.paid>0){ const d=T.value-T.paid, sp=document.createElement("span"); sp.className=d>=0?"pos":"neg"; sp.textContent=(d>=0?"+":"−")+money0(Math.abs(d)); gain=[sp," vs. "+money0(T.paid)+" paid"]; }
  cell("Collection value", money0(T.value), ...gain);
  cell("Cost to finish", money0(T.need), (T.count-T.owned)+" cards to go");
  cell("Full sets value", money0(T.full), withT.length+" binders");
  box.append(h,g);
}
// One row per binder: progress ring (or the Pokémon's picture), name, cards owned and value.
// "Edit" at the top shows a Remove button on each row, so it can't be tapped by accident.
const setEditing = () => $("drEdit").getAttribute("aria-pressed")==="true";
function setEdit(on){ $("drEdit").setAttribute("aria-pressed", on); $("drEdit").textContent=on ? "Done" : "Edit"; drawSets(); if(on && state.sets.some(x=>x.images)) watchPictures(); }
function ring(pct){ const r=document.createElement("span"); r.className="ring"; r.style.setProperty("--p", pct); r.textContent=pct+"%"; r.setAttribute("aria-hidden","true"); return r; }
function drawSets(){
  drawAllSum();
  const L=$("setList"), editing=setEditing(); L.replaceChildren();
  $("drEdit").hidden=!state.sets.length;
  if(!state.sets.length){ const p=document.createElement("p"); p.className="note"; p.style.padding="12px 14px"; p.textContent="No sets yet. Add one to start."; L.append(p); }
  for(const s of state.sets){
    const total=s.count||s.total||0, own=s.owned||0, pct=Math.round(own/Math.max(1,total)*100);
    const row=document.createElement("div"); row.className="srow"; if(s.id===state.sid) row.setAttribute("aria-current","true");
    const go=document.createElement("button"); go.type="button"; go.className="ui-row go";
    const l=document.createElement("span"); l.className="ui-l";
    const b=document.createElement("b"); b.textContent=s.name; if(s.custom) b.append(" ", customBadge(s.custom));
    const sm=document.createElement("small"), base=own+" of "+total+(s.totals?" · "+money0(s.totals.value):"");
    sm.textContent=base;
    const lead=ring(pct);
    // master sets: the Pokémon's picture sits next to its name, so every row lines up with the same ring
    if(isDex(s.id)){ const im=document.createElement("img"); im.className="sprite"; im.alt=""; im.src="set/"+enc(s.id)+"/sprite.png"; im.onerror=()=>im.remove(); b.prepend(im); }
    l.append(b,sm); go.append(lead,l);
    go.setAttribute("aria-label", s.name+", "+own+" of "+total+" owned"+(s.id===state.sid?", open now":""));
    if(editing && isOwn(s.id)){   // your own binders: tap the name to rename it
      const pen=document.createElement("span"); pen.className="pen"; pen.setAttribute("aria-hidden","true"); pen.textContent="✎"; b.append(pen);
      go.setAttribute("aria-label","Rename "+s.name); go.onclick=()=>renameOwn(s);
      sm.textContent="Tap to rename";
    }
    else if(editing){ go.disabled=true;
      const pc=s.pics; if(pc && pc.total) sm.textContent=s.images ? "Getting pictures…" : pc.saved>=pc.total ? "All pictures saved" : "Pictures "+pc.saved+"/"+pc.total; }
    else { const c=document.createElement("span"); c.className="ui-chev"; c.setAttribute("aria-hidden","true"); go.append(c); go.onclick=()=>{ $("drawer").close(); openSet(s.id); }; }
    if(editing && state.sets.length>1){
      const g=document.createElement("button"); g.type="button"; g.className="sgrip"; g.textContent="⠿";
      g.setAttribute("aria-label","Move "+s.name+" (drag, or use the arrow keys)"); g.title="Drag to reorder";
      g.addEventListener("pointerdown",e=>startSetDrag(e,row));
      g.addEventListener("touchstart",e=>e.stopPropagation(),{passive:true});   // not a swipe to close the menu
      g.addEventListener("keydown",e=>setGripKey(e,row));
      row.append(g);
    }
    row.dataset.sid=s.id;
    row.append(go);
    if(editing){
      const rm=document.createElement("button"); rm.type="button"; rm.className="srm"; rm.textContent="Remove"; rm.setAttribute("aria-label","Remove "+s.name);
      rm.onclick=async()=>{
        if(!rm.classList.contains("confirm")){ rm.classList.add("confirm"); rm.textContent="Tap again"; setTimeout(()=>{ if(rm.isConnected){ rm.classList.remove("confirm"); rm.textContent="Remove"; } },4000); return; }
        rm.disabled=true;
        try{ const r=await fetch("api/sets/"+enc(s.id),{method:"DELETE"}); if(!r.ok) throw 0; }catch(_){ rm.disabled=false; rm.textContent="Couldn't remove"; return; }
        const wasOpen=state.sid===s.id;
        await loadSets(); if(wasOpen) openSet(state.sets[0] ? state.sets[0].id : null); drawSets();
        toast("Removed "+s.name+".", "Undo", ()=>restoreSet(s.id, wasOpen));
      };
      const pc=s.pics;
      if(pc && pc.total && pc.saved<pc.total && !s.images){
        const gp=document.createElement("button"); gp.type="button"; gp.className="srm sget"; gp.textContent="Get pictures";
        gp.setAttribute("aria-label","Download all pictures for "+s.name+" now");
        gp.onclick=async()=>{ gp.disabled=true;
          try{ const r=await fetch("api/sets/"+enc(s.id)+"/pictures",{method:"POST"}); if(!r.ok) throw 0; }catch(_){ gp.disabled=false; gp.textContent="Couldn't start"; return; }
          s.images=true; sm.textContent="Getting pictures…"; gp.remove(); watchPictures(); if(s.id===state.sid) watchImages(); };
        row.append(gp);
      }
      row.append(rm);
    }
    L.append(row);
  }
  drawRemoved(editing);
}
// ---------- reorder binders in the sets menu (Edit mode) ----------
function setsReordered(){
  const order=[...$("setList").querySelectorAll(".srow[data-sid]")].map(r=>r.dataset.sid);
  const byId=new Map(state.sets.map(x=>[x.id,x]));
  state.sets=order.map(id=>byId.get(id)).filter(Boolean);
  fetch("api/sets/order",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({order})})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); }))
    .catch(err=>{ toast((err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't save the order. Check that "+srv()+" is running."); loadSets().then(drawSets); });
}
function setGripKey(e,row){
  const L=$("setList");
  const prev=row.previousElementSibling, next=row.nextElementSibling;
  if(e.key==="ArrowUp" && prev && prev.dataset.sid) L.insertBefore(row,prev);
  else if(e.key==="ArrowDown" && next && next.dataset.sid) L.insertBefore(next,row);
  else return;
  e.preventDefault(); e.currentTarget.focus(); setsReordered();
}
// Same feel as the shopping list: the row lifts and follows your finger, the others slide out of the way.
function startSetDrag(e,row){
  if(e.button!==undefined && e.button!==0) return;
  e.preventDefault(); e.stopPropagation();
  const L=$("setList"), rows=[...L.querySelectorAll(".srow[data-sid]")], from=rows.indexOf(row);
  if(from<0 || rows.length<2) return;
  const sc=L.closest(".sheet")||document.scrollingElement, dlg=L.closest("dialog");
  const id=e.pointerId, y0=e.clientY, s0=sc.scrollTop;
  const r0=row.getBoundingClientRect(), H=r0.height;
  const mids=rows.map(r=>{ const b=r.getBoundingClientRect(); return b.top+sc.scrollTop+b.height/2; });
  // the lifted copy lives inside the menu (it's on top of the page), placed where the row is
  const ghost=row.cloneNode(true); ghost.classList.add("sdrag-ghost"); ghost.removeAttribute("aria-current"); ghost.setAttribute("aria-hidden","true");
  const off=dlg && getComputedStyle(dlg).transform!=="none" ? dlg.getBoundingClientRect() : {left:0,top:0};
  Object.assign(ghost.style,{left:(r0.left-off.left)+"px", top:(r0.top-off.top)+"px", width:r0.width+"px", height:H+"px"});
  (dlg||document.body).append(ghost);
  requestAnimationFrame(()=>ghost.classList.add("lifted"));
  row.classList.add("drag-slot"); document.body.classList.add("drag-shop");
  rows.forEach(r=>{ if(r!==row) r.classList.add("drag-shift"); });
  try{ if(navigator.vibrate) navigator.vibrate(8); }catch(_){}
  let to=from, py=y0, raf=0, done=false;
  const place=()=>{
    ghost.style.transform="translateY("+(py-y0)+"px)";
    const center=mids[from]+(py-y0)+(sc.scrollTop-s0);
    let t=from;
    while(t+1<rows.length && center>mids[t+1]) t++;
    while(t>0 && center<mids[t-1]) t--;
    if(t===to) return;
    to=t;
    rows.forEach((r,i)=>{
      if(r===row) return;
      const shift = from<to && i>from && i<=to ? -H : from>to && i<from && i>=to ? H : 0;
      r.style.transform = shift ? "translateY("+shift+"px)" : "";
    });
  };
  const tick=()=>{   // scroll the menu when the finger is near its top or bottom
    raf=0; const b=sc.getBoundingClientRect(), edge=70; let v=0;
    if(py<b.top+edge) v=-Math.ceil((b.top+edge-py)/6); else if(py>b.bottom-edge) v=Math.ceil((py-(b.bottom-edge))/6);
    if(v){ const before=sc.scrollTop; sc.scrollTop+=v; if(sc.scrollTop!==before) raf=requestAnimationFrame(tick); }
    place();
  };
  const move=ev=>{ if(ev.pointerId!==id) return; py=ev.clientY; if(!raf) raf=requestAnimationFrame(tick); };
  const finish=cancel=>{
    if(done) return; done=true;
    window.removeEventListener("pointermove",move); window.removeEventListener("pointerup",up);
    window.removeEventListener("pointercancel",onCancel); window.removeEventListener("keydown",key,true);
    cancelAnimationFrame(raf);
    if(cancel){ to=from; rows.forEach(r=>{ r.style.transform=""; }); }
    else {
      rows.forEach(r=>{ r.style.transition="none"; r.style.transform=""; });
      if(to!==from) L.insertBefore(row, to>from ? rows[to].nextSibling : rows[to]);
      void L.offsetHeight; rows.forEach(r=>{ r.style.transition=""; });
    }
    const cleanup=()=>{ ghost.remove(); row.classList.remove("drag-slot"); rows.forEach(r=>r.classList.remove("drag-shift")); document.body.classList.remove("drag-shop"); };
    const end=row.getBoundingClientRect();
    ghost.classList.add("settle"); ghost.classList.remove("lifted"); ghost.style.transform="translateY("+(end.top-r0.top)+"px)";
    if(matchMedia("(prefers-reduced-motion: reduce)").matches) cleanup();
    else { ghost.addEventListener("transitionend",cleanup,{once:true}); setTimeout(cleanup,320); }
    if(to!==from) setsReordered();
  };
  const up=ev=>{ if(ev.pointerId===id) finish(false); };
  const onCancel=ev=>{ if(ev.pointerId===id) finish(true); };
  const key=ev=>{ if(ev.key==="Escape"){ ev.preventDefault(); ev.stopPropagation(); finish(true); } };
  window.addEventListener("pointermove",move); window.addEventListener("pointerup",up);
  window.addEventListener("pointercancel",onCancel); window.addEventListener("keydown",key,true);
}
// While the sets menu is in Edit mode, keep the "pictures saved" counts up to date during a download.
let picTimer=null;
function watchPictures(){
  clearTimeout(picTimer);
  picTimer=setTimeout(async()=>{
    if(!$("drawer").open || !setEditing()) return;
    await loadSets(); drawSets();
    if(state.sets.some(x=>x.images)) watchPictures();
  },3000);
}
// Binders removed in the last 30 days, shown while editing, each with a Restore button.
function drawRemoved(editing){
  const box=$("rmList"), list=state.removed||[];
  box.hidden=!editing || !list.length; box.replaceChildren(); if(box.hidden) return;
  const h=document.createElement("h3"); h.className="ui-h"; h.textContent="Recently removed";
  const g=document.createElement("div"); g.className="ui-group";
  for(const r of list){
    const row=document.createElement("div"); row.className="ui-row ui-static";
    const l=document.createElement("span"); l.className="ui-l";
    const b=document.createElement("b"); b.textContent=r.name;
    const sm=document.createElement("small"); sm.textContent="Kept "+r.daysLeft+" more day"+(r.daysLeft===1?"":"s")+", with everything in it";
    l.append(b,sm);
    const bt=document.createElement("button"); bt.type="button"; bt.className="btn"; bt.textContent="Restore"; bt.onclick=()=>restoreSet(r.id, false);
    row.append(l,bt); g.append(row);
  }
  const n=document.createElement("div"); n.className="note"; n.textContent="Removed binders are deleted for good after "+(state.keepDays||30)+" days.";
  box.append(h,g,n);
}
// Add a binder. If it was removed before with cards still saved, ask: bring them back, or start fresh?
// Resolves the new binder's info (restored:true when the old cards came back), or null if the person cancels.
async function addSetAsk(id){
  const post=keep=>fetch("api/sets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(keep==null?{id}:{id,keep})});
  let r=await post(), j=await r.json().catch(()=>({}));
  if(r.status===409 && j.saved){
    const sv=j.saved, ago=sv.at ? agoText(new Date(sv.at*1000).toISOString()) : "";
    const pick=await askChoice("Bring back your "+sv.name+" cards?",
      "You removed this binder"+(ago?" "+ago:" before")+" with "+sv.owned+" card"+(sv.owned===1?"":"s")+" owned. They're still saved on "+srv()+".",
      "Restore", {safe:true, alt:"Start fresh",
        body:Object.assign(document.createElement("div"),{className:"note",textContent:"Restore brings back your cards, what you paid, notes and photos. Start fresh begins with an empty binder (a backup is saved first, just in case)."})});
    if(!pick) return null;
    r=await post(pick==="ok"); j=await r.json().catch(()=>({}));
  }
  if(!r.ok) throw new Error(j.error||"Couldn't add that set");
  return j;
}
async function restoreSet(id, reopen){
  try{ const r=await fetch("api/sets/"+enc(id)+"/restore",{method:"POST"}); if(!r.ok) throw 0; }
  catch(_){ toast("Couldn't restore it. Check that "+srv()+" is online."); return; }
  await loadSets(); drawSets();
  const s=state.sets.find(x=>x.id===id); if(s) toast("Restored "+s.name+".");
  if(reopen) openSet(id);
}
// A short message at the bottom of the screen, with an optional button (like Undo). Disappears by itself.
let toastTimer=0;
// A problem message with a Try again button, for places that show a note instead of a toast.
function retryNote(text, again){
  const d=document.createElement("div"); d.className="note retry"; d.setAttribute("role","alert");
  const sp=document.createElement("span"); sp.textContent=text+" ";
  const b=document.createElement("button"); b.type="button"; b.className="btn"; b.textContent="Try again"; b.onclick=again;
  d.append(sp,b); return d;
}
const offlineHint = () => "Check that "+srv()+" is on, and that Tailscale is on if you're away from home.";
function toast(text, action, onAction){
  let t=$("toast");
  if(!t){ t=document.createElement("div"); t.id="toast"; t.className="toast"; t.setAttribute("role","status"); t.setAttribute("aria-live","polite");
    if("popover" in HTMLElement.prototype) t.setAttribute("popover","manual");   // so it shows above open windows
    document.body.append(t); }
  t.replaceChildren(); const sp=document.createElement("span"); sp.textContent=text; t.append(sp);
  if(action){ const b=document.createElement("button"); b.type="button"; b.textContent=action; b.onclick=()=>{ hide(); onAction(); }; t.append(b); }
  // live inside the open window (if any): a full-screen window blocks taps on everything outside it
  if(t.hidePopover) try{ t.hidePopover(); }catch(_){}
  const host=document.querySelector("dialog[open]:modal")||document.body; if(t.parentNode!==host) host.append(t);
  if(t.showPopover) t.showPopover();   // top layer: shows above the window and isn't cut off by its edges
  clearTimeout(toastTimer); requestAnimationFrame(()=>requestAnimationFrame(()=>t.classList.add("in")));
  function hide(){ clearTimeout(toastTimer); t.classList.remove("in"); toastTimer=setTimeout(()=>{ if(t.hidePopover && !t.classList.contains("in")) try{ t.hidePopover(); }catch(_){} }, 250); }
  toastTimer=setTimeout(hide, action ? 10000 : 3500);
}
// ---------- add a Pokémon (master set binder) ----------
let addKind="set", dexTimer=null;
function loadDex(){
  clearTimeout(dexTimer);
  return fetch("api/pokedex").then(r=>r.json()).then(j=>{
    state.dex=j;
    if(!j.ready && addKind==="dex" && !$("drAdd").hidden) dexTimer=setTimeout(()=>loadDex().then(drawCatalog),2000);
  }).catch(()=>{ state.dex={ready:false, error:"Couldn't reach "+srv()+""}; });
}
function drawDex(){
  const C=$("catalog"); C.replaceChildren();
  const d=state.dex;
  if(!d){ $("addMsg").textContent="Loading the Pokémon list…"; return; }
  if(d.building) setBar($("addBar"), d.done, d.total); else hideBar($("addBar"));
  if(!d.ready){
    $("addMsg").textContent = d.error && !d.building ? "Couldn't make the Pokémon list ("+d.error+"). Check that "+srv()+" is online and reopen this menu."
      : "Making the Pokémon list from every set (first time only, about 2 minutes)… "+(d.total ? d.done+" of "+d.total+" sets" : "");
    return;
  }
  const term=$("addQ").value.trim().toLowerCase().replace(/^#/,"");
  const have=new Set(state.sets.map(s=>s.id));
  const list=d.list.filter(p=>!term || p.name.toLowerCase().includes(term) || String(p.dex)===term.replace(/^0+/,""));
  $("addMsg").textContent = !term ? "Search for a Pokémon to collect every English card of it, from every set." : list.length ? "" : "No Pokémon match that search.";
  if(!term) return;
  for(const p of list.slice(0,40)){
    const id="dex-"+p.dex;
    const row=document.createElement("div"); row.className="catrow";
    const im=document.createElement("img"); im.className="sprite"; im.alt=""; im.loading="lazy";
    im.src=p.dex<=251 ? "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-ii/crystal/transparent/"+p.dex+".png"
      : p.dex<=649 ? "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/"+p.dex+".png"
      : "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"+p.dex+".png";
    im.onerror=()=>im.remove();
    const dv=document.createElement("div"); const b=document.createElement("b"); b.textContent=p.name;
    const sp=document.createElement("span"); sp.textContent="#"+String(p.dex).padStart(4,"0")+" · "+p.count+" cards"; dv.append(b,sp);
    row.append(im,dv);
    if(have.has(id)){ const em=document.createElement("em"); em.textContent="In your binder"; row.append(em); }
    else {
      const add=document.createElement("button"); add.type="button"; add.className="btn"; add.textContent="Add";
      add.onclick=async()=>{
        add.disabled=true; add.textContent="Adding…";
        try{
          const j=await addSetAsk(id);
          if(!j){ add.disabled=false; add.textContent="Add"; return; }
          await loadSets(); $("drawer").close(); showAdd(false); openSet(id);
          if(j.restored) toast("Restored "+p.name+" with your cards.");
          else { $("sync").textContent=p.name+" master set added. Prices start filling in within a few minutes."; setTimeout(poll,1500); }
        }catch(err){ add.disabled=false; add.textContent="Add"; $("addMsg").textContent=err.message+"."; }
      };
      row.append(add);
    }
    C.append(row);
  }
}
function setAddKind(k){
  addKind=k;
  [...$("addKind").children].forEach(x=>x.setAttribute("aria-pressed", x.dataset.k===k));
  $("addQ").hidden=k==="own";
  $("addQ").placeholder=k==="dex" ? "Search Pokémon, like Totodile or 158" : "Search sets, like Neo Genesis";
  $("addQ").setAttribute("aria-label", k==="dex" ? "Search Pokémon" : "Search sets");
  $("addQ").value="";
  if(k==="dex") loadDex().then(drawCatalog);
  drawCatalog(); if(k!=="own") $("addQ").focus();
}
$("addKind").addEventListener("click",e=>{ const b=e.target.closest("button"); if(b) setAddKind(b.dataset.k); });

const COTTAGE_MAX=251;
// PokéCottage page names: lowercase with dashes, like pokemon-master-sets/totodile or /mr-mime.
const cottageSlug = name => name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
  .replace(/♀/g,"-f").replace(/♂/g,"-m").replace(/['’.:]/g,"").replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");

function drawCatalog(){
  if(addKind==="own") return drawOwn();
  if(addKind==="dex") return drawDex();
  hideBar($("addBar"));
  const C=$("catalog"); C.replaceChildren();
  if(!state.catalog){ $("addMsg").textContent="Loading the set list…"; return; }
  const term=$("addQ").value.trim().toLowerCase();
  const have=new Set(state.sets.map(s=>s.id));
  const groups={};
  state.catalog.filter(s=>!term || s.name.toLowerCase().includes(term) || (s.series||"").toLowerCase().includes(term))
    .forEach(s=>{ (groups[s.series||"Other"] ||= []).push(s); });
  const order=Object.keys(groups).sort((a,b)=>(groups[a][0].releaseDate||"").localeCompare(groups[b][0].releaseDate||""));
  $("addMsg").textContent=order.length ? "" : "No sets match that search.";
  for(const g of order){
    const h=document.createElement("h3"); h.textContent=g; C.append(h);
    for(const s of groups[g].sort((a,b)=>(a.releaseDate||"").localeCompare(b.releaseDate||""))){
      const row=document.createElement("div"); row.className="catrow";
      const d=document.createElement("div"); const b=document.createElement("b"); b.textContent=s.name;
      const sp=document.createElement("span"); sp.textContent=year(s.releaseDate)+" · "+s.total+" cards"; d.append(b,sp);
      row.append(d);
      if(have.has(s.id)){ const em=document.createElement("em"); em.textContent="In your binder"; row.append(em); }
      else {
        const add=document.createElement("button"); add.type="button"; add.className="btn"; add.textContent="Add";
        add.onclick=async()=>{
          add.disabled=true; add.textContent="Adding…";
          try{
            const j=await addSetAsk(s.id);
            if(!j){ add.disabled=false; add.textContent="Add"; return; }
            await loadSets(); $("drawer").close(); showAdd(false); openSet(s.id);
            if(j.restored) toast("Restored "+s.name+" with your cards.");
            else { $("sync").textContent=s.name+" added. Prices start filling in within a few minutes."; setTimeout(poll,1500); }
          }catch(err){ add.disabled=false; add.textContent="Add"; $("addMsg").textContent=err.message+". Check that "+srv()+" is online and try again."; }
        };
        row.append(add);
      }
      C.append(row);
    }
  }
}
function showAdd(on){
  $("drSets").hidden=on; $("drAdd").hidden=!on;
  $("drTitle").textContent=on ? "Add a binder" : "Your binders"; $("addBack").hidden=!on; $("drEdit").hidden=on || !state.sets.length;   // one title bar, with a back arrow on the add page
  if(!on) clearTimeout(dexTimer);
  if(on){
    $("addQ").value=""; setAddKind("set"); setTimeout(()=>$("addQ").focus(),50);
    if(!state.catalog) fetch("api/catalog").then(r=>r.json()).then(j=>{ state.catalog=j.sets||[]; drawCatalog(); if(!state.catalog.length) $("addMsg").textContent="Couldn't load the set list. Check that "+srv()+" is online."; }).catch(()=>{ $("addMsg").textContent="Couldn't load the set list. Check that "+srv()+" is online."; });
  }
}
// Sets menu open/close with the grow-out animation. Wide screens: beside the binder, pushing it over.
const wideNav = () => matchMedia("(min-width: 900px)").matches;
const drawerEl=$("drawer"), dialogClose=HTMLDialogElement.prototype.close;
function openDrawer(){
  if(drawerEl.open) return;
  $("drMode").querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed", String((b.dataset.m==="show")===atShow())));
  const push=wideNav();
  drawerEl.classList.toggle("pushed", push);
  push ? drawerEl.show() : drawerEl.showModal();
  requestAnimationFrame(()=>requestAnimationFrame(()=>{ drawerEl.classList.add("in"); if(push) document.body.classList.add("nav-open"); }));
}
drawerEl.close=function(){   // every existing close() call animates out first
  if(!this.open || this.dataset.closing) return;
  this.dataset.closing="1"; this.classList.remove("in"); document.body.classList.remove("nav-open");
  const done=()=>{ delete this.dataset.closing; dialogClose.call(this); this.classList.remove("pushed"); };
  matchMedia("(prefers-reduced-motion: reduce)").matches ? done() : setTimeout(done,260);
};
drawerEl.addEventListener("cancel",e=>{ e.preventDefault(); drawerEl.close(); });
// Swipe left to close. Up/down still scrolls the menu; only a mostly sideways swipe moves it.
(()=>{
  let x0=null, y0=0, dx=0, t0=0, side=null;
  drawerEl.addEventListener("touchstart",e=>{ const t=e.touches[0]; x0=t.clientX; y0=t.clientY; dx=0; t0=Date.now(); side=null; },{passive:true});
  drawerEl.addEventListener("touchmove",e=>{
    if(x0==null) return;
    const t=e.touches[0], mx=t.clientX-x0, my=t.clientY-y0;
    if(side==null){ if(Math.abs(mx)<8 && Math.abs(my)<8) return; side=Math.abs(mx)>Math.abs(my)*1.2; }
    if(!side){ x0=null; return; }
    e.preventDefault(); dx=Math.min(0,mx);
    drawerEl.classList.add("drag"); drawerEl.style.transform="translateX("+dx+"px)";
  },{passive:false});
  drawerEl.addEventListener("touchend",()=>{
    if(x0==null || !side){ x0=null; return; }
    const fast=dx<-40 && (Date.now()-t0)<250;
    drawerEl.classList.remove("drag"); drawerEl.style.transform="";
    if(dx<-80 || fast) drawerEl.close();
    x0=null;
  });
})();
document.addEventListener("keydown",e=>{ if(e.key==="Escape" && drawerEl.open && drawerEl.classList.contains("pushed") && !document.querySelector("dialog[open]:modal")) drawerEl.close(); });
$("menuBtn").onclick=()=>goHome();
$("drClose").onclick=()=>$("drawer").close();
$("drEdit").onclick=()=>setEdit(!setEditing());
document.addEventListener("pointerdown",e=>{
  if(!drawerEl.open || !drawerEl.classList.contains("pushed")) return;
  if(e.target.closest("#drawer, #menuBtn, dialog[open], #toast")) return;
  drawerEl.close();
  if(e.target.closest("header.top button, header.top a")) return;   // buttons at the top (Settings, Refresh...) still work
  // a click on the page only closes the menu (it doesn't also open the card under it)
  const eat=ev=>{ ev.preventDefault(); ev.stopPropagation(); };
  window.addEventListener("click", eat, {capture:true, once:true});
  setTimeout(()=>window.removeEventListener("click", eat, true), 500);
});
$("drawer").addEventListener("close",()=>{ if(setEditing()) setEdit(false); });
$("drawer").addEventListener("click",e=>{ if(e.target===$("drawer")) $("drawer").close(); });
$("addOpen").onclick=()=>showAdd(true);
$("addBack").onclick=()=>{ showAdd(false); drawSets(); };
$("addQ").addEventListener("input",drawCatalog);

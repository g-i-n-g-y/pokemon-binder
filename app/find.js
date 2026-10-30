// Find a card, and your own binders.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- Find a card ----------
// Search every English card and set. Nothing is searched while typing: only when Search (or Enter) is tapped.
const fd={view:"home", q:"", res:null, set:null, setQ:"", pick:null, poll:null, scroll:0};
function openFind(text){
  if($("drawer").open) $("drawer").close();
  if(text!=null){ $("fdQ").value=text; }
  fdShow();
  if(!$("fdlg").open) $("fdlg").showModal();
  if(text) fdSearch();
  else if(fd.view==="home") setTimeout(()=>$("fdQ").focus(),60);
}
// The back arrow in the title bar (from a set to the results)
const fdBack=(()=>{
  const bar=$("fdlg").querySelector(".fbar"), b=document.createElement("button");
  b.type="button"; b.className="fclose ui-back"; b.title="Back"; b.setAttribute("aria-label","Back to results"); b.hidden=true;
  b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
  bar.prepend(b); b.onclick=()=>fdGoBack(); return b;
})();
function fdGoBack(){
  if(!$("fdPick").hidden){ fdClosePick(); return true; }
  if(fd.view==="set"){ fd.view=fd.res ? "results" : "home"; fdShow(); $("fdSheet").scrollTop=fd.scroll; return true; }
  return false;
}
$("fdlg").addEventListener("cancel",e=>{ if(fdGoBack()) e.preventDefault(); });
$("fdClose").onclick=()=>$("fdlg").close();
$("fdlg").addEventListener("close",()=>{ clearTimeout(fd.poll); fdClosePick(); });
$("fdForm").onsubmit=e=>{ e.preventDefault(); fdSearch(); };
$("fdDim").onclick=()=>fdClosePick();
$("findOpen").onclick=()=>openFind();

function fdNote(text){ const p=document.createElement("p"); p.className="fd-hint"; p.textContent=text; return p; }
function fdBuilding(r){
  if(r.building || !r.ready){ setBar($("fdBar"), r.done||0, r.total||0); }
  const B=$("fdBody"); B.replaceChildren();
  B.append(fdNote(r.error && !r.building ? "Couldn't make the card list ("+r.error+"). Check that "+srv()+" is online and try again."
    : "Making the list of every card from every set. This happens once and takes about a minute"+(r.total ? ": "+r.done+" of "+r.total+" sets." : ".")));
}
async function fdSearch(){
  const text=$("fdQ").value.trim();
  clearTimeout(fd.poll); fdClosePick();
  if(!text){ fd.view="home"; fd.res=null; fdShow(); return; }
  fd.q=text; fd.view="results";
  $("fdBody").replaceChildren(fdNote("Searching…"));
  try{
    const r=await fetch("api/find?q="+enc(text)).then(x=>x.json());
    if(fd.q!==text) return;
    if(!r.ready){ fdBuilding(r); if(!r.error || r.building) fd.poll=setTimeout(fdSearch,2500); return; }
    hideBar($("fdBar"));
    fd.res=r; fdShow(); $("fdSheet").scrollTop=0;
  }catch(_){ $("fdBody").replaceChildren(retryNote("Couldn't search. "+offlineHint(), ()=>fdSearch())); }
}
function fdShow(){
  fdBack.hidden = fd.view!=="set";
  $("fdForm").hidden = fd.view==="set";
  const B=$("fdBody"); B.replaceChildren();
  if(fd.view==="set" && fd.set) return fdDrawSet();
  if(fd.view==="results" && fd.res) return fdDrawResults();
  const h=document.createElement("div"); h.className="fd-hint";
  h.innerHTML='Type what\'s printed on the card. The number at the bottom, like <code>80/111</code>, narrows it to one set. '
    +'Try <code>Totodile</code>, <code>80/111</code>, <code>Dark Gengar 6</code>, or a set like <code>Neo Genesis</code> to see all its cards.';
  B.append(h);
}
function fdTags(c){
  const box=document.createElement("span"); box.className="fd-tags";
  for(const w of (c.in||[])){
    const own=w.qty>0 && !isPrivate();
    const t=document.createElement("span"); t.className="fd-tag"+(own?" own":"");
    t.textContent=(own?"Owned · ":"In ")+binderName(w.sid); box.append(t);
  }
  return box;
}
function fdImg(c, cls){
  if(!c.img){ const d=document.createElement("span"); d.className="ph"; return d; }
  const im=document.createElement("img"); im.alt=""; im.loading="lazy"; im.decoding="async"; im.src=smallImg(c.img);
  if(cls) im.className=cls;
  im.onerror=()=>{ const d=document.createElement("span"); d.className="ph"; im.replaceWith(d); };
  return im;
}
function fdDrawResults(){
  const r=fd.res, B=$("fdBody");
  if(r.sets.length){
    const sec=document.createElement("div"); sec.className="fd-sec";
    const h=document.createElement("h3"); h.className="ui-h"; h.textContent="Sets"; sec.append(h);
    const g=document.createElement("div"); g.className="ui-group";
    for(const st of r.sets){
      const row=document.createElement("button"); row.type="button"; row.className="ui-row";
      const l=document.createElement("span"); l.className="ui-l";
      const b=document.createElement("b"); b.textContent=st.name;
      const sm=document.createElement("small"); sm.textContent=[st.total+" cards", st.series, year(st.date), st.inBinder?"One of your binders":""].filter(Boolean).join(" · ");
      l.append(b,sm); const ch=document.createElement("span"); ch.className="ui-chev"; ch.setAttribute("aria-hidden","true");
      row.append(l,ch); row.onclick=()=>fdOpenSet(st.id); g.append(row);
    }
    sec.append(g); B.append(sec);
  }
  if(r.cards.length){
    const sec=document.createElement("div"); sec.className="fd-sec";
    const h=document.createElement("h3"); h.className="ui-h"; h.textContent="Cards ";
    const sp=document.createElement("span"); sp.textContent=r.count>r.cards.length ? r.cards.length+" of "+r.count : String(r.count); h.append(sp); sec.append(h);
    const g=document.createElement("div"); g.className="ui-group";
    for(const c of r.cards) g.append(fdRow(c));
    sec.append(g);
    if(r.count>r.cards.length) sec.append(fdNote("Showing the first "+r.cards.length+". Add the number at the bottom of the card, like 80/111, or the set name to narrow it down."));
    B.append(sec);
  }
  if(!r.sets.length && !r.cards.length) B.append(fdNote("Nothing matched “"+r.q+"”. Check the spelling, or try just the name or just the number."));
}
function fdRow(c){
  const row=document.createElement("button"); row.type="button"; row.className="fd-row";
  const d=document.createElement("span"); const b=document.createElement("b"); b.textContent=c.name;
  const sm=document.createElement("small"); sm.textContent=[c.set, padNo(c.num,c.pt), c.rarity].filter(Boolean).join(" · ");
  d.append(b,sm); if(c.in && c.in.length) d.append(fdTags(c));
  row.append(fdImg(c), d); row._c=c; row.onclick=()=>fdOpenPick(c); return row;
}
async function fdOpenSet(id){
  fd.scroll=$("fdSheet").scrollTop; fd.view="set"; fd.set=null; fd.setQ="";
  fdBack.hidden=false; $("fdForm").hidden=true;
  $("fdBody").replaceChildren(fdNote("Loading the set…"));
  try{
    const r=await fetch("api/find/set/"+enc(id)).then(x=>x.json());
    if(fd.view!=="set") return;
    if(!r.ready || !r.set){ $("fdBody").replaceChildren(fdNote(r.error||"Couldn't load that set.")); return; }
    fd.set=r; fdShow(); $("fdSheet").scrollTop=0;
  }catch(_){ $("fdBody").replaceChildren(retryNote("Couldn't load that set. "+offlineHint(), ()=>fdOpenSet(id))); }
}
function fdDrawSet(){
  const r=fd.set, st=r.set, B=$("fdBody");
  const head=document.createElement("div"); head.className="fd-sethead";
  const t=document.createElement("div"); const h=document.createElement("h3"); h.textContent=st.name;
  const sm=document.createElement("div"); sm.className="note"; sm.textContent=[st.total+" cards", st.series, year(st.date)].filter(Boolean).join(" · ");
  t.append(h,sm); head.append(t);
  const act=document.createElement("button"); act.type="button"; act.className="btn";
  if(st.inBinder){ act.textContent="Open this binder"; act.onclick=()=>fdOpenIn(st.id, null); }
  else {
    act.textContent="+ Add the whole set as a binder";
    act.onclick=async()=>{
      act.disabled=true; act.textContent="Adding…";
      try{
        const j=await addSetAsk(st.id);
        if(!j){ act.disabled=false; act.textContent="+ Add the whole set as a binder"; return; }
        st.inBinder=true; await loadSets(); act.disabled=false; act.textContent="Open this binder"; act.onclick=()=>fdOpenIn(st.id, null);
        toast(st.name+(j.restored?" restored with your cards.":" added as a binder."), "Open", ()=>fdOpenIn(st.id, null));
      }catch(err){ act.disabled=false; act.textContent="+ Add the whole set as a binder"; toast(err.message+"."); }
    };
  }
  head.append(act); B.append(head);
  const f=document.createElement("form"); f.className="fd-form"; f.setAttribute("role","search");
  const inp=document.createElement("input"); inp.type="search"; inp.className="field"; inp.placeholder="Find in this set: name or number"; inp.setAttribute("aria-label","Find in this set"); inp.value=fd.setQ; inp.setAttribute("enterkeyhint","search");
  const go=document.createElement("button"); go.type="submit"; go.className="btn"; go.textContent="Find";
  f.append(inp,go); B.append(f);
  const grid=document.createElement("div"); grid.className="fd-grid";
  const draw=()=>{
    grid.replaceChildren();
    const term=fd.setQ.trim().toLowerCase();
    const list=r.cards.filter(c=>!term || c.name.toLowerCase().includes(term) || normNum(String(c.num))===normNum(term.replace(/^#/,"").split("/")[0]));
    for(const c of list){
      const b=document.createElement("button"); b.type="button"; b.className="fd-tile"; b.setAttribute("aria-label",c.name+" "+padNo(c.num,c.pt));
      const nm=document.createElement("span"); nm.className="nm"; nm.textContent=c.name;
      const no=document.createElement("span"); no.className="no"; no.textContent=padNo(c.num,c.pt);
      const own=!isPrivate() && (c.in||[]).some(w=>w.qty>0);
      if(c.in && c.in.length){ const tg=document.createElement("span"); tg.className="fd-tag"+(own?" own":""); tg.textContent=own?"Owned":"In binder"; no.append(tg); }
      b.append(fdImg(c), nm, no); b._c=c; b.onclick=()=>fdOpenPick(c); grid.append(b);
    }
    if(!list.length) grid.append(fdNote("No card in this set matches that."));
  };
  f.onsubmit=e=>{ e.preventDefault(); fd.setQ=inp.value; draw(); };
  draw(); B.append(grid);
}
// The card panel: links, which binders have it, and where it can be added.
function fdOpenPick(c){ fd.pick=c; $("fdDim").hidden=false; $("fdPick").hidden=false; fdDrawPick(); $("fdPick").scrollTop=0; setTimeout(()=>{ const x=$("fdPick").querySelector(".fclose"); if(x) x.focus(); },30); }
function fdClosePick(){ fd.pick=null; $("fdDim").hidden=true; $("fdPick").hidden=true; }
function fdDrawPick(){
  const c=fd.pick, P=$("fdPick"); P.replaceChildren(); if(!c) return;
  const head=document.createElement("div"); head.className="fd-ph";
  const d=document.createElement("div"); const b=document.createElement("b"); b.textContent=c.name;
  const sm=document.createElement("small"); sm.textContent=[c.set, padNo(c.num,c.pt), c.rarity].filter(Boolean).join(" · ");
  const L=document.createElement("div"); L.className="links";
  [["TCGplayer",tcgSearchUrl(c.set,c.name)],["eBay sold",ebaySoldUrl({year:c.date, set:c.set, name:c.name, rarity:c.rarity, num:c.num, pt:c.pt})]]
    .forEach(([t,u])=>{ const a=document.createElement("a"); a.href=u; a.target="_blank"; a.rel="noopener"; a.textContent=t+" ↗"; L.append(a); });
  d.append(b,sm);
  const x=document.createElement("button"); x.type="button"; x.className="fclose"; x.setAttribute("aria-label","Close"); x.title="Close";
  x.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  x.onclick=()=>fdClosePick();
  head.append(fdImg(c), d, x); P.append(head, L);
  const inn=(c.in||[]).filter(w=>state.sets.some(s=>s.id===w.sid));
  if(inn.length){
    const h=document.createElement("h3"); h.className="ui-h"; h.textContent="In your binders"; P.append(h);
    const g=document.createElement("div"); g.className="ui-group";
    for(const w of inn){
      const row=document.createElement("button"); row.type="button"; row.className="ui-row";
      const l=document.createElement("span"); l.className="ui-l"; const bb=document.createElement("b"); bb.textContent=binderName(w.sid);
      const s2=document.createElement("small"); s2.textContent=isPrivate() ? "In this binder" : w.qty>0 ? (w.qty>1?"Owned ×"+w.qty:"Owned") : "Need";
      l.append(bb,s2); const v=document.createElement("span"); v.className="ui-v"; v.textContent="Open";
      row.append(l,v); row.onclick=()=>fdOpenIn(w.sid, w.n); g.append(row);
    }
    P.append(g);
  }
  const have=new Set(inn.map(w=>w.sid));
  const targets=state.sets.filter(s=>!have.has(s.id));
  const h2=document.createElement("h3"); h2.className="ui-h"; h2.textContent=inn.length ? "Also add to" : "Add to"; P.append(h2);
  const g2=document.createElement("div"); g2.className="ui-group";
  for(const s of targets){
    const row=document.createElement("button"); row.type="button"; row.className="ui-row";
    const l=document.createElement("span"); l.className="ui-l"; const bb=document.createElement("b"); bb.textContent=s.name;
    const s2=document.createElement("small"); s2.textContent=isOwn(s.id) ? "Your own binder" : isDex(s.id) ? "Adds it to this master set" : "Adds it as an extra card";
    l.append(bb,s2); const v=document.createElement("span"); v.className="ui-v"; v.textContent="Add";
    row.append(l,v); row.onclick=()=>fdAdd(c, s.id, row); g2.append(row);
  }
  const nb=document.createElement("button"); nb.type="button"; nb.className="ui-row";
  nb.innerHTML='<span class="ui-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></span><span class="ui-l"><b>New binder</b><small>Your own binder, like Favorites or Trade pile</small></span>';
  nb.onclick=()=>{
    const f=document.createElement("form"); f.className="fd-new";
    const inp=document.createElement("input"); inp.className="field"; inp.placeholder="Binder name"; inp.maxLength=40; inp.setAttribute("aria-label","New binder name");
    const ok=document.createElement("button"); ok.type="submit"; ok.className="btn primary"; ok.textContent="Make and add";
    f.append(inp,ok); nb.replaceWith(f); inp.focus();
    f.onsubmit=async e=>{
      e.preventDefault(); if(!inp.value.trim()){ inp.focus(); return; }
      ok.disabled=true; ok.textContent="Making…";
      try{
        const r=await fetch("api/sets/own",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:inp.value})});
        const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't make the binder");
        await loadSets(); await fdAdd(c, j.id, null);
      }catch(err){ ok.disabled=false; ok.textContent="Make and add"; toast(err.message+"."); }
    };
  };
  g2.append(nb); P.append(g2);
}
async function fdAdd(c, sid, row){
  if(row){ row.disabled=true; const v=row.querySelector(".ui-v"); if(v) v.textContent="Adding…"; }
  try{
    const r=await fetch("api/set/"+enc(sid)+"/cards",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:c.n})});
    const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't add the card");
    c.in=(c.in||[]).filter(w=>w.sid!==sid).concat([{sid, n:j.n, qty:(state.sid===sid?qty(j.n):0)}]);
    await loadSets();
    if(state.sid===sid) loadState();
    if(fd.pick===c) fdDrawPick();
    if(fd.view==="results") fdShow(); else if(fd.view==="set") { const top=$("fdSheet").scrollTop; fdShow(); $("fdSheet").scrollTop=top; }
    toast((j.already ? c.name+" is already in " : "Added "+c.name+" to ")+binderName(sid)+".", "Open", ()=>fdOpenIn(sid, j.n));
  }catch(err){ if(row){ row.disabled=false; const v=row.querySelector(".ui-v"); if(v) v.textContent="Add"; } toast((err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't add. Check that "+srv()+" is online."); }
}
function fdOpenIn(sid, n){
  $("fdlg").close();
  const go=()=>{ if(n!=null && state.cards.some(x=>x.n===n)){ setView("cards"); openCard(n); } };
  if(state.sid===sid && state.ready){ go(); return; }
  openSet(sid).then(go);
}

// ---------- your own binders ----------
function drawOwn(){
  hideBar($("addBar")); $("addMsg").textContent="";
  const C=$("catalog"); C.replaceChildren();
  const f=document.createElement("form"); f.className="own-form";
  const lab=document.createElement("label"); lab.className="f"; lab.textContent="Binder name";
  const inp=document.createElement("input"); inp.id="ownName"; inp.maxLength=40; inp.placeholder="Favorites, Trade pile, Gym leaders…"; inp.autocomplete="off"; lab.append(inp);
  const ok=document.createElement("button"); ok.type="submit"; ok.className="btn primary"; ok.textContent="Make binder";
  const p=document.createElement("p"); p.className="note"; p.textContent="An empty binder you fill yourself, with cards from any set, using Find a card. Prices, owned, purchases, photos and pages work like any other binder.";
  f.append(lab,ok,p); C.append(f);
  f.onsubmit=async e=>{
    e.preventDefault(); if(!inp.value.trim()){ inp.focus(); return; }
    ok.disabled=true; ok.textContent="Making…";
    try{
      const r=await fetch("api/sets/own",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:inp.value})});
      const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't make the binder");
      await loadSets(); $("drawer").close(); showAdd(false); openSet(j.id);
      toast(j.name+" is ready. Add cards with Find a card.", "Find a card", ()=>openFind());
    }catch(err){ ok.disabled=false; ok.textContent="Make binder"; $("addMsg").textContent=err.message+"."; }
  };
  setTimeout(()=>inp.focus(),50);
}
async function renameOwn(s){
  const box=document.createElement("label"); box.className="f"; box.textContent="New name";
  const inp=document.createElement("input"); inp.maxLength=40; inp.value=s.name; box.append(inp);
  setTimeout(()=>{ inp.focus(); inp.select(); },60);
  inp.addEventListener("keydown",e=>{ if(e.key==="Enter"){ e.preventDefault(); $("cfOk").click(); } });
  const ok=await askConfirm("Rename binder", "", "Rename", {safe:true, body:box});
  if(!ok || !inp.value.trim() || inp.value.trim()===s.name) return;
  try{
    const r=await fetch("api/sets/"+enc(s.id)+"/name",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:inp.value})});
    const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't rename");
    await loadSets(); drawSets(); if(state.sid===s.id){ state.set.name=j.name; header(); }
  }catch(err){ toast((err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't rename. Check that "+srv()+" is online."); }
}
$("dXDel").onclick=async()=>{
  const n=state.open, c=state.cards.find(x=>x.n===n); if(!c || !c.extra) return;
  const extra = qty(n)>0 ? " Your "+qty(n)+" cop"+(qty(n)===1?"y":"ies")+", purchases and photos for it are deleted too." : "";
  const ok=await askConfirm("Remove from this binder?", c.name+" · "+(c.set||"")+" "+padNo(c.num,c.pt), "Remove",
    {body:Object.assign(document.createElement("div"),{className:"note",textContent:"It's taken out of "+(state.set.name||"this binder")+"."+extra+" You can add it again with Find a card."})});
  if(!ok) return;
  const r=await fetch("api/set/"+enc(state.sid)+"/cards/"+enc(n),{method:"DELETE"}).catch(()=>null);
  if(!r || !r.ok){ $("dSaved").textContent="Couldn't remove. Check that "+srv()+" is online."; return; }
  $("dlg").close(); toast("Removed "+c.name+" from "+(state.set.name||"this binder")+".");
  await loadState(); loadSets();
};

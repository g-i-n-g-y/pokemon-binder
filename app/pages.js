// Pages: the binder laid out like a real binder.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- Pages: the binder laid out like a real binder ----------
// Page 1 starts on the right-hand side (the inside cover is on the left), then each spread is the back of one
// page and the front of the next. The layout (pocket size, starting order, and any cards you moved) is saved
// on the server per binder. Until you move a card, the pages simply follow the starting order.
const POCKETS=[4,9,12,16], PK_COLS={4:2,9:3,12:3,16:4};
const RAR_RANK=["Common","Uncommon","Rare","Reverse Holo","Holo","Rare Holo","Rare Shining","Rare Holo EX","Rare Ultra","Rare Secret"];
function pageOrders(){
  const o=[["num", isDex(state.sid) ? "Release date" : isOwn(state.sid) ? "Set and number" : "Set number"],
           ["rarity","Rarity"],["dex","Pokédex number"],["type","Pokémon, then Trainers and Energy"],["value","Value, high to low"]];
  if(!isPrivate()) o.push(["owned","Owned first"]);
  if(isOwn(state.sid)) o.unshift(["added","Order added"]);
  return o;
}
const defaultOrder = () => isOwn(state.sid) ? "added" : "num";
function orderCards(order){
  const base=state.cards.slice();
  if(order==="num" && isOwn(state.sid)) base.sort((a,b)=>(a.date||"").localeCompare(b.date||"") || (a.set||"").localeCompare(b.set||"") || (numVal(a.num||a.n)[1]-numVal(b.num||b.n)[1]));
  const pos=new Map(base.map((c,i)=>[c.n,i])), by=f=>base.slice().sort((a,b)=>f(a,b) || pos.get(a.n)-pos.get(b.n));
  if(order==="rarity"){ const r=c=>{ const i=RAR_RANK.indexOf(c.rarity); return i<0 ? RAR_RANK.length+(c.rarity?0:1) : i; }; return by((a,b)=>r(a)-r(b)); }
  if(order==="dex"){ loadDexNums(); return by((a,b)=>(a.dex||99999)-(b.dex||99999)); }
  if(order==="type"){ const t=c=>c.type==="Pokémon"?0:c.type==="Trainer"?1:c.type==="Energy"?2:c.custom?4:3; return by((a,b)=>t(a)-t(b)); }
  if(order==="value") return by((a,b)=>basePrice(b.n)-basePrice(a.n));
  if(order==="owned") return by((a,b)=>(qty(b.n)>0)-(qty(a.n)>0));
  return base;
}
// Pokédex numbers come from the server only when the Pokédex order is picked.
let dexNumsFor=null;
function loadDexNums(){
  const sid=state.sid; if(dexNumsFor===sid || !state.ready) return;
  dexNumsFor=sid;
  fetch("api/set/"+enc(sid)+"/dexnums").then(r=>r.json()).then(j=>{
    if(state.sid!==sid) return;
    if(!j.ready){ dexNumsFor=null; return; }
    for(const c of state.cards) if(j.dex[c.n]) c.dex=j.dex[c.n];
    if(state.view==="pages") drawPages();
    if(state.open && $("dlg").open){ const sp=cardSpot(state.open); if(sp) setSpot(sp.text); }
  }).catch(()=>{ dexNumsFor=null; });
}
function pageLayout(){
  const L=state.layout||{}, pk=POCKETS.includes(+L.pockets) ? +L.pockets : 9;
  const order=pageOrders().some(o=>o[0]===L.order) ? L.order : defaultOrder();
  const ordered=orderCards(order).map(c=>c.n), have=new Set(ordered);
  let slots, custom=Array.isArray(L.slots);
  if(custom){
    slots=L.slots.map(x=>x && have.has(x) ? x : null);
    const placed=new Set(slots.filter(Boolean)), more=ordered.filter(n=>!placed.has(n));   // new cards go at the end
    if(more.length){ while(slots.length && slots[slots.length-1]==null) slots.pop(); slots=slots.concat(more); }
  } else slots=ordered;
  return {pk, order, slots, custom};
}
const sideName = i => "Page "+(i+1);   // every side of a sheet is its own page number: 1, 2, 3, 4… (page 1 is the front of the first sheet)
function cardSpot(n){
  const L=pageLayout(), i=L.slots.indexOf(n); if(i<0) return null;
  const side=Math.floor(i/L.pk), k=i%L.pk, cols=PK_COLS[L.pk];
  return {side, text:sideName(side)+", row "+(Math.floor(k/cols)+1)+", pocket "+(k%cols+1)};
}
const pg={at:-1, arr:false, sel:-1, saveT:null, flash:null};
function saveLayout(next){
  const was=state.layout||{};   // keep the cover pick and color choice through other layout saves
  if(!("cover" in next) && was.cover) next={...next, cover:was.cover};
  if(!("allColor" in next) && was.allColor) next={...next, allColor:true};
  state.layout=next; rememberSlots();
  clearTimeout(pg.saveT);
  pg.saveT=setTimeout(()=>{
    const sid=state.sid;
    fetch("api/set/"+enc(sid)+"/layout",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(next)})
      .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save the pages"); }))
      .catch(err=>toast((err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't save the pages.", "Try again", ()=>saveLayout(next)));
  },350);
}
function pocket(n, i, L){
  const c=n ? state.cards.find(x=>x.n===n) : null;
  const b=document.createElement("button"); b.type="button"; b.className="pk"; b.dataset.i=i;
  if(!c){ b.classList.add("gap"); b.setAttribute("aria-label","Empty pocket"); if(!pg.arr) b.tabIndex=-1; }
  else {
    const priv=isPrivate(), own=qty(n)>0; if(!own && !priv) b.classList.add("need");
    b.dataset.price=!own && !priv && basePrice(n) ? money0(basePrice(n)) : "";
    const no=document.createElement("span"); no.className="pk-no"; no.textContent=label(c);
    const im=document.createElement("img"); im.alt=""; im.loading="lazy"; im.decoding="async"; im.draggable=false; im.src=base()+"/img/"+enc(n)+".png";
    im.onerror=()=>{ if(!im.dataset.r && c.img){ im.dataset.r=1; im.src=smallImg(c.img); } else im.remove(); };
    const nm=document.createElement("span"); nm.className="pk-nm"; nm.textContent=c.name;
    b.append(no,im,nm);
    b.setAttribute("aria-label",c.name+" "+label(c)+(priv ? "" : ", "+(own?"owned":"needed")));
  }
  if(i===pg.sel) b.classList.add("sel");
  if(n && n===pg.flash) b.classList.add("flash");
  return b;
}
function sideEl(i, L){
  const box=document.createElement("div"); box.className="pg-side"; box.dataset.side=i;
  const g=document.createElement("div"); g.className="pg-grid"; g.style.gridTemplateColumns="repeat("+PK_COLS[L.pk]+",minmax(0,1fr))";
  let own=0, cards=0, cost=0;
  for(let k=0;k<L.pk;k++){
    const idx=i*L.pk+k, n=L.slots[idx]||null; g.append(pocket(n, idx, L));
    if(n){ cards++; if(qty(n)>0) own++; else cost+=basePrice(n); }
  }
  const f=document.createElement("div"); f.className="pg-foot";
  const a=document.createElement("b"); a.textContent=sideName(i);
  const r=document.createElement("span"); r.textContent=!cards ? "Empty" : isPrivate() ? cards+" card"+(cards===1?"":"s") : own+" of "+cards+" owned";
  if(cost>0){ const c=document.createElement("span"); c.className="cost"; c.textContent=" · "+money0(cost)+" to fill"; r.append(c); }
  f.append(a,r); box.append(g,f); return box;
}
const pagesWide = () => matchMedia("(min-width:760px)").matches;
// The inside cover, styled like the vintage binder covers: the featured card's own painted scene fills the
// cover, the Pokémon stands in front with a soft glow, and the set's logo sits near the bottom. Until the card
// picture is on the server, the set's colors and rays of light stand in for the scene. The featured Pokémon is one of the binder's hits
// (its most valuable Pokémon cards), drawn with Ken Sugimori's official artwork like the vintage binders
// (shiny colors for Shining cards).
// The small round buttons switch between the hits; the pick is saved with the binder's pages.
// Colors [light, deep, band, band edge]: the four Neo sets have their own; other sets take theirs from the logo.
const COVER_STYLE={neo1:["#f6f7fa","#bfc5d0","#a3a9b4","#5c626d"], neo2:["#ecf7dc","#7fc06a","#3f8a4a","#1f4d2a"],
  neo3:["#ffe27a","#ee6a2c","#c63c1f","#6e1a10"], neo4:["#ffe24d","#e8407a","#f39a4c","#6a2a6e"]};
const coverStyleCache={}, coverDex={};
const RARE_RANK = r => /Shining|Secret|Crystal|Gold Star|Star/.test(r) ? 4 : /Holo/.test(r) ? 3 : /Rare/.test(r) ? 2 : /Uncommon/.test(r) ? 1 : 0;
function coverHits(){
  return state.cards.filter(c=>!c.custom && (c.type==="Pokémon" || isDex(state.sid)))
    .sort((a,b)=>(basePrice(b.n)-basePrice(a.n)) || (RARE_RANK(b.rarity||"")-RARE_RANK(a.rarity||""))).slice(0,3);
}
const cardGid = c => (isMulti(state.sid) || c.extra) ? c.n : state.sid+"-"+c.n;
const isShining = c => /Shining/.test((c.rarity||"")+" "+c.name);
function hitDex(c){ return isDex(state.sid) ? +String(state.sid).slice(4) : coverDex[cardGid(c)]; }
// Pokédex numbers for the hits are asked for once, then the cover redraws.
let coverAsking=false;
function loadCoverDex(hits){
  const need=hits.map(cardGid).filter(g=>!(g in coverDex));
  if(!need.length || coverAsking || isDex(state.sid)) return;
  coverAsking=true;
  fetch("api/covernums?c="+enc(need.join(","))).then(r=>r.json()).then(j=>{
    for(const g of need) coverDex[g]=(j.dex||{})[g]||0;
    coverAsking=false; if(state.view==="pages") drawPages();
  }).catch(()=>{ coverAsking=false; });
}
// The logo's two strongest hues, turned into cover colors.
function logoStyle(img){
  try{
    const w=48, h=Math.max(8,Math.round(48*img.naturalHeight/Math.max(1,img.naturalWidth)));
    const cv=document.createElement("canvas"); cv.width=w; cv.height=h; const g=cv.getContext("2d"); g.drawImage(img,0,0,w,h);
    const d=g.getImageData(0,0,w,h).data, bins={};
    for(let i=0;i<d.length;i+=4){
      if(d[i+3]<200) continue;
      const r=d[i]/255, gg=d[i+1]/255, b=d[i+2]/255, mx=Math.max(r,gg,b), mn=Math.min(r,gg,b), l=(mx+mn)/2, sat=mx===mn?0:(mx-mn)/(1-Math.abs(2*l-1));
      if(sat<.35 || l<.15 || l>.85) continue;
      let hue=mx===r?((gg-b)/(mx-mn))%6:mx===gg?(b-r)/(mx-mn)+2:(r-gg)/(mx-mn)+4; hue=(hue*60+360)%360;
      const k=Math.round(hue/30)%12; bins[k]=(bins[k]||0)+1;
    }
    const top=Object.entries(bins).sort((a,b)=>b[1]-a[1]).map(x=>+x[0]*30);
    if(!top.length) return null;
    const h1=top[0], h2=top.find(x=>Math.min(Math.abs(x-h1),360-Math.abs(x-h1))>=60) ?? (h1+40)%360;
    return ["hsl("+h1+" 80% 88%)", "hsl("+h2+" 60% 62%)", "hsl("+h1+" 60% 58%)", "hsl("+h1+" 50% 26%)"];
  }catch(_){ return null; }
}
function setCoverStyle(cv, st){ ["--v1","--v2","--v3","--v4"].forEach((k,i)=>cv.style.setProperty(k, st[i])); }
function coverArt(c, cls){
  const d=hitDex(c), im=document.createElement("img"); im.className=cls; im.alt=c.name; im.decoding="async"; im.draggable=false;
  if(d) im.src="art/"+d+(isShining(c) ? "s" : "")+".png"; else if(cls==="vb-mon") im.classList.add("no-art");
  im.onerror=()=>{
    if(/\/art\/\d+s\.png$/.test(im.src)) im.src="art/"+d+".png";   // no shiny art: use the usual colors
    else if(cls==="vb-dot" && !/\/img\//.test(im.src)){ im.classList.add("card"); im.src=base()+"/img/"+enc(c.n)+".png"; }   // no artwork: the card's picture
    else { im.classList.add("no-art"); const cv=im.closest(".vb-cover"); if(cv && cls==="vb-mon") cv.classList.add("no-mon"); }
  };
  if(!d){ if(cls==="vb-dot"){ im.classList.add("card"); im.src=base()+"/img/"+enc(c.n)+".png"; } }
  return im;
}
function coverEl(){
  const cv=document.createElement("div"); cv.className="pg-side cover vb-cover";
  const s=state.set||{}, sid=state.sid, dex=isDex(sid), own=isOwn(sid);
  const st=COVER_STYLE[sid] || coverStyleCache[sid]; if(st) setCoverStyle(cv, st);
  if(!dex && !own){
    const im=document.createElement("img"); im.alt=s.name||""; im.className="vb-logo"; im.decoding="async";
    im.onload=()=>{ if(!COVER_STYLE[sid] && !coverStyleCache[sid]){ const c=logoStyle(im); if(c){ coverStyleCache[sid]=c; setCoverStyle(cv, c); } } };
    im.onerror=()=>{ const t=document.createElement("div"); t.className="vb-name"; t.textContent=s.name||""; im.replaceWith(t); };
    im.src=base()+"/logo.png"; cv.append(im);
  } else { const t=document.createElement("div"); t.className="vb-name"; t.textContent=s.name||""; cv.append(t); }
  const hits=coverHits(), L=state.layout||{};
  const feat=state.cards.find(c=>c.n===L.cover && !c.custom) || hits[0];
  loadCoverDex(feat && !hits.includes(feat) ? hits.concat(feat) : hits);
  if(feat){   // the featured card's own painted scene fills the cover, with the Pokémon standing in front
    const sc=document.createElement("div"); sc.className="vb-scene"; sc.setAttribute("aria-hidden","true");
    const w=document.createElement("div"), im=document.createElement("img"); im.alt=""; im.decoding="async"; im.draggable=false;
    im.onload=()=>cv.classList.add("has-scene"); im.onerror=()=>sc.remove();
    im.src=base()+"/img/"+enc(feat.n)+".png?full=1"; w.append(im); sc.append(w); cv.prepend(sc);
    cv.append(coverArt(feat,"vb-mon"));
  }
  if(hits.length>1){
    const pick=document.createElement("div"); pick.className="vb-pick"; pick.setAttribute("role","group"); pick.setAttribute("aria-label","Cover Pokémon");
    for(const c of hits){
      const b=document.createElement("button"); b.type="button"; b.title=b.ariaLabel="Show "+c.name+" on the cover";
      b.setAttribute("aria-pressed", String(c===feat)); b.append(coverArt(c,"vb-dot"));
      b.onclick=()=>{ const P=pageLayout(); saveLayout({pockets:P.pk, order:P.order, slots:P.custom ? P.slots : null, cover:c.n}); drawPages(); };
      pick.append(b);
    }
    cv.append(pick);
  }
  return cv;
}
function drawPages(){
  const V=$("pgView"); if(!V || state.view!=="pages") return;
  const L=pageLayout(), sides=Math.max(1, Math.ceil(L.slots.length/L.pk));
  $("pgPk").value=String(L.pk);
  const os=$("pgOrder"); os.replaceChildren();
  for(const [v,t] of pageOrders()){ const o=document.createElement("option"); o.value=v; o.textContent="Order: "+t; os.append(o); }
  os.value=L.order;
  const allColor=!!(state.layout && state.layout.allColor);
  $("pgColor").setAttribute("aria-pressed", allColor); $("pgColor").hidden=isPrivate(); V.classList.toggle("all-color", allColor);
  $("pgArr").setAttribute("aria-pressed", pg.arr); $("pgArr").textContent=pg.arr ? "Done arranging" : "Arrange";
  const sheets=Math.ceil(sides/2), cards=L.slots.filter(Boolean).length;
  $("pgSum").textContent = !cards ? "No cards yet." :
    cards+" card"+(cards===1?"":"s")+" fill "+sides+" page"+(sides===1?"":"s")+" of "+L.pk+" pockets ("+sheets+" sheet"+(sheets===1?"":"s")+", front and back)."+(pagesWide() ? " Page 1 is on the right, after the inside cover." : " Swipe to turn the page.")
    +(L.custom ? " You've moved some cards: new cards go at the end." : "")
    +(pg.arr ? " Tap a card, then tap where it should go"+(matchMedia("(pointer:fine)").matches ? ", or drag it there." : ".") : "");
  V.replaceChildren(); V.classList.toggle("pg-arr", pg.arr);
  pg.at=Math.max(pagesWide() ? 0 : -1, Math.min(pg.at, sides-1));   // phones: -1 is the inside cover
  if(pagesWide()){
    const wrap=document.createElement("div"); wrap.className="pg-spreads";
    for(let s=-1; s<sides; s+=2){   // [inside cover | page 1], [page 2 | page 3], ...
      const sp=document.createElement("div"); sp.className="pg-spread";
      if(s<0) sp.append(coverEl());
      else sp.append(sideEl(s, L));
      if(s+1<sides) sp.append(sideEl(s+1, L));
      else { const e=document.createElement("div"); e.className="pg-side cover"; e.textContent="Back cover"; sp.append(e); }
      wrap.append(sp);
    }
    V.append(wrap);
  } else {
    V.append(pg.at<0 ? coverEl() : sideEl(pg.at, L));
    const nav=document.createElement("div"); nav.className="pg-pager";
    const prev=document.createElement("button"); prev.type="button"; prev.className="icon-btn"; prev.setAttribute("aria-label","Previous page"); prev.disabled=pg.at===0;
    prev.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
    const next=document.createElement("button"); next.type="button"; next.className="icon-btn"; next.setAttribute("aria-label","Next page"); next.disabled=pg.at>=sides-1;
    prev.disabled=pg.at<0;
    next.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>';
    // where you are, then one button per page
    const lab=document.createElement("div"); lab.className="pg-where"; lab.setAttribute("aria-live","polite");
    const lb=document.createElement("b"); lb.textContent=pg.at<0 ? "Inside cover" : sideName(pg.at); const ls=document.createElement("span"); ls.textContent=pg.at<0 ? sides+" page"+(sides===1?"":"s")+" after this" : (pg.at+1)+" of "+sides;
    lab.append(lb,ls);
    prev.onclick=()=>{ pg.at--; drawPages(); }; next.onclick=()=>{ pg.at++; drawPages(); };
    nav.append(prev,lab,next); V.append(nav);
    const strip=document.createElement("div"); strip.className="pg-strip"; strip.setAttribute("role","group"); strip.setAttribute("aria-label","Pages");
    const cb=document.createElement("button"); cb.type="button"; cb.className="cv"; cb.textContent="Cover"; if(pg.at<0) cb.setAttribute("aria-current","true");
    cb.onclick=()=>{ pg.at=-1; drawPages(); }; strip.append(cb);
    for(let p=0;p<sides;p++){
      const b=document.createElement("button"); b.type="button"; b.textContent=p+1;
      const here=pg.at===p; if(here) b.setAttribute("aria-current","true");
      b.setAttribute("aria-label","Page "+(p+1)+(here?", showing":""));
      b.onclick=()=>{ pg.at=p; drawPages(); };
      strip.append(b);
    }
    V.append(strip);
    const cur=strip.querySelector("[aria-current]"); if(cur) requestAnimationFrame(()=>cur.scrollIntoView({block:"nearest",inline:"center"}));
  }
  pgBar();
  if(pg.flash){ const f=V.querySelector(".pk.flash"); if(f) f.scrollIntoView({block:"center", behavior:"smooth"}); setTimeout(()=>{ pg.flash=null; },1700); }
}
function pgBar(){
  const L=pageLayout(), on=pg.arr && pg.sel>=0, n=on ? L.slots[pg.sel] : null;
  $("pgBar").hidden=!on; if(!on) return;
  const c=n && state.cards.find(x=>x.n===n);
  $("pgBarText").textContent=c ? c.name+" "+label(c)+" picked up. Tap where it should go." : "Empty pocket picked. Tap a card to move it here, or remove the gap.";
  $("pgGap").hidden=!c; $("pgUngap").hidden=!!c;
}
// Move the card at index a to pocket b (swapping with whatever is there).
function pgMove(a, b){
  const L=pageLayout(); if(a===b || a<0 || b<0) return;
  const s=L.slots.slice(); while(s.length<=Math.max(a,b)) s.push(null);
  [s[a], s[b]]=[s[b], s[a]];
  while(s.length && s[s.length-1]==null) s.pop();
  pg.sel=-1; saveLayout({pockets:L.pk, order:L.order, slots:s}); drawPages();
}
$("pgView").addEventListener("click",e=>{
  const b=e.target.closest(".pk"); if(!b || pg.drag) return;
  const i=+b.dataset.i, n=pageLayout().slots[i];
  if(!pg.arr){ if(n) openCard(n); return; }
  if(pg.sel<0){ pg.sel=i; drawPages(); return; }
  if(pg.sel===i){ pg.sel=-1; drawPages(); return; }
  pgMove(pg.sel, i);
});
$("pgColor").onclick=()=>{ const P=pageLayout(); saveLayout({pockets:P.pk, order:P.order, slots:P.custom ? P.slots : null, allColor:!(state.layout && state.layout.allColor)}); drawPages(); };
$("pgArr").onclick=()=>{ pg.arr=!pg.arr; pg.sel=-1; drawPages(); };
$("pgDone").onclick=()=>{ pg.sel=-1; drawPages(); };
$("pgGap").onclick=()=>{   // push this card (and everything after it) one pocket along, leaving an empty pocket
  const L=pageLayout(), s=L.slots.slice(); if(pg.sel<0) return;
  s.splice(pg.sel,0,null); pg.sel++; saveLayout({pockets:L.pk, order:L.order, slots:s}); drawPages();
};
$("pgUngap").onclick=()=>{
  const L=pageLayout(), s=L.slots.slice(); if(pg.sel<0 || s[pg.sel]) return;
  s.splice(pg.sel,1); pg.sel=-1; saveLayout({pockets:L.pk, order:L.order, slots:s}); drawPages();
};
$("pgPk").onchange=()=>{ const L=pageLayout(); saveLayout({pockets:+$("pgPk").value, order:L.order, slots:L.custom ? L.slots : null}); pg.sel=-1; drawPages(); };
$("pgOrder").onchange=async()=>{
  const L=pageLayout(), v=$("pgOrder").value;
  if(L.custom){
    const ok=await askConfirm("Start the pages over?", "Order: "+(pageOrders().find(o=>o[0]===v)||[,v])[1], "Start over",
      {body:Object.assign(document.createElement("div"),{className:"note",textContent:"Every card goes back into this order, and the cards you moved go back too."})});
    if(!ok){ $("pgOrder").value=L.order; return; }
  }
  pg.sel=-1; saveLayout({pockets:L.pk, order:v, slots:null}); drawPages();
};
// Drag a card to another pocket while arranging, with a mouse. (On touch screens it's tap, then tap,
// so a finger on the pages still scrolls.)
$("pgView").addEventListener("pointerdown",e=>{
  if(!pg.arr || e.pointerType==="touch" || (e.button!==undefined && e.button!==0)) return;
  const b=e.target.closest(".pk"); if(!b || b.classList.contains("gap")) return;
  const from=+b.dataset.i, x0=e.clientX, y0=e.clientY, id=e.pointerId;
  let ghost=null, hit=null;
  const move=ev=>{
    if(ev.pointerId!==id) return;
    if(!ghost){
      if(Math.hypot(ev.clientX-x0, ev.clientY-y0)<8) return;
      pg.drag=true; ghost=document.createElement("div"); ghost.className="pk-ghost";
      const im=b.querySelector("img"); if(im) ghost.append(im.cloneNode());
      document.body.append(ghost); b.classList.add("sel");
      try{ b.releasePointerCapture(id); }catch(_){}
    }
    ev.preventDefault();
    ghost.style.left=ev.clientX+"px"; ghost.style.top=ev.clientY+"px";
    const t=document.elementFromPoint(ev.clientX, ev.clientY), p=t && t.closest("#pgView .pk");
    if(hit && hit!==p) hit.classList.remove("hit");
    hit=p && p!==b ? p : null; if(hit) hit.classList.add("hit");
  };
  const end=ev=>{
    if(ev.pointerId!==id) return;
    window.removeEventListener("pointermove",move); window.removeEventListener("pointerup",end); window.removeEventListener("pointercancel",end);
    if(!ghost) return;
    ghost.remove(); b.classList.remove("sel");
    if(hit && ev.type==="pointerup") pgMove(from, +hit.dataset.i); else drawPages();
    setTimeout(()=>{ pg.drag=false; },0);
  };
  window.addEventListener("pointermove",move,{passive:false}); window.addEventListener("pointerup",end); window.addEventListener("pointercancel",end);
});
// Phones: swipe left or right to turn the page (not while arranging).
(()=>{
  let x0=null, y0=0;
  $("pgView").addEventListener("touchstart",e=>{
    x0=null;
    if(pg.arr || pagesWide()) return;
    if(e.target.closest(".pg-strip, .pg-pager")) return;   // swiping the page-number row only scrolls it; it never turns the page
    const t=e.touches[0]; x0=t.clientX; y0=t.clientY;
  },{passive:true});
  $("pgView").addEventListener("touchend",e=>{
    if(x0==null) return; const t=e.changedTouches[0], dx=t.clientX-x0, dy=t.clientY-y0; x0=null;
    if(Math.abs(dx)<60 || Math.abs(dx)<Math.abs(dy)*1.5) return;
    const sides=Math.max(1, Math.ceil(pageLayout().slots.length/pageLayout().pk));
    const to=pg.at+(dx<0?1:-1); if(to<-1 || to>=sides) return;
    pg.at=to; drawPages();
  });
})();
matchMedia("(min-width:760px)").addEventListener("change",()=>{ if(state.view==="pages") drawPages(); });
// From card details: jump to the card's pocket.
$("dSpot").onclick=()=>{
  const n=state.open, sp=cardSpot(n); if(!sp) return;
  $("dlg").close(); pg.at=sp.side; pg.flash=n; setView("pages");
};

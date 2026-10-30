// Stats charts and the zoomed card with its holo shimmer.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- stats ----------
function loadStats(){
  return fetch("api/spending").then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error); return j; })).then(sp=>{ state.spend=sp; state.spendStale=false; drawStats(); })
    .catch(()=>{ $("chLine").replaceChildren(retryNote("Couldn't load spending. "+offlineHint(), ()=>{ $("chLine").replaceChildren(note("Loading…")); loadStats(); })); });
}
function note(t){ const d=document.createElement("div"); d.className="empty-note"; d.textContent=t; return d; }
function drawStats(){
  const sp=state.spend; if(!sp) return;
  const T=sp.totals, gain=T.value-T.spent;
  $("tSpent").textContent=money0(T.spent);
  $("tSpentN").textContent=T.purchases+" purchase"+(T.purchases===1?"":"s")+(T.undated?" · "+T.undated+" undated":"");
  $("tValue").textContent=money0(T.value);
  $("tGain").replaceChildren();
  if(T.spent>0){ const s=document.createElement("span"); s.className=gain>=0?"pos":"neg"; s.textContent=(gain>=0?"+":"−")+money0(Math.abs(gain)); $("tGain").append(s, " vs. paid"); }
  else $("tGain").textContent="Log purchases to compare";
  const thisM=todayStr().slice(0,7), mo=sp.months.find(m=>m.m===thisM);
  $("tMonth").textContent=money0(mo?mo.spent:0); $("tMonthN").textContent=(mo?mo.count:0)+" purchase"+((mo&&mo.count===1)?"":"s");
  const avg=sp.months.length ? sp.months.reduce((a,m)=>a+m.spent,0)/sp.months.length : 0;
  $("tAvg").textContent=money0(avg); $("tAvgN").textContent=sp.months.length ? "over "+sp.months.length+" month"+(sp.months.length===1?"":"s") : "No dated purchases yet";
  drawLine(sp.timeline); drawMovers(); drawBars(sp.months); drawLog(sp.log);   // movers first: it decides how wide the spending chart is
}
const NS="http://www.w3.org/2000/svg";
function el(tag, attrs, text){ const e=document.createElementNS(NS,tag); for(const k in attrs) e.setAttribute(k,attrs[k]); if(text!=null) e.textContent=text; return e; }
function niceStep(v){ if(v<=0) return 1; const p=Math.pow(10,Math.floor(Math.log10(v))); for(const m of [1,1.5,2,2.5,3,4,5,6,8,10]) if(m*p>=v) return m*p; return 10*p; }
function niceMax(v){ return niceStep(v/4)*4; }  // 4 even gridline steps
const shortMoney = v => v>=1000 ? "$"+(v/1000).toFixed(v>=10000?0:1)+"k" : "$"+Math.round(v);
function drawLine(tl){
  const box=$("chLine"); box.replaceChildren();
  if(!tl || !tl.length){ box.append(note("Nothing to chart yet. This fills in as you add cards and prices are checked each night.")); return; }
  const legend=document.createElement("div"); legend.className="legend";
  legend.innerHTML='<span><i></i>Collection value</span><span><i class="dash"></i>Total spent</span>';
  if(tl.length<2){
    box.append(legend, note("Today: value "+money(tl[0].value)+", spent "+money(tl[0].spent)+". The chart fills in as "+srv()+" saves prices each day."));
    return;
  }
  const W=820,H=260,L=56,R=110,Tp=14,B=30;
  const xs=tl.map(p=>new Date(p.d+"T12:00:00").getTime());
  const x0=xs[0], x1=xs[xs.length-1];
  const ymax=niceMax(Math.max(...tl.map(p=>Math.max(p.value,p.spent)))*1.05);
  const X=t=>L+(t-x0)/(x1-x0||1)*(W-L-R), Y=v=>Tp+(1-v/ymax)*(H-Tp-B);
  const svg=el("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":"Collection value and total spent over time"});
  for(let i=0;i<=4;i++){ const v=ymax*i/4, y=Y(v);
    svg.append(el("line",{x1:L,x2:W-R,y1:y,y2:y,stroke:"var(--line)","stroke-width":1}));
    svg.append(el("text",{x:L-8,y:y+4,"text-anchor":"end","font-size":12,fill:"var(--muted)","font-family":"var(--f-mono)"},shortMoney(v))); }
  const ticks=Math.min(6,tl.length);
  for(let i=0;i<ticks;i++){ const idx=Math.round(i*(tl.length-1)/Math.max(1,ticks-1)); const d=new Date(tl[idx].d+"T12:00:00");
    svg.append(el("text",{x:X(xs[idx]),y:H-8,"text-anchor":i===0?"start":i===ticks-1?"end":"middle","font-size":12,fill:"var(--muted)"},d.toLocaleDateString("en-US",{month:"short",day:"numeric"}))); }
  const path=k=>tl.map((p,i)=>(i?"L":"M")+X(xs[i]).toFixed(1)+","+Y(p[k]).toFixed(1)).join("");
  svg.append(el("path",{d:path("spent"),fill:"none",stroke:"var(--muted)","stroke-width":2,"stroke-dasharray":"6 5","stroke-linejoin":"round"}));
  svg.append(el("path",{d:path("value"),fill:"none",stroke:"var(--dark)","stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"}));
  const last=tl[tl.length-1]; let yv=Y(last.value), ys=Y(last.spent);
  if(Math.abs(yv-ys)<30){ if(yv<=ys){ yv-=8; ys+=8; } else { yv+=8; ys-=8; } }
  svg.append(el("circle",{cx:X(x1),cy:Y(last.value),r:4,fill:"var(--dark)",stroke:"var(--surface)","stroke-width":2}));
  svg.append(el("text",{x:X(x1)+10,y:yv-2,"font-size":12,fill:"var(--muted)"},"Value"));
  svg.append(el("text",{x:X(x1)+10,y:yv+13,"font-size":13,fill:"var(--ink)","font-family":"var(--f-mono)"},shortMoney(last.value)));
  svg.append(el("text",{x:X(x1)+10,y:ys-2,"font-size":12,fill:"var(--muted)"},"Spent"));
  svg.append(el("text",{x:X(x1)+10,y:ys+13,"font-size":13,fill:"var(--ink)","font-family":"var(--f-mono)"},shortMoney(last.spent)));
  const cross=el("line",{x1:0,x2:0,y1:Tp,y2:H-B,stroke:"var(--muted)","stroke-width":1,opacity:0});
  const hv=el("circle",{r:5,fill:"var(--dark)",stroke:"var(--surface)","stroke-width":2,opacity:0});
  const hit=el("rect",{x:L,y:Tp,width:W-L-R,height:H-Tp-B,fill:"transparent"});
  svg.append(cross,hv,hit);
  const tip=document.createElement("div"); tip.className="tip"; tip.hidden=true;
  hit.addEventListener("pointermove",e=>{
    const r=svg.getBoundingClientRect(), sx=(e.clientX-r.left)/r.width*W;
    let i=0, best=1e18; xs.forEach((t,k)=>{ const dd=Math.abs(X(t)-sx); if(dd<best){ best=dd; i=k; } });
    const p=tl[i], cx=X(xs[i]);
    cross.setAttribute("x1",cx); cross.setAttribute("x2",cx); cross.setAttribute("opacity",.5);
    hv.setAttribute("cx",cx); hv.setAttribute("cy",Y(p.value)); hv.setAttribute("opacity",1);
    tip.hidden=false; tip.innerHTML="";
    const b=document.createElement("b"); b.textContent=fmtDay(p.d); tip.append(b, document.createElement("br"), "Value "+money(p.value), document.createElement("br"), "Spent "+money(p.spent));
    tip.style.left=(cx/W*r.width)+"px"; tip.style.top=(Y(p.value)/H*r.height)+"px";
  });
  hit.addEventListener("pointerleave",()=>{ tip.hidden=true; cross.setAttribute("opacity",0); hv.setAttribute("opacity",0); });
  box.append(legend,svg,tip);
}
function drawBars(months){
  const box=$("chBars"); box.replaceChildren();
  if(!months.length){ box.append(note("Log a purchase with a date to see monthly spending.")); return; }
  const ms=months.slice(-12);
  const H=220,L=48,R=8,Tp=20,B=28, W=Math.max(420, Math.round((box.clientWidth||420)*H/260));   // wider box: wider drawing, same height (about 260px)
  const ymax=niceMax(Math.max(...ms.map(m=>m.spent))*1.1);
  const bw=(W-L-R)/ms.length, Y=v=>Tp+(1-v/ymax)*(H-Tp-B);
  const svg=el("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":"Spending per month"});
  for(let i=0;i<=4;i++){ const v=ymax*i/4, y=Y(v);
    svg.append(el("line",{x1:L,x2:W-R,y1:y,y2:y,stroke:"var(--line)","stroke-width":1}));
    svg.append(el("text",{x:L-8,y:y+4,"text-anchor":"end","font-size":12,fill:"var(--muted)","font-family":"var(--f-mono)"},shortMoney(v))); }
  const tip=document.createElement("div"); tip.className="tip"; tip.hidden=true;
  let prevYear="";
  ms.forEach((m,i)=>{
    const w=Math.min(36,bw-6), x=L+i*bw+(bw-w)/2, y=Y(m.spent), h=Math.max(0,H-B-y), r=Math.min(4,h);
    const d="M"+x+","+(H-B)+"V"+(y+r)+"Q"+x+","+y+" "+(x+r)+","+y+"H"+(x+w-r)+"Q"+(x+w)+","+y+" "+(x+w)+","+(y+r)+"V"+(H-B)+"Z";
    const bar=el("path",{d,fill:"var(--dark)"}); svg.append(bar);
    const dt=new Date(m.m+"-15T12:00:00"), yr=String(dt.getFullYear());
    svg.append(el("text",{x:x+w/2,y:H-10,"text-anchor":"middle","font-size":12,fill:"var(--muted)"},dt.toLocaleDateString("en-US",{month:"short"})+(yr!==prevYear&&i>0?" ’"+yr.slice(2):"")));
    prevYear=yr;
    if(i===ms.length-1) svg.append(el("text",{x:x+w/2,y:y-6,"text-anchor":"middle","font-size":12,fill:"var(--ink)","font-family":"var(--f-mono)"},shortMoney(m.spent)));
    const hit=el("rect",{x:L+i*bw,y:Tp,width:bw,height:H-Tp-B,fill:"transparent"});
    hit.addEventListener("pointerenter",()=>{ const r=svg.getBoundingClientRect(); tip.hidden=false; tip.innerHTML="";
      const b=document.createElement("b"); b.textContent=dt.toLocaleDateString("en-US",{month:"long",year:"numeric"});
      tip.append(b,document.createElement("br"),money(m.spent)+" · "+m.count+" purchase"+(m.count===1?"":"s"));
      tip.style.left=((x+w/2)/W*r.width)+"px"; tip.style.top=(y/H*r.height)+"px"; bar.setAttribute("opacity",.8); });
    hit.addEventListener("pointerleave",()=>{ tip.hidden=true; bar.setAttribute("opacity",1); });
    svg.append(hit);
  });
  box.append(svg,tip);
}
function drawMovers(){
  const box=$("movers"); box.replaceChildren();
  $("moversTitle").textContent="Biggest movers · "+periodName().toLowerCase()+" · "+(state.set.name||"");
  const rows=state.cards.map(c=>({c,t:trend(c.n)})).filter(r=>r.t && r.t.from>=1 && Math.abs(r.t.pct)>=0.5);
  $("stTwo").classList.toggle("mv-empty", !rows.length);   // nothing moved: spending gets the full row, movers shrinks to one line
  if(!rows.length){
    const first=state.histFirst;
    box.append(note(first ? "No price changes yet. Prices have been saved daily since "+fmtDay(first)+"." : "Movers appear once "+srv()+" has saved prices for a few days."));
    return;
  }
  const up=rows.filter(r=>r.t.pct>0).sort((a,b)=>b.t.pct-a.t.pct).slice(0,5);
  const down=rows.filter(r=>r.t.pct<0).sort((a,b)=>a.t.pct-b.t.pct).slice(0,5);
  const g=document.createElement("div"); g.className="mv";
  const section=(title,list)=>{ if(!list.length) return; const h=document.createElement("h3"); h.textContent=title; g.append(h);
    for(const {c,t} of list){ const b=document.createElement("button"); b.type="button"; b.textContent=c.name; b.onclick=()=>openCard(c.n);
      const p=document.createElement("span"); p.className="p"; p.textContent=money(t.to); g.append(b,p,trendEl(t)); } };
  section("Going up",up); section("Going down",down);
  box.append(g);
}
function drawLog(log){
  const body=$("logBody"); body.replaceChildren();
  if(!log.length){ const tr=document.createElement("tr"); const td=document.createElement("td"); td.colSpan=6; td.className="empty"; td.textContent="No purchases logged yet. Tap Need on a card, or open a card and add a purchase."; tr.append(td); body.append(tr); return; }
  for(const r of log.slice(0,200)){
    const tr=document.createElement("tr");
    const c1=document.createElement("td"); c1.textContent=fmtDay(r.d); c1.style.whiteSpace="nowrap";
    const c2=document.createElement("td"); const nb=document.createElement("button"); nb.type="button"; nb.className="nm"; nb.textContent=r.name;
    nb.onclick=()=>{ if(r.set===state.sid) openCard(r.n); else { openSet(r.set).then(()=>openCard(r.n)); } }; c2.append(nb);
    const c3=document.createElement("td"); c3.textContent=r.setName;
    const c4=document.createElement("td"); c4.textContent=r.where||"–"; if(!r.where) c4.className="nil";
    const c6=document.createElement("td"); const se=sellerEl(r.seller); if(se) c6.append(se); else { c6.textContent="–"; c6.className="nil"; }
    const c5=document.createElement("td"); c5.className="num"; c5.textContent=r.price?money(r.price):"Not set";
    tr.append(c1,c2,c3,c4,c6,c5); body.append(tr);
  }
}
// Tap the card picture to see it as big as the screen allows (handy for showing a vendor); tap again to close.
// Holo shimmer for the zoomed card. Older holos shine only in the art window, reverse holos everywhere but the art window;
// full-art and secret rares shine all over.
// Foil pattern by era: Starlight stars (Base, Jungle, Fossil), glitter (Shining cards), Cosmos dots (everything else).
function zoomFoil(c, sid){
  const W=$("zoomWrap"), r=(c && c.rarity) || "";
  W.className="zwrap"; W.removeAttribute("style");
  if(!c || c.custom) return;
  let set=String(sid||c.sid||""); if(/^dex-|^own-|^$/.test(set) && /^[a-z0-9.]+-/.test(c.n||"")) set=c.n.split("-")[0];   // mixed binders: the card's own set
  const svRare = r==="Rare" && /^(sv|me)\d/.test(set);   // since Scarlet & Violet, every Rare is a holo
  const holoR = svRare || /holo|shining|shiny|star|secret|ultra|rainbow|illustration|hyper|double rare|radiant|amazing|classic collection|legend|prime|break|ace spec|rare ace|pikachu rare|mega_attack|futuristic|black white/i.test(r);
  // your own copies marked Reverse holo: shine that way when every copy is one, or when the regular card has no foil at all
  const cps=(!c.sid || c.sid===state.sid) && state.own ? buys(c.n) : [], revN=cps.filter(b=>b.rev).length;
  const myRev = revN>0 && (revN===cps.length || !holoR);
  if(myRev){ W.classList.add("holo","rev","f-cosmos");
    artBox(set).forEach((v,i)=>W.style.setProperty(["--t","--r","--b","--l"][i], v+"%")); return; }
  if(!holoR) return;
  // whole-card foil: full arts, secret and shiny cards, the "big" cards (EX, GX, V, VMAX, VSTAR, LV.X, ex, Prime, LEGEND, BREAK),
  // and holo Trainers and Energy, whose picture doesn't sit where a Pokémon's art window is
  const whole=c.type==="Trainer" || c.type==="Energy" || /secret|ultra|rainbow|illustration|hyper|double rare|shiny|radiant|amazing|trainer gallery|mega_attack|futuristic|black white|prime|legend|break/i.test(r) || /\b(EX|ex|GX|V|VMAX|VSTAR|LV\.X)$/.test(r);
  // foil look: glitter (Shining), stars (Base, Jungle, Fossil), gold (Hyper Rares, gold secret rares), etched lines (full arts),
  // smooth (Illustration and Rainbow Rares), dots (everything else)
  const look = /shining/i.test(r) ? "f-glitter" : /^base[123]$/.test(set) ? "f-star"
    : /hyper rare/i.test(r) || (r==="Rare Secret" && /^(sm|swsh)/.test(set)) ? "f-gold"
    : /rare ultra|^ultra rare|shiny ultra|trainer gallery|special illustration|mega_attack/i.test(r) ? "f-etched"
    : r==="Illustration Rare" || r==="Rare Rainbow" ? "f-smooth" : "f-cosmos";
  W.classList.add("holo", look);
  if(/reverse holo/i.test(r)) W.classList.add("rev");
  if(!whole) artBox(set).forEach((v,i)=>W.style.setProperty(["--t","--r","--b","--l"][i], v+"%"));   // the art window
}
// Where the picture sits on a card (top, right, bottom, left in %), by card layout, measured on real scans.
const ART_BOXES=[
  [/^(base|gym|neo|si\d|basep|cel25c|me55c)/, [11,9.8,47.5,10.3]],   // 1999–2003 Wizards cards, and their Classic Collection reprints
  [/^ecard/,      [13,6.5,50,10]],     // e-card: Expedition, Aquapolis, Skyridge
  [/^(ex\d|pop|tk)/, [9,5.5,52,5.5]], // EX era: Ruby & Sapphire to Power Keepers, and the EX trainer kits
  [/^(dp|pl)/,    [9,5,48,5]],         // Diamond & Pearl, Platinum
  [/^(hgss|col|hsp)/, [11,3,46,3]],    // HeartGold & SoulSilver, Call of Legends
  [/^(bw|dv|mcd1[12])/, [10,6,47,6]], // Black & White, and McDonald's 2011–2012
  [/^(xy|g1|dc|mcd1[456])/, [10,6,46,6]], // XY, and McDonald's 2014–2016
  [/^(sm|det|mcd1[789])/, [10,7,48,7]], // Sun & Moon, and McDonald's 2017–2019
  [/^(swsh|cel25|pgo)/, [9.5,7,48,6]], // Sword & Shield
];
const artBox = set => (ART_BOXES.find(([re])=>re.test(set)) || [0,[10,7,49,6.5]])[1];   // Scarlet & Violet, Mega and anything newer
const zl={raf:0, held:false, tilt:null};
function zoomLight(t){
  const W=$("zoomWrap");
  if(!$("zoom").open || !W.classList.contains("holo")){ zl.raf=0; return; }
  if(!zl.held){
    const p=zl.tilt || [50+38*Math.sin(t/2600), 50+22*Math.cos(t/3250)];   // phone tilt, or a slow sweep
    W.style.setProperty("--mx",p[0].toFixed(1)); W.style.setProperty("--my",p[1].toFixed(1));
  }
  zl.raf=requestAnimationFrame(zoomLight);
}
new MutationObserver(()=>{   // start the light when the zoom opens on a holo card, stop it when it closes
  if($("zoom").open && $("zoomWrap").classList.contains("holo") && !zl.raf && !matchMedia("(prefers-reduced-motion: reduce)").matches) zl.raf=requestAnimationFrame(zoomLight);
}).observe($("zoom"),{attributes:true,attributeFilter:["open"]});
$("zoomWrap").addEventListener("pointermove",e=>{ const r=$("zoomWrap").getBoundingClientRect(); zl.held=true;
  $("zoomWrap").style.setProperty("--mx",((e.clientX-r.left)/r.width*100).toFixed(1)); $("zoomWrap").style.setProperty("--my",((e.clientY-r.top)/r.height*100).toFixed(1)); });
$("zoomWrap").addEventListener("pointerleave",()=>{ zl.held=false; });
addEventListener("deviceorientation",e=>{ if(e.gamma==null || !$("zoom").open) return; zl.tilt=[Math.max(0,Math.min(100,50+e.gamma*1.6)), Math.max(0,Math.min(100,50+(e.beta-45)*1.6))]; });
$("dArtBtn").onclick=()=>{ const a=$("dArt"); if(a.hidden || !a.currentSrc) return; $("zoomImg").src=a.currentSrc; $("zoomImg").alt=a.alt;
  const c=state.cards.find(x=>x.n===state.open);
  zoomFoil(a.dataset.r ? null : c, c && (c.sid || state.sid));   // no shimmer on the image site's stand-in card back
  $("zoom").showModal(); };
$("zoomImg").addEventListener("error",()=>zoomFoil(null));
$("zoom").onclick=()=>$("zoom").close();
$("dlg").addEventListener("close",()=>{ if($("zoom").open) $("zoom").close(); });
$("dlg").addEventListener("close",()=>{ if(state.view==="stats" && state.spendStale) loadStats(); if(state.view==="shop") drawShop(); });

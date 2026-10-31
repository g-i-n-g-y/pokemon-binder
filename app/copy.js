// My copy: sellers, purchases, condition, notes and photos.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- sellers ----------
const PLAT = {
  instagram:{label:"Instagram", tag:"IG", url:h=>"https://www.instagram.com/"+enc(h)+"/"},
  tiktok:{label:"TikTok", tag:"TT", url:h=>"https://www.tiktok.com/@"+enc(h)},
  facebook:{label:"Facebook", tag:"FB", url:h=>"https://www.facebook.com/"+enc(h)},
  x:{label:"X", tag:"X", url:h=>"https://x.com/"+enc(h)},
  whatnot:{label:"Whatnot", tag:"WN", url:h=>"https://www.whatnot.com/user/"+enc(h)},
  ebay:{label:"eBay", tag:"EBAY", url:h=>"https://www.ebay.com/usr/"+enc(h)},
  venmo:{label:"Venmo", tag:"VEN", url:h=>"https://venmo.com/u/"+enc(h)},
  cashapp:{label:"Cash App", tag:"CASH", url:h=>"https://cash.app/$"+enc(h)},
  paypal:{label:"PayPal", tag:"PP", url:h=>"https://paypal.me/"+enc(h)},
  linktree:{label:"Linktree", tag:"LINK", url:h=>"https://linktr.ee/"+enc(h)},
  beacons:{label:"Beacons", tag:"LINK", url:h=>"https://beacons.ai/"+enc(h)},
  stan:{label:"Stan", tag:"LINK", url:h=>"https://stan.store/"+enc(h)},
  web:{label:"Website", tag:"WEB", url:h=>{ const u=/^https?:\/\//i.test(h)?h:"https://"+h; try{ const x=new URL(u); return /^https?:$/.test(x.protocol)?x.href:null; }catch(_){ return null; } }},
  shop:{label:"Card shop", tag:"SHOP", url:null}
};
// Accept "@name", "name", or a pasted profile link; keep just the handle.
function cleanHandle(p, raw){
  let h=(raw||"").trim(); if(!h) return "";
  if(p==="web"||p==="shop") return h;
  if(/^(https?:\/\/)?(www\.|m\.)?[a-z0-9-]+\.[a-z.]+\//i.test(h)){   // pasted profile link
    try{
      const u=new URL(/^https?:\/\//i.test(h)?h:"https://"+h);
      const seg=u.pathname.split("/").filter(Boolean);
      if(seg.length) h=seg[seg.length-1];
    }catch(_){}
  }
  return h.replace(/^[@$]+/,"").replace(/[\s/?#]+/g,"");
}
function sellerEl(sel){
  if(!sel || !sel.h) return null;
  const P=PLAT[sel.p]||PLAT.shop;
  const showAt = sel.p && !["web","shop"].includes(sel.p);
  const text=(showAt?"@":"")+sel.h;
  const tag=document.createElement("span"); tag.className="plat"; tag.textContent=P.tag;
  const href=P.url ? P.url(sel.h) : null;
  if(href){
    const a=document.createElement("a"); a.className="seller"; a.href=href; a.target="_blank"; a.rel="noopener noreferrer";
    a.title="Open "+text+" on "+P.label; a.append(tag, text+" ↗"); return a;
  }
  const sp=document.createElement("span"); sp.className="seller"; sp.append(tag, text); return sp;
}
// Past sellers: everyone you've bought from in any binder, most recent first (card details and card show mode).
let pastSellers=null;
function loadSellers(){
  return fetch("api/sellers").then(r=>r.ok?r.json():Promise.reject()).then(j=>{ pastSellers=j.sellers||[]; return pastSellers; })
    .catch(()=>pastSellers||(showData&&showData.sellers)||[]);
}
const mergeSellers=(...lists)=>{ const out=[], seen=new Set(); for(const l of lists) for(const x of l||[]){ if(!x||!x.h) continue; const k=x.p+"|"+x.h.toLowerCase(); if(!seen.has(k)){ seen.add(k); out.push(x); } } return out; };
function handleOptions(){
  const seen=new Map();
  for(const k in state.own) for(const b of (state.own[k].purchases||[])) if(b && b.seller && b.seller.h) seen.set(b.seller.p+"|"+b.seller.h, b.seller);
  const dl=$("handleList"); dl.replaceChildren();
  const plat=$("bPlat").value;
  for(const v of seen.values()) if(!plat || v.p===plat){ const o=document.createElement("option"); o.value=v.h; dl.append(o); }
}
var bSugList=[];
function drawBSug(){   // the card details seller button shows what the (hidden) site and name boxes hold
  const h=$("bHandle").value.trim(), cur=h ? {p:$("bPlat").value||"shop", h} : null;
  $("bSelBtn").textContent=cur ? sellerLabel(cur) : "Choose seller";
  $("bSelBtn").classList.toggle("set", !!cur); $("bSelX").hidden=!cur;
  return cur;
}
function setBSeller(sel){
  if(sel){ $("bPlat").value=[...$("bPlat").options].some(o=>o.value===sel.p) ? sel.p : "shop"; $("bHandle").disabled=false; $("bHandle").value=sel.h; }
  else { $("bPlat").value=""; $("bHandle").value=""; $("bHandle").disabled=true; }
  drawBSug();
}
$("bSelBtn").onclick=()=>openSellerPicker(bSugList, drawBSug(), setBSeller);
$("bSelX").onclick=()=>setBSeller(null);
$("bPlat").addEventListener("change",()=>{
  const p=$("bPlat").value; $("bHandle").disabled=!p;
  $("bHandle").placeholder = p==="web" ? "shopname.com" : p==="shop" ? "Shop or person's name" : "@handle";
  if(!p) $("bHandle").value="";
  handleOptions();
});
let editIdx=null;
// Bought, or Already had (pulled from a pack, a gift, kept since you were a kid): those copies need no price.
function setHow(had){
  $("dBuyForm").classList.toggle("had", had);
  for(const b of $("bHow").children) b.setAttribute("aria-pressed", String((b.dataset.had==="1")===had));
  if(editIdx==null) $("bDate").value = had && $("bDate").value===todayStr() ? "" : $("bDate").value || todayStr();
  $("bDate").required=!had; $("bDateK").textContent=had ? "When you got it (optional)" : "Date";
  $("bSubmit").textContent = editIdx!=null ? "Save changes" : had ? "Add copy" : "Add purchase";
}
for(const b of $("bHow").children) b.onclick=()=>setHow(b.dataset.had==="1");
// Reverse holos started with Legendary Collection (2002): Base to Neo, their promos and Southern Islands never had them.
function hasReverses(n){
  let set=String(state.sid||""); if(/^dex-|^own-/.test(set) && /^[a-z0-9.]+-/.test(String(n||""))) set=String(n).split("-")[0];
  const c=state.cards.find(x=>x.n===n);
  return !c || !c.custom ? !/^(base[1-5]|gym\d|neo\d|basep|si\d)$/.test(set) : false;
}
function resetBuyForm(){
  editIdx=null; $("dBuyForm").classList.remove("editing");
  $("bDate").value=todayStr(); $("bPrice").value=""; $("bWhere").value=""; drawWhereChips(); $("bPlat").value=""; $("bHandle").value=""; $("bHandle").disabled=true;
  $("bRev").checked=false; $("bRevRow").hidden=!hasReverses(state.open);
  $("bCancel").hidden=true; setHow(false); drawBSug();
}
function editBuy(n,i){
  const b=buys(n)[i]; if(!b) return;
  editIdx=i; $("dBuyForm").classList.add("editing");
  $("bDate").value=b.d||""; $("bPrice").value=(b.price==null?"":b.price); $("bWhere").value=b.where||""; drawWhereChips();
  $("bPlat").value=(b.seller&&b.seller.p)||""; $("bHandle").value=(b.seller&&b.seller.h)||""; $("bHandle").disabled=!$("bPlat").value;
  $("bRev").checked=!!b.rev; $("bRevRow").hidden=!hasReverses(n) && !b.rev;
  $("bCancel").hidden=false; setHow(isHad(b)); drawBSug();
  handleOptions(); $("bPrice").focus();
}
$("bCancel").onclick=resetBuyForm;

function drawWhereChips(){ const v=$("bWhere").value.trim().toLowerCase(); for(const b of $("bWhereChips").children) b.setAttribute("aria-pressed", String(b.textContent.toLowerCase()===v)); }
$("bWhere").addEventListener("input", drawWhereChips);
function whereOptions(){
  const seen=new Set(["eBay","TCGplayer","Local card shop","Card show","Facebook Marketplace"]);
  for(const k in state.own) for(const b of (state.own[k].purchases||[])) if(b && b.where) seen.add(b.where);
  const box=$("bWhereChips"); box.replaceChildren();
  const recent=[...seen].slice(5).reverse(), list=[...new Set([...recent.slice(0,6), "eBay","TCGplayer","Local card shop","Card show","Facebook Marketplace"])];
  for(const w of list){ const b=document.createElement("button"); b.type="button"; b.className="h-chip"; b.textContent=w;
    b.onclick=()=>{ $("bWhere").value=w; drawWhereChips(); }; box.append(b); }
  drawWhereChips();
}
function drawBuys(n){
  const ul=$("dBuys"); ul.replaceChildren();
  const list=buys(n);
  if(!list.length){ const li=document.createElement("li"); const sp=document.createElement("span"); sp.className="empty"; sp.textContent="No purchases yet. Add what you paid and where below, now or later."; li.append(sp); li.style.display="block"; ul.append(li); }
  list.forEach((b,i)=>{
    const li=document.createElement("li");
    const d=document.createElement("span"); d.className="d"; d.textContent=fmtDay(b.d);
    const w=document.createElement("span"); w.className="meta2";
    if(b.where){ const ww=document.createElement("span"); ww.className="w"; ww.textContent=b.where; w.append(ww); }
    const se=sellerEl(b.seller); if(se) w.append(se);
    if(b.rev){ const rv=document.createElement("span"); rv.className="rv"; rv.textContent="Reverse holo"; w.append(rv); }
    const pr=document.createElement("span"); pr.className="pr";
    if(isHad(b)){ pr.classList.add("had"); pr.textContent="Already had"; }
    else if(b.price==null || b.price===""){
      const inp=document.createElement("input"); inp.type="number"; inp.min="0"; inp.step="0.01"; inp.inputMode="decimal"; inp.placeholder="Paid $";
      inp.setAttribute("aria-label","What you paid on "+fmtDay(b.d));
      inp.onchange=()=>{ if(inp.value==="") return; const l=buys(n).slice(); l[i]={...l[i], price:Math.round(Number(inp.value)*100)/100}; save({purchases:l}); drawBuys(n); };
      pr.append(inp);
    } else pr.textContent=money(Number(b.price));
    const ed=document.createElement("button"); ed.type="button"; ed.className="ed"; ed.textContent="Edit"; ed.setAttribute("aria-label","Edit purchase from "+fmtDay(b.d));
    ed.onclick=()=>editBuy(n,i);
    const x=document.createElement("button"); x.type="button"; x.className="x"; x.textContent="×"; x.setAttribute("aria-label","Remove purchase from "+fmtDay(b.d));
    x.onclick=async()=>{
      const l=buys(n).slice();
      if(l.length===1){ clearCard(n); return; }
      const ok=await askConfirm("Delete this purchase?", "This removes "+whichBuy(b)+". Copies owned will drop to "+(l.length-1)+".", "Delete");
      if(!ok) return;
      l.splice(i,1); save({purchases:l}); if(editIdx!=null) resetBuyForm(); drawBuys(n); condOptions(n);
    };
    li.append(d,w,pr,ed,x); ul.append(li);
  });
  const total=paidFor(n);
  const unpriced=list.filter(b=>!isHad(b) && (b.price==null || b.price==="")).length;   // marked owned on the fly, price still to add
  const had=list.filter(isHad).length, paidN=list.length-unpriced-had;
  const bits=[];
  if(paidN) bits.push(money(total)+" total");
  if(had) bits.push(had===list.length ? "Already had" : had+" already had");
  if(unpriced) bits.push(unpriced===list.length ? "Price not added yet" : unpriced+" without a price");
  $("dPaid").textContent=bits.join(" · ");
  if(unpriced){   // one tap for cards you've had for years and never paid for
    const hb=document.createElement("button"); hb.type="button"; hb.className="had-all"; hb.textContent=unpriced===1 ? "Already had it?" : "Already had these?";
    hb.onclick=()=>{ save({purchases:buys(n).map(b=>!isHad(b) && (b.price==null || b.price==="") ? {...b, had:true} : b)}); drawBuys(n); };
    $("dPaid").append(hb);
  }
  whereOptions(); handleOptions();
}
$("dBuyForm").addEventListener("submit",e=>{
  e.preventDefault();
  const n=state.open; if(n==null) return;
  const d=$("bDate").value || (editIdx!=null || $("dBuyForm").classList.contains("had") ? "" : todayStr());
  const price=$("bPrice").value==="" ? null : Math.round(Number($("bPrice").value)*100)/100;
  const plat=$("bPlat").value, h=cleanHandle(plat,$("bHandle").value);
  if(plat==="web" && h && !PLAT.web.url(h)){ $("dSaved").textContent="That website address doesn't look right. Use something like shopname.com."; return; }
  const had=$("dBuyForm").classList.contains("had");
  const entry=had ? {d, price:null, where:"", had:true} : {d, price, where:$("bWhere").value.trim()};
  if(!had && plat && h) entry.seller={p:plat, h};
  if($("bRev").checked && !$("bRevRow").hidden) entry.rev=true;
  const l=buys(n).slice();
  if(editIdx!=null && l[editIdx]) l[editIdx]=entry; else l.push(entry);
  l.sort((a,b)=>(a.d||"").localeCompare(b.d||""));
  save({purchases:l}); resetBuyForm(); drawBuys(n); condOptions(n);
});
// The card's price chart: drag a finger (or the mouse) along it to read the price on any day, tap a condition to
// see its own line, and pick how far back. An up-or-down swipe that starts on the chart always scrolls the page:
// it only reads prices after a sideways move or a press and hold (touch-action: pan-y does the scrolling part).
const CH_CONDS=["NM","LP","MP","HP","DMG"];
const CH_RANGES=[["1M",30],["3M",91],["6M",182],["1Y",365],["All",0]];
const chart={n:null, pts:[], X:null, Y:null, W:0, lineEl:null, dotEl:null, idx:-1, show:null, reset:null};
const dayStr = d => d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
// One condition's prices, one point per day: saved change days carried forward, ending with today's live price
function condLine(n, c){
  const got=/** @type {any} */ (Array.isArray(state.seriesCache[n]) ? state.seriesCache[n] : null), live=((state.info[n]||{}).cond||{})[c], t=todayStr();
  const pts=(got && got.cond && got.cond[c] || []).map(p=>[p[0],p[1]]);
  if(live && live[0]!=null){ if(pts.length && pts[pts.length-1][0]===t) pts[pts.length-1][1]=live[0]; else if(!pts.length || pts[pts.length-1][0]<t) pts.push([t,live[0]]); }
  if(!pts.length) return [];
  const out=[]; let i=0, val=pts[0][1];
  for(const d=new Date(pts[0][0]+"T12:00:00"); out.length<4000; d.setDate(d.getDate()+1)){
    const k=dayStr(d); while(i<pts.length && pts[i][0]<=k){ val=pts[i][1]; i++; }
    out.push([k,val]); if(k>=t) break;
  }
  return out;
}
function drawSpark(n){
  const box=$("dSpark"); box.replaceChildren();
  chart.n=n; chart.pts=[]; chart.idx=-1; chart.lineEl=null;
  let mode=recall("nd-chart-cond")||"price"; if(mode!=="price" && !CH_CONDS.includes(mode)) mode="price";
  let range=+(recall("nd-chart-range")||0); if(!CH_RANGES.some(r=>r[1]===range)) range=0;
  const priceLine=series(n);   // also asks the server for this card's history when it isn't loaded yet
  const info=state.info[n]||{}, got=/** @type {any} */ (Array.isArray(state.seriesCache[n]) ? state.seriesCache[n] : null), sales=got && got.sales || {};
  // the readout: the latest price, or the day under your finger
  const read=document.createElement("div"); read.className="ch-read"; read.setAttribute("aria-live","polite");
  const rv=document.createElement("b"), rd=document.createElement("span"); read.append(rv,rd);
  const plot=document.createElement("div"); plot.className="ch-plot";
  // the condition buttons, each with its latest average
  const conds=document.createElement("div"); conds.className="seg ch-btns"; conds.setAttribute("role","group"); conds.setAttribute("aria-label","Which price");
  for(const c of ["price"].concat(CH_CONDS)){
    const v=c==="price" ? basePrice(n) : ((info.cond||{})[c]||[])[0];
    const b=document.createElement("button"); b.type="button"; b.setAttribute("aria-pressed",String(c===mode));
    if(c!=="price" && v==null && !(got && got.cond && got.cond[c])) b.classList.add("none");
    const l=document.createElement("span"); l.textContent=c==="price" ? "Price" : c;
    const sm=document.createElement("small"); sm.textContent=v ? money0(v) : "–";
    b.append(l,sm); b.onclick=()=>{ store("nd-chart-cond", c==="price" ? undefined : c); drawSpark(n); };
    conds.append(b);
  }
  const ranges=document.createElement("div"); ranges.className="seg ch-btns ch-range"; ranges.setAttribute("role","group"); ranges.setAttribute("aria-label","How far back");
  for(const [label,days] of CH_RANGES){
    const b=document.createElement("button"); b.type="button"; b.textContent=String(label); b.setAttribute("aria-pressed",String(days===range));
    b.onclick=()=>{ store("nd-chart-range", days ? String(days) : undefined); drawSpark(n); };
    ranges.append(b);
  }
  const cap=document.createElement("div"); cap.className="cap";
  box.append(read,plot,conds,ranges,cap);
  // the line to draw, cut to the chosen range
  const all=mode==="price" ? priceLine : condLine(n,mode);
  let pts=all;
  if(range){ const cut=new Date(); cut.setDate(cut.getDate()-range); const k=dayStr(cut); pts=all.filter(p=>p[0]>=k); }
  const label=mode==="price" ? "Price" : mode;
  const latest=all.length ? all[all.length-1] : null;
  const when=d=>d===todayStr() ? "today" : fmtDay(d);
  chart.reset=()=>{ rv.textContent=latest ? money(latest[1]) : (mode==="price" && basePrice(n) ? money(basePrice(n)) : "–"); rd.textContent=latest ? label+" · "+when(latest[0]) : label; };
  chart.show=i=>{ const p=chart.pts[i]; if(!p) return; rv.textContent=money(p[1]); rd.textContent=label+" · "+when(p[0]); };
  chart.reset();
  // the sale dots: this condition's, or on Price the conditions your price is made from
  const dotConds=mode==="price" ? activeSlots().filter(sl=>sl.t==="raw").map(sl=>sl.c) : [mode];
  // No line yet (each condition's line builds up one price check at a time): show the sales saved so far instead,
  // ending with today's average, so the chart is useful from the first day
  let salesOnly=0;
  if(pts.length<2){
    let sl=dotConds.flatMap(c=>(sales[c]||[]).map(s=>[s[0],s[1]])).sort((a,b)=>a[0]<b[0] ? -1 : a[0]>b[0] ? 1 : 0);
    if(range){ const cut=new Date(); cut.setDate(cut.getDate()-range); const k=dayStr(cut); sl=sl.filter(s=>s[0]>=k); }
    if(!sl.length){
      const m=document.createElement("div"); m.className="ch-msg";
      m.textContent = mode==="price" ? "Price trend appears after a few days of saved prices."
        : !all.length ? "No "+mode+" sales saved yet."
        : "Each condition's trend builds up from "+fmtDay(all[0][0])+".";
      plot.append(m); return;
    }
    salesOnly=sl.length;
    pts = latest && latest[0]>=sl[sl.length-1][0] ? sl.concat([latest]) : sl;
  }
  chart.show=i=>{ const p=chart.pts[i]; if(!p) return; rv.textContent=money(p[1]); rd.textContent=label+(i<salesOnly ? " sale" : "")+" · "+when(p[0]); };
  const k0=pts[0][0];
  const dots=salesOnly ? [] : dotConds.flatMap(c=>(sales[c]||[]).filter(s=>s[0]>=k0));
  const W=360,H=120,P=6, t0=Date.parse(pts[0][0]+"T12:00:00"), t1=Date.parse(pts[pts.length-1][0]+"T12:00:00");
  const ys=pts.map(p=>p[1]).concat(dots.map(s=>s[1])), y0=Math.min(...ys), y1=Math.max(...ys);
  const X=d=>P+(t1===t0?0.5:(Date.parse(d+"T12:00:00")-t0)/(t1-t0))*(W-2*P), Y=v=>H-P-(y1===y0?0.5:(v-y0)/(y1-y0))*(H-2*P);
  const line=pts.map(p=>X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).join(" ");
  const ns="http://www.w3.org/2000/svg", svg=document.createElementNS(ns,"svg"); svg.setAttribute("viewBox","0 0 "+W+" "+H); svg.setAttribute("role","img");
  const lo=Math.min(...pts.map(p=>p[1])), hi=Math.max(...pts.map(p=>p[1]));
  svg.setAttribute("aria-label", salesOnly ? label+" sales: "+salesOnly+" since "+fmtDay(pts[0][0])+", low "+money(lo)+", high "+money(hi)
    : label+" price chart: "+money(pts[0][1])+" on "+fmtDay(pts[0][0])+" to "+money(pts[pts.length-1][1])+" now, low "+money(lo)+", high "+money(hi));
  const mk=(tag,attrs)=>{ const e=document.createElementNS(ns,tag); for(const k in attrs) e.setAttribute(k,attrs[k]); return e; };
  if(!salesOnly){
    svg.append(mk("polygon",{points:P+","+(H-P)+" "+line+" "+(W-P)+","+(H-P), fill:"var(--dark)", opacity:"0.12"}));
    svg.append(mk("polyline",{points:line, fill:"none", stroke:"var(--dark)", "stroke-width":"2", "stroke-linejoin":"round", "stroke-linecap":"round"}));
  }
  for(const s of dots) svg.append(mk("circle",{cx:X(s[0]), cy:Y(s[1]), r:"2.5", fill:"var(--dark)", opacity:"0.45"}));
  for(const s of pts.slice(0,salesOnly)) svg.append(mk("circle",{cx:X(s[0]), cy:Y(s[1]), r:"3.5", fill:"var(--dark)", opacity:"0.7"}));
  const last=pts[pts.length-1];
  if(!salesOnly || pts.length>salesOnly)
    svg.append(mk("circle",{cx:X(last[0]), cy:Y(last[1]), r:"4", fill:"var(--dark)", stroke:"var(--surface)", "stroke-width":"2"}));
  chart.lineEl=mk("line",{y1:P, y2:H-P, stroke:"var(--ink)", "stroke-width":"1", opacity:"0.5", visibility:"hidden"});
  chart.dotEl=mk("circle",{r:"4.5", fill:"var(--ink)", stroke:"var(--surface)", "stroke-width":"2", visibility:"hidden"});
  svg.append(chart.lineEl, chart.dotEl);
  plot.append(svg); plot.tabIndex=0; plot.setAttribute("aria-label",(salesOnly ? "Sales chart" : "Price chart")+". Use the left and right arrow keys to read each "+(salesOnly ? "sale" : "day")+".");
  chart.pts=pts; chart.X=X; chart.Y=Y; chart.W=W;
  if(salesOnly){
    cap.append(salesOnly+" sale"+(salesOnly===1 ? "" : "s")+" saved since "+fmtDay(pts[0][0])+". "
      +(mode==="price" ? "The price line appears after a few days of saved prices." : "The "+mode+" line builds up from "+fmtDay(all.length ? all[0][0] : todayStr())+"."));
    return;
  }
  cap.append("Low "+money(lo)+" · High "+money(hi)+" since "+fmtDay(pts[0][0]));
  const w=mode==="price" && !range ? trend(n) : null;
  if(w){ cap.append(" · "+periodName()+" "); cap.append(trendEl(w)); }
}
// Show one day on the chart, with a line and a dot, and its price in the readout
function chartAt(i){
  if(!chart.pts.length || !chart.lineEl) return;
  i=Math.max(0,Math.min(chart.pts.length-1,i)); chart.idx=i;
  const p=chart.pts[i], x=chart.X(p[0]), y=chart.Y(p[1]);
  chart.lineEl.setAttribute("x1",x); chart.lineEl.setAttribute("x2",x); chart.lineEl.setAttribute("visibility","visible");
  chart.dotEl.setAttribute("cx",x); chart.dotEl.setAttribute("cy",y); chart.dotEl.setAttribute("visibility","visible");
  chart.show(i);
}
// the day nearest a spot on screen
function chartAtX(clientX){
  const svg=$("dSpark").querySelector(".ch-plot svg"); if(!svg || !chart.pts.length) return;
  const r=svg.getBoundingClientRect(), vx=(clientX-r.left)/r.width*chart.W;
  let best=0, bd=Infinity; chart.pts.forEach((p,i)=>{ const d=Math.abs(chart.X(p[0])-vx); if(d<bd){ bd=d; best=i; } });
  chartAt(best);
}
function chartOff(){
  chart.idx=-1;
  if(chart.lineEl){ chart.lineEl.setAttribute("visibility","hidden"); chart.dotEl.setAttribute("visibility","hidden"); }
  if(chart.reset) chart.reset();
}
// One set of listeners on the chart's box, for whichever card is open (the chart inside is redrawn per card)
(()=>{
  const box=$("dSpark");
  let start=null, reading=false, hold=0;
  const stop=()=>{ clearTimeout(hold); start=null; reading=false; chartOff(); };
  box.addEventListener("pointerdown",e=>{
    if(e.pointerType==="mouse" || !e.target.closest(".ch-plot svg")) return;
    start={x:e.clientX, y:e.clientY, id:e.pointerId}; reading=false;
    clearTimeout(hold); hold=setTimeout(()=>{ if(start){ reading=true; chartAtX(start.x); } },300);   // press and hold
  });
  box.addEventListener("pointermove",e=>{
    if(e.pointerType==="mouse"){ if(e.target.closest(".ch-plot svg")) chartAtX(e.clientX); else if(chart.idx>=0) chartOff(); return; }
    if(!start || e.pointerId!==start.id) return;
    if(!reading){
      const dx=Math.abs(e.clientX-start.x), dy=Math.abs(e.clientY-start.y);
      if(dx<8 && dy<8) return;
      clearTimeout(hold);
      if(dy>=dx){ start=null; return; }   // up or down first: the page scrolls, the chart leaves it alone
      reading=true;
      const plot=e.target.closest(".ch-plot"); if(plot && plot.setPointerCapture) try{ plot.setPointerCapture(e.pointerId); }catch(_){}
    }
    chartAtX(e.clientX);
  });
  for(const ev of ["pointerup","pointercancel"]) box.addEventListener(ev,e=>{ if(e.pointerType!=="mouse") stop(); });
  box.addEventListener("pointerleave",e=>{ if(e.pointerType==="mouse") chartOff(); });
  box.addEventListener("contextmenu",e=>{ if(e.target.closest(".ch-plot")) e.preventDefault(); });   // press and hold reads prices, not a menu
  box.addEventListener("keydown",e=>{
    if(!e.target.classList || !e.target.classList.contains("ch-plot") || !chart.pts.length) return;
    if(e.key==="ArrowLeft" || e.key==="ArrowRight"){ e.preventDefault(); chartAt(chart.idx<0 ? chart.pts.length-1 : chart.idx+(e.key==="ArrowLeft"?-1:1)); }
    else if(e.key==="Escape" && chart.idx>=0){ e.preventDefault(); e.stopPropagation(); chartOff(); }
  });
  box.addEventListener("focusout",e=>{ if(e.target.classList && e.target.classList.contains("ch-plot")) chartOff(); });
})();
let tNote; $("dNote").oninput=e=>{ clearTimeout(tNote); tNote=setTimeout(()=>save({note:e.target.value}),700); };
let photoSide="front";
function drawPhoto(n){
  const c=state.cards.find(x=>x.n===n), r=rec(n), back=photoSide==="back";
  const v=back ? r.photoBack : r.photo;
  [...$("dSide").children].forEach(b=>{
    b.setAttribute("aria-pressed", b.dataset.side===photoSide);
    const has=b.dataset.side==="back" ? r.photoBack : r.photo;
    b.replaceChildren(b.dataset.side==="back"?"B":"F"); if(has){ const d=document.createElement("span"); d.className="dot"; d.setAttribute("aria-hidden","true"); b.append(d); }
    b.title=(b.dataset.side==="back"?"Back":"Front")+(has?" (photo added)":" (no photo yet)");
  });
  const ph=$("dPhoto"); ph.replaceChildren();
  if(v){ const im=document.createElement("img"); im.alt=(back?"Back":"Front")+" of your "+(c?c.name:"card"); im.src=base()+"/photo/"+enc(n)+(back?"/back":"")+"?v="+v; ph.append(im); }
  else ph.textContent="No "+(back?"back":"front")+" photo yet";
  $("dUpLabel").textContent=(v?"Replace ":"Add ")+(back?"back":"front")+" photo";
}
$("dSide").addEventListener("click",e=>{ const b=e.target.closest("button"); if(!b||state.open==null) return; photoSide=b.dataset.side; $("dUpMsg").textContent=""; drawPhoto(state.open); });
$("dUp").onchange=async e=>{
  const f=e.target.files[0]; e.target.value=""; if(!f) return;
  if(f.size>15*1024*1024){ $("dUpMsg").textContent="That photo is too big. Use one under 15 MB."; return; }
  const n=state.open, back=photoSide==="back";
  $("dUpMsg").textContent="Uploading…";
  try{
    const r=await fetch("api/set/"+enc(state.sid)+"/photo/"+enc(n)+(back?"/back":""),{method:"POST",headers:{"Content-Type":f.type||"image/jpeg"},body:f});
    const j=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(j.error||"");
    save(back?{photoBack:j.v}:{photo:j.v}); $("dUpMsg").textContent=(back?"Back":"Front")+" photo added"; drawPhoto(n);
  }catch(e){ $("dUpMsg").textContent=(e&&e.message) ? e.message+"." : "Upload failed. Try again."; }
};

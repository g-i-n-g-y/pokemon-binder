// Card details: price slots, the finished-binder celebration, recent sales, the vendor price check.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- card sheet ----------
// ---------- price slots ----------
const COND_NAME={NM:"Near Mint",LP:"Lightly Played",MP:"Moderately Played",HP:"Heavily Played",DMG:"Damaged"};
const activeSlots = () => state.slots.filter(sl=>sl.t!=="none");
const allRaw = () => activeSlots().every(sl=>sl.t==="raw");
const slotName = sl => sl.t==="raw" ? sl.c : sl.t==="graded" ? (sl.co==="Any" ? "Graded "+sl.g : sl.co+" "+sl.g) : "";
const slotKey = sl => sl.t==="raw" ? sl.c : sl.co+" "+sl.g;
function slotVal(n, sl){ const i=state.info[n]||{}; return sl.t==="raw" ? (i.cond||{})[sl.c] : sl.t==="graded" ? (i.graded||{})[slotKey(sl)] : null; }
const mainLabel = () => allRaw() ? "Combined "+activeSlots().map(slotName).join("/") : slotName(state.slots[0])+" price";
// Old prices: the newest sale is over STALE_DAYS old, or there are no recent sales and the market price is used.
const STALE_DAYS=90;
const STALE_SVG='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
function staleWhy(n){
  const i=state.info[n]; if(!i || !priceOf(n)) return "";
  if(i.src==="tcgdex") return "No recent sales, so this is TCGplayer's market price";
  if((i.src==="tcgplayer"||i.src==="pricecharting") && i.last){
    const d=(new Date(todayStr())-new Date(i.last.slice(0,10)+"T00:00:00"))/864e5;
    if(d>STALE_DAYS) return "Last sold "+when(i.last.slice(0,10));
  }
  return "";
}
function staleEl(why){ const s=document.createElement("span"); s.className="stale"; s.innerHTML=STALE_SVG; s.title="Old price: "+why; s.setAttribute("role","img"); s.setAttribute("aria-label","Old price: "+why); return s; }
function priceSource(n){
  const i=state.info[n];
  const sales = i ? i.count+" recent "+"sale"+(i.count===1?"":"s") : "";
  const late = i && i.last ? ", latest "+when(i.last) : "";
  if(i && i.src==="pricecharting"){
    const g=activeSlots().find(sl=>sl.t==="graded"&&slotVal(n,sl)) || state.slots[0];
    return "from "+i.count+" recent "+slotName(g)+" sale"+(i.count===1?"":"s")+" on eBay (via PriceCharting)"+late+". Used for set totals.";
  }
  if(i && i.src==="tcgplayer" && state.slots[0].t==="graded") return "no recent "+slotName(state.slots[0])+" sales, so this uses "+slotName(activeSlots().find(sl=>sl.t==="raw")||state.slots[0])+": "+sales+late+". Used for set totals.";
  if(i && i.src==="tcgplayer") return "from "+sales+late+". Used for set totals.";
  if(i && i.src==="manual") return "the price you typed for this custom card"+(customOf(n)&&customOf(n).tcg ? " (no recent TCGplayer sales yet)" : ". Add its TCGplayer link to use real sales instead")+". Used for set totals.";
  if(i && i.src==="tcgdex") return "no recent sales for your price options, so this uses TCGplayer's market price (via TCGdex)"+(i.last?", updated "+when(i.last):"")+". Used for set totals.";
  if(i && i.note) return i.note+".";
  return priceOf(n) ? "starting price from PriceCharting. Replaced on the next price check." : "fills in after the next price check.";
}
function mktLine(n){
  const m=(state.info[n]||{}).mkt||{}, el=$("dMkt"), bits=[];
  if(m.tp) bits.push("TCGplayer "+money(m.tp)+(m.tpLow?" (low "+money(m.tpLow)+")":""));
  // Cardmarket is saved in dollars since v2.16.2 (cmUsd); older euro numbers stay hidden until the next price check
  if(m.cmUsd && (m.cm30||m.cmTrend)) bits.push("Cardmarket 30-day avg "+money(m.cm30||m.cmTrend));
  el.hidden=!bits.length;
  el.textContent = bits.length ? "Market prices: "+bits.join(" · ")+". From TCGdex, a rough second opinion"+(bits.length>1?" (Cardmarket is converted from euros and may mix editions)":"")+"." : "";
}
function lpmpBox(n){
  const i=state.info[n]||{};
  state.slots.forEach((sl,k)=>{
    if(k===1) $("dS1box").hidden = sl.t==="none";
    if(sl.t==="none") return;
    const v=slotVal(n,sl), have = sl.t==="raw" ? i.cond : i.graded;
    $("dS"+k+"k").textContent = slotName(sl)+" average";
    $("dS"+k).textContent = v ? money(v[0]) : "–";
    $("dS"+k+"s").textContent = v ? v[1]+" sale"+(v[1]===1?"":"s")+(v[2]?" · latest "+new Date(v[2]+"T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric"}):"") : (have ? "No recent sales" : "After next refresh");
  });
  $("dBoxes").classList.toggle("one", state.slots[1].t==="none");
  $("dPk").textContent = mainLabel();
}
// ---------- binder complete celebration ----------
// Unown sprites (Pokémon Crystal, from PokeAPI, cached on the server) swirl around the screen like the
// vortex in Pokémon 3, then fly into place to spell CONGRATS and float gently until you tap.
const CELE_WORD="CONGRATS";
const celeOn = () => recall("nd-cele")!=="off";
let celeRun=null;
// Unown art sits in the lower part of its picture: trim to the drawing so the letters line up.
function trimSprite(im){
  const c=document.createElement("canvas"), w=im.naturalWidth, h=im.naturalHeight; c.width=w; c.height=h;
  const x=c.getContext("2d"); x.drawImage(im,0,0);
  let d; try{ d=x.getImageData(0,0,w,h).data; }catch(_){ return null; }
  let x0=w,y0=h,x1=-1,y1=-1;
  for(let y=0;y<h;y++) for(let i=0;i<w;i++) if(d[(y*w+i)*4+3]>20){ if(i<x0)x0=i; if(i>x1)x1=i; if(y<y0)y0=y; if(y>y1)y1=y; }
  if(x1<0) return null;
  const side=Math.max(x1-x0,y1-y0)+3, cx=(x0+x1)/2, cy=(y0+y1)/2;
  const o=document.createElement("canvas"); o.width=o.height=side;
  o.getContext("2d").drawImage(c, Math.round(cx-side/2), Math.round(cy-side/2), side, side, 0, 0, side, side);
  return o;
}
function loadUnown(ch){
  return new Promise(res=>{
    const im=new Image(); const t=setTimeout(()=>res(null),4000);
    im.onload=()=>{ clearTimeout(t); res(trimSprite(im)); }; im.onerror=()=>{ clearTimeout(t); res(null); };
    im.src="unown/"+ch.toLowerCase()+".png";
  });
}
async function celebrate(sub){
  if(celeRun) return;
  celeRun={};
  // a dialog of its own so it shows above any open window (card details, Settings)
  const ov=document.createElement("dialog"); ov.className="cele"; ov.setAttribute("role","alertdialog"); ov.setAttribute("aria-label","Binder complete. Congrats!");
  const msg=document.createElement("div"); msg.className="cele-msg";
  const m1=document.createElement("b"); m1.textContent="Binder complete!";
  const m2=document.createElement("span"); m2.textContent=sub||"";
  const m3=document.createElement("small"); m3.textContent="Tap anywhere to close";
  msg.append(m1); if(sub) msg.append(m2); msg.append(m3);
  ov.append(msg); document.body.append(ov); ov.showModal();
  const sprites=await Promise.all([...CELE_WORD].map(loadUnown));
  const els=[...CELE_WORD].map((ch,i)=>{
    let el=sprites[i];
    if(!el){ el=document.createElement("div"); el.classList.add("txt"); el.textContent=ch; }   // no picture: plain letter
    el.classList.add("unown"); el.setAttribute("aria-hidden","true"); ov.append(el); return el;
  });
  requestAnimationFrame(()=>ov.classList.add("on"));
  const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
  const n=els.length, rnd=()=>Math.random();
  const P=els.map((_,i)=>({ ph:i/n*Math.PI*2+rnd()*.5, sp:2.4+rnd()*1.3, rx:.75+rnd()*.4, ry:.75+rnd()*.4, tw:rnd()*6, tb:.6+rnd()*.8 }));
  const SWIRL=reduce?0:1.8, SETTLE=reduce?0:1.1, STAG=.07, CLOSE=14;
  const ease=k=>{ const c=1.5; return 1+(c+1)*Math.pow(k-1,3)+c*Math.pow(k-1,2); };   // ease-out with a small overshoot
  let t0=null, raf=0;
  const frame=now=>{
    if(t0===null) t0=now;
    const t=(now-t0)/1000, W=innerWidth, H=innerHeight;
    // phones: bigger letters packed closer, a taller swirl, and the word nearer the middle
    const narrow=W<640, u=narrow?Math.min(60,(W-28)/(n*1.02)):Math.min(72, W/(n+2.2)), gap=u*(narrow?1.02:1.12), fy=H*(narrow?.44:.42);
    const RX=narrow?W*.42:W*.38, RY=narrow?H*.24:H*.17, RW=narrow?H*.05:H*.07;
    for(let i=0;i<n;i++){
      const p=P[i], el=els[i];
      // the vortex: an ellipse around the middle, closer letters bigger and blurrier
      const th=p.ph+p.sp*t;
      const d=(Math.sin(th)+1)/2;
      const sx=W/2+Math.cos(th)*RX*p.rx*(1-.15*Math.sin(t*3+i));
      const sy=H*.46+Math.sin(th)*RY*p.ry+Math.sin(th*2+p.tw)*RW;
      const ss=narrow?.5+d*1.6:.45+d*1.9, sr=Math.sin(th*1.7+p.tw)*35, sb=d>.78?(d-.78)*14:0;
      // the word: each letter's spot, with a slow float
      const fx=W/2+(i-(n-1)/2)*gap;
      const bob=reduce?0:Math.sin(t*2*Math.PI/1.9+i*.7)*u*.09, tilt=reduce?0:Math.sin(t*1.4+i)*3;
      const k=Math.min(1,Math.max(0,(t-SWIRL-i*STAG)/SETTLE)), e=k>=1?1:ease(k);
      const x=sx+(fx-sx)*e, y=sy+(fy+bob-sy)*e, sc=ss+(1-ss)*e, r=sr+(tilt-sr)*e, bl=sb*(1-e);
      const fade=Math.min(1,t/.35);
      el.style.width=el.style.height=u+"px";
      if(el.classList.contains("txt")) el.style.fontSize=(u*.8)+"px";
      el.style.transform="translate3d("+(x-u/2)+"px,"+(y-u/2)+"px,0) scale("+sc+") rotate("+r+"deg)";
      el.style.filter=(bl>.2?"blur("+bl.toFixed(1)+"px) ":"")+"drop-shadow(0 0 "+(4+3*e)+"px rgba(225,215,255,.75))";
      el.style.opacity=fade;
      el.style.zIndex=k<1 ? String(Math.round(d*100)) : "100";
    }
    msg.style.top=(fy+u*.9+18)+"px";
    if(t>SWIRL+SETTLE+(n-1)*STAG-.2) msg.classList.add("on");
    if(t>CLOSE) return close();
    raf=requestAnimationFrame(frame);
  };
  const close=()=>{
    cancelAnimationFrame(raf); ov.classList.remove("on");
    document.removeEventListener("keydown",key,true);
    setTimeout(()=>{ if(ov.open) ov.close(); ov.remove(); celeRun=null; },380);
  };
  ov.addEventListener("cancel",e=>{ e.preventDefault(); close(); });
  const key=e=>{ if(e.key==="Escape"||e.key==="Enter"||e.key===" "){ e.preventDefault(); e.stopPropagation(); close(); } };
  ov.addEventListener("click",close);
  document.addEventListener("keydown",key,true);
  raf=requestAnimationFrame(frame);
}
// fetch the 8 letters quietly a little after the page opens, so the celebration starts instantly
setTimeout(()=>{ if(celeOn()) for(const ch of new Set(CELE_WORD.toLowerCase())){ const im=new Image(); im.src="unown/"+ch+".png"; } }, 8000);
$("stCele").checked=celeOn();
$("stCele").onchange=e=>store("nd-cele", e.target.checked ? undefined : "off");
$("stLp").value=lpMode();
$("stLp").onchange=e=>{ store("nd-lp", e.target.value==="ebay" ? undefined : e.target.value); $("sumPhone").textContent=e.target.value==="off" ? "" : "Hold a card: "+e.target.selectedOptions[0].textContent; };
$("stCeleTry").onclick=()=>celebrate((state.set.name||"Your binder")+" · "+state.cards.length+" of "+state.cards.length+" cards");

// ---------- recent sales tab ----------
let cardTab="info";
function setCardTab(t){
  if(t==="mine" && isPrivate()) t="info";
  // wider screens have room for prices and recent sales together, so the Prices tab shows both
  const wide=matchMedia("(min-width:760px)").matches;
  if(wide && t==="sales") t="info";
  cardTab=t;
  for(const b of $("dTabs").querySelectorAll("button")) b.setAttribute("aria-pressed", b.dataset.tab===t ? "true" : "false");
  $("tabInfo").hidden = t!=="info"; $("tabSales").hidden = !(t==="sales" || (wide && t==="info")); $("tabMine").hidden = t!=="mine";
  const m=document.querySelector("#dlg .cs-main"); if(m) m.scrollTop=0;
}
// The short "You own 2 · LP" line under the card name, and the copy count on the My copy tab.
function ownLine(n){
  const q=qty(n), c=rec(n).cond, el=$("dOwn");
  el.textContent = q>0 ? "You own "+(q>1?q+" copies":"this card")+(c?" · "+c:"") : "Still needed";
  el.classList.toggle("have", q>0);
  $("dTabN").textContent = q>0 ? String(q) : "";
}
matchMedia("(min-width:760px)").addEventListener("change",()=>{ if($("dlg").open) setCardTab(cardTab); });
$("dTabs").addEventListener("click",e=>{ const b=e.target.closest("button[data-tab]"); if(b) setCardTab(b.dataset.tab); });
const shortDay = d => d ? new Date(d+"T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "";
// where a sale happened: a link to the listing when there is one, else to the store's page for the card
function saleLink(href, label){
  const a=document.createElement(href ? "a" : "span"); a.className="rs-src"; a.textContent=label+(href ? " ↗" : "");
  if(href){ a.href=href; a.target="_blank"; a.rel="noopener noreferrer"; a.title="Open on "+label; }
  return a;
}
function salesBlock(title, avg, list, mine, emptyText, where){
  const box=document.createElement("div"); box.className="rs-cond"+(mine?" mine":"");
  const head=document.createElement("div"); head.className="rs-head";
  const b=document.createElement("b"); b.textContent=title;
  if(mine){ const t=document.createElement("span"); t.className="rs-tag"; t.textContent="Your price"; b.append(t); }
  const a=document.createElement("span"); a.className="s"; a.textContent = avg ? "Avg "+money(avg[0])+" · "+avg[1]+" sale"+(avg[1]===1?"":"s") : "";
  head.append(b,a); box.append(head);
  if(list && list.length){
    const ul=document.createElement("ul"); ul.className="rs-list";
    for(const sale of list){ const [d,p]=sale; const li=document.createElement("li"); const x=document.createElement("span"); x.textContent=shortDay(d); const y=document.createElement("span"); y.className="rs-p"; y.textContent=money(p);
      li.append(x); if(where){ const w=where(sale); if(w) li.append(saleLink(w[0], w[1])); } li.append(y); ul.append(li); }
    box.append(ul);
  } else { const e=document.createElement("div"); e.className="rs-none"; e.textContent=emptyText; box.append(e); }
  return box;
}
function drawSales(n){
  const i=state.info[n]||{}, box=$("dSales"); box.replaceChildren();
  if(!i.recent){
    const e=document.createElement("div"); e.className="rs-none";
    e.textContent = "Recent sales show here after the next price check.";
    box.append(e); return;
  }
  const mineRaw=new Set(activeSlots().filter(sl=>sl.t==="raw").map(sl=>sl.c));
  // raw sales are TCGplayer sales: each one links to the card's TCGplayer page, which has its sales history
  const cc=state.cards.find(x=>x.n===n)||{}, tcgId=i.tcgId||cc.tcg;
  const tcgUrl=tcgId ? "https://www.tcgplayer.com/product/"+enc(tcgId) : "";
  for(const c of ["NM","LP","MP","HP","DMG"])
    box.append(salesBlock(c+" · "+COND_NAME[c], (i.cond||{})[c], (i.recent||{})[c], mineRaw.has(c), "No recent "+c+" sales found.", ()=>[tcgUrl, "TCGplayer"]));
  for(const sl of activeSlots().filter(sl=>sl.t==="graded")){
    const key=slotKey(sl);
    let list=(i.gradedRecent||{})[key];
    if(sl.co==="Any") list=Object.entries(i.gradedRecent||{}).filter(([k])=>k.endsWith(" "+sl.g)).flatMap(([,v])=>v).sort((a,b)=>b[0].localeCompare(a[0])).slice(0,5);
    box.append(salesBlock(slotName(sl)+" · eBay via PriceCharting", (i.graded||{})[key], list, true, i.graded ? "No recent "+slotName(sl)+" sales found." : "Graded sales show here after the next price refresh.",
      sale=>sale[2] ? [sale[2], "eBay"] : [i.pc||"", "PriceCharting"]));
  }
}
// ---------- vendor price check: what to counter with ----------
// Compares a vendor's price with recent sales for that condition and suggests an opening offer and a
// walk-away price. A rising price (30 days) moves both closer to the sticker; a falling one moves them lower.
// "habit" (from the server) is what you usually pay compared with the price, from your purchase log.
const OFFER_SPLIT=20;   // same as the server: cheap cards are under $20
let habit=null, habitAt=0;
function loadHabit(then){
  if(habit && Date.now()-habitAt<60000){ then&&then(); return; }
  fetch("api/habit").then(r=>r.json()).then(j=>{ habit=j||{}; habitAt=Date.now(); then&&then(); }).catch(()=>{});
}
const median = a => { const s=[...a].sort((x,y)=>x-y), m=s.length>>1; return s.length ? (s.length%2 ? s[m] : (s[m-1]+s[m])/2) : 0; };
// The recent-sales price to compare with: the middle of the newest sales when there are 3 or more,
// else that condition's average, else the binder's price.
function offerRef(cond, avg, recent, base){
  const list=(recent||[]).map(x=>Number(x[1])).filter(v=>v>0);
  if(cond && list.length>=3) return {p:median(list), how:"the middle of the last "+list.length+" "+cond+" sales"};
  if(cond && avg && avg[0]) return {p:avg[0], how:"the "+cond+" average of "+avg[1]+" sale"+(avg[1]===1?"":"s")};
  if(base) return {p:base, how:cond ? "the card's price (no recent "+cond+" sales)" : "the card's price"};
  return null;
}
const offerRound = v => v>=100 ? Math.round(v/5)*5 : v>=20 ? Math.round(v) : Math.max(0.25, Math.round(v*4)/4);
// The card's saved price history, for the vendor price check. h90 = [lowest, middle, days, first day] over the last
// 90 days (from the server), cur = today's price, t7 = 7-day change. Needs 5+ saved days across 2+ weeks, else null.
function offerHist(h90, cur, t7){
  if(!Array.isArray(h90) || !(cur>0) || !(h90[0]>0) || !(h90[1]>0) || h90[2]<5) return null;
  const span=Math.round((new Date(todayStr())-new Date(h90[3]))/864e5);
  if(!(span>=14)) return null;
  const vsUsual=cur/h90[1];
  const tag = (vsUsual>=1.15 || (t7!=null && t7>=15)) ? "wait" : vsUsual<=0.95 ? "dip" : "";
  return {low:h90[0]/cur, usual:h90[1]/cur, lowP:h90[0], usualP:h90[1], days:h90[2], span, vsUsual, t7, tag};
}
// ask can be empty (no price typed yet): then only the open and walk-away numbers matter.
function offerAdvice(ask, ref, t30, hist){
  let open, walk, fair=ref.p, up=false, down=false;
  if(hist){
    // Based on the card's own history: open near its 90-day low, walk away a little over its usual price
    // (or today's, if that's lower), so a short spike never sets what you pay.
    fair=Math.min(ref.p, ref.p*hist.usual);
    open=offerRound(Math.min(0.90, Math.max(0.75, hist.low))*ref.p);
    walk=offerRound(Math.max(fair*1.10, open));
  }else{
    up=t30!=null && t30>=5; down=t30!=null && t30<=-5;
    const openF=up?0.90:down?0.80:0.85, walkF=up?1.20:down?1.05:1.15;
    walk=offerRound(ref.p*walkF); open=offerRound(ref.p*openF);
  }
  if(ask>0 && open>=ask) open=null;   // the sticker is already below where you'd start
  const good=ask<=fair*0.95, high=ask>walk;
  return {pct:(ask-ref.p)/ref.p*100, open, walk, up, down, verdict:good?"Good deal":high?"High":"Fair", cls:good?"good":high?"high":"fair"};
}
// The Wait / Good time to buy tag from the card's history (nothing when there isn't enough of it).
function offerTag(box, hist){
  if(!hist || !hist.tag) return;
  const d=document.createElement("div"); d.className="of-tag "+hist.tag;
  const p=document.createElement("span"); p.className="of-pill "+(hist.tag==="dip"?"good":"high");
  p.textContent = hist.tag==="dip" ? "Good time to buy" : "Wait if you can";
  const s=document.createElement("span"); s.className="of-pct";
  s.textContent = hist.tag==="dip" ? Math.round((1-hist.vsUsual)*100)+"% under its usual price ("+money(hist.usualP)+")" :
    hist.t7!=null && hist.t7>=15 && hist.vsUsual<1.15 ? "Jumped "+Math.round(hist.t7)+"% this week, likely a short spike" :
    Math.round((hist.vsUsual-1)*100)+"% over its usual price ("+money(hist.usualP)+"), likely a short spike";
  d.append(p,s); box.append(d);
}
// Fills `box` with the advice. o = {ask, ref, t30, stale, hist}. Before a price is typed it shows just what to
// aim for and when to walk away, so you know your numbers before you ask.
function drawOffer(box, o){
  box.replaceChildren();
  const line=(cls,txt)=>{ const d=document.createElement("div"); d.className=cls; d.textContent=txt; box.append(d); return d; };
  if(!(o.ask>0)){
    if(!o.ref) return;
    const a=offerAdvice(0, o.ref, o.t30, o.hist);
    offerTag(box, o.hist);
    line("of-note of-plan", "Before you ask: aim for "+money(a.open)+", walk away above "+money(a.walk)+".");
    return;
  }
  if(!o.ref){ line("of-note","No price for this card yet, so there's nothing to compare with."); return; }
  const a=offerAdvice(o.ask, o.ref, o.t30, o.hist);
  offerTag(box, o.hist);
  const top=document.createElement("div"); top.className="of-top";
  const pill=document.createElement("span"); pill.className="of-pill "+a.cls; pill.textContent=a.verdict;
  const pc=document.createElement("span"); pc.className="of-pct";
  pc.textContent = Math.abs(a.pct)<0.5 ? "Right at recent sales ("+money(o.ref.p)+")" : Math.round(Math.abs(a.pct))+"% "+(a.pct>0?"over":"under")+" recent sales ("+money(o.ref.p)+")";
  top.append(pill,pc); box.append(top);
  const nums=document.createElement("div"); nums.className="of-nums";
  const num=(k,v,s)=>{ const d=document.createElement("div"); const kk=document.createElement("span"); kk.className="k"; kk.textContent=k; const vv=document.createElement("b"); vv.textContent=v; d.append(kk,vv); if(s){ const ss=document.createElement("span"); ss.className="s"; ss.textContent=s; d.append(ss); } nums.append(d); };
  if(a.cls==="good") num("Take it", money(o.ask), "Under recent sales");
  else num("Open at", a.open!=null ? money(a.open) : money(o.ask), a.open!=null ? "Your first counter" : "Already close to it");
  num("Walk away above", money(a.walk), a.cls==="high" ? "The sticker is past this" : "");
  box.append(nums);
  line("of-note", "Recent sales = "+o.ref.how+".");
  if(o.hist) line("of-note", "From "+o.hist.days+" days of saved prices: usually "+money(o.hist.usualP)+", lowest "+money(o.hist.lowP)+". You open near the low and walk away a little over the usual price.");
  else if(o.t30!=null) line("of-note", a.up ? "Up "+Math.round(o.t30)+"% in 30 days, so prices are climbing: the counter sits closer to the sticker." :
    a.down ? "Down "+Math.round(Math.abs(o.t30))+"% in 30 days, so you can push lower." : "Steady over 30 days.");
  if(o.stale) line("of-note warn", "Old price: "+o.stale+". Check eBay sold before you trust these numbers.");
  const h=!isPrivate() && habit && habit[o.ref.p<OFFER_SPLIT?"cheap":"dear"];
  if(h && h.n>=2){
    const d=Math.round((h.r-1)*100);
    line("of-note", "On "+(o.ref.p<OFFER_SPLIT?"cards under $"+OFFER_SPLIT:"cards $"+OFFER_SPLIT+" and up")+" you've usually paid "+(Math.abs(d)<1?"right at":Math.abs(d)+"% "+(d>0?"over":"under"))+" the price ("+h.n+" purchases).");
  }
}
// Card details: the Vendor's price box in the Prices tab.
let offerCond="";
function offerConds(n){
  const cb=$("oCond"); cb.replaceChildren();
  for(const k of ["NM","LP","MP","HP","DMG"]){ const b=document.createElement("button"); b.type="button"; b.textContent=k; b.setAttribute("aria-pressed", k===offerCond); b.onclick=()=>{ offerCond=offerCond===k?"":k; offerConds(n); drawCardOffer(n); }; cb.append(b); }
}
function drawCardOffer(n){
  const i=state.info[n]||{}, ask=parseFloat($("oAsk").value.replace(/^\$/,""));
  const t=trend(n,30), t7=trend(n,7);
  drawOffer($("oOut"), {ask, ref:offerRef(offerCond, (i.cond||{})[offerCond], (i.recent||{})[offerCond], basePrice(n)), t30:t?t.pct:null, stale:staleWhy(n),
    hist:offerHist((state.trends[n]||{}).h90, basePrice(n), t7?t7.pct:null)});
}
function resetCardOffer(n){
  const raw=activeSlots().find(sl=>sl.t==="raw");
  offerCond = recall("nd-offer-cond") || (raw && raw.c) || "LP";
  $("oAsk").value=""; offerConds(n); drawCardOffer(n);
  loadHabit();
}
$("oAsk").addEventListener("input",()=>{ if(state.open!=null) drawCardOffer(state.open); });
$("oCond").addEventListener("click",()=>{ if(offerCond) store("nd-offer-cond", offerCond); });
function condOptions(n){
  const sel=$("dCond"), cur=rec(n).cond||"";
  for(const o of sel.options){
    if(!o.value){ o.textContent="Not set"; continue; }
    const i=state.info[n], v=i && i.cond && i.cond[o.value];
    o.textContent = v ? o.value+" · "+money(v[0]) : o.value+" · no sales";
  }
  sel.value=cur;
  const yours=$("dYours");
  if(qty(n)>0 && cur && condPrice(n,cur)){ yours.hidden=false; yours.textContent="Your "+cur+" copy counts at "+money(condPrice(n,cur))+" in your collection value."; }
  else if(qty(n)>0 && cur){ yours.hidden=false; yours.textContent="No recent "+cur+" sales, so your copy counts at the "+mainLabel().replace(/^Combined /,"")+" average."; }
  else yours.hidden=true;
}
// Price-check links for a card in the open binder. Master set cards search with their own set and printed number, like "Expedition Totodile 134/165".
function cardLinks(n){
  const c=state.cards.find(x=>x.n===n); if(!c) return null;
  const setName=(c.set||state.set.name).replace(/ Base Set$/,"");
  const s=q(setName+" "+c.name+" "+(c.num ? c.num+(c.pt?"/"+c.pt:"") : n));
  return {
    ebay: ebaySoldUrl({year:c.date||(c.set?"":state.set.releaseDate), set:setName, name:c.name, rarity:c.rarity, num:c.num||(c.custom?"":n), pt:c.num ? c.pt : (c.custom?"":printed())}),
    pc: (state.info[n]||{}).pc || "https://www.pricecharting.com/search-products?type=prices&q="+s,
    tcg: c.tcg ? "https://www.tcgplayer.com/product/"+c.tcg : "https://www.tcgplayer.com/search/pokemon/product?q="+q(c.name+" "+setName)
  };
}
// Same links for a card from Find a card (any set).
function findLinks(c){
  const setName=(c.set||"").replace(/ Base Set$/,"");
  return {
    ebay: ebaySoldUrl({year:c.date, set:c.set, name:c.name, rarity:c.rarity, num:c.num, pt:c.pt}),
    pc: "https://www.pricecharting.com/search-products?type=prices&q="+q(setName+" "+c.name+" "+(c.num ? c.num+(c.pt?"/"+c.pt:"") : "")),
    tcg: tcgSearchUrl(c.set,c.name)
  };
}
function openCard(n){
  const c=state.cards.find(x=>x.n===n); if(!c) return; state.open=n;
  const r=rec(n);
  const art=$("dArt"); art.hidden=false; art.dataset.r=""; art.alt=c.name; art.src=base()+"/img/"+enc(n)+".png?full=1";
  art.onerror=()=>{ if(!art.dataset.r && c.img){ art.dataset.r=1; art.src=c.img; } else art.hidden=true; $("dArtBtn").hidden=art.hidden; };
  $("dArtBtn").hidden=false;
  if($("zoom").open) $("zoom").close();   // a card always opens with the small picture
  art.classList.toggle("need",qty(n)===0);
  $("dNo").textContent="No. "+label(c);
  $("dName").textContent=c.name;
  $("dRar").textContent=(c.custom?"Custom card · ":"")+(c.set ? c.set+(c.rarity?" · "+c.rarity:"") : cat(c))+(isSecret(c)?" · secret rare":"");
  $("dCustom").hidden=!c.custom; $("dExtra").hidden=!c.extra;
  { const sp=cardSpot(n); $("dSpot").hidden=!sp; if(sp) setSpot(sp.text); }
  $("dP").textContent=basePrice(n) ? money(basePrice(n)) : "–";
  { const sw=staleWhy(n); if(sw) $("dP").append(staleEl(sw)); }
  lpmpBox(n); mktLine(n); drawSales(n); ownLine(n); resetCardOffer(n); setCardTab(cardTab);
  { const sd=document.querySelector("#dlg .cs-side"); if(sd) sd.scrollTop=0; }
  $("dPsrc").textContent=priceSource(n);
  condOptions(n);
  const L=$("dLinks"); L.replaceChildren(); const k=cardLinks(n);
  [["eBay sold",k.ebay],["PriceCharting",k.pc],["TCGplayer",k.tcg]]
   .forEach(([t,u])=>{ const a=document.createElement("a"); a.href=u; a.target="_blank"; a.rel="noopener"; a.textContent=t+" ↗"; L.append(a); });
  $("dLinks2").replaceChildren(...[...L.children].map(a=>a.cloneNode(true)));   // phones show the store links in the Prices tab
  $("dQty").textContent=qty(n);
  $("dCond").value=r.cond||"";
  $("dNote").value=r.note||"";
  resetBuyForm();
  bSugList=[]; drawBSug(); loadSellers().then(list=>{ if(state.open!==n) return; bSugList=list; drawBSug(); });
  drawBuys(n); drawSpark(n);
  photoSide="front"; drawPhoto(n);
  $("dSaved").textContent=state.ready ? "" : "Can't reach "+srv()+" right now, so changes won't save.";
  $("dUpMsg").textContent="";
  $("dlg").showModal();
}
$("dClose").onclick=()=>$("dlg").close();
$("dlg").addEventListener("click",e=>{ if(e.target===$("dlg")) $("dlg").close(); });

let saveChain=Promise.resolve();
function saveCard(n, patch, done){
  const sid=state.sid;
  if(isOffline()){ return offlineSave(n, patch, done); }   // no connection: only "owned" + a new purchase, kept on the phone
  const next={...rec(n),...patch}; delete next.ed; delete next.cost;
  if(Array.isArray(next.purchases)) next.qty=next.purchases.length;
  const allOwned=()=>state.cards.length>0 && state.cards.every(c=>qty(c.n)>0);
  const wasDone=allOwned();
  state.own[n]=next;
  if(!wasDone && allOwned() && celeOn() && !isPrivate()) setTimeout(()=>celebrate((state.set.name||"Your binder")+" · all "+state.cards.length+" cards"),350); render(); if(state.open===n && $("dlg").open) ownLine(n); if(state.view==="pages") drawPages(); if(state.view==="shop") drawShop(); if(state.view==="upg") drawUpg(); if(state.view==="stats") state.spendStale=true;
  saveChain=saveChain.then(()=>fetch("api/set/"+enc(sid)+"/card/"+enc(n),{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(next)}))
    .then(r=>{ if(!r.ok) throw 0; const s=state.sets.find(x=>x.id===sid); if(s){ s.owned=state.cards.filter(c=>qty(c.n)>0).length; } done&&done(true); })
    .catch(()=>{ done&&done(false); const c=state.cards.find(x=>x.n===n); toast("Couldn't save "+(c?c.name:"that card")+".", "Try again", ()=>saveCard(n, patch, done)); });
}
function save(patch){
  const n=state.open; if(n==null) return;
  $("dSaved").textContent="Saving…";
  saveCard(n, patch, ok=>{ $("dSaved").textContent = ok ? "Saved" : "Couldn't save. Check that "+srv()+" is online."; });
  $("dQty").textContent=qty(n);
}
$("dPlus").onclick=()=>{
  const n=state.open; const l=buys(n).slice(); l.push({d:todayStr(), price:null, where:""});
  save({purchases:l}); drawBuys(n); condOptions(n);
};
$("dMinus").onclick=async()=>{
  const n=state.open; const l=buys(n).slice(); if(!l.length) return;
  if(l.length===1){ clearCard(n); return; }
  // remove the newest purchase; ask first unless it's a blank one just added
  let idx=l.length-1; for(let i=l.length-1;i>=0;i--){ if((l[i].d||"")>(l[idx].d||"")) idx=i; }
  const b=l[idx];
  if(!(isBlank(b) && b.d===todayStr())){
    const ok=await askConfirm("Remove a copy?", "This deletes "+whichBuy(b)+".", "Remove");
    if(!ok) return;
  }
  l.splice(idx,1); save({purchases:l}); drawBuys(n); condOptions(n);
};
$("dCond").onchange=e=>{ save({cond:e.target.value}); condOptions(state.open); };

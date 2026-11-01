// The card's price chart: drawing it, reading prices along it, and its condition, range and data controls.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// The card's price chart: a smooth line (green when the price went up over the range, red when it went down) you can
// drag a finger or the mouse along to read the price on any day, condition tiles to switch lines, and how far back.
// An up-or-down swipe that starts on the chart always scrolls the page: it only reads prices after a sideways move
// or a press and hold (touch-action: pan-y does the scrolling part).
const CH_CONDS=["NM","LP","MP","HP","DMG"];
const CH_RANGES=[["2W",14],["1M",30],["3M",91],["6M",182],["1Y",365],["All",0]];
// where a card's main price came from, as the server saves it (see main_price)
const CH_SRC={tcgplayer:"TCGplayer sales", pricecharting:"eBay · PriceCharting", tcgdex:"TCGplayer market", justtcg:"JustTCG", manual:"Your price"};
const chart={n:null, key:"", pts:[], salesOnly:0, W:0, H:0, X:null, Y:null, at:null, idx:-1, show:null, reset:null,
             lineEl:null, dotEl:null, samples:null, anim:0, quiet:false, Wprev:0};
const chMotion = () => !matchMedia("(prefers-reduced-motion: reduce)").matches;
const dayStr = d => d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
// One condition's prices, one point per day: saved change days carried forward, ending with today's live price
// (c can also be "MKT": the market price from TCGdex, TCGplayer's when there is one, else Cardmarket's)
function marketNow(n){ const m=(state.info[n]||{}).mkt||{}; return m.tp!=null ? m.tp : m.cm30!=null ? m.cm30 : null; }
function condLine(n, c){
  const got=/** @type {any} */ (Array.isArray(state.seriesCache[n]) ? state.seriesCache[n] : null), t=todayStr();
  const live=c==="MKT" ? (marketNow(n)!=null ? [marketNow(n)] : null) : ((state.info[n]||{}).cond||{})[c];
  const saved=c==="MKT" ? (got && got.market && ((state.info[n]||{}).mkt||{}).tp==null && got.market.Cardmarket || got && got.market && got.market.TCGplayer)
    : got && got.cond && got.cond[c];
  const pts=(saved || []).map(p=>[p[0],p[1]]);
  if(live && live[0]!=null){ if(pts.length && pts[pts.length-1][0]===t) pts[pts.length-1][1]=live[0]; else if(!pts.length || pts[pts.length-1][0]<t) pts.push([t,live[0]]); }
  if(!pts.length) return [];
  const out=[]; let i=0, val=pts[0][1];
  for(const d=new Date(pts[0][0]+"T12:00:00"); out.length<4000; d.setDate(d.getDate()+1)){
    const k=dayStr(d); while(i<pts.length && pts[i][0]<=k){ val=pts[i][1]; i++; }
    out.push([k,val]); if(k>=t) break;
  }
  return out;
}
// A smooth line through points [[x,y],...] that never overshoots them (monotone cubic), so it can't invent a high
// or a low. Returns the SVG path and at(x), the line's height at any x.
function smoothLine(P){
  const n=P.length, h=[], s=[], m=[];
  for(let i=0;i<n-1;i++){ h[i]=P[i+1][0]-P[i][0]; s[i]=(P[i+1][1]-P[i][1])/(h[i]||1); }
  m[0]=s[0]||0; m[n-1]=s[n-2]||0;
  for(let i=1;i<n-1;i++) m[i] = s[i-1]*s[i]<=0 ? 0 : 3*(h[i-1]+h[i])/((2*h[i]+h[i-1])/s[i-1]+(h[i]+2*h[i-1])/s[i]);
  let d="M"+P[0][0].toFixed(1)+","+P[0][1].toFixed(1);
  for(let i=0;i<n-1;i++){
    const q=h[i]/3;
    d+="C"+(P[i][0]+q).toFixed(1)+","+(P[i][1]+m[i]*q).toFixed(1)+" "+(P[i+1][0]-q).toFixed(1)+","+(P[i+1][1]-m[i+1]*q).toFixed(1)+" "+P[i+1][0].toFixed(1)+","+P[i+1][1].toFixed(1);
  }
  const at=x=>{
    if(n<2 || x<=P[0][0]) return P[0][1];
    if(x>=P[n-1][0]) return P[n-1][1];
    let i=0; while(i<n-2 && x>P[i+1][0]) i++;
    const t=(x-P[i][0])/(h[i]||1), t2=t*t, t3=t2*t;
    return (2*t3-3*t2+1)*P[i][1]+(t3-2*t2+t)*h[i]*m[i]+(-2*t3+3*t2)*P[i+1][1]+(t3-t2)*h[i]*m[i+1];
  };
  return {d, at};
}
function drawSpark(n){
  const box=$("dSpark");
  const fresh=chart.n!==n, quiet=chart.quiet; chart.quiet=false;
  box.replaceChildren();
  chart.n=n; chart.pts=[]; chart.idx=-1; chart.lineEl=null; chart.salesOnly=0;
  let mode=recall("nd-chart-cond")||"price"; if(mode!=="price" && mode!=="MKT" && !CH_CONDS.includes(mode)) mode="price";
  let range=+(recall("nd-chart-range")||0); if(!CH_RANGES.some(r=>r[1]===range)) range=0;
  const priceLine=series(n);   // also asks the server for this card's history when it isn't loaded yet
  const info=state.info[n]||{}, got=/** @type {any} */ (Array.isArray(state.seriesCache[n]) ? state.seriesCache[n] : null), sales=got && got.sales || {};
  const label=mode==="price" ? "Price" : mode==="MKT" ? "Market" : mode, rangeName=(CH_RANGES.find(r=>r[1]===range)||["All"])[0];
  // the readout: big price, then how it changed today and over the range (the date instead, while you drag)
  const top=document.createElement("div"); top.className="ch-top"; top.setAttribute("aria-live","polite");
  const big=document.createElement("div"); big.className="ch-big";
  const bv=document.createElement("b"), bl=document.createElement("span"); bl.className="ch-lab"; bl.textContent=label; big.append(bv,bl);
  const sub=document.createElement("div"); sub.className="ch-sub";
  top.append(big,sub);
  const plot=document.createElement("div"); plot.className="ch-plot";
  const ranges=document.createElement("div"); ranges.className="ch-ranges"; ranges.setAttribute("role","group"); ranges.setAttribute("aria-label","How far back");
  for(const [rl,days] of CH_RANGES){
    const b=document.createElement("button"); b.type="button"; b.textContent=String(rl); b.setAttribute("aria-pressed",String(days===range));
    b.onclick=()=>{ store("nd-chart-range", days ? String(days) : undefined); drawSpark(n); };
    ranges.append(b);
  }
  // the condition tiles, each with its latest average; the row swipes sideways if it doesn't fit
  const tiles=document.createElement("div"); tiles.className="ch-tiles"; tiles.setAttribute("role","group"); tiles.setAttribute("aria-label","Which price");
  for(const c of ["price","MKT"].concat(CH_CONDS)){
    const v=c==="price" ? basePrice(n) : c==="MKT" ? marketNow(n) : ((info.cond||{})[c]||[])[0];
    const b=document.createElement("button"); b.type="button"; b.className="ch-tile"; b.setAttribute("aria-pressed",String(c===mode));
    if(c!=="price" && v==null && !(c==="MKT" ? got && got.market && Object.keys(got.market).length : got && got.cond && got.cond[c])) b.classList.add("none");
    const l=document.createElement("small"); l.textContent=c==="price" ? "Price" : c==="MKT" ? "Market" : c;
    const p=document.createElement("b"); p.textContent=v ? money(v) : "–";
    b.append(l,p); b.onclick=()=>{ store("nd-chart-cond", c==="price" ? undefined : c); drawSpark(n); };
    tiles.append(b);
  }
  const cap=document.createElement("div"); cap.className="cap";
  box.append(top,plot,ranges,tiles,cap);
  // slide the tiles row only when the chosen tile would be hidden
  requestAnimationFrame(()=>{ const on=/** @type {HTMLElement} */ (tiles.querySelector('[aria-pressed="true"]')); if(!on) return; const r=tiles.getBoundingClientRect(), o=on.getBoundingClientRect(); if(o.right>r.right+1) tiles.scrollLeft+=o.left-r.left-r.width/2+o.width/2; });
  // the line to draw, cut to the chosen range
  const all=mode==="price" ? priceLine : condLine(n,mode);
  let pts=all;
  if(range){ const cut=new Date(); cut.setDate(cut.getDate()-range); const k=dayStr(cut); pts=all.filter(p=>p[0]>=k); }
  const latest=all.length ? all[all.length-1] : null;
  const when=d=>d===todayStr() ? "Today" : fmtDay(d);
  const change=(from,to,what)=>{
    const d=document.createElement("div"), dd=to-from, up=dd>=0;
    d.className=Math.abs(dd)<0.005 ? "" : up ? "pos" : "neg";
    d.textContent=(Math.abs(dd)<0.005 ? "–" : up ? "↑" : "↓")+" "+money(Math.abs(dd))+" ("+(from ? (Math.abs(dd)/from*100).toFixed(1) : "0.0")+"%) "+what;
    return d;
  };
  // the sale dots: this condition's, or on Price the conditions your price is made from
  const dotConds=mode==="price" ? activeSlots().filter(sl=>sl.t==="raw").map(sl=>sl.c) : mode==="MKT" ? [] : [mode];
  // No line yet (each condition's line builds up one price check at a time): show the sales saved so far instead,
  // ending with today's average, so the chart is useful from the first day
  if(pts.length<2){
    let sl=dotConds.flatMap(c=>(sales[c]||[]).map(s=>[s[0],s[1]])).sort((a,b)=>a[0]<b[0] ? -1 : a[0]>b[0] ? 1 : 0);
    if(range){ const cut=new Date(); cut.setDate(cut.getDate()-range); const k=dayStr(cut); sl=sl.filter(s=>s[0]>=k); }
    if(sl.length){ chart.salesOnly=sl.length; pts = latest && latest[0]>=sl[sl.length-1][0] ? sl.concat([latest]) : sl; }
  }
  const salesOnly=chart.salesOnly;
  chart.reset=()=>{
    bv.textContent=latest ? money(latest[1]) : (mode==="price" && basePrice(n) ? money(basePrice(n)) : "–");
    sub.replaceChildren();
    if(pts.length<2){ const d=document.createElement("div"); d.textContent=latest ? when(latest[0]) : ""; sub.append(d); return; }
    if(all.length>1) sub.append(change(all[all.length-2][1], all[all.length-1][1], "Today"));
    sub.append(change(pts[0][1], pts[pts.length-1][1], range ? rangeName+" change" : "since "+fmtDay(pts[0][0])));
  };
  chart.show=i=>{
    const p=chart.pts[i]; if(!p) return;
    bv.textContent=money(p[1]);
    sub.replaceChildren(); const d=document.createElement("div"); d.textContent=(i<salesOnly ? "Sale · " : "")+when(p[0]); sub.append(d);
  };
  chart.reset();
  if(pts.length<2){
    const m=document.createElement("div"); m.className="ch-msg";
    m.textContent = mode==="price" ? "Price trend appears after a few days of saved prices."
      : mode==="MKT" ? (!all.length ? "No market price for this card yet." : "The market price trend builds up from "+fmtDay(all[0][0])+".")
      : !all.length ? "No "+mode+" sales saved yet."
      : "Each condition's trend builds up from "+fmtDay(all[0][0])+".";
    plot.append(m); chart.samples=null; return;
  }
  // size the drawing to the space it has, so text and dots stay crisp (redrawn if that changes)
  // PR: room on the right for the price axis; DB: room at the bottom for dates; B: where the plot ends
  const W=Math.round(plot.clientWidth)||340, H=W<500 ? 204 : 224, PT=34, PB=56, PX=8, PR=44, DB=18, B=H-DB;
  const t0=Date.parse(pts[0][0]+"T12:00:00"), t1=Date.parse(pts[pts.length-1][0]+"T12:00:00");
  const k0=pts[0][0];
  const dots=salesOnly ? [] : dotConds.flatMap(c=>(sales[c]||[]).filter(s=>s[0]>=k0));
  const ys=pts.map(p=>p[1]).concat(dots.map(s=>s[1])), y0=Math.min(...ys), y1=Math.max(...ys);
  const X=d=>PX+(t1===t0?0.5:(Date.parse(d+"T12:00:00")-t0)/(t1-t0))*(W-PX-PR), Y=v=>H-PB-(y1===y0?0.5:(v-y0)/(y1-y0))*(H-PT-PB);
  // the curve goes through each day the price changed (plus the first and last), so it eases from one price to the next
  const keyPts=pts.filter((p,i)=>i===0 || i===pts.length-1 || p[1]!==pts[i-1][1]).map(p=>[X(p[0]),Y(p[1])]);
  // while a condition's daily prices build up, the line goes through its saved sales (one point per day, the
  // average when there were several), ending at today's average
  const byDay=[];
  if(salesOnly) for(const p of pts){ const l=byDay[byDay.length-1]; if(l && l[0]===p[0]){ l[1]+=p[1]; l[2]++; } else byDay.push([p[0],p[1],1]); }
  const curvePts=salesOnly ? byDay.map(d=>[X(d[0]),Y(d[1]/d[2])]) : keyPts;
  const curve=curvePts.length>1 ? smoothLine(curvePts.filter((p,i)=>i===0 || p[0]>curvePts[i-1][0])) : null;
  const up=pts[pts.length-1][1]>=pts[0][1], color=up ? "var(--good)" : "var(--bad)";
  const ns="http://www.w3.org/2000/svg", svg=document.createElementNS(ns,"svg");
  svg.setAttribute("viewBox","0 0 "+W+" "+H); svg.setAttribute("width",String(W)); svg.setAttribute("height",String(H)); svg.setAttribute("role","img");
  const lo=Math.min(...pts.map(p=>p[1])), hi=Math.max(...pts.map(p=>p[1]));
  svg.setAttribute("aria-label", salesOnly ? label+" sales: "+salesOnly+" since "+fmtDay(pts[0][0])+", low "+money(lo)+", high "+money(hi)
    : label+" price chart: "+money(pts[0][1])+" on "+fmtDay(pts[0][0])+" to "+money(pts[pts.length-1][1])+" now, low "+money(lo)+", high "+money(hi));
  const mk=(tag,attrs)=>{ const e=document.createElementNS(ns,tag); for(const k in attrs) e.setAttribute(k,attrs[k]); return e; };
  const gid="chg"+Date.now();
  const defs=mk("defs",{}), grad=mk("linearGradient",{id:gid, x1:"0", y1:"0", x2:"0", y2:"1"});
  grad.append(mk("stop",{offset:"0", "stop-color":color, "stop-opacity":"0.28"}), mk("stop",{offset:"1", "stop-color":color, "stop-opacity":"0"}));
  const clip=mk("clipPath",{id:gid+"c"}), clipRect=mk("rect",{x:"0", y:"0", width:String(W), height:String(H)});
  clip.append(clipRect); defs.append(grad,clip); svg.append(defs);
  // the price axis: a few round prices as faint lines with their value on the right, and dates along the bottom
  const span=y1-y0 || Math.max(1,y1*0.1), raw=span/3, mag=Math.pow(10,Math.floor(Math.log10(raw))), f=raw/mag;
  const step=(f<=1 ? 1 : f<=2 ? 2 : f<=2.5 ? 2.5 : f<=5 ? 5 : 10)*mag;
  const axisMoney=v=>"$"+(step<1 ? v.toFixed(2) : v>=10000 ? Math.round(v/1000)+"k" : Math.round(v).toLocaleString("en-US"));
  const lo0=y1===y0 ? y0-step : y0, hi0=y1===y0 ? y0+step : y1;
  for(let v=Math.ceil(lo0/step)*step; v<=hi0+step*1e-6; v+=step){
    const y=y1===y0 ? Y(y0)+(y0-v)/step*20 : Y(v); if(y<PT-8 || y>B-4) continue;
    svg.append(mk("line",{x1:String(PX), x2:String(W-PR+4), y1:y.toFixed(1), y2:y.toFixed(1), class:"ch-grid"}));
    const t=mk("text",{x:String(W-2), y:(y+4).toFixed(1), "text-anchor":"end", class:"ch-axis"}); t.textContent=axisMoney(v); svg.append(t);
  }
  const nDates=W<420 ? 3 : 4, short=d=>new Date(d+"T12:00:00").toLocaleDateString("en-US",{month:"short", day:"numeric"});
  for(let i=0;i<nDates;i++){
    const tt=t0+(t1-t0)*i/(nDates-1), d=dayStr(new Date(tt)), x=X(d);
    const t=mk("text",{x:x.toFixed(1), y:String(H-3), "text-anchor":i===0 ? "start" : i===nDates-1 ? "end" : "middle", class:"ch-axis"});
    t.textContent=short(d); svg.append(t);
    if(t1===t0) break;
  }
  const g=mk("g",{"clip-path":"url(#"+gid+"c)"}); svg.append(g);
  let area=null, lineP=null;
  if(curve){
    area=mk("path",{d:curve.d+"L"+curvePts[curvePts.length-1][0].toFixed(1)+","+B+"L"+curvePts[0][0].toFixed(1)+","+B+"Z", fill:"url(#"+gid+")"});
    lineP=mk("path",{d:curve.d, fill:"none", stroke:color, "stroke-width":"2.5", "stroke-linejoin":"round", "stroke-linecap":"round"});
    g.append(area,lineP);
  }
  for(const s of dots) g.append(mk("circle",{cx:X(s[0]), cy:Y(s[1]), r:"2.5", fill:"var(--ink)", opacity:"0.35"}));
  for(const s of pts.slice(0,salesOnly)) g.append(mk("circle",{cx:X(s[0]), cy:Y(s[1]), r:"3", fill:"var(--ink)", opacity:"0.45"}));
  const last=pts[pts.length-1];
  if(curve || pts.length>salesOnly) g.append(mk("circle",{cx:X(last[0]), cy:curve ? curve.at(X(last[0])) : Y(last[1]), r:"4", fill:color, stroke:"var(--surface)", "stroke-width":"2"}));
  // High and Low labels at the highest and lowest points (not on a flat line)
  if(hi>lo){
    const hiP=pts.find(p=>p[1]===hi), loP=pts.find(p=>p[1]===lo);
    const lab=(p,word,above)=>{
      const x=X(p[0]), anchor=x<44 ? "start" : x>W-PR-36 ? "end" : "middle", tx=Math.max(4,Math.min(W-PR-2,x));
      const yv=above ? Y(p[1])-10 : Y(p[1])+32, yw=yv-14;
      const t1=mk("text",{x:tx, y:yw, "text-anchor":anchor, class:"ch-hl-k"}); t1.textContent=word;
      const t2=mk("text",{x:tx, y:yv, "text-anchor":anchor, class:"ch-hl-v"}); t2.textContent=money(p[1]);
      svg.append(t1,t2);
    };
    lab(hiP,"High",true); lab(loP,"Low",false);
  }
  chart.lineEl=mk("line",{y1:"0", y2:String(B), stroke:"var(--ink)", "stroke-width":"1", opacity:"0.35", visibility:"hidden"});
  chart.dotEl=mk("circle",{r:"6", fill:color, stroke:"var(--surface)", "stroke-width":"2.5", visibility:"hidden"});
  svg.append(chart.lineEl, chart.dotEl);
  plot.append(svg); plot.tabIndex=0; plot.setAttribute("aria-label",(salesOnly ? "Sales chart" : "Price chart")+". Use the left and right arrow keys to read each "+(salesOnly ? "sale" : "day")+".");
  chart.pts=pts; chart.X=X; chart.Y=Y; chart.W=W; chart.H=H; chart.at=curve ? curve.at : null;
  // View price data: every day the price changed (and each saved sale), newest first
  const det=document.createElement("details"); det.className="ch-data"; det.open=!!chart.tableOpen;
  det.addEventListener("toggle",()=>{ chart.tableOpen=det.open; });
  const sum=document.createElement("summary"); sum.textContent="View price data";
  const tbl=document.createElement("table"), cp=document.createElement("caption"), thead=document.createElement("thead"), tb=document.createElement("tbody");
  cp.textContent=label+(salesOnly ? " sales saved so far" : (mode==="price" ? "" : " price")+", each day it changed")+(range ? ", last "+rangeName : "");
  const hr=document.createElement("tr"); for(const t of ["Date","From","Price"]){ const th=document.createElement("th"); th.scope="col"; th.textContent=t; hr.append(th); } thead.append(hr);
  // where each row's price came from: on Price, the source saved for that day (today's is the live one)
  const srcDays=got && got.src || [], mktName=info.mkt && info.mkt.tp==null && got && got.market && got.market.Cardmarket ? "Cardmarket" : "TCGplayer market";
  const srcOn=d=>{ if(d===todayStr() && info.src) return CH_SRC[info.src]||""; let s=""; for(const [k,v] of srcDays){ if(k>d) break; s=v; } return CH_SRC[s]||""; };
  const from=(p,i)=>i<salesOnly ? "TCGplayer sale" : mode==="price" ? srcOn(p[0]) : mode==="MKT" ? mktName : "TCGplayer sales";
  let unknown=false;
  for(let i=pts.length-1;i>=0;i--){
    const p=pts[i]; if(!(i<salesOnly || i===0 || i===pts.length-1 || p[1]!==pts[i-1][1])) continue;
    const tr=document.createElement("tr"), td1=document.createElement("td"), td2=document.createElement("td"), td3=document.createElement("td");
    const f=from(p,i); if(!f) unknown=true;
    td1.textContent=fmtDay(p[0]); td3.className="ch-src"; td3.textContent=f||"–"; td2.textContent=money(p[1]); tr.append(td1,td3,td2); tb.append(tr);
  }
  tbl.append(cp,thead,tb); const wrap=document.createElement("div"); wrap.className="ch-table"; wrap.append(tbl);
  det.append(sum,wrap); box.append(det);
  if(unknown){ const nt=document.createElement("div"); nt.className="ch-note"; nt.textContent="– means that day is from before the binder saved where prices came from."; det.append(nt); }
  if(salesOnly) cap.append("For now the line goes through the "+salesOnly+" sale"+(salesOnly===1 ? "" : "s")+" saved since "+fmtDay(pts[0][0])+". "
    +(mode==="price" ? "It switches to your saved prices after a few days." : "It switches to "+mode+"'s saved daily prices once they build up (from "+fmtDay(all.length ? all[0][0] : todayStr())+")."));
  // movement: a new card's line draws itself in; switching condition or range slides the line into its new shape
  const x0=curvePts.length ? curvePts[0][0] : PX, x1=curvePts.length ? curvePts[curvePts.length-1][0] : W-PR;
  const N=72, samples=curve ? Array.from({length:N},(_,i)=>curve.at(x0+i*(x1-x0)/(N-1))) : null;
  cancelAnimationFrame(chart.anim);
  const prev=chart.samples; chart.samples=samples;
  if(quiet || !chMotion()) return;
  if(fresh || !prev || !samples || prev.length!==N || chart.Wprev!==W){
    clipRect.setAttribute("width","0"); const start=performance.now();
    const grow=now=>{ const k=Math.min(1,(now-start)/650), e=1-Math.pow(1-k,3); clipRect.setAttribute("width",String(W*e)); if(k<1) chart.anim=requestAnimationFrame(grow); };
    chart.anim=requestAnimationFrame(grow);
  } else if(lineP && area){
    const final=lineP.getAttribute("d"), finalArea=area.getAttribute("d"), start=performance.now();
    const path=ys=>"M"+ys.map((y,i)=>(x0+i*(x1-x0)/(N-1)).toFixed(1)+","+y.toFixed(1)).join("L");
    const step=now=>{
      const k=Math.min(1,(now-start)/320), e=k<.5 ? 4*k*k*k : 1-Math.pow(-2*k+2,3)/2;
      if(k<1){
        const d=path(samples.map((y,i)=>prev[i]+(y-prev[i])*e));
        lineP.setAttribute("d",d); area.setAttribute("d",d+"L"+x1.toFixed(1)+","+B+"L"+x0.toFixed(1)+","+B+"Z");
        chart.anim=requestAnimationFrame(step);
      } else { lineP.setAttribute("d",final); area.setAttribute("d",finalArea); }
    };
    chart.anim=requestAnimationFrame(step);
  }
  chart.Wprev=W;
}
// Show the line at a spot: the dot glides along the line under your finger, the readout shows that day
function chartGlide(x){
  if(!chart.pts.length || !chart.lineEl) return;
  x=Math.max(0,Math.min(chart.W,x));
  let best=0, bd=Infinity; chart.pts.forEach((p,i)=>{ const d=Math.abs(chart.X(p[0])-x); if(d<bd){ bd=d; best=i; } });
  const snap=!chart.at;   // sales only: the dot sits on each sale
  const px=snap ? chart.X(chart.pts[best][0]) : x, py=snap ? chart.Y(chart.pts[best][1]) : chart.at(x);
  chart.lineEl.setAttribute("x1",px); chart.lineEl.setAttribute("x2",px); chart.lineEl.setAttribute("visibility","visible");
  chart.dotEl.setAttribute("cx",px); chart.dotEl.setAttribute("cy",py); chart.dotEl.setAttribute("visibility","visible");
  if(best!==chart.idx){ chart.idx=best; chart.show(best); return true; }
  return false;
}
function chartAt(i){ if(chart.pts[i]) chartGlide(chart.X(chart.pts[i][0])); }
function chartAtX(clientX){
  const svg=$("dSpark").querySelector(".ch-plot svg"); if(!svg) return false;
  const r=svg.getBoundingClientRect();
  return chartGlide((clientX-r.left)/r.width*chart.W);
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
  const buzz=()=>{ try{ if(navigator.vibrate) navigator.vibrate(4); }catch(_){} };   // a tiny tick on each new day (phones)
  const stop=()=>{ clearTimeout(hold); start=null; reading=false; chartOff(); };
  box.addEventListener("pointerdown",e=>{
    if(e.pointerType==="mouse" || !e.target.closest(".ch-plot svg")) return;
    start={x:e.clientX, y:e.clientY, id:e.pointerId}; reading=false;
    clearTimeout(hold); hold=setTimeout(()=>{ if(start){ reading=true; chartAtX(start.x); buzz(); } },300);   // press and hold
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
    if(chartAtX(e.clientX)) buzz();
  });
  for(const ev of ["pointerup","pointercancel"]) box.addEventListener(ev,e=>{ if(e.pointerType!=="mouse") stop(); });
  box.addEventListener("pointerleave",e=>{ if(e.pointerType==="mouse") chartOff(); });
  box.addEventListener("contextmenu",e=>{ if(e.target.closest(".ch-plot")) e.preventDefault(); });   // press and hold reads prices, not a menu
  box.addEventListener("keydown",e=>{
    if(!e.target.classList || !e.target.classList.contains("ch-plot") || !chart.pts.length) return;
    if(e.key==="ArrowLeft" || e.key==="ArrowRight"){ e.preventDefault(); chartAt(chart.idx<0 ? chart.pts.length-1 : Math.max(0,Math.min(chart.pts.length-1,chart.idx+(e.key==="ArrowLeft"?-1:1)))); }
    else if(e.key==="Escape" && chart.idx>=0){ e.preventDefault(); e.stopPropagation(); chartOff(); }
  });
  box.addEventListener("focusout",e=>{ if(e.target.classList && e.target.classList.contains("ch-plot")) chartOff(); });
  // the chart is drawn to fit its space: draw it again (without movement) when that space changes size
  if(window.ResizeObserver) new ResizeObserver(()=>{
    const plot=box.querySelector(".ch-plot"); if(!plot || chart.n==null || !$("dlg").open) return;
    const w=Math.round(plot.clientWidth); if(w && chart.W && Math.abs(w-chart.W)>2){ chart.quiet=true; drawSpark(chart.n); }
  }).observe(box);
})();

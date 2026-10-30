// Shared basics: themes list, the app's state, small helpers, binder kinds.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

const SKINS = [
  ["night","Night","Violet and gold, the default",["#15121E","#A88BEA","#E2B04A","#5CC3CC"]],
  ["ember","Ember","Warm reds, Dark Typhlosion style",["#18110F","#E2734D","#F0A23B","#E8C547"]],
  ["abyss","Abyss","Deep teal, Shining Kabutops style",["#0D1618","#64B9CB","#E7C15A","#7FE0C8"]],
  ["haunter","Haunter","Purple and pink, ghost type",["#150F1C","#C882F0","#F2C14E","#F07FB6"]],
  ["graphite","Graphite","Neutral charcoal, lets the cards pop",["#111213","#9FAABC","#D6B25E","#7EC8D8"]]
];
const RSYM = {"Common":"●","Uncommon":"◆","Rare":"★","Rare Holo":"★ Holo","Rare Shining":"★ Shining","Rare Secret":"★ Secret"};
const DEFAULT_SLOTS=[{t:"raw",c:"LP"},{t:"raw",c:"MP"}];
const state = { serverName:"", slots:DEFAULT_SLOTS, slotOpts:null, trends:{}, histFirst:"", seriesCache:{}, view:"cards", spend:null, sid:null, set:{}, cards:[], own:{}, prices:{}, info:{}, updated:"", sets:[], catalog:null,
                filter:"all", rar:"", sort:"num", q:"", ready:false, open:null };
/** @type {(id: string) => any} any page element: an input, a dialog, a list... */
const $ = id => document.getElementById(id);
const money = v => v==null ? "–" : "$"+v.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const money0 = v => "$"+Math.round(v||0).toLocaleString("en-US");
const store = (k,v) => { try{ v===undefined ? localStorage.removeItem(k) : localStorage.setItem(k,v); }catch(_){} };
const recall = k => { try{ return localStorage.getItem(k); }catch(_){ return null; } };
// What holding a card opens: eBay sold (default), TCGplayer, PriceCharting, or nothing
function lpMode(){ const v=recall("nd-lp"); return ["tcg","pc","off"].includes(v) ? v : "ebay"; }
const enc = encodeURIComponent;
const q = s => enc(s).replace(/%20/g,"+");
const when = s => { if(!s) return "setup"; const d=new Date(s.length===10 ? s+"T12:00:00" : s); return isNaN(d) ? s : d.toLocaleString("en-US", s.length===10 ? {month:"short",day:"numeric",year:"numeric"} : {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}); };
const year = s => (s||"").slice(0,4);
// Search by name, or by the number printed on the card: "1", "001", "#1" or "1/105".
const normNum = t => t.toLowerCase().replace(/^([a-z]*)0+(?=\d)/,"$1");
function matchQ(c, q){
  // A search that's just a number ("2", "#2", "002", "2/105") matches the card number only,
  // so "2" finds card 2 and not every name with a 2 in it (like Porygon2).
  const m=/^(?:no\.?\s*)?#?\s*([a-z]{0,2}\d+[a-z]?)\s*(?:\/\s*(\d*))?$/.exec(q);
  if(m && /\d/.test(q) && !/^[a-z]{3,}/.test(q)) return normNum(m[1])===normNum(c.num||c.n);
  return c.name.toLowerCase().includes(q) || (c.set||"").toLowerCase().includes(q);
}
const numVal = n => { const m=/^([A-Za-z]*)(\d+)/.exec(n); return m ? [m[1], +m[2]] : [n,0]; };
// A Pokémon master set binder (id like dex-158) holds one Pokémon's cards from every set.
// Each of its cards carries its own set name (set), printed number (num) and set size (pt).
const isDex = id => /^dex-\d+$/.test(id||"");
// ---------- binder kinds ----------
// Set binders hold one set. Master sets (dex-158) and your own binders (my-1) hold cards from many sets,
// and each of those cards remembers its own set and number.
const isOwn = id => /^my-\d+$/.test(id||"");
const isMulti = id => isDex(id) || isOwn(id);
const padNo = (num, pt) => { const n=numVal(String(num||"")); return (n[0] ? num : String(n[1]).padStart(3,"0"))+(pt?"/"+pt:""); };
// eBay sold listings, searched the way listings are titled: "2002 Neo Destiny Dark Ampharos Holo #1/105".
// eBay only shows listings with every word, so only words sellers nearly always use go in ("Holo", not "Holo Rare").
const ebaySoldUrl = ({year, set, name, rarity, num, pt}) => {
  const no = num ? "#"+String(num).replace(/^0+(?=\d)/,"")+(pt ? "/"+pt : "") : "";
  const words=[String(year||"").slice(0,4), (set==="Base" ? "Base Set" : (set||"").replace(/ Base Set$/,"")), name, /Holo/.test(rarity||"") ? "Holo" : "", no].filter(Boolean).join(" ");
  return "https://www.ebay.com/sch/i.html?_nkw="+enc(words)+"&LH_Sold=1&LH_Complete=1";
};
const tcgSearchUrl = (set, name) => "https://www.tcgplayer.com/search/pokemon/product?q="+q(name+" "+(set||"").replace(/ Base Set$/,""));
const binderName = sid => (state.sets.find(s=>s.id===sid)||{}).name || sid;

const byNum = (a,b) => { if(!!a.custom!==!!b.custom) return a.custom?1:-1; if(a.custom) return numVal(a.n)[1]-numVal(b.n)[1];
  /* cards added from Find a card: after the set's own, in the order added */ if(!!a.extra!==!!b.extra) return a.extra?1:-1; if(a.extra) return (a.k||0)-(b.k||0);
  if(a.i!=null && b.i!=null) return a.i-b.i; const x=numVal(a.n), y=numVal(b.n); return x[0]<y[0]?-1:x[0]>y[0]?1:x[1]-y[1]; };
const printed = () => state.set.printedTotal || 0;
const label = c => {
  const num=c.num||c.n, pt=c.num ? c.pt : printed(), n=numVal(num);
  return (n[0] ? num : String(n[1]).padStart(3,"0")) + (pt ? "/"+pt : "");
};
const isSecret = c => { const pt=c.num ? c.pt : printed(), n=numVal(c.num||c.n); return pt && !n[0] && n[1] > pt; };
const tint = c => /Shining|Secret|Star/.test(c.rarity) || isSecret(c) ? "t-shine" : c.name.startsWith("Dark ") ? "t-dark" : c.name.startsWith("Light ") ? "t-light" : "";
const cat = c => c.set ? c.set : (c.rarity || "Unlisted") + (c.type==="Trainer" ? " · Trainer" : c.type==="Energy" ? " · Energy" : "");
const rec = n => state.own[n] || {};
const qty = n => Number(rec(n).qty)||0;
const basePrice = n => (state.prices[n]||[0])[0] || 0;
const condPrice = (n,c) => { const i=state.info[n]; const v=i && i.cond && i.cond[c]; return v ? v[0] : 0; };
// Owned cards with a condition set use that condition's average; everything else uses the main price from Settings.
const isPrivate = () => document.documentElement.hasAttribute("data-private");
// In privacy mode every card shows the same market price, so condition-based values can't hint at ownership.
const priceOf = n => (!isPrivate() && qty(n)>0 && rec(n).cond && condPrice(n,rec(n).cond)) || basePrice(n);
const base = () => "set/"+enc(state.sid);
const todayStr = () => { const d=new Date(); return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0"); };
const buys = n => {
  const l=(rec(n).purchases||[]).filter(b=>b && typeof b==="object");
  const q=Number(rec(n).qty)||0;
  return q>l.length ? Array.from({length:q-l.length},()=>({d:"",price:null,where:""})).concat(l) : l;
};
const whichBuy = b => b.d ? "the purchase from "+fmtDay(b.d)+(b.price?" ("+money(Number(b.price))+")":"") : "a copy logged before tracking"+(b.price?" ("+money(Number(b.price))+")":"");
const isBlank = b => !b.price && !b.where && !(b.seller && b.seller.h);
// In-page confirm box. Resolves true when the person confirms.
function askConfirm(title, msg, okLabel, opts={}){
  return askChoice(title, msg, okLabel, opts).then(v=>v==="ok");
}
// Same box with an optional middle button (opts.alt = its label). Resolves "ok", "alt", or "" for Cancel.
function askChoice(title, msg, okLabel, opts={}){
  return new Promise(res=>{
    const dlg=$("confirm"); $("cfTitle").textContent=title; $("cfMsg").textContent=msg; $("cfOk").textContent=okLabel||"Delete";
    $("cfBody").replaceChildren(...(opts.body?[opts.body]:[]));
    $("cfOk").className="btn "+(opts.safe?"primary":"danger");
    $("cfAlt").hidden=!opts.alt; $("cfAlt").textContent=opts.alt||"";
    dlg.returnValue=""; dlg.onclose=()=>res(dlg.returnValue==="ok"||dlg.returnValue==="alt" ? dlg.returnValue : "");
    dlg.showModal(); $("cfCancel").focus();
  });
}
const paidFor = n => buys(n).reduce((a,b)=>a+(Number(b.price)||0),0);
const fmtDay = d => d ? new Date(d+"T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "Before tracking";
// Price history for one card: [[date, price], ...] oldest first, ending with today's live price.
// The server sends one card's history when its details open (the rest of the page only needs the summary in state.trends).
function loadSeries(n){
  const sid=state.sid;
  if(state.seriesCache[n]) return;
  state.seriesCache[n]="loading";
  fetch("api/set/"+enc(sid)+"/history?card="+enc(n)).then(r=>r.json()).then(j=>{
    if(state.sid!==sid || !Array.isArray(j.points)) return;
    state.seriesCache[n]=j.points;
    if(state.open===n && $("dlg").open) drawSpark(n);
  }).catch(()=>{ if(state.seriesCache[n]==="loading") delete state.seriesCache[n]; });
}
function series(n){
  const got=state.seriesCache[n];
  if(!Array.isArray(got)){ loadSeries(n); return []; }
  const out=got.map(p=>[p[0],p[1]]);
  const cur=basePrice(n), t=todayStr();
  if(cur){ if(out.length && out[out.length-1][0]===t) out[out.length-1][1]=cur; else out.push([t,cur]); }
  return out;
}
// Price change period, chosen in Settings or the phone Filters panel (0 = all time). Saved per device.
const PERIODS=[[1,"1 day"],[7,"7 days"],[30,"30 days"],[90,"90 days"],[365,"1 year"],[0,"All time"]];
state.period = (()=>{ const v=recall("nd-period"); return v!=null && PERIODS.some(p=>String(p[0])===v) ? +v : 7; })();
const periodName = (d=state.period) => (PERIODS.find(p=>p[0]===d)||[0,d+" days"])[1];
// How many days of saved prices this binder has, for the "still filling in" note.
const historyDays = () => state.histFirst ? Math.round((new Date(todayStr())-new Date(state.histFirst))/864e5) : 0;
function periodNote(){
  const have=historyDays(), want=state.period;
  if(!state.histFirst) return "Price changes appear once "+srv()+" has saved a few days of prices.";
  if(want===0) return "All time = since "+fmtDay(state.histFirst)+".";
  if(have<want) return Srv()+" has "+have+" day"+(have===1?"":"s")+" of saved prices so far (since "+fmtDay(state.histFirst)+"), so this shows the change over those days until "+periodName()+" builds up.";
  return "";
}
function setPeriod(d){
  state.period=d; store("nd-period",String(d));
  if($("stPeriod")) $("stPeriod").value=String(d);
  if($("stPeriodNote2")){ const t=periodNote(); $("stPeriodNote2").textContent=t; $("stPeriodNote2").hidden=!t; }
  render(); if(state.view==="stats") renderView();
}
// Change over the last `days` days (uses the oldest point if history is shorter; 0 = all time).
// the server's summary per card (state.trends[n]): first and last saved price, how many days, and the price as it
// stood 1/7/30/90/365 days back. Gives the same answer as reading every saved day.
function trend(n, days=state.period){
  const h=state.trends[n]; if(!h) return null;
  const cur=basePrice(n), t=todayStr();
  const points=cur ? h.count+(h.last[0]===t?0:1) : h.count;   // saved days, plus today's live price
  if(points<2) return null;
  const from=days ? (h.at[days]||h.first) : h.first;
  const to=cur ? [t,cur] : h.last;
  if(!from[1] || (!cur && from[0]===h.last[0])) return null;
  const span=Math.round((new Date(to[0])-new Date(from[0]))/864e5);
  return {pct:(to[1]-from[1])/from[1]*100, diff:to[1]-from[1], from:from[1], to:to[1], span};
}
function trendEl(t, small){
  const sp=document.createElement("span");
  if(!t){ sp.className="trend flat"; sp.textContent=small?"":"–"; return sp; }
  const up=t.pct>=0.5, down=t.pct<=-0.5;
  sp.className="trend "+(up?"up":down?"down":"flat");
  sp.textContent=(up?"▲ ":down?"▼ ":"")+Math.abs(t.pct).toFixed(small?0:1)+"%";
  sp.title=(up?"Up ":down?"Down ":"No change ")+money(Math.abs(t.diff))+" over "+t.span+" day"+(t.span===1?"":"s");
  return sp;
}
let showEd = recall("nd-ed")!=="off";

// The card database's small picture (the grid needs no more); the full scan is only for card details.
const smallImg = u => /_hires\.png$/.test(u||"") ? u.replace(/_hires\.png$/,".png") : u;
function cardImg(c){
  const im=document.createElement("img"); im.alt=c.name; im.loading="lazy"; im.src=base()+"/img/"+enc(c.n)+".png";
  im.onerror=()=>{ if(!im.dataset.r && c.img){ im.dataset.r=1; im.src=smallImg(c.img); } else im.remove(); };
  return im;
}

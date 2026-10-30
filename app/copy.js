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
function drawSpark(n){
  const box=$("dSpark"); box.replaceChildren();
  const sr=series(n);
  if(sr.length<2){ const c=document.createElement("div"); c.className="cap"; c.textContent="Price trend appears after a few days of saved prices."; box.append(c); return; }
  const W=360,H=56,P=4, xs=sr.map(p=>new Date(p[0]).getTime()), ys=sr.map(p=>p[1]);
  const x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
  const X=v=>P+(x1===x0?0.5:(v-x0)/(x1-x0))*(W-2*P), Y=v=>H-P-(y1===y0?0.5:(v-y0)/(y1-y0))*(H-2*P);
  const pts=sr.map((p,i)=>X(xs[i]).toFixed(1)+","+Y(ys[i]).toFixed(1)).join(" ");
  const ns="http://www.w3.org/2000/svg", svg=document.createElementNS(ns,"svg"); svg.setAttribute("viewBox","0 0 "+W+" "+H); svg.setAttribute("role","img");
  const t=trend(n,30);
  svg.setAttribute("aria-label","Price trend: "+money(ys[0])+" to "+money(ys[ys.length-1]));
  const area=document.createElementNS(ns,"polygon"); area.setAttribute("points",P+","+(H-P)+" "+pts+" "+(W-P)+","+(H-P)); area.setAttribute("fill","var(--dark)"); area.setAttribute("opacity","0.12");
  const line=document.createElementNS(ns,"polyline"); line.setAttribute("points",pts); line.setAttribute("fill","none"); line.setAttribute("stroke","var(--dark)"); line.setAttribute("stroke-width","2"); line.setAttribute("stroke-linejoin","round"); line.setAttribute("stroke-linecap","round");
  const dot=document.createElementNS(ns,"circle"); dot.setAttribute("cx",X(xs[xs.length-1])); dot.setAttribute("cy",Y(ys[ys.length-1])); dot.setAttribute("r","4"); dot.setAttribute("fill","var(--dark)"); dot.setAttribute("stroke","var(--surface)"); dot.setAttribute("stroke-width","2");
  svg.append(area,line,dot); box.append(svg);
  const cap=document.createElement("div"); cap.className="cap";
  const w=trend(n);
  cap.append("Low "+money(y0)+" · High "+money(y1)+" since "+fmtDay(sr[0][0])+(w?" · "+periodName()+" ":""));
  if(w) cap.append(trendEl(w));
  box.append(cap);
}
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

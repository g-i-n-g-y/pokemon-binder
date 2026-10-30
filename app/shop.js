// Shopping list and upgrades.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- shopping list ----------
// Order: "lo" cheapest, "hi" priciest, "num" set number, "mine" your own (saved on the server, shared across devices).
function shopList(){
  const need=state.cards.filter(c=>qty(c.n)===0);
  const pr=c=>basePrice(c.n)||0, mode=(state.shop||{}).mode||"lo";
  if(mode==="hi") return need.sort((a,b)=>pr(b)-pr(a));
  if(mode==="num") return need.sort(byNum);
  const cheap=need.slice().sort((a,b)=>(pr(a)||1e9)-(pr(b)||1e9));
  if(mode!=="mine") return cheap;
  // Your order first; cards not placed yet (new needs, new sets) go at the end, cheapest first.
  const pos=new Map(((state.shop||{}).order||[]).map((n,i)=>[n,i]));
  return cheap.slice().sort((a,b)=>(pos.has(a.n)?pos.get(a.n):1e6+cheap.indexOf(a))-(pos.has(b.n)?pos.get(b.n):1e6+cheap.indexOf(b)));
}
function saveShop(){
  if(!state.sid) return;
  fetch("api/set/"+enc(state.sid)+"/shop",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(state.shop)})
    .then(r=>{ if(!r.ok) throw 0; }).catch(()=>{ $("shopMsg").textContent="Couldn't save the order. Check that "+srv()+" is online."; });
}
function setShopMode(m){
  const order = m==="mine" && !((state.shop||{}).order||[]).length ? shopList().map(c=>c.n) : ((state.shop||{}).order||[]);
  state.shop={mode:m, order}; saveShop(); drawShop();
}
$("shopSort").addEventListener("click",e=>{ const b=e.target.closest("button[data-m]"); if(b) setShopMode(b.dataset.m); });
// Recalculate running totals and budget shading from the rows as they're currently arranged.
function shopTotals(){
  const budget=Number($("shopBudget").value)||0;
  let run=0, fit=0, fitCost=0, count=0;
  for(const tr of $("shopBody").querySelectorAll("tr[data-n]")){
    run+=basePrice(tr.dataset.n)||0; count++;
    tr.querySelector(".run").textContent=money(run);
    tr.classList.remove("fits","over");
    if(budget){ if(run<=budget){ tr.classList.add("fits"); fit++; fitCost=run; } else tr.classList.add("over"); }
  }
  const msg=$("shopMsg"); msg.replaceChildren();
  if(budget && count){
    const b1=document.createElement("b"); b1.textContent=money(budget);
    const b2=document.createElement("b"); b2.textContent=String(fit);
    const b3=document.createElement("b"); b3.textContent=money(fitCost);
    msg.append("With ",b1," you can get ",b2," card"+(fit===1?"":"s")+" for ",b3,".");
  } else if(count){
    msg.textContent=count+" cards needed · "+money(run)+" to finish this binder.";
  }
}
// Rows were rearranged by hand: switch to "My order" and save it.
function shopReordered(){
  const shown=[...$("shopBody").querySelectorAll("tr[data-n]")].map(tr=>tr.dataset.n);
  const keep=((state.shop||{}).order||[]).filter(n=>!shown.includes(n));   // owned cards keep their old spot at the end
  state.shop={mode:"mine", order:shown.concat(keep)}; saveShop(); markShopMode(); shopTotals();
}
function markShopMode(){
  const m=(state.shop||{}).mode||"lo";
  for(const b of $("shopSort").querySelectorAll("button")) b.setAttribute("aria-pressed", b.dataset.m===m ? "true" : "false");
}
// Drag to reorder: the grabbed row lifts and follows the pointer, the other rows slide out of its way,
// and it settles into its new spot when let go. Escape (or the phone cancelling the touch) puts it back.
function startDrag(e, tr){
  if(e.button!==undefined && e.button!==0) return;
  e.preventDefault();
  const body=$("shopBody"), rows=[...body.querySelectorAll("tr[data-n]")], from=rows.indexOf(tr);
  if(from<0 || rows.length<2) return;
  const id=e.pointerId, y0=e.clientY, sy0=window.scrollY;
  const r0=tr.getBoundingClientRect(), H=r0.height;
  const mids=rows.map(r=>{ const b=r.getBoundingClientRect(); return b.top+window.scrollY+b.height/2; });
  // the lifted copy that follows the pointer
  const ghost=document.createElement("table"); ghost.className="shop drag-ghost"; ghost.setAttribute("aria-hidden","true");
  const gb=document.createElement("tbody"), copy=tr.cloneNode(true); gb.append(copy); ghost.append(gb);
  [...tr.children].forEach((td,i)=>{ copy.children[i].style.width=td.getBoundingClientRect().width+"px"; });
  Object.assign(ghost.style,{left:r0.left+"px", top:r0.top+"px", width:r0.width+"px"});
  document.body.append(ghost);
  requestAnimationFrame(()=>ghost.classList.add("lifted"));
  tr.classList.add("drag-slot"); document.body.classList.add("drag-shop");
  rows.forEach(r=>{ if(r!==tr) r.classList.add("drag-shift"); });
  try{ if(navigator.vibrate) navigator.vibrate(8); }catch(_){}
  let to=from, py=y0, raf=0, done=false;
  const place=()=>{
    ghost.style.transform="translateY("+(py-y0)+"px)";
    const center=mids[from]+(py-y0)+(window.scrollY-sy0);   // where the row's middle is on the page
    let t=from;
    while(t+1<rows.length && center>mids[t+1]) t++;
    while(t>0 && center<mids[t-1]) t--;
    if(t===to) return;
    to=t;
    rows.forEach((r,i)=>{
      if(r===tr) return;
      const shift = from<to && i>from && i<=to ? -H : from>to && i<from && i>=to ? H : 0;
      r.style.transform = shift ? "translateY("+shift+"px)" : "";
    });
  };
  const tick=()=>{   // scroll the page when the pointer is near the top or bottom edge
    raf=0; const edge=80; let v=0;
    if(py<edge) v=-Math.ceil((edge-py)/6); else if(py>innerHeight-edge) v=Math.ceil((py-(innerHeight-edge))/6);
    if(v){ window.scrollBy(0,v); raf=requestAnimationFrame(tick); }
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
      // put the real row in its new place; the rows that slid are already drawn where they end up
      rows.forEach(r=>{ r.style.transition="none"; r.style.transform=""; });
      if(to!==from) body.insertBefore(tr, to>from ? rows[to].nextSibling : rows[to]);
      void body.offsetHeight; rows.forEach(r=>{ r.style.transition=""; });
    }
    const cleanup=()=>{ ghost.remove(); tr.classList.remove("drag-slot"); rows.forEach(r=>r.classList.remove("drag-shift")); document.body.classList.remove("drag-shop"); };
    // let the lifted copy settle into its slot, then show the real row again
    const end=tr.getBoundingClientRect();
    ghost.classList.add("settle"); ghost.classList.remove("lifted"); ghost.style.transform="translateY("+(end.top-r0.top)+"px)";
    if(matchMedia("(prefers-reduced-motion: reduce)").matches) cleanup();
    else { ghost.addEventListener("transitionend",cleanup,{once:true}); setTimeout(cleanup,320); }
    if(to!==from) shopReordered();
  };
  const up=ev=>{ if(ev.pointerId===id) finish(false); };
  const onCancel=ev=>{ if(ev.pointerId===id) finish(true); };
  const key=ev=>{ if(ev.key==="Escape"){ ev.preventDefault(); ev.stopPropagation(); finish(true); } };
  window.addEventListener("pointermove",move); window.addEventListener("pointerup",up);
  window.addEventListener("pointercancel",onCancel); window.addEventListener("keydown",key,true);
}
function gripKey(e, tr){
  const body=$("shopBody");
  if(e.key==="ArrowUp" && tr.previousElementSibling){ body.insertBefore(tr, tr.previousElementSibling); }
  else if(e.key==="ArrowDown" && tr.nextElementSibling){ body.insertBefore(tr.nextElementSibling, tr); }
  else return;
  e.preventDefault(); e.currentTarget.focus(); shopReordered();
}
function drawShop(){
  const need=shopList();
  const body=$("shopBody"); body.replaceChildren();
  markShopMode();
  for(const c of need){
    const pr=basePrice(c.n);
    const tr=document.createElement("tr"); tr.dataset.n=c.n;
    const tdG=document.createElement("td"); tdG.className="c-grip";
    const g=document.createElement("button"); g.type="button"; g.className="grip"; g.textContent="⠿";
    g.setAttribute("aria-label","Move "+c.name+" (drag, or use the arrow keys)"); g.title="Drag to reorder";
    g.addEventListener("pointerdown",e=>startDrag(e,tr)); g.addEventListener("keydown",e=>gripKey(e,tr));
    tdG.append(g);
    const tdI=document.createElement("td"); tdI.className="c-img";
    const im=document.createElement("img"); im.className="thumb"; im.alt=""; im.loading="lazy"; im.src=base()+"/img/"+enc(c.n)+".png";
    im.onerror=()=>{ if(!im.dataset.r && c.img){ im.dataset.r=1; im.src=smallImg(c.img); } else im.style.visibility="hidden"; };
    tdI.append(im);
    const tdN=document.createElement("td");
    const nb=document.createElement("button"); nb.type="button"; nb.className="nm"; nb.textContent=c.name; nb.onclick=()=>openCard(c.n);
    const sub=document.createElement("span"); sub.className="sub"; sub.textContent=(c.set?c.set+" · ":"")+label(c)+" · "+(c.rarity||"");
    tdN.append(nb,sub);
    const tdP=document.createElement("td"); tdP.className="num"; tdP.textContent=pr?money(pr):"–";
    const tdT=document.createElement("td"); tdT.className="num hide-sm c-trend"; tdT.append(trendEl(trend(c.n)));
    const tdR=document.createElement("td"); tdR.className="num run";
    const tdA=document.createElement("td");
    const bt=document.createElement("button"); bt.type="button"; bt.className="btn"; bt.textContent="Got it";
    bt.title="Mark as owned and log today's date"; bt.onclick=()=>{ quickToggle(c.n); };
    tdA.append(bt);
    tr.append(tdG,tdI,tdN,tdP,tdT,tdR,tdA); body.append(tr);
  }
  if(!need.length){ const tr=document.createElement("tr"); const td=document.createElement("td"); td.colSpan=7; td.className="empty"; td.textContent="You own every card in this binder."; tr.append(td); body.append(tr); }
  // a column of "0.0%" says nothing: show price changes only once at least one card here has moved
  const moved=need.some(c=>{ const t=trend(c.n); return t && Math.abs(t.pct)>=0.5; });
  body.closest("table").classList.toggle("no-trend", !moved);
  shopTotals();
}
// ---------- upgrades ----------
const COND_RANK={NM:0,LP:1,MP:2,HP:3,DMG:4};
const upgPrefs = () => Object.assign({from:["HP","DMG"], to:"LP"}, (state.shop||{}).upg||{});
function saveUpg(p){
  state.shop=Object.assign({mode:"lo", order:[]}, state.shop||{}, {upg:p}); saveShop(); drawUpg();
}
$("upgFrom").addEventListener("click",e=>{
  const b=e.target.closest("button[data-c]"); if(!b) return;
  const p=upgPrefs(), set=new Set(p.from);
  set.has(b.dataset.c) ? set.delete(b.dataset.c) : set.add(b.dataset.c);
  saveUpg({from:[...set], to:p.to});
});
$("upgTo").onchange=e=>{ const p=upgPrefs(); saveUpg({from:p.from, to:e.target.value}); };
function drawUpg(){
  const p=upgPrefs();
  for(const b of $("upgFrom").querySelectorAll("button")) b.setAttribute("aria-pressed", p.from.includes(b.dataset.c) ? "true" : "false");
  $("upgTo").value=p.to;
  const owned=state.cards.filter(c=>qty(c.n)>0);
  const noCond=owned.filter(c=>!rec(c.n).cond).length;
  const rows=owned.filter(c=>{ const k=rec(c.n).cond; return k && p.from.includes(k) && COND_RANK[k]>COND_RANK[p.to]; })
    .map(c=>{ const mine=condPrice(c.n,rec(c.n).cond), up=condPrice(c.n,p.to); return {c, mine, up, net: up ? up-mine : null}; })
    .sort((a,b)=>(a.net==null?1e9:a.net)-(b.net==null?1e9:b.net));
  const body=$("upgBody"); body.replaceChildren();
  let run=0, net=0, priced=0;
  for(const r of rows){
    const c=r.c, tr=document.createElement("tr");
    const tdI=document.createElement("td"); tdI.className="c-img";
    const im=document.createElement("img"); im.className="thumb"; im.alt=""; im.loading="lazy"; im.src=base()+"/img/"+enc(c.n)+".png";
    im.onerror=()=>{ if(!im.dataset.r && c.img){ im.dataset.r=1; im.src=smallImg(c.img); } else im.style.visibility="hidden"; };
    tdI.append(im);
    const tdN=document.createElement("td");
    const nb=document.createElement("button"); nb.type="button"; nb.className="nm"; nb.textContent=c.name; nb.onclick=()=>openCard(c.n);
    const sub=document.createElement("span"); sub.className="sub"; sub.textContent=(c.set?c.set+" · ":"")+label(c)+(qty(c.n)>1?" · "+qty(c.n)+" copies":"");
    tdN.append(nb,sub);
    const tdY=document.createElement("td"); tdY.className="num"; tdY.textContent=rec(c.n).cond+" "+(r.mine?money(r.mine):"–");
    const tdU=document.createElement("td"); tdU.className="num"; tdU.textContent=r.up ? money(r.up) : "No "+p.to+" sales";
    const tdD=document.createElement("td"); tdD.className="num"; tdD.textContent=r.net==null ? "–" : (r.net<0?"−":"")+money(Math.abs(r.net));
    if(r.up){ run+=r.up; net+=r.net; priced++; }
    const tdR=document.createElement("td"); tdR.className="num hide-sm"; tdR.textContent=r.up ? money(run) : "–";
    tr.append(tdI,tdN,tdY,tdU,tdD,tdR); body.append(tr);
  }
  if(!rows.length){
    const tr=document.createElement("tr"); const td=document.createElement("td"); td.colSpan=6; td.className="empty";
    td.textContent = !owned.length ? "You don't own any cards in this binder yet. Mark the ones you have on the Cards tab, and better copies to look for show up here." : !p.from.length ? "Pick at least one condition to upgrade." : "No cards to upgrade with these choices.";
    tr.append(td); body.append(tr);
  }
  $("upgMsg").textContent = priced ? rows.length+" card"+(rows.length===1?"":"s")+" to upgrade · "+money(run)+" for "+p.to+" copies, or about "+money(net)+" after selling yours." : "";
  $("upgNote").textContent = noCond ? noCond+" owned card"+(noCond===1?" has":"s have")+" no condition set, so "+(noCond===1?"it isn't":"they aren't")+" listed. Set the condition in a card's details." : "";
}
$("shopBudget").addEventListener("input",()=>{ store("nd-budget",$("shopBudget").value||undefined); drawShop(); });
$("shopBudget").value=recall("nd-budget")||"";

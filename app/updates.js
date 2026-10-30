// Version, What's new, the update notice, local card shows.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- version, what's new, update notice ----------
let news=null;
function inlineMd(t){   // **bold** and `code` from the changelog, everything else as plain text
  const frag=document.createDocumentFragment();
  t.split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach(part=>{
    if(/^\*\*.+\*\*$/.test(part)){ const b=document.createElement("b"); b.textContent=part.slice(2,-2); frag.append(b); }
    else if(/^`.+`$/.test(part)){ const c=document.createElement("code"); c.textContent=part.slice(1,-1); frag.append(c); }
    else if(part) frag.append(part);
  });
  return frag;
}
function loadNews(){
  return fetch("api/changelog").then(r=>r.json()).then(j=>{ news=j; showUpdateDot(); showUpdated(); return j; }).catch(()=>null);
}
// After an update: once per device, a short list of what changed since the version this device last saw.
async function showUpdated(){
  const j=news; if(!j || !j.running || !j.entries || !j.entries.length) return;
  let seen=recall("nd-seen-ver");
  if(!seen){   // this device never saved a version: use the one the server ran before an install in the last 2 days
    try{
      const v=await fetch("api/version",{cache:"no-store"}).then(r=>r.json()), p=(v.previous||[])[0];
      if(v.installed && Date.now()-new Date(v.installed)<2*86400e3 && p && p.version) seen=p.version;
    }catch(_){}
  }
  if(!seen || cmpV(vt(j.running),vt(seen))<=0){ store("nd-seen-ver", j.running); return; }   // first visit or a rollback: nothing to show
  if(!vtReady || document.querySelector("dialog[open]")){ setTimeout(showUpdated, 1500); return; }   // wait for the splash and any open window
  const list=j.entries.filter(e=>cmpV(vt(e.v),vt(seen))>0 && cmpV(vt(e.v),vt(j.running))<=0);
  store("nd-seen-ver", j.running);
  if(!list.length) return;
  $("upTitle").textContent="Updated to v"+j.running;
  $("upSub").textContent="What changed since v"+seen+":";
  const L=$("upList"); L.replaceChildren();
  // just the bold headline of each change ("**Smaller Add a binder button:** ..." → "Smaller Add a binder button")
  const headline=t=>{ const m=t.match(/^\*\*(.+?)\*\*/); return (m ? m[1] : t.replace(/\*\*|`/g,"")).replace(/:$/,""); };
  list.forEach(e=>{
    if(list.length>1){ const h=document.createElement("div"); h.className="rel-head"; h.textContent="v"+e.v; L.append(h); }
    const ul=document.createElement("ul"); ul.className="up-list";
    e.items.forEach(it=>{ const li=document.createElement("li"); li.textContent=headline(it.t); ul.append(li); });
    L.append(ul);
  });
  $("updated").showModal();
}
function showUpdateDot(){
  const j=news; if(!j) return;
  $("verNum").replaceChildren("v"+j.running);
  if(j.updateAvailable){ const s=document.createElement("span"); s.className="new"; s.textContent="v"+j.latest+" available"; $("verNum").append(" ",s); }
  let dot=$("menuBtn").querySelector(".dot");
  if(j.updateAvailable && !dot){ dot=document.createElement("span"); dot.className="dot"; dot.title="Update available"; $("menuBtn").append(dot); $("menuBtn").setAttribute("aria-label","Your binders (update available)"); }
  if(!j.updateAvailable && dot){ dot.remove(); $("menuBtn").setAttribute("aria-label","Your binders"); }
}
function drawNews(){
  const j=news, L=$("nwList"); L.replaceChildren();
  if(!j){ $("nwSub").textContent="Couldn't load the release notes."; return; }
  $("nwSub").textContent="Release notes for Pokémon Binder. You're on v"+j.running+".";
  $("nwUpd").hidden=!j.updateAvailable;
  if(j.updateAvailable) $("nwUpdText").textContent="v"+j.latest+" is available. Installing asks you to confirm first.";
  $("nwAll").href=j.repo ? "https://github.com/"+j.repo+"/blob/"+(j.branch||"main")+"/CHANGELOG.md" : "#";
  $("nwAll").hidden=!j.repo;
  if(!j.entries.length){ const p=document.createElement("p"); p.className="note"; p.textContent=j.error ? "Couldn't reach GitHub ("+j.error+")." : "No release notes yet."; L.append(p); return; }
  const run=vt(j.running), line=run.slice(0,2).join("."), latest=j.entries[0].v;
  // groups: newer than yours, this version line (like everything since v2.12), then earlier releases
  const groups=[["Newer than yours",[]],["Since v"+line,[]],["Earlier releases",[]]];
  j.entries.forEach(e=>{ const c=cmpV(vt(e.v),run); groups[c>0?0:(vt(e.v).slice(0,2).join(".")===line?1:2)][1].push(e); });
  // year only when it isn't this year (keeps rows short on phones)
  const shortDate=s=>{ const d=new Date(s); if(isNaN(d)) return s; const o={month:"short",day:"numeric"}; if(d.getFullYear()!==new Date().getFullYear()) o.year="numeric"; return d.toLocaleDateString("en-US",o); };
  groups.filter(g=>g[1].length).forEach(([title,list])=>{
   const h=document.createElement("div"); h.className="rel-head"; h.textContent=title; L.append(h);
   list.forEach(e=>{
    const d=document.createElement("details"); d.className="relnote";
    const newer=cmpV(vt(e.v),run)>0, here=e.v===j.running;
    if(here || newer) d.open=true;
    const sm=document.createElement("summary"); const b=document.createElement("b"); b.textContent="v"+e.v; sm.append(b);
    const tag=(t,c)=>{ const x=document.createElement("span"); x.className="tag "+c; x.textContent=t; sm.append(x); };
    if(here) tag("Installed","own");
    if(e.v===latest) tag("Latest","tcg");
    if(e.items.length){ const n=document.createElement("span"); n.className="cnt"; n.textContent=e.items.length+" change"+(e.items.length===1?"":"s"); sm.append(n); }
    const dt=document.createElement("span"); dt.className="d"; dt.textContent=shortDate(e.date); sm.append(dt);
    d.append(sm);
    e.notes.forEach(n=>{ const p=document.createElement("p"); p.append(inlineMd(n)); d.append(p); });
    if(e.items.length){
      const ul=document.createElement("ul");
      e.items.forEach(it=>{ const li=document.createElement("li"); li.append(inlineMd(it.t));
        if(it.sub.length){ const u2=document.createElement("ul"); it.sub.forEach(x=>{ const l2=document.createElement("li"); l2.append(inlineMd(x)); u2.append(l2); }); li.append(u2); }
        ul.append(li); });
      d.append(ul);
    }
    L.append(d);
   });
  });
}
const vt = v => (v||"").split(".").map(Number);
const cmpV = (a,b) => { for(let i=0;i<Math.max(a.length,b.length);i++){ const x=a[i]||0, y=b[i]||0; if(x!==y) return x-y; } return 0; };
$("verLine").onclick=()=>{ $("drawer").close(); drawNews(); $("news").showModal(); loadNews().then(drawNews); };
$("nwClose").onclick=$("nwDone").onclick=()=>$("news").close();
$("news").addEventListener("click",e=>{ if(e.target===$("news")) $("news").close(); });
$("upClose").onclick=$("upDone").onclick=()=>$("updated").close();
$("updated").addEventListener("click",e=>{ if(e.target===$("updated")) $("updated").close(); });   // tap outside the window closes it
$("upMore").onclick=()=>{ $("updated").close(); drawNews(); $("news").showModal(); };
$("nwInstall").onclick=()=>{ $("news").close(); loadSettings(); loadVersion(); $("settings").showModal(); setTimeout(()=>$("stUpdate").click(),150); };
loadNews(); setInterval(loadNews, 3*3600*1000);

// ---------- local card shows ----------
let showsKind=recall("nd-shows-kind")||"tcg", showsData=null, showsPoll=null;
function loadShows(){
  clearTimeout(showsPoll);
  return fetch("api/shows").then(r=>r.json()).then(j=>{
    showsData=j; drawShows();
    if(j.running && $("shows").open) showsPoll=setTimeout(loadShows,1500);
  }).catch(()=>{ $("shInfo").textContent="Couldn't reach "+srv()+"."; });
}
function drawShows(){
  const j=showsData; if(!j) return;
  [...$("shKind").children].forEach(x=>x.setAttribute("aria-pressed", x.dataset.k===showsKind));
  $("shAuto").checked=!!j.auto;
  if(document.activeElement!==$("shAreas")) $("shAreas").value=(j.areas||[]).join(", ");
  $("shScan").disabled=!!j.running; $("shScan").textContent=j.running ? "Scanning…" : "Scan now";
  const list=(j.shows||[]).filter(x=>showsKind==="all" || x.tcg);
  const isNew=x=>j.firstScan && x.first>j.firstScan && (Date.now()-new Date(x.first))<14*864e5;
  const newN=list.filter(x=>isNew(x) && !(j.today && x.date<=j.today)).length, upN=list.filter(x=>!j.today || x.date>=j.today).length;
  let info=j.scanned ? "Last checked "+when(j.scanned)+". "+upN+" upcoming"+(showsKind==="tcg"?" Pokémon/TCG":"")+" show"+(upN===1?"":"s")+(newN?", "+newN+" new":"")+"." : "Not checked yet. Tap Scan now.";
  if(j.running){ info="Checking for shows"+(j.total ? ": step "+Math.min(j.done+1,j.total)+" of "+j.total : "…"); setBar($("shBar"), j.done, j.total); }
  else { hideBar($("shBar")); if(j.error) info+=" Last scan had a problem: "+j.error+"."; }
  $("shInfo").textContent=info;
  const L=$("shList"); L.replaceChildren(); let month="";
  if(j.scanned && !list.length && !j.running){ const p=document.createElement("p"); p.className="note"; p.textContent=showsKind==="tcg" ? "No upcoming Pokémon/TCG shows found. Try All." : "No upcoming shows found in these towns."; L.append(p); }
  for(const x of list){
    const d=new Date(x.date+"T12:00:00");
    const m=d.toLocaleString("en-US",{month:"long",year:"numeric"});
    if(m!==month){ month=m; const h=document.createElement("h3"); h.textContent=m; L.append(h); }
    const row=document.createElement("div"); row.className="show";
    const w=document.createElement("div"); w.className="when";
    const wd=document.createElement("span"); wd.textContent=d.toLocaleString("en-US",{weekday:"short"});
    const dn=document.createElement("b"); dn.textContent=d.getDate();
    const mo=document.createElement("span"); mo.textContent=d.toLocaleString("en-US",{month:"short"});
    w.append(wd,dn,mo);
    const wh=document.createElement("div"); wh.className="what";
    const a=document.createElement("a"); a.href=x.url; a.target="_blank"; a.rel="noopener"; a.textContent=x.name+" ↗";
    const sub=document.createElement("span"); sub.className="s"; sub.textContent=x.town+(x.desc ? " · "+x.desc : "");
    const tags=document.createElement("div"); tags.className="tags";
    if(x.date===j.today){ const t=document.createElement("span"); t.className="tag new"; t.textContent="Today"; tags.append(t); }
    else if(j.today && x.date<j.today){ row.classList.add("past"); const t=document.createElement("span"); t.className="tag"; t.textContent="Yesterday"; tags.append(t); }
    else if(isNew(x)){ const t=document.createElement("span"); t.className="tag new"; t.textContent="New"; tags.append(t); }
    if(x.tcg){ const t=document.createElement("span"); t.className="tag tcg"; t.textContent="Pokémon / TCG"; tags.append(t); }
    wh.append(a,sub); if(tags.children.length) wh.append(tags);
    row.append(w,wh); L.append(row);
  }
}
$("showsBtn").onclick=()=>{ $("shSaved").textContent=""; $("shows").showModal(); loadShows(); };
$("shClose").onclick=()=>$("shows").close();
$("shows").addEventListener("click",e=>{ if(e.target===$("shows")) $("shows").close(); });
$("shows").addEventListener("close",()=>clearTimeout(showsPoll));
$("shKind").addEventListener("click",e=>{ const b=e.target.closest("button"); if(!b) return; showsKind=b.dataset.k; store("nd-shows-kind",showsKind); drawShows(); });
$("shScan").onclick=async()=>{
  $("shScan").disabled=true; $("shScan").textContent="Scanning…"; setBar($("shBar"),0,0);
  try{ await fetch("api/shows/scan",{method:"POST"}); }catch(_){}
  loadShows();
};
const saveShows=body=>fetch("api/shows",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}).then(async r=>{ const j=await r.json(); if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; });
$("shAuto").onchange=e=>saveShows({auto:e.target.checked}).then(()=>{ $("shSaved").textContent="Saved"; }).catch(err=>{ $("shSaved").textContent=err.message; });
$("shSave").onclick=()=>{
  const areas=$("shAreas").value.split(",").map(x=>x.trim()).filter(Boolean);
  saveShows({areas}).then(()=>{ $("shSaved").textContent="Saved. Tap Scan now to check these towns."; loadShows(); }).catch(err=>{ $("shSaved").textContent=err.message+"."; });
};
$("settings").addEventListener("click",e=>{ if(e.target===$("settings")) $("settings").close(); });

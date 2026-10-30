// Settings: themes, backups, spreadsheet import, tab icon, list windows.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- settings / themes ----------
function applySkin(id){
  document.documentElement.dataset.skin=id; store("nd-skin",id);
  try{ $("themeColor").content=getComputedStyle(document.body).backgroundColor||"#111213"; }catch(_){}   // phone's top bar matches the theme
  [...$("skins").children].forEach(b=>b.setAttribute("aria-pressed",b.dataset.id===id));
}
SKINS.forEach(([id,name,desc,cols])=>{
  const b=document.createElement("button"); b.type="button"; b.className="skin"; b.dataset.id=id;
  const sw=document.createElement("span"); sw.className="sw"; cols.forEach(c=>{ const i=document.createElement("i"); i.style.background=c; sw.append(i); });
  const t=document.createElement("div"); const bb=document.createElement("b"); bb.textContent=name; const sp=document.createElement("span"); sp.textContent=desc; t.append(bb,sp);
  b.append(sw,t); b.onclick=()=>applySkin(id); $("skins").append(b);
});
applySkin(document.documentElement.dataset.skin||"night");
const TZ = (()=>{ try{ return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York"; }catch(_){ return "America/New_York"; } })();
function showNext(iso, auto){
  $("stNext").textContent = !auto ? "Off. Use Refresh prices to update by hand." :
    iso ? new Date(iso).toLocaleString("en-US",{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}) : "–";
  $("stTz").textContent = auto ? "Time zone: "+TZ.replace(/_/g," ") : "";
  $("stTime").disabled = !auto;
}
function slotSelect(opts, val, label){
  const sel=document.createElement("select"); sel.setAttribute("aria-label", label);
  opts.forEach(([v,t])=>{ const o=document.createElement("option"); o.value=v; o.textContent=t; sel.append(o); });
  sel.value=val; return sel;
}
function drawSlots(){
  const box=$("slotRows"); box.replaceChildren();
  const o=state.slotOpts || {raw:["NM","LP","MP","HP","DMG"], graders:["PSA","BGS","CGC","SGC","TAG","ACE","Any"], grades:["10","9.5","9","8.5","8","7.5","7","6","5","4","3","2","1"]};
  state.slots.forEach((sl,i)=>{
    const row=document.createElement("div"); row.className="slotrow";
    const k=document.createElement("span"); k.className="k"; k.textContent="Price "+(i+1);
    const sels=document.createElement("div"); sels.className="sels";
    const types=[["raw","Raw condition"],["graded","Graded"]]; if(i===1) types.push(["none","None"]);
    const t=slotSelect(types, sl.t, "Price "+(i+1)+" type"); sels.append(t);
    const c=slotSelect(o.raw.map(x=>[x,COND_NAME[x]?x+" · "+COND_NAME[x]:x]), sl.c||"LP", "Price "+(i+1)+" condition");
    const co=slotSelect(o.graders.map(x=>[x,x==="Any"?"Any company":x]), sl.co||"PSA", "Price "+(i+1)+" grading company");
    const g=slotSelect(o.grades.map(x=>[x,"Grade "+x]), sl.g||"9", "Price "+(i+1)+" grade");
    c.hidden = sl.t!=="raw"; co.hidden = g.hidden = sl.t!=="graded";
    sels.append(c,co,g);
    const save=()=>{
      const next = t.value==="raw" ? {t:"raw",c:c.value} : t.value==="graded" ? {t:"graded",co:co.value,g:g.value} : {t:"none"};
      const slots=state.slots.slice(); slots[i]=next; saveSlots(slots);
    };
    [t,c,co,g].forEach(x=>x.onchange=save);
    row.append(k,sels); box.append(row);
  });
}
const slotsText = sl => sl.filter(x=>x.t!=="none").map(slotName).join(" + ");
async function saveSlots(slots){
  const msg=$("slotMsg"); msg.textContent="";
  if(!state.sid){ drawSlots(); return; }
  const before=slotsText(state.slots), after=slotsText(slots);
  const graded=slots.some(x=>x.t==="graded"), raw=slots.every(x=>x.t!=="graded");
  const ul=document.createElement("ul"); ul.className="changes";
  [ "Only "+(state.set.name||"this binder")+" changes. Your other binders keep their own price options.",
    raw ? "Card prices and set totals switch to the "+(slots[1].t==="none"?after:"combined "+after)+" average right away, using sales already saved."
        : "Card prices and set totals switch to the "+slotName(slots[0])+" price"+(slots[1].t!=="none"?" (or "+slotName(slots[1])+" when there are no "+slotName(slots[0])+" sales)":"")+".",
    graded ? "Graded prices come from eBay sold listings on PriceCharting. If they haven't been downloaded for this binder yet, they fill in on the next price check, which takes a bit longer than usual." : null,
    "The price history chart starts following the new price from today, so expect a jump on today's date. Older days stay as they were.",
    "Owned cards with a condition set still count at that condition's price in your collection value."
  ].filter(Boolean).forEach(t=>{ const li=document.createElement("li"); li.textContent=t; ul.append(li); });
  const ok=await askConfirm("Change the price average?", before+"  →  "+after, "Change", {safe:true, body:ul});
  if(!ok){ drawSlots(); return; }
  msg.textContent="Saving…";
  fetch("api/set/"+enc(state.sid)+"/slots",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({slots})})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; }))
    .then(j=>{
      state.slots=j.slots||slots; drawSlots(); msg.replaceChildren();
      if(j.needsRefresh){
        msg.append("Saved. Graded prices load on the next price check (a little slower than raw prices).");
        const b=document.createElement("button"); b.className="btn"; b.type="button"; b.textContent="Refresh now";
        b.onclick=()=>{ $("settings").close(); $("refresh").click(); }; msg.append(b);
      } else msg.append("Saved. Prices updated.");
      return state.sid && loadState();
    })
    .catch(e=>{ drawSlots(); msg.textContent=(e&&e.message&&e.message!=="Failed to fetch") ? e.message : "Couldn't save. Check that "+srv()+" is online."; });
}
function getSlots(){
  return fetch("api/settings").then(r=>r.json()).then(s=>{ if(s.options) state.slotOpts=s.options; setServerName(s.serverName); state.lastSync=s.lastSync||null; pendUI(); if($("stHosts") && document.activeElement!==$("stHosts")) $("stHosts").value=(s.otherHosts||[]).join(", "); return s; }).catch(()=>null);
}
// The server's name from Settings (like "Attic"), or "the server" when none is set.
const srv = () => state.serverName || "the server";
const Srv = () => state.serverName || "The server";
function setServerName(name){
  state.serverName=(name||"").trim();
  document.querySelectorAll(".srv").forEach(el=>{ el.textContent=srv(); });
  if($("stSrv") && document.activeElement!==$("stSrv")) $("stSrv").value=state.serverName;
}
$("stSrv").addEventListener("change",()=>{
  const v=$("stSrv").value.replace(/\s+/g," ").trim();
  fetch("api/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({serverName:v})})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; }))
    .then(()=>{ setServerName(v); $("stSrvMsg").textContent = v ? "Saved. Messages now say \u201c"+v+"\u201d." : "Saved. Messages say \u201cthe server\u201d."; })
    .catch(e=>{ $("stSrvMsg").textContent=e.message+"."; });
});
// ---------- backup and restore ----------
$("bkUp").onchange=async e=>{
  const f=e.target.files[0]; e.target.value=""; if(!f) return;
  const ul=document.createElement("ul"); ul.className="changes";
  ["Everything in the binder is replaced with what's in the backup: cards, purchases, notes, photos, prices, price options and settings.",
   "A safety copy of your current data is saved on "+srv()+" first, in the backups folder, in case you change your mind.",
   "Card pictures download again by themselves after the restore."].forEach(t=>{ const li=document.createElement("li"); li.textContent=t; ul.append(li); });
  const ok=await askConfirm("Restore this backup?", f.name+" · "+(f.size/1048576).toFixed(1)+" MB", "Restore", {body:ul});
  if(!ok) return;
  $("bkMsg").textContent="Restoring…";
  fetch("api/restore",{method:"POST",headers:{"Content-Type":"application/zip"},body:f})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Restore failed"); return j; }))
    .then(j=>{ $("bkMsg").textContent="Restored "+j.files+" files. Reloading…"; setTimeout(()=>reloadHome(),1200); })
    .catch(err=>{ $("bkMsg").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't restore. Check that "+srv()+" is online."; });
};

// ---------- backups saved on the server ----------
const bkKind = {update:"Before update", "import":"Before import", restore:"Before restore", sync:"Before phone sync", fresh:"Before starting a binder fresh", daily:"Daily"};
function loadAutoBackups(){
  fetch("api/backups").then(r=>r.json()).then(j=>{
    const list=(j.backups||[]).slice(0,6), ul=$("bkAuto"); ul.replaceChildren();
    $("bkAutoWrap").hidden=!list.length;
    for(const b of list){
      const li=document.createElement("li"), info=document.createElement("div");
      const t=document.createElement("b"); t.textContent=bkKind[b.kind]||"Backup";
      const d=document.createElement("div"); d.className="s"; d.textContent=shortDate(b.created)+", "+new Date(b.created).toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})+" · "+(b.size<1048576 ? Math.max(1,Math.round(b.size/1024))+" KB" : (b.size/1048576).toFixed(1)+" MB")+(b.photos===false ? " · without photos" : "");
      info.append(t,d);
      const btns=document.createElement("div"); btns.className="btnrow";
      const dl=document.createElement("a"); dl.className="btn"; dl.href="api/backups/"+enc(b.name); dl.download=""; dl.textContent="Download";
      const rs=document.createElement("button"); rs.className="btn"; rs.type="button"; rs.textContent="Restore";
      rs.onclick=async()=>{
        const ok=await askConfirm("Restore this backup?", t.textContent+" · "+d.textContent, "Restore",
          {body:Object.assign(document.createElement("div"),{className:"note",textContent:"Everything in the binder goes back to how it was then. A safety copy of your current data is saved first."})});
        if(!ok) return;
        $("bkMsg").textContent="Restoring…";
        fetch("api/backups/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:b.name})})
          .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Restore failed"); return j; }))
          .then(j=>{ $("bkMsg").textContent="Restored "+j.files+" files. Reloading…"; setTimeout(()=>reloadHome(),1200); })
          .catch(err=>{ $("bkMsg").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message+"." : "Couldn't restore. Check that "+srv()+" is online."; });
      };
      btns.append(dl,rs); li.append(info,btns); ul.append(li);
    }
  }).catch(()=>{ $("bkAutoWrap").hidden=true; });
}
// ---------- spreadsheet import ----------
const imHelp=$("imMsg").textContent;
function importSetup(){
  const dex=/^dex-/.test(state.sid||"");
  $("imMsg").textContent=imHelp;
  $("imSet").textContent=state.set.name ? "for "+state.set.name : "";
  $("imTpl").href = state.sid && !dex ? "api/set/"+enc(state.sid)+"/template.csv" : "#";
  $("imTpl").toggleAttribute("download", !!state.sid && !dex);
  $("imTpl").setAttribute("aria-disabled", dex||!state.sid ? "true" : "false");
  $("imUp").disabled = dex || !state.sid;
  if(dex) $("imMsg").textContent="Spreadsheets work for set binders. Switch to a set from the menu to use them.";
}
$("imTpl").addEventListener("click",e=>{ if($("imTpl").getAttribute("aria-disabled")==="true") e.preventDefault(); });
$("imUp").onchange=async e=>{
  const f=e.target.files[0]; e.target.value=""; if(!f || !state.sid) return;
  if(f.size>10*1048576){ $("imMsg").textContent="That file is too big (10 MB max)."; return; }
  const url="api/set/"+enc(state.sid)+"/import", post=q=>fetch(url+q,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:f})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Import failed"); return j; }));
  $("imMsg").textContent="Reading "+f.name+"…";
  let plan;
  try { plan=await post(""); }
  catch(err){ $("imMsg").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message : "Couldn't read the file. Check that "+srv()+" is online."; return; }
  const ch=plan.changes, newOwned=ch.filter(c=>c.have===0).length, more=ch.filter(c=>c.have>0&&c.add>0).length, extra=ch.filter(c=>!c.add).length;
  const ul=document.createElement("ul"); ul.className="changes";
  const line=t=>{ const li=document.createElement("li"); li.textContent=t; ul.append(li); };
  if(newOwned) line(newOwned+" card"+(newOwned===1?"":"s")+" marked owned: "+ch.filter(c=>c.have===0).slice(0,12).map(c=>"#"+c.n+" "+c.name).join(", ")+(newOwned>12?", and more":""));
  if(more) line(more+" card"+(more===1?" gets":"s get")+" extra copies");
  if(extra) line(extra+" owned card"+(extra===1?" gets":"s get")+" a condition or note filled in");
  if(plan.already) line(plan.already+" card"+(plan.already===1?" is":"s are")+" already up to date");
  if(plan.need) line(plan.need+" row"+(plan.need===1?"":"s")+" with Qty 0 left alone (cards you own stay owned)");
  for(const sk of plan.skipped.slice(0,8)) line("Skipped row "+sk.row+": "+sk.why);
  if(plan.skippedCount>8) line("…and "+(plan.skippedCount-8)+" more skipped rows");
  if(!ch.length){ $("imMsg").replaceChildren(); $("imMsg").append("Nothing to change from "+f.name+".", ul); return; }
  const ok=await askConfirm("Import this spreadsheet?", f.name+" into "+(state.set.name||"this binder"), "Import", {safe:true, body:ul});
  if(!ok){ $("imMsg").textContent="Import cancelled. Nothing changed."; return; }
  $("imMsg").textContent="Importing…";
  try {
    const done=await post("?apply=1");
    $("imMsg").textContent="Imported. "+done.changes.length+" card"+(done.changes.length===1?"":"s")+" updated. A backup from just before is saved on "+srv()+".";
    loadAutoBackups(); if(state.sid) loadState();
  } catch(err){ $("imMsg").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message : "Couldn't import. Check that "+srv()+" is online."; }
};
// ---------- tab icon ----------
function setIcon(v){
  const u="favicon?v="+(v||Date.now());
  $("favicon").href=u; $("icPrev").src=u;
  fetch("api/icon").then(r=>r.json()).then(j=>{ $("icReset").hidden=!j.custom; }).catch(()=>{});
}
$("icUp").onchange=e=>{
  const f=e.target.files[0]; e.target.value=""; if(!f) return;
  $("icMsg").textContent="Saving…";
  fetch("api/icon",{method:"POST",headers:{"Content-Type":f.type||"application/octet-stream"},body:f})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; }))
    .then(j=>{ setIcon(j.v); $("icMsg").textContent="Saved. Other open tabs pick it up when reloaded."; })
    .catch(err=>{ $("icMsg").textContent=(err&&err.message&&err.message!=="Failed to fetch") ? err.message : "Couldn't save. Check that "+srv()+" is online."; });
};
$("icReset").onclick=()=>fetch("api/icon",{method:"DELETE"}).then(()=>{ setIcon(); $("icMsg").textContent="Back to the default icon."; });
function loadSettings(){
  loadPsaSetting();
  $("stSaved").textContent=""; $("slotMsg").textContent=""; drawSlots(); setIcon(Date.now()); loadAutoBackups(); importSetup();
  $("slotSet").textContent=state.set.name ? "for "+state.set.name : "";
  getSlots().then(s=>{ if(!s) throw 0; drawSlots(); return s; }).then(s=>{
    $("stAuto").checked=!!s.auto; $("stTime").value=s.time||"03:00"; showNext(s.next, s.auto);
    $("stBackup").checked = s.backup!==false;
    $("stAll").checked = !!s.refreshAll;
    if(s.tz!==TZ) saveSettings({tz:TZ, offset:-new Date().getTimezoneOffset()}, true);
    settingsSummary();
  }).catch(()=>{ $("stNext").textContent="Can't reach "+srv()+"."; });
}
function saveSettings(patch, quiet){
  if(!quiet) $("stSaved").textContent="Saving…";
  return fetch("api/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(patch)})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw 0; return j; }))
    .then(j=>{ showNext(j.next, $("stAuto").checked); if(!quiet) $("stSaved").textContent="Saved"; })
    .catch(()=>{ $("stSaved").textContent="Couldn't save. Check that "+srv()+" is online."; });
}
$("stAuto").onchange=e=>saveSettings({auto:e.target.checked, tz:TZ, offset:-new Date().getTimezoneOffset()});
$("stTime").onchange=e=>{ if(/^\d\d:\d\d$/.test(e.target.value)) saveSettings({time:e.target.value, tz:TZ, offset:-new Date().getTimezoneOffset()}); };
$("stBackup").onchange=e=>saveSettings({backup:e.target.checked}).then(()=>state.sid && loadState());
$("stAll").onchange=e=>saveSettings({refreshAll:e.target.checked});
$("stEd").checked=showEd;
$("stEd").onchange=e=>{ showEd=e.target.checked; store("nd-ed", showEd?"on":"off"); render(); };
$("stPeriod").replaceChildren(...PERIODS.map(([d,l])=>{ const o=document.createElement("option"); o.value=String(d); o.textContent=l; return o; }));
$("stPeriod").value=String(state.period);
$("stPeriod").onchange=e=>setPeriod(+e.target.value);
(()=>{ const n=document.createElement("div"); n.className="note"; n.id="stPeriodNote2"; $("stPeriodNote").after(n); })();
$("cog").addEventListener("click",()=>{ $("stPeriod").value=String(state.period); const t=periodNote(); $("stPeriodNote2").textContent=t; $("stPeriodNote2").hidden=!t; });
const shortDate = d => d ? new Date(d).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "";
const verTitle = v => v.subject || (v.version ? "Version "+v.version : v.commit ? "Version "+v.commit.slice(0,7) : "Older version");
// Version pill: "v1.2" when the version is numbered, otherwise the short code.
// Version pill: "v1.2" when the version is numbered, otherwise the short code. A numbered version links to its
// release notes on GitHub (the CHANGELOG heading for that version) when updates come from GitHub.
const ghVer = {repo:"", dates:{}};
function verLink(ver){
  if(!ghVer.repo || !ver) return "";
  const base="https://github.com/"+ghVer.repo+"/blob/main/CHANGELOG.md", d=ghVer.dates[ver];
  if(!d) return base+"#:~:text="+encodeURIComponent("v"+ver+" (");
  // GitHub's heading anchor: lower case, punctuation dropped, spaces become dashes
  return base+"#"+("v"+ver+" ("+d+")").toLowerCase().replace(/[^a-z0-9 _-]/g,"").replace(/ /g,"-");
}
function shaTag(sha, ver){
  const url=verLink(ver), s=document.createElement(url?"a":"span");
  s.className="sha"+(ver?" vtag":""); s.textContent=ver?"v"+ver:(sha?sha.slice(0,7):"local");
  if(url){ s.href=url; s.target="_blank"; s.rel="noopener"; s.title="What's in v"+ver+" (opens GitHub)"; s.setAttribute("aria-label","v"+ver+", release notes on GitHub"); }
  else if(ver&&sha) s.title="Code "+sha.slice(0,7);
  return s;
}
const fmtSize = b => b==null ? "unknown" : b<1048576 ? Math.max(1,Math.round(b/1024))+" KB" : b<1073741824 ? (b/1048576).toFixed(1)+" MB" : (b/1073741824).toFixed(1)+" GB";
function agoText(t){
  if(!t) return "never";
  const ms=Date.now()-(typeof t==="number" ? t*1000 : Date.parse(t)); if(!(ms>=0)) return shortDate(t);
  const m=Math.round(ms/60000); if(m<2) return "just now"; if(m<60) return m+" minutes ago";
  const h=Math.round(m/60); if(h<36) return h+(h===1?" hour ago":" hours ago");
  const d=Math.round(h/24); return d+(d===1?" day ago":" days ago");
}
// Settings > About > Status: is everything healthy, in plain words.
function loadStatus(){
  const box=$("stStatus");
  const row=(label, value, note, bad)=>{ const r=document.createElement("div"); r.className="ui-row ui-static";
    const l=document.createElement("span"); l.className="ui-l"; const b=document.createElement("b"); b.textContent=label; l.append(b);
    if(note){ const n=document.createElement("small"); n.textContent=note; l.append(n); }
    const v=document.createElement("span"); v.className="ui-v"; v.textContent=value; if(bad) v.style.color="var(--bad)";
    r.append(l,v); return r; };
  fetch("api/status").then(r=>r.json()).then(s=>{
    const rows=[];
    const pc=row(s.refreshing ? "Price check" : "Last price check", s.refreshing ? "Running now" : agoText(s.lastRefresh),
      s.settings&&s.settings.auto ? "Runs each night at "+(s.settings.time||"03:00") : "Nightly check is off");
    if(s.refreshing){   // a progress bar that follows the check while this page is open
      pc.classList.add("ui-stack"); pc.id="stPrice";
      const top=document.createElement("div"); top.style.cssText="display:flex;align-items:center;gap:12px"; top.append(...pc.children); pc.append(top);
      const bar=document.createElement("div"); bar.className="pbar"; bar.id="stPriceBar"; bar.setAttribute("role","progressbar"); bar.setAttribute("aria-label","Price check progress"); bar.append(document.createElement("i"));
      pc.append(bar); watchStatusJob();
    }
    rows.push(pc);
    const bk=s.lastBackup; rows.push(row("Last automatic backup", bk ? agoText(bk.created) : "none yet", "A daily copy is kept for 7 days"));
    rows.push(row("Database size", fmtSize(s.dbSize)));
    rows.push(row("Card pictures", fmtSize(s.pictures), "Saved on "+srv()+" as you view cards"));
    if(s.backupCount!=null) rows.push(row("Automatic backups", fmtSize(s.backupSize), s.backupCount+" kept · the oldest are deleted by themselves"));
    const low=s.freeSpace!=null && s.freeSpace<1073741824;
    rows.push(row("Free space", fmtSize(s.freeSpace), low ? "Running low" : "", low));
    const pr=s.problems||[];
    if(pr.length){
      // a plain summary ("card shows: 6"), with the full messages behind Show details
      const kinds={}; for(const p of pr){ const k=(p.msg.match(/^([^:]{2,40}):/)||[,"other"])[1].trim(); kinds[k]=(kinds[k]||0)+1; }
      const r=row("Recent problems", pr.length+" in the last day", Object.entries(kinds).map(([k,n])=>k+(n>1?" ("+n+")":"")).join(" · "), true);
      r.classList.add("ui-stack");
      const det=document.createElement("details"); det.className="prob-det"; const sum=document.createElement("summary"); sum.textContent="Show details";
      const pre=document.createElement("small"); pre.textContent=pr.map(p=>new Date(p.at*1000).toLocaleTimeString([], {hour:"numeric",minute:"2-digit"})+"  "+p.msg).join("\n");
      det.append(sum,pre); r.querySelector(".ui-l").append(det); rows.push(r); }
    else rows.push(row("Recent problems", "None"));
    box.replaceChildren(...rows);
  }).catch(()=>{ box.replaceChildren(row("Status", "Couldn't reach "+srv(), "", true)); });
}
// While a price check runs, keep the Status bar and its "card 12 of 113" line moving (every 2 seconds).
let stJobTimer=null;
function watchStatusJob(){
  clearTimeout(stJobTimer);
  fetch("api/refresh").then(r=>r.json()).then(j=>{
    const bar=$("stPriceBar"); if(!bar || !$("settings").open) return;
    if(!j.running){ loadStatus(); return; }
    setBar(bar, j.done, j.total);
    const v=document.querySelector("#stPrice .ui-v"), n=document.querySelector("#stPrice .ui-l small");
    if(v) v.textContent=(j.total ? Math.round(j.done/j.total*100) : 0)+"%";
    if(n) n.textContent="Checking "+(j.name||"prices")+": card "+Math.min(j.done+1,j.total||1)+" of "+(j.total||"…");
    showJob(j);   // the top of the page shows it too
    stJobTimer=setTimeout(watchStatusJob,2000);
  }).catch(()=>{ if($("settings").open) stJobTimer=setTimeout(watchStatusJob,5000); });
}
function loadVersion(){
  loadStatus();
  const notes=fetch("api/changelog").then(r=>r.json()).then(c=>{ for(const e of c.entries||[]) ghVer.dates[e.v]=e.date; }).catch(()=>{});
  fetch("api/version").then(r=>r.json()).then(async v=>{
    ghVer.repo = v.github && /^[\w.-]+\/[\w.-]+$/.test(v.repo||"") ? v.repo : "";
    await notes;
    const box=$("stVersion"); box.replaceChildren();
    const k=document.createElement("span"); k.className="k"; k.textContent="Installed version";
    const t=document.createElement("b"); t.textContent=verTitle(v);
    if(v.version) $("sumAbout").textContent="v"+v.version;
    const s=document.createElement("span"); s.className="s";
    s.append(shaTag(v.commit, v.version), " Installed "+shortDate(v.installed||v["server.py"])+" · "+(v.github?"updates from GitHub":v.updatesFolder?"updates from the updates folder":"updates not set up"));
    box.append(k,t,s);
    if(v.storage){ const d=document.createElement("span"); d.className="s"; const mb=v.storage.size/1048576;
      d.textContent="Your data: one database file on "+srv()+" ("+v.storage.file+", "+(mb<1 ? Math.max(1,Math.round(v.storage.size/1024))+" KB" : mb.toFixed(1)+" MB")+")"; box.append(d); }
    if(v.error){ const e=document.createElement("span"); e.className="s"; e.style.color="var(--bad)"; e.textContent="Last check failed: "+v.error+"."; box.append(e); }
    $("stUpdate").hidden = !(v.github || v.updatesFolder);
    const prev=v.previous||[], ul=$("stPrev"); ul.replaceChildren(); $("stPrevWrap").hidden=!prev.length;
    for(const p of prev){
      const li=document.createElement("li");
      const tt=document.createElement("span"); tt.className="t"; tt.textContent=verTitle(p);
      const ss=document.createElement("span"); ss.className="s"; ss.append(shaTag(p.commit, p.version)," Used until "+shortDate(p.saved));
      const b=document.createElement("button"); b.type="button"; b.className="btn"; b.textContent="Roll back";
      b.onclick=()=>doRollback(p);
      li.append(tt,ss,b); ul.append(li);
    }
  }).catch(()=>{ $("stVersion").textContent="Couldn't check the installed version."; });
}
// Updates, restores, Reload the app and Clear saved copy all start fresh on My binders (not the binder or card show you were on).
const reloadHome = () => location.replace(location.pathname+location.search);
async function afterInstall(j, msgEl, text){
  msgEl.textContent=text;
  const wait=ms=>new Promise(res=>setTimeout(res,ms));
  if(j.restarting){ await wait(2500); for(let i=0;i<20;i++){ try{ const r=await fetch("api/version",{cache:"no-store"}); if(r.ok) break; }catch(_){} await wait(1000); } }
  reloadHome();
}
function changeList(changes){
  const ul=document.createElement("ul"); ul.className="changes";
  for(const c of changes){
    const li=document.createElement("li");
    const t=document.createElement("span"); t.className="t"; t.textContent=c.subject||"Update";
    const s=document.createElement("span"); s.className="s"; s.append(shaTag(c.sha, c.version), shortDate(c.date));
    li.append(t,s); ul.append(li);
  }
  return ul;
}
$("stUpdate").onclick=async()=>{
  const b=$("stUpdate"), msg=$("stUpdMsg"); b.disabled=true; msg.textContent="Checking…";
  try{
    const v=await (await fetch("api/version")).json();
    let changes=null;
    if(v.github){
      const r=await fetch("api/update/check"); const j=await r.json();
      if(!r.ok) throw new Error(j.error||"Update check failed");
      if(j.upToDate){ msg.textContent="You're up to date."; b.disabled=false; loadVersion(); return; }
      changes=j.changes;
    }
    msg.textContent="";
    const n=changes?changes.length:0;
    const latestVer=changes&&changes[0]&&changes[0].version;
    const ok=await askConfirm(latestVer?"Update to v"+latestVer+"?":"Update available", changes ? (n===1?"1 change since your version:":n+" changes since your version:") : "Install the files from your updates folder?",
      "Install update", {safe:true, body: changes?changeList(changes):null});
    if(!ok){ b.disabled=false; return; }
    let r, j;
    for(;;){
      if(!await waitForPriceCheck(msg)){ msg.textContent="Update not installed: Settings was closed while waiting. Check for updates again any time."; b.disabled=false; return; }
      msg.textContent="Installing…";
      r=await fetch("api/update",{method:"POST"}); j=await r.json();
      if(r.status!==409 || !/price check/i.test(j.error||"")) break;   // a price check started in between: wait for it too (anything else busy: say so)
    }
    if(!r.ok) throw new Error(j.error||"Update failed");
    if(!j.installed.length){ msg.textContent="Nothing new to install."; b.disabled=false; loadVersion(); return; }
    afterInstall(j, msg, "Installed. Reloading…");
  }catch(e){ msg.textContent=e.message+"."; b.disabled=false; }
};
// Updates wait for a running price check, so the check isn't cut off. Shows its progress, then carries on.
// Resolves true when no check is running, false if Settings is closed while waiting.
async function waitForPriceCheck(msg){
  const bar=$("stUpdBar");
  try{
    for(;;){
      const j=await fetch("api/refresh").then(r=>r.json());
      if(!j.running) return true;
      if(!$("settings").open) return false;
      setBar(bar, j.done, j.total);
      msg.textContent="Waiting for the price check to finish ("+(j.name||"prices")+": card "+Math.min(j.done+1,j.total||1)+" of "+(j.total||"…")+"). The update installs right after.";
      await new Promise(res=>setTimeout(res,2000));
    }
  } finally { hideBar(bar); }
}
async function doRollback(p){
  const ok=await askConfirm(p.version?"Roll back to v"+p.version+"?":"Roll back to this version?", "“"+verTitle(p)+"” will be reinstalled. Your collection, purchases and photos are not affected.", "Roll back", {safe:true});
  if(!ok) return;
  const msg=$("stUpdMsg"); msg.textContent="Rolling back…";
  try{
    const r=await fetch("api/rollback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:p.id})});
    const j=await r.json(); if(!r.ok) throw new Error(j.error||"Roll back failed");
    afterInstall(j, msg, "Rolled back. Reloading…");
  }catch(e){ msg.textContent=e.message+"."; }
}
$("cog").onclick=()=>{ loadSettings(); loadVersion(); settingsSummary(); $("settings").showModal(); };
$("sClose").onclick=()=>$("settings").close();
// While a window is open on top of the page (modal), scrolling outside its scrolling area does nothing,
// so a fast scroll can't move the binder behind it. Inside the window, scrolling stops at its edges (CSS above).
const modalOpen = () => !!document.querySelector("dialog[open]:modal");
const stopBehind = e => { if(modalOpen() && !e.target.closest("dialog[open] .sheet, dialog#drawer[open]")) e.preventDefault(); };
document.addEventListener("wheel", stopBehind, {passive:false});
document.addEventListener("touchmove", stopBehind, {passive:false});

// Floating windows get a title bar: the window's name on the left, a close icon on the right.
// The old Close button moves into the bar (keeps its id and click handler); the title is moved, not copied.
document.querySelectorAll("dialog.float").forEach(dlg=>{
  const sheet=dlg.querySelector(".sheet"), close=sheet.querySelector(":scope > .close");
  const bar=document.createElement("div"); bar.className="fbar";
  const h=dlg.id==="dlg" ? null : sheet.querySelector("h2");
  if(h){ bar.append(h); }
  else { const t=document.createElement("span"); t.className="ftitle"; t.textContent="Card details"; bar.append(t); }
  if(close){
    close.className="fclose"; close.setAttribute("aria-label","Close"); close.title="Close";
    close.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    bar.append(close);
  }
  dlg.prepend(bar);
  sheet.addEventListener("scroll",()=>bar.classList.toggle("scrolled", sheet.scrollTop>4),{passive:true});
  dlg.addEventListener("close",()=>{ sheet.scrollTop=0; bar.classList.remove("scrolled"); });
});

// ---------- building block: a window with a list of sections ----------
// Phones: the list shows first; tapping a row opens that section full screen with a back arrow
// (the phone's back gesture also goes back to the list). Wider screens: the list stays on the left.
const wideUI=matchMedia("(min-width:760px)");
function uiPages(dlg){
  const sheet=dlg.querySelector(".ui-split"), nav=sheet.querySelector(".ui-nav"), pages=[...sheet.querySelectorAll(".ui-page")];
  const bar=dlg.querySelector(".fbar"), title=bar.querySelector("h2"), home=title.textContent;
  const back=document.createElement("button"); back.type="button"; back.className="fclose ui-back"; back.setAttribute("aria-label","Back to "+home); back.title="Back";
  back.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
  back.hidden=true; bar.prepend(back);
  let at="";
  function go(id, focus){
    if(!id && wideUI.matches) id=pages[0].dataset.page;
    at=id||"";
    const page=pages.find(p=>p.dataset.page===at);
    pages.forEach(p=>p.classList.toggle("on", p===page));
    nav.querySelectorAll("[data-go]").forEach(r=>{ if(r.dataset.go===at) r.setAttribute("aria-current","page"); else r.removeAttribute("aria-current"); });
    const sub=!wideUI.matches && !!page;
    nav.hidden=sub; back.hidden=!sub;
    title.textContent=sub ? page.dataset.title : home;
    sheet.scrollTop=0; if(page) page.scrollTop=0;
    if(focus){ if(sub) back.focus(); else { const r=nav.querySelector('[data-go="'+focus+'"]'); if(r) r.focus(); } }
  }
  nav.addEventListener("click",e=>{ const r=e.target.closest("[data-go]"); if(r) go(r.dataset.go, wideUI.matches ? null : true); });
  back.onclick=()=>go("", at);
  dlg.addEventListener("cancel",e=>{ if(!wideUI.matches && at){ e.preventDefault(); go("", at); } });
  dlg.addEventListener("close",()=>go(""));
  wideUI.addEventListener("change",()=>go(wideUI.matches ? at : ""));
  go("");
  return {go, get at(){ return at; }};
}
const settingsPages=uiPages($("settings"));
// The value shown on each row of the Settings list, like "Night" or "3:00 AM".
const slotShort = sl => !sl||sl.t==="none" ? "" : sl.t==="raw" ? sl.c : (sl.co==="Any" ? "Graded" : sl.co)+" "+sl.g;
function settingsSummary(){
  const sk=SKINS.find(x=>x[0]===(document.documentElement.dataset.skin||"night"))||SKINS[0];
  $("sumLook").textContent=sk[1]; $("skinNote").textContent=sk[1]+": "+sk[2]+".";
  $("sumPrices").textContent=(state.slots||[]).map(slotShort).filter(Boolean).join(" + ");
  const t=$("stTime").value||"03:00", [h,m]=t.split(":").map(Number);
  $("sumRefresh").textContent=$("stAuto").checked ? new Date(2000,0,1,h,m).toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"}) : "Off";
  $("sumSrv").textContent=state.serverName||"Not named";
  { const o=$("stLp").selectedOptions[0]; $("sumPhone").textContent=lpMode()==="off" ? "" : "Hold a card: "+(o?o.textContent:""); }
  if(!$("sumAbout").textContent) $("sumAbout").textContent=($("verNum").textContent||"").split(" ")[0];
  $("sumBackup").textContent="";
}
$("settings").addEventListener("change",()=>setTimeout(settingsSummary,50));
$("settings").addEventListener("click",e=>{ if(e.target.closest(".skin,.slotrow")) setTimeout(settingsSummary,50); });

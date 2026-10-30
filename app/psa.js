// PSA slab check.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- PSA slab check ----------
// Scan the barcode or QR code on a PSA slab's label (or type the cert number). The server asks PSA, then this shows
// the card, grade and PSA's photos, the matching card in your binders, and links to recent sales of that grade.
const PSA_SHIELD='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>';
const PSA_WARN='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/></svg>';
let psaReady=null;   // is a PSA access code saved on the server? (null = not known yet)
function psaCertFrom(raw){
  const t=String(raw||"").trim();
  let m=t.match(/psacard\.com\/cert\/(\d{5,12})/i); if(m) return m[1];
  if(/^[\d\s-]{5,20}$/.test(t)){ const d=t.replace(/\D/g,""); if(d.length>=5 && d.length<=12) return d; }
  m=t.match(/(?:^|\D)(\d{7,10})(?:\D|$)/); return m ? m[1] : "";
}
const psaSet = d => d.brand.replace(/^pokemon\s+/i,"").replace(/^game$/i,"Base Set");   // PSA calls Base Set "Pokemon Game"
const psaName = d => psaTitle(d.subject.replace(/-holo$/i,""));
const psaTitle = t => String(t||"").toLowerCase().replace(/(^|[\s\-(\/])([a-z])/g,(a,b,c)=>b+c.toUpperCase());
function psaShow(){
  psaStopLive();
  $("psaBody").hidden=true; $("psaStart").hidden=false; $("psaMsg").textContent=""; $("psaMsg").className="note";
  $("psaNum").value="";
}
function openPsa(){
  if($("drawer").open) $("drawer").close();
  psaShow(); $("psaDlg").showModal();
}
function psaEbayUrl(d){
  const m=d.match, grade="PSA "+(d.grade||"");
  const first=/1st/i.test(d.variety);
  let words;
  if(m){
    const no=m.cardNum ? "#"+String(m.cardNum).replace(/^0+(?=\d)/,"")+(m.pt ? "/"+m.pt : "") : "";
    const set=(m.set||"").replace(/ Base Set$/,"");
    words=[d.year||m.year, set==="Base" ? "Base Set" : set, m.name, /Holo/.test(m.rarity||"") ? "Holo" : "", no];
  } else {
    words=[d.year, psaTitle(psaSet(d)), psaName(d), /holo/i.test(d.subject) ? "Holo" : "", d.num ? "#"+d.num : ""];
  }
  words.push(d.grade ? grade : "PSA", first ? "1st Edition" : "-1st");
  return "https://www.ebay.com/sch/i.html?_nkw="+enc(words.filter(Boolean).join(" "))+"&LH_Sold=1&LH_Complete=1&_sop=13";
}
function psaPcUrl(d){
  const m=d.match;
  if(m && m.pc) return m.pc;
  const s=m ? (m.set||"").replace(/ Base Set$/,"")+" "+m.name+" "+(m.cardNum||"") : psaSet(d)+" "+psaName(d)+" "+d.num;
  return "https://www.pricecharting.com/search-products?type=prices&q="+q(s);
}
function psaLinkRow(href, title, sub){
  const a=document.createElement("a"); a.className="ui-row"; a.href=href; a.target="_blank"; a.rel="noopener noreferrer";
  const l=document.createElement("span"); l.className="ui-l"; const b=document.createElement("b"); b.textContent=title; const s=document.createElement("small"); s.textContent=sub;
  l.append(b,s); const ar=document.createElement("span"); ar.className="psa-go"; ar.setAttribute("aria-hidden","true"); ar.textContent="↗";
  a.append(l,ar); return a;
}
function psaDraw(d){
  const box=$("psaBody"); box.replaceChildren(); box.hidden=false; $("psaStart").hidden=true; $("psaMsg").textContent="";
  const ban=document.createElement("div");
  if(d.manual){ psaDrawManual(box, d); return; }
  if(!d.found){
    ban.className="psa-ban no"; ban.innerHTML=PSA_WARN+'<div><b>No PSA record found</b><small></small></div>';
    ban.querySelector("small").textContent="Cert "+d.cert;
    const n=document.createElement("div"); n.className="note"; n.textContent="Double-check the number on the label. If it's right and PSA has no record, treat the slab as fake.";
    const row=document.createElement("div"); row.className="row-end"; const again=document.createElement("button"); again.className="btn primary"; again.type="button"; again.textContent="Try again"; again.onclick=psaShow; row.append(again);
    box.append(ban,n,row); again.focus(); return;
  }
  ban.className="psa-ban ok"; ban.innerHTML=PSA_SHIELD+'<div><b>Real PSA cert</b><small></small></div>';
  ban.querySelector("small").textContent="Cert "+d.cert+" is in PSA's records";
  const m=d.match;
  // the card: PSA's photo of the slab when it has one, else the binder's picture
  const card=document.createElement("div"); card.className="psa-card";
  const th=document.createElement("button"); th.type="button"; th.className="psa-th";
  const im=document.createElement("img"); im.alt="";
  const sides=d.imgs||[];
  const src=sides.includes("front") ? "api/psa/"+d.cert+"/front.jpg" : m ? "set/"+enc(m.sid)+"/img/"+enc(m.n)+".png" : "";
  if(src){ im.src=src; im.onerror=()=>th.remove(); th.append(im); th.setAttribute("aria-label","Show the picture bigger");
    th.onclick=()=>{ zoomFoil(null); $("zoomImg").src=sides.includes("front") ? "api/psa/"+d.cert+"/front.jpg" : "set/"+enc(m.sid)+"/img/"+enc(m.n)+".png?full=1"; $("zoom").showModal(); }; }
  const info=document.createElement("div"); info.className="psa-info";
  const nm=document.createElement("div"); nm.className="nm"; nm.textContent=m ? m.name : psaName(d);
  const s1=document.createElement("small"); s1.textContent=[m ? m.set : psaTitle(psaSet(d)), d.num ? "#"+d.num : "", psaTitle(d.variety)].filter(Boolean).join(" · ");
  const s2=document.createElement("small"); s2.textContent=[d.year, d.pop!=null && d.pop!=="" ? "PSA has graded "+d.pop+" at this grade"+(Number(d.higher)>0 ? ", "+d.higher+" higher" : "") : ""].filter(Boolean).join(" · ");
  info.append(nm,s1,s2);
  const gr=document.createElement("div"); gr.className="psa-grade"; const gb=document.createElement("b"); gb.textContent=d.grade||"A"; const gs=document.createElement("small"); gs.textContent=(d.gradeText||"").toUpperCase(); gr.append(gb,gs);
  card.append(th,info,gr);
  const warn=document.createElement("div"); warn.className="note";
  warn.textContent=(sides.includes("front") ? "This is PSA's own photo of this slab. " : "")+"Make sure the slab in your hand shows the same card and grade. Fake slabs sometimes copy a real cert number.";
  box.append(ban,card,warn);
  if(sides.includes("back")){ const bk=document.createElement("button"); bk.type="button"; bk.className="hm-link psa-back"; bk.textContent="See PSA's photo of the back";
    bk.onclick=()=>{ zoomFoil(null); $("zoomImg").src="api/psa/"+d.cert+"/back.jpg"; $("zoom").showModal(); }; box.append(bk); }
  // recent sales: eBay sold listings for this exact grade, and PriceCharting's prices by grade
  const h=document.createElement("h3"); h.className="ui-h"; h.textContent="Recent sales";
  const g=document.createElement("div"); g.className="ui-group";
  const gname=d.grade ? "PSA "+d.grade : "PSA";
  g.append(psaLinkRow(psaEbayUrl(d), "eBay sold · "+gname, (/1st/i.test(d.variety) ? "1st Edition" : "Unlimited")+" "+gname+" sales, newest first"),
           psaLinkRow(psaPcUrl(d), "PriceCharting", "Prices for every grade · opens in a new tab"),
           psaLinkRow("https://www.psacard.com/cert/"+d.cert+"/psa", "PSA's page for this slab", "Cert details and PSA's auction prices"));
  box.append(h,g);
  // your binders
  const h2=document.createElement("h3"); h2.className="ui-h"; h2.textContent="Your binders";
  const g2=document.createElement("div"); g2.className="ui-group";
  if(m){
    const r=document.createElement("button"); r.type="button"; r.className="ui-row";
    const l=document.createElement("span"); l.className="ui-l"; const b=document.createElement("b"); const s=document.createElement("small");
    b.textContent=isPrivate() ? "In your "+m.binder+" binder" : m.owned ? "You own this card" : "You need this card";
    s.textContent=[m.binder+(m.page ? ", page "+m.page : ""), m.price ? "raw price "+money(m.price) : "", m.sure ? "" : "best guess"].filter(Boolean).join(" · ");
    l.append(b,s); const c=document.createElement("span"); c.className="ui-chev"; c.setAttribute("aria-hidden","true"); r.append(l,c);
    r.onclick=()=>{ $("psaDlg").close(); goBinder(m.sid, ()=>{ if(state.sid===m.sid) openCard(m.n); }); };
    g2.append(r);
  } else {
    const r=document.createElement("div"); r.className="ui-row ui-static"; r.innerHTML='<span class="ui-l"><b>Not in your binders</b><small>None of your binders has this card.</small></span>'; g2.append(r);
  }
  box.append(h2,g2);
  if(m && /1st/i.test(d.variety)){ const n=document.createElement("div"); n.className="note"; n.textContent="This slab is 1st Edition. Your binder's prices are for Unlimited cards."; box.append(n); }
  const row=document.createElement("div"); row.className="row-end";
  const again=document.createElement("button"); again.className="btn primary"; again.type="button"; again.textContent="Check another"; again.onclick=psaShow;
  row.append(again); box.append(row);
}
// When the server can't read PSA (PSA hasn't approved the access code and its cert page couldn't be read),
// PSA's page opens on the phone instead, and the sales links are built from the grade and card you pick.
function psaDrawManual(box, d){
  const ban=document.createElement("div"); ban.className="psa-ban info"; ban.innerHTML=PSA_SHIELD+'<div><b>Check it on PSA\'s site</b><small></small></div>';
  ban.querySelector("small").textContent="The server couldn't read PSA's records for cert "+d.cert+", so open PSA's page on your phone.";
  const go=document.createElement("a"); go.className="btn primary psa-scan"; go.href="https://www.psacard.com/cert/"+d.cert+"/psa"; go.target="_blank"; go.rel="noopener noreferrer"; go.textContent="Open PSA's page for this slab ↗";
  const n=document.createElement("div"); n.className="note"; n.textContent="It shows the card, grade and PSA's photos. If PSA has no record, or the photos don't match the slab in your hand, treat it as fake.";
  const h=document.createElement("h3"); h.className="ui-h"; h.textContent="Recent sales";
  const f=document.createElement("div"); f.className="psa-man";
  const card=document.createElement("input"); card.className="field"; card.id="psaManCard"; card.autocomplete="off"; card.placeholder="Card, like Neo Destiny Dark Espeon 4"; card.setAttribute("aria-label","The card on the label");
  card.value=psaManCard; card.enterKeyHint="done";
  const dl=document.createElement("div"); dl.className="h-chips"; dl.id="psaManList";   // suggestions from every English card, as you type
  let sugT=0, sugQ="";
  card.addEventListener("input",()=>{ clearTimeout(sugT); const v=card.value.trim(); if(v.length<3 || v===sugQ) return;
    sugT=setTimeout(()=>{ sugQ=v; fetch("api/find?q="+enc(v)).then(r=>r.json()).then(j=>{ if(card.value.trim()!==v) return; dl.replaceChildren();
      for(const c of (j.cards||[]).slice(0,8)){ const o=document.createElement("button"); o.type="button"; o.className="h-chip";
        o.textContent=[String(c.date||"").slice(0,4), (c.set||"").replace(/ Base Set$/,""), c.name, c.num ? c.num+(c.pt ? "/"+c.pt : "") : ""].filter(Boolean).join(" ");
        o.onclick=()=>{ card.value=sugQ=o.textContent; dl.replaceChildren(); links(); }; dl.append(o); }
    }).catch(()=>{}); },300); });

  const gl=document.createElement("div"); gl.className="note"; gl.textContent="Grade on the label";
  const chips=document.createElement("div"); chips.className="psa-grades"; chips.setAttribute("role","group"); chips.setAttribute("aria-label","Grade");
  for(const g of ["10","9","8.5","8","7","6","5","4","3","2","1"]){ const b=document.createElement("button"); b.type="button"; b.className="chip"; b.textContent=g; b.setAttribute("aria-pressed", String(g===psaManGrade));
    b.onclick=()=>{ psaManGrade=g; chips.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed", String(x===b))); links(); if(!card.value.trim()) card.focus(); }; chips.append(b); }
  const ed=document.createElement("label"); ed.className="psa-ed"; const cb=document.createElement("input"); cb.type="checkbox"; cb.checked=psaManFirst; ed.append(cb, " 1st Edition");
  cb.onchange=()=>{ psaManFirst=cb.checked; links(); };
  const g=document.createElement("div"); g.className="ui-group";
  const links=()=>{
    psaManCard=card.value.trim(); g.replaceChildren();
    if(!psaManCard || !psaManGrade){ const r=document.createElement("div"); r.className="ui-row ui-static"; const l=document.createElement("span"); l.className="ui-l"; const t=document.createElement("small");
      t.textContent = !psaManCard && psaManGrade ? "Now type the card name from the label (PSA "+psaManGrade+" is picked). The server couldn't read PSA's page, so it doesn't know the card." : psaManCard ? "Now tap the grade on the label." : "Type the card name from the label and tap its grade to see recent sales.";
      l.append(t); r.append(l); g.append(r); return; }
    const words=psaManCard+" PSA "+psaManGrade+(psaManFirst ? " 1st Edition" : " -1st");
    g.append(psaLinkRow("https://www.ebay.com/sch/i.html?_nkw="+enc(words)+"&LH_Sold=1&LH_Complete=1&_sop=13", "eBay sold · PSA "+psaManGrade, (psaManFirst ? "1st Edition" : "Unlimited")+" PSA "+psaManGrade+" sales, newest first"),
             psaLinkRow("https://www.pricecharting.com/search-products?type=prices&q="+q(psaManCard), "PriceCharting", "Prices for every grade · opens in a new tab"));
  };
  card.oninput=links;
  f.append(card, dl, gl, chips, ed);
  const row=document.createElement("div"); row.className="row-end";
  const again=document.createElement("button"); again.className="btn"; again.type="button"; again.textContent="Check another"; again.onclick=psaShow; row.append(again);
  box.append(ban, go, n, h, f, g, row); links();
}
let psaManCard="", psaManGrade="", psaManFirst=false;
async function psaCheck(cert){
  const msg=$("psaMsg"); msg.className="note";
  if(!/^\d{5,12}$/.test(cert||"")){ msg.textContent="Type the cert number from the label (5 to 12 digits)."; return; }
  if(!navigator.onLine){ msg.textContent="You're offline. Checking a slab needs a connection to "+srv()+"."; return; }
  msg.textContent="Asking PSA…"; $("psaGo").disabled=$("psaScan").disabled=true;
  try{
    const r=await fetch("api/psa/"+cert); const j=await r.json();
    if(!r.ok){ msg.className="err"; msg.textContent=j.error||"Couldn't check that slab."; return; }
    psaDraw(j);
  }catch(_){ msg.className="err"; msg.textContent="Couldn't reach "+srv()+". Try again."; }
  finally{ $("psaGo").disabled=$("psaScan").disabled=false; }
}
$("psaOpen").onclick=openPsa;
$("swPsa").onclick=openPsa;
$("psaClose").onclick=()=>$("psaDlg").close();
$("psaDlg").addEventListener("click",e=>{ if(e.target===$("psaDlg")) $("psaDlg").close(); });
$("psaGo").onclick=()=>psaCheck(psaCertFrom($("psaNum").value));
$("psaNum").addEventListener("keydown",e=>{ if(e.key==="Enter"){ e.preventDefault(); $("psaGo").click(); } });
// Reading the label. A live camera view inside the pop-up keeps trying as you move closer (best for the small
// barcode on PSA labels). Where the browser can't show a live camera, a photo is used, read in pieces and enlarged.
const PSA_FORMATS=["code_128","qr_code","code_39","code_93","codabar","itf","ean_13","data_matrix","pdf417"];
let psaDetector=null, psaStream=null, psaTimer=0;
async function psaGetDetector(){
  if(psaDetector) return psaDetector;
  if(!("BarcodeDetector" in window)) return null;
  let have=PSA_FORMATS;
  try{ if(BarcodeDetector.getSupportedFormats) have=await BarcodeDetector.getSupportedFormats(); }catch(_){}
  const use=PSA_FORMATS.filter(x=>have.includes(x));
  return psaDetector = use.length ? new BarcodeDetector({formats:use}) : null;
}
const psaCanLive = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.isSecureContext);
// Reads one picture (a camera frame or a photo): the whole thing first, then enlarged pieces, since the
// barcode is a thin strip at the top of the label and often too small to read in a full-size photo.
async function psaRead(src, w, h, deep){
  const det=await psaGetDetector(); if(!det) return null;
  const pick = codes => codes.map(c=>psaCertFrom(c.rawValue)).find(Boolean) || "";
  let seen=false;
  try{ const c=await det.detect(src); if(c.length) seen=true; const v=pick(c); if(v) return {cert:v}; }catch(_){}
  const parts = deep ? [[0,0,1,.5],[0,.25,1,.5],[0,.5,1,.5],[0,0,.6,.35],[.4,0,.6,.35],[.15,.2,.7,.6]] : [[.1,.25,.8,.5]];
  const cv=document.createElement("canvas"), ctx=cv.getContext("2d");
  for(const [x,y,pw,ph] of parts){
    const sw=w*pw, sh=h*ph, k=Math.min(3, 2200/Math.max(sw,1));
    cv.width=Math.round(sw*k); cv.height=Math.round(sh*k);
    ctx.imageSmoothingQuality="high"; ctx.drawImage(src, w*x, h*y, sw, sh, 0, 0, cv.width, cv.height);
    try{ const c=await det.detect(cv); if(c.length) seen=true; const v=pick(c); if(v) return {cert:v}; }catch(_){}
  }
  return seen ? {other:true} : null;
}
function psaStopLive(){
  clearTimeout(psaTimer); psaTimer=0;
  if(psaStream){ psaStream.getTracks().forEach(t=>t.stop()); psaStream=null; }
  const v=$("psaVideo"); if(v) v.srcObject=null;
  $("psaLive").hidden=true;
}
async function psaStartLive(){
  const msg=$("psaMsg"); msg.className="note"; msg.textContent="";
  if(!await psaGetDetector()){ msg.textContent="This browser can't read barcodes. Chrome on Android can. Type the cert number instead."; return; }
  if(!psaCanLive()){ $("psaCam").click(); return; }
  try{
    psaStream=await navigator.mediaDevices.getUserMedia({audio:false, video:{facingMode:{ideal:"environment"}, width:{ideal:1920}, height:{ideal:1080}}});
  }catch(e){
    msg.textContent = e && e.name==="NotAllowedError" ? "The camera is blocked for this app. Allow it in your browser's site settings, or take a photo instead." : "Couldn't open the camera. Taking a photo instead.";
    if(!(e && e.name==="NotAllowedError")) $("psaCam").click();
    return;
  }
  const v=$("psaVideo"); v.srcObject=psaStream; $("psaLive").hidden=false; $("psaStart").hidden=true;
  try{ await v.play(); }catch(_){}
  // a little zoom helps the phone focus on a small label without holding it too close
  const tr=psaStream.getVideoTracks()[0];
  try{ const cap=tr.getCapabilities ? tr.getCapabilities() : {}; const adv={};
    if(cap.zoom) adv.zoom=Math.min(cap.zoom.max, Math.max(cap.zoom.min, 2));
    if(cap.focusMode && cap.focusMode.includes("continuous")) adv.focusMode="continuous";
    if(Object.keys(adv).length) await tr.applyConstraints({advanced:[adv]}); }catch(_){}
  let tick=0;
  const loop=async()=>{
    if(!psaStream) return;
    if(v.readyState>=2 && v.videoWidth){
      const r=await psaRead(v, v.videoWidth, v.videoHeight, (++tick)%4===0);
      if(!psaStream) return;
      if(r && r.cert){ if(navigator.vibrate) navigator.vibrate(60); psaStopLive(); $("psaStart").hidden=false; $("psaNum").value=r.cert; psaCheck(r.cert); return; }
      $("psaLiveMsg").textContent = r && r.other ? "That code isn't a PSA cert number. Aim at the barcode on the label." : "Hold the label's barcode inside the box. Move closer if it's small.";
    }
    psaTimer=setTimeout(loop, 180);
  };
  loop();
}
$("psaScan").onclick=psaStartLive;
$("psaLiveStop").onclick=()=>{ psaStopLive(); $("psaStart").hidden=false; };
$("psaLivePhoto").onclick=()=>{ psaStopLive(); $("psaStart").hidden=false; $("psaCam").click(); };
$("psaDlg").addEventListener("close", psaStopLive);
document.addEventListener("visibilitychange",()=>{ if(document.hidden && psaStream){ psaStopLive(); $("psaStart").hidden=false; } });
$("psaCam").onchange=async e=>{
  const f=e.target.files && e.target.files[0]; e.target.value=""; if(!f) return;
  const msg=$("psaMsg"); msg.className="note";
  if(!await psaGetDetector()){ msg.textContent="This browser can't read barcodes. Chrome on Android can. Type the cert number instead."; return; }
  msg.textContent="Reading the label…";
  try{
    const img=await createImageBitmap(f);
    const r=await psaRead(img, img.width, img.height, true);
    if(!r || !r.cert){ msg.textContent= r && r.other ? "That code isn't a PSA cert number. Try the barcode on the label, or type the number." : "Couldn't find the barcode. Try again closer, so the label fills most of the photo, or type the number printed under the grade."; return; }
    $("psaNum").value=r.cert; psaCheck(r.cert);
  }catch(_){ msg.textContent="Couldn't read that photo. Try again, or type the cert number."; }
};
// Settings > Prices: the PSA access code (only "saved or not" ever comes back from the server)
function loadPsaSetting(){
  fetch("api/settings").then(r=>r.json()).then(s=>{ psaReady=!!s.psa; drawPsaSetting(); }).catch(()=>{});
}
function drawPsaSetting(){
  $("stPsa").value=""; $("stPsa").placeholder=psaReady ? "Saved · paste a new code to replace it" : "Paste your code";
  $("stPsaRm").hidden=!psaReady;
  if(!$("stPsaMsg").dataset.keep) $("stPsaMsg").textContent=psaReady ? "A code is saved." : "";
  delete $("stPsaMsg").dataset.keep;
}
function savePsa(v){
  fetch("api/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({psaToken:v})})
    .then(r=>r.json().then(j=>{ if(!r.ok) throw new Error(j.error||"Couldn't save"); return j; }))
    .then(()=>{ psaReady=!!v; $("stPsaMsg").textContent=v ? "Saved." : "Removed."; $("stPsaMsg").dataset.keep=1; drawPsaSetting(); })
    .catch(e=>{ $("stPsaMsg").textContent=e.message+"."; });
}
$("stPsa").addEventListener("change",()=>{ const v=$("stPsa").value.trim(); if(v) savePsa(v); });
$("stPsaRm").onclick=()=>savePsa("");
// card show mode's seller button
function setSeller(sel){
  buySeller=sel && sel.h ? {p:sel.p, h:sel.h} : null;
  $("sbSelBtn").textContent=buySeller ? sellerLabel(buySeller) : "Choose seller";
  $("sbSelBtn").classList.toggle("set", !!buySeller); $("sbSelX").hidden=!buySeller;
  const box=$("sbLink"); box.replaceChildren();
  const P=buySeller && PLAT[buySeller.p], href=P && P.url ? P.url(buySeller.h) : null;
  if(href){ const a=document.createElement("a"); a.href=href; a.target="_blank"; a.rel="noopener noreferrer"; a.textContent=href.replace(/^https?:\/\/(www\.)?/,"")+" ↗"; box.append("Links to ", a); }
}
$("sbSelBtn").onclick=()=>openSellerPicker(mergeSellers(todayKey("nd-show-sellers"), (showData&&showData.sellers), pastSellers), buySeller, sel=>{ if(sel) rememberSeller(sel); setSeller(sel); });
$("sbSelX").onclick=()=>setSeller(null);
function rememberSeller(sel){ const today=(todayKey("nd-show-sellers")||[]).filter(x=>!(x.p===sel.p && x.h===sel.h)); today.unshift(sel); setTodayKey("nd-show-sellers", today.slice(0,8)); }
function openBuy(c){
  buyCard=c; buySeller=null; buyCond=recall("nd-show-cond")||"";
  showThumb(c, $("sbTh"));
  $("sbName").textContent=c.name; $("sbSet").textContent=c.set+" · "+showNum(c);
  const st=showStale(c); $("sbAvg").textContent=c.price ? "Price "+money(c.price)+(st?" · "+st:"") : "No price yet";
  $("sbPrice").value=""; $("sbDelta").textContent=""; $("sbDelta").className="sb-delta"; $("sbOffer").replaceChildren();
  $("sbWhere").value=todayKey("nd-show-where")||"";
  const cb=$("sbCond"); cb.replaceChildren();
  for(const k of ["NM","LP","MP","HP","DMG"]){ const b=document.createElement("button"); b.type="button"; b.textContent=k; b.setAttribute("aria-pressed", k===buyCond); b.onclick=()=>{ buyCond=buyCond===k?"":k; [...cb.children].forEach(x=>x.setAttribute("aria-pressed", x.textContent===buyCond)); drawBuyOffer(); }; cb.append(b); }
  setSeller(null);
  $("sbNote").textContent=isOffline() ? "No signal: this is saved on the phone and synced after you confirm, once you're back online." : "Adds a copy to "+c.set+" with today's date.";
  $("sbSave").disabled=false;
  drawBuyOffer();
  $("swBuy").showModal();
}
// The vendor price check in the Got it sheet: type their price to see what to counter with, then change it
// to what you paid before saving.
function drawBuyOffer(){
  const c=buyCard; if(!c) return;
  if(showData && showData.habit) habit=showData.habit;
  const ask=parseFloat($("sbPrice").value.trim().replace(/^\$/,""));
  drawOffer($("sbOffer"), {ask, ref:offerRef(buyCond, (c.cond||{})[buyCond], (c.recent||{})[buyCond], c.price), t30:c.t30, stale:showStale(c),
    hist:offerHist(c.h90, c.price, c.t7)});
}
$("sbPrice").oninput=()=>{ $("sbDelta").textContent=""; $("sbDelta").className="sb-delta"; drawBuyOffer(); };
$("sbClose").onclick=()=>$("swBuy").close();
$("swBuy").addEventListener("click",e=>{ if(e.target===$("swBuy")) $("swBuy").close(); });
$("sbSave").onclick=async()=>{
  const c=buyCard; if(!c) return;
  const raw=$("sbPrice").value.trim().replace(/^\$/,""), price=raw==="" ? null : Math.round(parseFloat(raw)*100)/100;
  if(raw!=="" && !(price>=0 && price<1e7)){ $("sbDelta").className="sb-delta over"; $("sbDelta").textContent="That price doesn't look right."; return; }
  const where=$("sbWhere").value.trim().slice(0,60); setTodayKey("nd-show-where", where);
  if(buyCond) store("nd-show-cond", buyCond);
  const purchase={id:newId(), d:todayStr(), price, where};
  if(buySeller){ purchase.seller=buySeller; rememberSeller(buySeller); }
  const keepOnPhone=()=>{
    const pend=pendingList(); pend.push({sid:c.sid, n:c.n, name:c.name, set:c.set, at:new Date().toISOString(), purchase, cond:buyCond||undefined}); setPending(pend);
  };
  $("sbSave").disabled=true;
  let online=false;
  if(!isOffline()){
    try{
      const r=await fetch("api/set/"+enc(c.sid)+"/card/"+enc(c.n)+"/buy",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({purchase, cond:buyCond||null})});
      if(r.status===400){ const j=await r.json().catch(()=>({})); $("sbSave").disabled=false; $("sbNote").textContent=(j.error||"Couldn't save that")+"."; return; }
      online=r.ok;
    }catch(_){}
  }
  if(!online) keepOnPhone();   // no signal (or it dropped mid-save): wait on the phone; the purchase id stops it being added twice
  else { c.gone=true; showData.bought=(showData.bought||0)+1; showData.spent=(showData.spent||0)+(price||0); }
  if(state.sid===c.sid) state.ready=false;   // that binder reloads next time it opens
  $("swBuy").close(); drawShowView();
  toast(online ? c.name+" marked owned"+(price!=null?" · "+money(price):"")+"." : c.name+" saved on this phone. It syncs when you're back online.");
};

// Download spreadsheet, or the list for TCGplayer's Collection import: pick which binders go in
// (the spreadsheet starts with all of them, TCGplayer with none, since you'd usually import one binder at a time)
let xlKind="xlsx";
function openXl(kind){
  xlKind=kind;
  $("xlTitle").textContent = kind==="tcg" ? "Download for TCGplayer" : "Download spreadsheet";
  $("xlNote").textContent = kind==="tcg" ? "Pick the binders to put in the list. Each card you own is one line, ready for Collection → Import in the TCGplayer app (pick the Pokémon tab there first). TCGplayer's import can't read printing or condition, so it files them as 1st Edition Near Mint; the list is sorted by your condition (Near Mint first, Lightly Played if none is set) to make fixing them quick."
    : "Pick the binders to put in the Excel file. Each one gets its own tab.";
  const box=$("xlList"); box.replaceChildren(); $("xlErr").textContent="";
  for(const s of state.sets){
    const l=document.createElement("label"), sp=document.createElement("span"), b=document.createElement("b"), sm=document.createElement("small");
    b.textContent=s.name; sm.textContent=(s.owned||0)+" of "+(s.count||0)+" owned"; sp.append(b,sm);
    const cb=document.createElement("input"); cb.type="checkbox"; cb.value=s.id; cb.checked=kind!=="tcg"; cb.setAttribute("aria-label","Include "+s.name);
    l.append(sp,cb); box.append(l);
  }
  $("xlDlg").showModal();
}
$("bkXlsx").onclick=()=>{ (state.sets && state.sets.length ? Promise.resolve() : loadSets()).then(()=>openXl("xlsx")); };
$("bkTcg").onclick=()=>{ (state.sets && state.sets.length ? Promise.resolve() : loadSets()).then(()=>openXl("tcg")); };
$("xlClose").onclick=()=>$("xlDlg").close();
$("xlDlg").addEventListener("click",e=>{ if(e.target===$("xlDlg")) $("xlDlg").close(); });
$("xlAll").onclick=()=>$("xlList").querySelectorAll("input").forEach(x=>x.checked=true);
$("xlNone").onclick=()=>$("xlList").querySelectorAll("input").forEach(x=>x.checked=false);
$("xlGo").onclick=()=>{
  const all=[...$("xlList").querySelectorAll("input")], ids=all.filter(x=>x.checked).map(x=>x.value);
  if(!ids.length){ $("xlErr").textContent="Pick at least one binder."; return; }
  if(isOffline()){ $("xlErr").textContent="Downloading needs a connection to "+srv()+"."; return; }
  const pick=ids.length===all.length ? "" : "?b="+ids.map(enc).join(",");
  if(xlKind==="tcg"){ tcgDownload(pick); return; }
  const a=document.createElement("a"); a.href="api/export.xlsx"+pick; a.download="";
  document.body.append(a); a.click(); a.remove(); $("xlDlg").close();
};
// The TCGplayer list is fetched first, so the window can say how many cards TCGplayer's list didn't have
async function tcgDownload(pick){
  $("xlGo").disabled=true; $("xlErr").textContent="Matching your cards to TCGplayer's list…";
  try{
    const r=await fetch("api/export/tcgplayer.txt"+pick);
    if(!r.ok){ const j=await r.json().catch(()=>({})); throw new Error(j.error||"Couldn't make the list."); }
    const text=await r.text(), missed=Number(r.headers.get("X-Binder-Missed"))||0;
    if(!text.trim()){ $("xlErr").textContent="None of the cards you own in those binders are on TCGplayer's list."; return; }
    const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([text],{type:"text/plain"}));
    a.download="tcgplayer-import-"+todayStr()+".txt"; document.body.append(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(a.href),5000);
    $("xlDlg").close();
    const n=text.trim().split("\n").length;
    toast(n+" card"+(n===1?"":"s")+" ready for TCGplayer"+(missed ? ". "+missed+" couldn't be matched (often promos or custom cards), so add those by hand." : "."));
  }catch(e){ $("xlErr").textContent=e.message||"Couldn't make the list."; }
  finally{ $("xlGo").disabled=false; }
}
// which binders you're working on
function openPick(){
  const box=$("spList"); box.replaceChildren(); $("spErr").textContent="";
  const picked=new Set((showData&&showData.picked)||[]);
  for(const s of state.sets){
    const l=document.createElement("label"), sp=document.createElement("span"), b=document.createElement("b"), sm=document.createElement("small");
    b.textContent=s.name; const left=(s.count||0)-(s.owned||0); sm.textContent=left>0 ? left+" to go" : "Complete";
    sp.append(b,sm);
    const cb=document.createElement("input"); cb.type="checkbox"; cb.value=s.id; cb.checked=picked.has(s.id); cb.setAttribute("aria-label","Working on "+s.name);
    l.append(sp,cb); box.append(l);
  }
  $("swPick").showModal();
}
$("swShows").onclick=()=>$("showsBtn").click();
$("swCog").onclick=()=>$("cog").click();
$("swPriv").onclick=()=>{ setPrivate(!isPrivate()); if(atShow()) drawShowView(); };
$("spClose").onclick=()=>$("swPick").close();
$("swPick").addEventListener("click",e=>{ if(e.target===$("swPick")) $("swPick").close(); });
$("spDone").onclick=async()=>{
  const ids=[...$("spList").querySelectorAll("input:checked")].map(x=>x.value);
  if(isOffline()){ $("spErr").textContent="Changing binders needs a connection to "+srv()+"."; return; }
  try{
    const r=await fetch("api/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({showBinders:ids})});
    if(!r.ok) throw 0;
  }catch(_){ $("spErr").textContent="Couldn't save. Check that "+srv()+" is online."; return; }
  $("swPick").close(); showData=null; drawShowView(); loadShow(); if(homeData) homeData.working=ids;
};
function goBinder(sid, then){
  if(location.hash!=="#"+sid) history.pushState(null,"","#"+sid);
  if(state.view!=="cards") setView("cards");   // a binder always opens on its Cards tab, even the one you just left
  showBinder();
  const p = state.sid===sid && state.ready ? Promise.resolve() : openSet(sid);
  if(then) p.then(then);
}
let homeData=null;
function loadHome(){
  return Promise.all([fetch("api/home").then(r=>r.json()), loadSets()]).then(([j])=>{ homeData=j; if(atHome()) drawHome(); }).catch(()=>{});
}
// Set logos come in different shapes, and some have empty space around them, so with one fixed height
// a squarer logo (like Neo Revelation's) looked much smaller than a wide one. This trims the empty edges and
// gives every logo about the same area: wide ones get shorter, square ones taller. Leaves it as is if anything fails.
function fitLogo(img){
  try{
    const W=img.naturalWidth, H=img.naturalHeight; if(!W || !H) return;
    const cv=document.createElement("canvas"); cv.width=W; cv.height=H; const g=cv.getContext("2d"); g.drawImage(img,0,0);
    const d=g.getImageData(0,0,W,H).data; let x0=W, y0=H, x1=-1, y1=-1;
    for(let y=0;y<H;y++) for(let x=0;x<W;x++) if(d[(y*W+x)*4+3]>16){ if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
    if(x1<0) return;
    const w=x1-x0+1, h=y1-y0+1;
    img.dataset.fit="1";
    if(w<W || h<H){ const c2=document.createElement("canvas"); c2.width=w; c2.height=h; c2.getContext("2d").drawImage(cv,x0,y0,w,h,0,0,w,h); img.src=c2.toDataURL("image/png"); }
    img.style.setProperty("--lr", Math.min(1.15, 1/Math.sqrt(w/h)).toFixed(3)); img.classList.add("fit");
  }catch(_){}
}
function homeStyle(b, el, img){   // the binder's colors: the Neo sets have their own, others come from the logo or the Pokémon
  const st=COVER_STYLE[b.id] || coverStyleCache[b.id];
  if(st){ el.style.setProperty("--v1",st[0]); el.style.setProperty("--v2",st[1]); return; }
  const use=c=>{ if(c){ coverStyleCache[b.id]=c; el.style.setProperty("--v1",c[0]); el.style.setProperty("--v2",c[1]); } };
  if(!isDex(b.id) && !isOwn(b.id)){ const lg=new Image(); lg.onload=()=>use(logoStyle(lg)); lg.src="set/"+enc(b.id)+"/logo.png"; }
  else if(img) img.addEventListener("load",()=>{ if(!coverStyleCache[b.id]) use(logoStyle(img)); },{once:true});
}
function drawHome(){
  const shelf=$("hmShelf"), list=homeData ? homeData.binders : state.sets.map(s=>({id:s.id, name:s.name, releaseDate:s.releaseDate, printedTotal:s.printedTotal, count:s.count, owned:s.owned}));
  shelf.replaceChildren();
  for(const b of list){
    const t=document.createElement("button"); t.type="button"; t.className="bk";
    const pct=b.count ? Math.floor(b.owned/b.count*100) : 0;
    const sub = isDex(b.id) ? "Master set · "+b.count+" cards" : isOwn(b.id) ? "My binder · "+b.count+" cards" : [year(b.releaseDate), (b.printedTotal||b.count)+" cards"].filter(Boolean).join(" · ");
    let im=null;
    const cv=b.cover;
    if(cv && cv.dex){
      im=document.createElement("img"); im.className="bk-mon"; im.alt=""; im.decoding="async"; im.loading="lazy";
      im.src="art/"+cv.dex+(cv.shiny?"s":"")+".png";
      im.onerror=()=>{ if(/s\.png$/.test(im.src)) im.src="art/"+cv.dex+".png"; else im.remove(); };
      t.append(im);
    }
    homeStyle(b, t, im);
    const ring=document.createElement("span"); ring.className="ring"; ring.style.setProperty("--p",pct); ring.setAttribute("aria-hidden","true");
    const ri=document.createElement("i"); ri.textContent=pct+"%"; ring.append(ri);
    const nm=document.createElement("span"); nm.className="bk-nm"; const nb=document.createElement("b"); nb.textContent=b.name; const ns=document.createElement("span"); ns.textContent=sub; nm.append(nb,ns);
    if(!isDex(b.id) && !isOwn(b.id)){   // set binders show the set's logo (the same one as the inside cover); the name stays if there's none
      const lg=document.createElement("img"); lg.className="bk-logo"; lg.alt=""; lg.decoding="async";
      lg.onload=()=>{ if(lg.dataset.fit) return; fitLogo(lg); nb.replaceWith(lg); nm.classList.add("has-logo"); }; lg.onerror=()=>lg.remove(); lg.src="set/"+enc(b.id)+"/logo.png";
    }
    t.append(ring,nm);
    if(((homeData&&homeData.working)||[]).includes(b.id)){ const wk=document.createElement("span"); wk.className="bk-work"; wk.textContent="Working on"; t.append(wk); }
    t.setAttribute("aria-label", b.name+", "+sub+(!isPrivate() ? ", "+pct+"% complete" : ""));
    t.onclick=()=>goBinder(b.id);
    shelf.append(t);
  }
  const add=document.createElement("button"); add.type="button"; add.className="bk add";
  add.innerHTML='<span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>Add a binder</span>';
  add.onclick=$("hmAdd").onclick=()=>{ showAdd(true); openDrawer(); };
  if(!list.length) shelf.append(add);   // with binders, the small button by "Your binders" adds one
  $("hmEdit").hidden=$("hmAdd").hidden=!list.length;
  const rec=(homeData && homeData.recent)||[], box=$("hmRecent");
  $("hmRecentBox").hidden=!rec.length; box.replaceChildren();
  for(const r of rec){
    const c=document.createElement("button"); c.type="button"; c.className="hm-card";
    const f=document.createElement("span"); f.className="c"; const im=document.createElement("img"); im.alt=""; im.loading="lazy"; im.decoding="async";
    im.src="set/"+enc(r.sid)+"/img/"+enc(r.n)+".png"; im.onerror=()=>im.remove(); f.append(im);
    const b=document.createElement("b"); b.textContent=r.name; const sm=document.createElement("small"); sm.textContent=r.set+" · "+addedAgo(r.d);
    c.append(f,b,sm); c.setAttribute("aria-label", r.name+", "+r.set+", added "+addedAgo(r.d));
    c.onclick=()=>goBinder(r.sid, ()=>{ if(state.sid===r.sid) openCard(r.n); });
    box.append(c);
  }
}
// "today", "3 days ago", "last week" for a date (recently added cards). Status uses agoText for exact times.
function addedAgo(d){
  const days=Math.round((new Date(todayStr())-new Date(d.slice(0,10)))/864e5);
  return days<=0 ? "today" : days===1 ? "yesterday" : days<7 ? days+" days ago" : days<14 ? "last week" : days<60 ? Math.round(days/7)+" weeks ago" : new Date(d).toLocaleDateString(undefined,{month:"short",year:"numeric"});
}
$("hmPriv").onclick=()=>{ setPrivate(!isPrivate()); if(atHome()) drawHome(); };
$("hmCog").onclick=()=>$("cog").click();
$("hmShows").onclick=()=>$("showsBtn").click();
$("stReload").onclick=()=>reloadHome();
// Clear saved copy: the phone app's offline copy (page, binder data, pictures) is deleted and downloaded again.
// Nothing on the server changes, and changes waiting to sync (kept separately) stay. Only while connected,
// so the app can't be left with nothing to open.
$("stClear").onclick=async()=>{
  if(isOffline()){ toast("Clearing needs a connection to "+srv()+", so the app can download a fresh copy."); return; }
  const ok=await askConfirm("Clear the saved copy?", "This device downloads a fresh copy of the app, your binder data and card pictures from "+srv()+". Your binders, purchases and photos stay on "+srv()+(pendingList().length?", and "+(pendingList().length===1?"the change waiting to sync stays":"the "+pendingList().length+" changes waiting to sync stay")+" on this phone.":"."), "Clear", {safe:true});
  if(!ok) return;
  try{ if(window.caches) for(const k of await caches.keys()) if(k.startsWith("binder-")) await caches.delete(k); }catch(_){}
  try{ if(navigator.serviceWorker) for(const r of await navigator.serviceWorker.getRegistrations()) await r.unregister(); }catch(_){}
  store("nd-warm");   // save the offline copy again soon
  reloadHome();
};
$("hmMenu").onclick=()=>{ showAdd(false); drawSets(); openDrawer(); loadSets().then(drawSets); };
// Edit on My binders: the Binder covers window (background style), with the old reorder/rename/remove one tap away.
const COVER_STYLES=[["rays","Sunburst"],["spot","Spotlight"],["ball","Poké Ball"],["holo","Holo"],["dots","Halftone"]];
const coverBg = () => document.documentElement.dataset.cover || "rays";
function setCoverBg(k){ if(k==="rays"){ delete document.documentElement.dataset.cover; store("nd-cover"); } else { document.documentElement.dataset.cover=k; store("nd-cover",k); } drawCoverOpts(); }
function drawCoverOpts(){
  const box=$("cvOpts"); box.replaceChildren();
  const sample=document.querySelector("#hmShelf .bk:not(.add)");
  for(const [k,label] of COVER_STYLES){
    const b=document.createElement("button"); b.type="button"; b.className="cover-opt"; b.setAttribute("aria-pressed", k===coverBg());
    let t; if(sample){ t=sample.cloneNode(true); t.removeAttribute("aria-label"); t.tabIndex=-1; } else { t=document.createElement("div"); t.className="bk"; t.style.setProperty("--v1","#ffe24d"); t.style.setProperty("--v2","#e8407a"); }
    t.classList.add("cvp","cv-"+k);
    const l=document.createElement("span"); l.textContent=label;
    b.append(t,l); b.setAttribute("aria-label", label+" background"); b.onclick=()=>setCoverBg(k); box.append(b);
  }
}
$("hmEdit").onclick=()=>{ drawCoverOpts(); $("coverDlg").showModal(); };
$("cvClose").onclick=()=>$("coverDlg").close();
$("coverDlg").addEventListener("click",e=>{ if(e.target===$("coverDlg")) $("coverDlg").close(); });
$("cvEdit").onclick=()=>{ $("coverDlg").close(); showAdd(false); drawSets(); openDrawer(); loadSets().then(drawSets).then(()=>setEdit(true)); };
$("hmFind").onsubmit=e=>{ e.preventDefault(); openFind($("hmQ").value.trim()); };
$("drawer").addEventListener("close",()=>{ if(atHome()) loadHome(); });

// "Where it goes in your binder" button in card details: a page icon, the spot, and › (opens the Pages view).
function setSpot(text){
  const b=$("dSpot"); b.replaceChildren();
  b.insertAdjacentHTML("afterbegin",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5.5C4.5 4 7.5 4 10 5.5v14c-2.5-1.5-5.5-1.5-8 0z"/><path d="M22 5.5c-2.5-1.5-5.5-1.5-8 0v14c2.5-1.5 5.5-1.5 8 0z"/></svg>');
  const t=document.createElement("span"); t.className="dspot-t"; t.textContent=text;
  const g=document.createElement("span"); g.className="dspot-go"; g.textContent="›"; g.setAttribute("aria-hidden","true");
  b.append(t,g); b.title="Show it on the Pages view"; b.setAttribute("aria-label","In your binder: "+text+". Show it on the Pages view");
}

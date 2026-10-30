// Start-up: runs last, once every other file has loaded.
// Part of the binder page: index.html loads app/*.js in order and they all share one scope.

// ---------- start ----------
// The installed app opens on a launch screen with its icon, shown for at least 1.5 s and until the first screen is ready.
const splashAt=Date.now();
function hideSplash(){
  const el=$("splash"); if(!el || el.dataset.out) return; el.dataset.out="1";
  setTimeout(()=>{ el.classList.add("out"); document.documentElement.classList.remove("splashing"); setTimeout(()=>el.remove(),400); }, Math.max(0,1500-(Date.now()-splashAt)));
}
setTimeout(hideSplash,3500);   // never longer than 3.5 s, even if the server is slow
header(); render();
setPrivate(isPrivate());
getSlots().then(loadSets).then(()=>{
  const want=location.hash.slice(1);
  if(want==="show" && state.sets.length){ openShow(false); return; }
  if(state.sets.some(s=>s.id===want)) return openSet(want);
  if(want) history.replaceState(null,"",location.pathname+location.search);
  if(!state.sets.length) return openSet(null);   // no binders yet: the binder screen explains how to add one
  showHome();
}).finally(()=>{ hideSplash(); vtReady=true; }).then(()=>fetch("api/refresh")).then(r=>r&&r.json()).then(j=>{ if(j&&j.running) showJob(j); }).catch(()=>{ $("sync").textContent="Can't reach "+srv()+"."; toast("Can't reach "+srv()+". "+offlineHint(), "Try again", ()=>location.reload()); });
window.addEventListener("popstate",()=>{   // phone back/forward between home and a binder
  const sid=location.hash.slice(1);
  if(!sid){ if(state.sets.length) showHome(); return; }
  if(sid==="show"){ openShow(false); return; }
  if(state.sets.some(s=>s.id===sid)){ showBinder(); if(sid!==state.sid) openSet(sid); }
  else if(state.sets.length){ history.replaceState(null,"",location.pathname+location.search); showHome(); }   // not one of your binders
});

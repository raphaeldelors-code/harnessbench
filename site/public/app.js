/* HarnessBench dashboard — data/site.json → two lanes on one page:
   harness (overview, runs, rig, calibration, methodology) and models (engine/quantization
   tuning rounds of the served model). One router, one chart house style, one data file. */
const PALETTE = ["#4cc9f0","#b57bff","#3ddc84","#ffb020","#ff5d8f","#57d0ff","#9d7bff",
                 "#6fe3a0","#ffd166","#ff8fa3","#8fd3ff"];
/* R/E/T/U outcome hues — one source of truth: instance-grid cells (drawGrid, translucent alphas)
   and the failure-mix stacked bars (same rgb, alpha 1). Letters order = bottom→top stack order. */
const OKEYS = ["R","E","T","U"];
const OLAB = {R:"resolved", E:"empty patch", T:"timeout", U:"ungraded"};
const ORGB = {R:"61,220,132", E:"255,93,93", T:"255,176,32", U:"130,160,255"};
const OALPHA = {R:.85, E:.5, T:.65, U:.14};
const fmt = n => n==null ? "–" : n.toLocaleString("en-US");
const fmt1 = n => n==null ? "–" : n.toFixed(1);
const fmt2 = n => n==null ? "–" : n.toFixed(2);
let DATA, lane = "harness", section = "overview", runIdx = 0, hidden = new Set(), charts = {};
let modelIdx = 0, modelView = "overview", hiddenLegs = new Set(), sdNight = null;

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

function crossRun(){
  /* pseudo-run: best result of each harness across all real runs */
  const best = {};
  DATA.runs.forEach(r=>{
    Object.entries(r.harnesses).forEach(([h,x])=>{
      const pct = x.resolved / r.n_instances;
      if(!best[h] || pct > best[h].pct) best[h] = {pct, r, x};
    });
  });
  const harnesses = {};
  Object.entries(best).forEach(([h,b])=>{
    harnesses[h] = {...b.x, pct: 100*b.pct, src_run: b.r.id, n_inst: b.r.n_instances};
  });
  const insts = DATA.runs.reduce((a,r)=> r.n_instances>a.length? r.instances:a, []);
  return {id:"cross", date:"", model:[...new Set(DATA.runs.map(r=>r.model))].join(", "),
          n_instances: Math.max(...DATA.runs.map(r=>r.n_instances)),
          instances:insts, harnesses, windows:{}, mcnemar:{},
          versions:{note:"each cell = best run for that harness (see tooltips for the source run)"}};
}
const visible = () => harnessNames().filter(h => !hidden.has(h));
function harnessNames(){ return Object.keys(run().harnesses); }
function run(){ return DATA.runs[runIdx]; }
function color(h, names){ names = names || harnessNames(); return PALETTE[names.indexOf(h) % PALETTE.length]; }

/* ---------- exact two-sided McNemar ---------- */
function binom(n,k){ let r=1; for(let i=1;i<=k;i++) r=r*(n-i+1)/i; return r; }
function mcNemarP(a,b){ const n=a+b; if(!n) return 1;
  let s=0; for(let k=0;k<=Math.min(a,b);k++) s+=binom(n,k);
  return Math.min(1, 2*s/Math.pow(2,n)); }

/* ---------- lane + section routing ---------- */
function showSection(route){
  /* one router for both lanes. A route is a section name, or a pseudo-run deep link
     "runs/<id>" / "models/<id>" — the same mechanism the run tabs already used. */
  let name = route || "overview";
  modelView = "overview";                     // plain "#models" always lands on the lane overview
  if(name.startsWith("runs/")){
    const i = DATA.runs.findIndex(r=>r.id===name.slice(5));
    if(i>=0) runIdx = i;
    name = "runs";
  } else if(name.startsWith("models/")){
    const i = (DATA.model_runs||[]).findIndex(m=>m.id===name.slice(7));
    if(i>=0){ modelIdx = i; modelView = "run"; hiddenLegs.clear(); }
    /* leg filters are one round's view state: the leg names repeat across rounds (a/b/c…),
       so a filter carried over by a hash change would hide a leg the reader never hid.
       (The round tabs already clear it — this covers the deep-link/back-button path.) */
    name = "models";
  }
  if(!document.getElementById("sec-"+name)) name = "overview";   // unknown hash → safe default
  lane = name==="models" ? "models" : "harness";
  section = name;
  $$(".panel").forEach(p=>p.hidden = p.id !== "sec-"+name);
  $$("#secNav .tab").forEach(t=>t.classList.toggle("on", t.dataset.sec===name));
  $$("#laneNav .tab").forEach(t=>t.classList.toggle("on", t.dataset.lane===lane));
  $("#secNav").hidden = lane==="models";      // the model lane carries its own tabs in-panel
  render();
}
function render(){
  renderHero();
  if(section==="overview") renderOverview();
  if(section==="runs") renderRun();
  if(section==="models") renderModels();
  if(section==="rig") renderRig();
  if(section==="calibration") renderTuning();
  $("#foot").innerHTML=`Data regenerated ${DATA.generated} · harness runs keep a manifest + exact component versions under <code>runs/&lt;id&gt;/</code>, model rounds under <code>runs/m-&lt;id&gt;/</code> · repo: <a href="https://github.com/raphaeldelors-code/harnessbench">harnessbench</a>`;
}

/* ---------- chrome ---------- */
function renderTabs(){
  const t = $("#runTabs"); t.innerHTML="";
  DATA.runs.forEach((r,i)=>{
    const b=document.createElement("button"); b.className="tab"+(i===runIdx?" on":"");
    b.textContent = r.id.replace(/-strata-iq3s/,"");
    b.onclick=()=>{ runIdx=i; hidden.clear(); renderRun(); };
    t.appendChild(b);
  });
}
function renderChips(){
  const c=$("#chips"); c.innerHTML="";
  harnessNames().forEach(h=>{
    const el=document.createElement("span");
    el.className="chip"+(hidden.has(h)?" off":"");
    el.innerHTML=`<i style="background:${color(h)}"></i>${h}`;
    el.onclick=()=>{ hidden.has(h)?hidden.delete(h):hidden.add(h); renderRun(); };
    c.appendChild(el);
  });
  $("#chipAll").onclick=()=>{ hidden.clear(); renderRun(); };
}
function renderHero(){
  if(lane==="models") return renderModelHero();
  const cross = crossRun();
  const hs=Object.entries(cross.harnesses).map(([h,x])=>({h,v:x.pct})).sort((a,b)=>b.v-a.v);
  const nRuns=DATA.runs.length, nH=hs.length;
  const rigs=[...new Set(DATA.runs.map(r=>r.rig_id).filter(Boolean))].join(", ")||"bench-rig-01";
  $("#hero").innerHTML=`<div class="big">${nH} coding-agent harnesses · ${nRuns} runs · ${DATA.runs.map(r=>r.n_instances).join(" + ")} graded instances ·
    model <b>${[...new Set(DATA.runs.map(r=>r.model))].join(", ")}</b> on a single RTX 3090 <span class="dim">(${rigs})</span></div>
    <div class="champ"><span class="medal">🏆</span><b>${hs[0].h}</b> leads the board at
    <b>${hs[0].v.toFixed(0)}%</b> resolved (best cohort)</div>`;
}

/* ---------- models lane: model bench (engine / quantization tuning rounds) ----------
   A model round asks one question: did this engine setting make the served model faster?
   Legs are compared inside input-size cells; warm-up rows stay in the table only.
   Nothing here is a quality or cross-model claim — the metric is tok/s on one rig.
   Agentic showdown rounds (manifest `agentic`) ask a different question (see renderShowdown),
   so they get their own tab and never join a tuning chart, cell or median. */
const VGOOD = ["KEEP","CONFIRM-KEEP","PASS"], VBAD = ["UNDO","REVERT"], VPART = ["PARTIAL"];
const vclass = v => VGOOD.includes(v) ? "keep" : (VBAD.includes(v) ? "undo"
  : (VPART.includes(v) ? "partial" : "info"));      // PASS/PARTIAL grade a showdown score, no tuning verdict is in those lists
const vdot = v => ({keep:"#3ddc84", undo:"#ff5d5d", partial:"#ffb020", info:"#8a94a8"})[vclass(v)];
const pill = v => `<span class="pill ${vclass(v)}">${v}</span>`;
const isWarm = leg => leg.startsWith("warm");
const mrun = () => (DATA.model_runs||[])[modelIdx];
const shortId = id => id.replace(/^m-\d{4}-\d{2}-\d{2}-/,"");
const sdRuns = () => (DATA.model_runs||[]).filter(m=>m.agentic);
const SD_CHARTS = ["#sdResolved","#sdEff"];
const PF_CHARTS = ["#pfDecode","#pfEncode","#pfCache","#pfMTP"];
/* the artifact round a showdown card belongs to: id minus its date prefix and its model-slug
   suffix ("m-2026-11-14-run7-strata_iq3s" → "run7"); falls back to the whole short id */
const runLabel = m => { const s = shortId(m.id), slug = (m.model||{}).slug||"";
  return slug && s.endsWith("-"+slug) ? (s.slice(0, -slug.length-1) || s) : s; };
/* bench nights, newest first: the round's run label is the night key, dated by its newest round */
function sdNights(runs){
  const last = {};
  runs.forEach(m=>{ const k=runLabel(m); if(!last[k] || m.date>last[k]) last[k]=m.date; });
  return Object.keys(last).sort((a,b)=> last[b].localeCompare(last[a]) || a.localeCompare(b));
}
/* Agent-phase performance of the showdown rounds (manifest `agentic.perf`): how fast the served
   build was while mini-swe-agent drove it. Copied into the manifest from the round's own capture —
   nothing here is recomputed, and a field the capture did not record stays blank, never zero. */
const perfOf = m => (m.agentic||{}).perf || {};
/* chart label: night + slug without its "strata_" prefix ("…run4-strata_iq3s" → "run4 iq3s") */
const pfLabel = m => { const slug = (m.model||{}).slug||"";
  return [runLabel(m), slug.replace(/^strata_/,"")].filter(Boolean).join(" "); };
function pfRows(runs, key){
  return runs.filter(m=>perfOf(m)[key]!=null)
    .map(m=>({label:pfLabel(m), name:pfLabel(m), v:perfOf(m)[key], raw:m}))
    .sort((a,b)=>(b.v-a.v) || a.label.localeCompare(b.label));      // house style: descending value
}
/* No request count means the round was never swept as a window, so its medians are the round
   write-up's prose figures — the charts have to say that instead of implying a measured window. */
const pfProse = m => perfOf(m).requests==null;
const pfProseTip = m => pfProse(m) ? " · quoted median from the round write-up, not a window statistic" : "";
function medianOf(vs){
  const v = vs.filter(x=>x!=null).sort((a,b)=>a-b);
  if(!v.length) return null;
  const m = v.length>>1;
  return v.length%2 ? v[m] : (v[m-1]+v[m])/2;
}
function medOf(m, leg, key){ return medianOf(m.cells.map(c=>c.legs[leg] ? c.legs[leg][key] : null)); }

function renderModelHero(){
  const mrs = DATA.model_runs||[], models = DATA.models||[];
  const nRows = mrs.reduce((a,m)=>a+m.n_rows,0), nWarm = mrs.reduce((a,m)=>a+m.n_warm,0);
  const nSd = mrs.filter(m=>m.agentic).length, nTune = mrs.length-nSd;
  const gpu = (DATA.hardware||{}).gpu?.model || "local GPU";
  const rigs = [...new Set(mrs.map(m=>m.hardware).filter(Boolean))].join(", ")||"bench-rig-01";
  const served = models.map(m=>`${m.slug}${m.quant?" · "+m.quant:""}`).join(", ");
  const tune = mrs.filter(m=>!m.agentic);
  const nKeep = tune.filter(m=>vclass(m.verdict)==="keep").length;   // "kept" is a tuning decision: a showdown PASS kept nothing
  const sd = mrs.filter(m=>m.agentic);
  const nPass = sd.filter(m=>vclass(m.verdict)==="keep").length;     // PASS grade = 3+ resolved
  const scored = models.filter(m=>m.best_resolved!=null).sort((a,b)=>b.best_resolved-a.best_resolved);
  const best = scored[0];
  $("#hero").innerHTML=`<div class="big">${nTune} tuning rounds · ${nSd} agentic showdown rounds · ${nRows} captured rows (${nWarm} warm-up, table only) · ${models.length} served model${models.length===1?"":"s"}
    <b>${served||"—"}</b> on a single ${gpu} <span class="dim">(${rigs})</span></div>
    <div class="champ"><span class="medal">⚙</span>${tune.map(m=>`<span class="pill ${vclass(m.verdict)}">${m.verdict}</span>`).join(" ")}
    <span class="dim">tuning rounds are speed only — no task-quality claim</span>${nKeep?` · <b>${nKeep}</b> kept`:``}</div>
    ${nSd?`<div class="champ"><span class="medal">⚔</span>showdown best: <b>${best.slug}</b> <b>${(best.best_resolved*100).toFixed(0)}%</b> resolved
      <span class="dim">(${scored.length} served model${scored.length===1?"":"s"} scored over ${nSd} rounds, <b>${nPass}</b> at 3+ resolved — Showdown tab)</span></div>`:""}`;
}
function renderModels(){
  const mrs = DATA.model_runs||[];
  if(modelIdx>=mrs.length) modelIdx = 0;
  /* the showdown and performance views are both about agentic rounds — without any, they have
     nothing to show, so the lane falls back to its tuning overview */
  if((modelView==="showdown" || modelView==="perf") && !mrs.some(m=>m.agentic)) modelView = "overview";
  renderModelTabs(); renderModelSub();
  const inRun = modelView==="run" && mrs.length>0;
  $("#modelBanner").hidden = !inRun;
  $("#modelOverview").hidden = modelView!=="overview";
  $("#modelShowdown").hidden = modelView!=="showdown";
  $("#modelPerf").hidden = modelView!=="perf";
  $("#modelRunView").hidden = !inRun;
  if(modelView==="showdown") renderShowdown();
  else if(modelView==="perf") renderModelPerf();
  else if(inRun) renderModelRun(mrun());
  else renderModelOverview();
}
function renderModelSub(){
  /* the lane's three views, in chip style like the leg chips. Buttons, not spans: these switch
     what is on screen, so they have to be tabbable and operable from the keyboard. */
  const c = $("#modelSub"); c.innerHTML="";
  const sd = sdRuns().length;
  [["overview","Overview"],["showdown","Showdown"],["perf","Performance"]].forEach(([view,label])=>{
    if(view!=="overview" && !sd) return;
    const on = modelView===view;
    const b = document.createElement("button");
    b.type="button"; b.className="chip"+(on?" on":"");
    b.setAttribute("aria-pressed", on?"true":"false");
    b.textContent = label;
    b.onclick=()=>{ modelView=view; render(); };
    c.appendChild(b);
  });
}
function renderModelTabs(){
  /* pseudo-run tabs, exactly like #runTabs: buttons switch state, no hash churn. The row lists the
     rounds only — which of the lane's three views is open belongs to the submenu above it, so the
     tabs no longer carry an overview/showdown pair that would fight it for the same state. */
  const t = $("#modelTabs"); t.innerHTML="";
  const mk=(label,on,fn,dot)=>{
    const b=document.createElement("button"); b.className="tab"+(on?" on":"");
    b.innerHTML=(dot?`<i class="dot" style="background:${dot}"></i>`:"")+label;
    b.onclick=fn; t.appendChild(b);
  };
  (DATA.model_runs||[]).forEach((m,i)=>mk(shortId(m.id), modelView==="run"&&i===modelIdx,
    ()=>{ modelIdx=i; modelView="run"; hiddenLegs.clear(); render(); }, vdot(m.verdict)));
}
function renderModelRun(m){
  const c = vclass(m.verdict);
  const b = $("#modelBanner"); b.className = "banner "+c;
  const model = [m.model.slug||m.id, m.model.quant, m.model.family].filter(Boolean).join(" · ");
  const ag = !!m.agentic;
  const meta = [m.date, m.hardware,
                ag ? `${m.agentic.resolved}/${m.agentic.n_instances} resolved`
                   : `${m.n_rows} rows${m.n_warm?` (${m.n_warm} warm-up, table only)`:""}`,
                ag ? `${m.agentic.steps_cap??"—"}-step cap` : `legs ${m.legs.join(" / ")||"—"}`].join(" · ");
  b.innerHTML=`${pill(m.verdict)}
    <div><h2>${m.title}</h2>
      <div class="meta">${model} · ${m.engine||"engine unrecorded"}</div>
      <div class="meta">${meta}</div>
      ${m.notes?`<div class="meta">${m.notes}</div>`:""}</div>`;
  SD_CHARTS.forEach(dropChart); PF_CHARTS.forEach(dropChart);
  if(ag){
    /* a showdown round has no tuning legs: its score is the outcome, its only row is telemetry
       the agent work produced — so the leg charts would draw empty axes over a real result. */
    ["#mDecode","#mPrefill"].forEach(id=>{ dropChart(id); $(id).closest(".card").hidden = true; });
    $("#modelFilters").hidden = true;
    const note = $("#cellNote");
    note.hidden = false;
    note.textContent = "This round is an agentic showdown, not a tuning ladder: it holds one telemetry row for the whole agent phase, so no prompt-size cells exist — the score and the per-instance grid below are the result.";
    const card = $("#sdRunCard"); card.hidden = false; card.innerHTML = sdCard(m);
    modelRows(m);
    return;
  }
  ["#mDecode","#mPrefill"].forEach(id=>$(id).closest(".card").hidden = false);
  $("#modelFilters").hidden = false;
  const card = $("#sdRunCard"); card.hidden = true; card.innerHTML = "";
  renderLegChips(m);
  modelNote(m);
  cellChart(m, "#mDecode", "tps", "output tok/s", "output tok/s");
  cellChart(m, "#mPrefill", "pp", "input tok/s", "input tok/s");
  modelRows(m);
}
function modelNote(m){
  /* Say out loud when a round's cells do not actually match the legs up on prompt length —
     the charts would otherwise imply a comparison the capture does not contain. */
  const note = $("#cellNote");
  const cells = m.cells || [];
  if(cells.some(c=>c.in_tok==null)){
    note.hidden = false;
    note.textContent = "Some rows of this round recorded no input size, so their bars share one unlabelled cell and are not matched on prompt length — read the raw rows below before comparing legs.";
    return;
  }
  const matched = cells.some(c=>m.legs.filter(l=>c.legs[l] && c.legs[l].tps!=null).length > 1);
  note.hidden = matched;
  if(!matched) note.textContent = "In this round each input size was measured by a single leg, so no cell holds two legs side by side — the round-level medians in the verdict table are the only comparison it supports.";
}
function renderLegChips(m){
  /* leg chips are this lane's legend (house style keeps chart legends off) — colors come
     from the shared PALETTE keyed on the run's own leg order */
  const c = $("#modelLegs"); c.innerHTML="";
  m.legs.forEach(l=>{
    const el=document.createElement("span");
    el.className="chip"+(hiddenLegs.has(l)?" off":"");
    el.innerHTML=`<i style="background:${color(l,m.legs)}"></i>${l}`;
    el.onclick=()=>{ hiddenLegs.has(l)?hiddenLegs.delete(l):hiddenLegs.add(l); renderModelRun(m); };
    c.appendChild(el);
  });
  $("#legAll").onclick=()=>{ hiddenLegs.clear(); renderModelRun(m); };
}
function cellChart(m, id, key, yTitle, unit){
  /* x = input-size cell (the ladder is the measurement design: same prompt size, legs side by
     side), so the house-style descending sort governs the leg order, not the x axis. */
  const legs = m.legs.filter(l=>!hiddenLegs.has(l)).sort((a,b)=>(medOf(m,b,key)??-Infinity)-(medOf(m,a,key)??-Infinity));
  const cells = m.cells.filter(c=>legs.some(l=>c.legs[l] && c.legs[l][key]!=null));
  if(!legs.length || !cells.length){ dropChart(id); return; }
  const narrow = narrowBox(id);
  mkChart(id,{type:"bar",
    data:{labels:cells.map(c=>lab(c.cell,narrow)),
      datasets:legs.map(l=>({label:l,                                   // label feeds the tooltip
        data:cells.map(c=>c.legs[l] ? c.legs[l][key] : null),           // null → Chart.js gap
        backgroundColor:color(l,m.legs), borderRadius:8, maxBarThickness:46}))},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:cn=>{
        const e = cells[cn.dataIndex].legs[cn.dataset.label];
        if(!e || cn.parsed.y==null) return "";                 // cell not measured for this leg
        return `${cn.parsed.y.toFixed(1)} ${unit} · ${e.n} rep${e.n>1?"s":""} in this cell`;}}}},
      scales:scaled(narrow,yTitle)}});
}
function modelRows(m){
  const head=["leg","tag","input tok","output tok","prefill tok/s","decode tok/s","draft","draft_acc"];
  let html="<table><thead><tr>"+head.map(h=>`<th>${h}</th>`).join("")+"</tr></thead><tbody>";
  m.rows.forEach(r=>{
    const cells=[r.leg||"—", r.tag||"—", fmt(r.in_tok), fmt(r.out_tok), fmt1(r.pp), fmt1(r.tps),
                 fmt(r.draft), fmt(r.draft_acc)];
    html+=`<tr${isWarm(r.leg||"")?' class="dim"':""}>`+cells.map(v=>`<td>${v}</td>`).join("")+"</tr>";
  });
  $("#modelRows").innerHTML=html+"</tbody></table>";
}
function renderModelOverview(){
  const models = DATA.models||[];
  // the round-view charts belong to an open round; don't leave them attached to hidden canvases
  dropChart("#mDecode"); dropChart("#mPrefill");
  SD_CHARTS.forEach(dropChart); PF_CHARTS.forEach(dropChart);
  if(!models.length){
    dropChart("#mModelTps"); dropChart("#mModelPp");
    $("#modelVerdicts").innerHTML="<p class='dim'>No model runs published yet.</p>";
    return;
  }
  const names = models.map(m=>m.slug);   // colors keyed on slug, so the sort below can't repaint
  // house style: every bar chart sorts by its own descending value — build.py's models[] is
  // sorted by decode, which is a different order for the prefill chart, so sort per metric here
  const rowsFor = key => models.filter(m=>m[key]!=null)
    .map(m=>({label:m.slug,name:m.slug,v:m[key],raw:m})).sort((a,b)=>b.v-a.v);
  bars("#mModelTps", rowsFor("tps"),
    "output tok/s", (v,n,x)=>`${v.toFixed(1)} median output tok/s · ${x.raw.n_runs} round${x.raw.n_runs>1?"s":""}`+
      (x.raw.tps_range?` · spread ${fmt1(x.raw.tps_range[0])}–${fmt1(x.raw.tps_range[1])}`:""), names);
  bars("#mModelPp", rowsFor("pp"),
    "input tok/s", (v,n,x)=>`${v.toFixed(1)} median input tok/s · ${x.raw.n_runs} round${x.raw.n_runs>1?"s":""}`, names);
  modelVerdicts(models);
}
function modelVerdicts(models){
  let html="<table><thead><tr><th>model</th><th>round</th><th>date</th><th>verdict</th>"+
    "<th>decode tok/s</th><th>Δ vs other rounds</th><th>prefill tok/s</th><th>rows · legs</th></tr></thead><tbody>";
  models.forEach(m=>m.verdicts.forEach(v=>{
    // Δ against the sibling rounds' medians — the lane's own noise reference, not a p-value
    const base = medianOf(m.verdicts.filter(x=>x.id!==v.id).map(x=>x.tps));
    let d='<span class="dim">—</span>';
    if(v.tps!=null && base!=null){
      const dv = v.tps-base;
      d=`<span class="${dv>0?"up":(dv<0?"down":"dim")}">${dv>0?"+":""}${dv.toFixed(1)}</span>`;
    }
    html+=`<tr><td>${m.slug}</td><td>${shortId(v.id)}${v.agentic?` <span class="pill info">showdown</span>`:""}</td><td>${v.date}</td><td>${pill(v.verdict)}</td>`+
      `<td>${fmt1(v.tps)}</td><td>${d}</td><td>${fmt1(v.pp)}</td>`+
      `<td class="dim">${v.n_rows} · ${v.legs.join("/")||"—"}</td></tr>`;
  }));
  $("#modelVerdicts").innerHTML=html+"</tbody></table>";
}

/* ---------- models lane: agentic showdown rounds ----------
   One round = mini-swe-agent run once over the sb10 set on one served build, graded by the
   official SWE-bench eval container (schemas/modelrun.schema.json → `agentic`). Score and
   efficiency here; the tuning medians above never see these rounds (build.py is_agent).
   Outcome hues are this section's own: green resolved / amber unresolved / grey empty. */
const SDCELL = {resolved:["r","resolved"], unresolved:["u","unresolved — patch submitted, eval failed it"],
                empty:["e","empty — step cap hit, no patch submitted"]};
function renderShowdown(){
  dropChart("#mDecode"); dropChart("#mPrefill"); PF_CHARTS.forEach(dropChart);
  const runs = sdRuns();
  if(!runs.length){
    SD_CHARTS.forEach(dropChart);
    $("#sdCards").innerHTML = "<p class='dim'>No agentic showdown rounds published.</p>";
    return;
  }
  const nights = sdNights(runs);
  if(!nights.includes(sdNight)) sdNight = nights[0];   // default: the newest night (final protocol)
  renderSdNights(runs, nights);
  const named = runs.filter(m=>runLabel(m)===sdNight);
  const note = $("#sdNightNote");
  note.hidden = nights.length<2;
  note.textContent = nights.length<2 ? ""
    : `Cards below are the ${named.length} ${sdNight} rounds of ${runs.length} in total. The two bars above score every bench night together, so they do not move when the chip changes.`;
  const names = runs.map(m=>shortId(m.id));     // one PALETTE hue per round, like every bars() caller
  const desc = (a,b) => (b.v-a.v) || a.label.localeCompare(b.label);
  const rows = runs.map(m=>({label:shortId(m.id), name:shortId(m.id), v:m.agentic.resolved, raw:m}));
  bars("#sdResolved", rows.slice().sort(desc), "resolved instances",
    (v,n,x)=>{ const a=x.raw.agentic;
      return `${v} of ${a.n_instances} resolved · ${x.raw.date}` +
        (a.partial_credit!=null?` · partial credit ${fmt2(a.partial_credit)}`:"") +
        (a.steps_cap?` · ${a.steps_cap}-step cap`:""); }, names);
  const eff = runs.filter(m=>m.agentic.resolved_per_gpu_h!=null)
                  .map(m=>({label:shortId(m.id), name:shortId(m.id), v:m.agentic.resolved_per_gpu_h, raw:m}))
                  .sort(desc);
  $("#sdEffCard").hidden = !eff.length;
  bars("#sdEff", eff, "resolved / GPU-hour",
    (v,n,x)=>`${v.toFixed(2)} resolved / GPU-h · ${x.raw.agentic.resolved} resolved in ${fmt2(x.raw.agentic.gpu_hours)} GPU-h`, names);
  $("#sdCards").innerHTML = named.map(sdCard).join("");
}
function renderSdNights(runs, nights){
  /* second-level chips inside the showdown view: one bench night of round cards at a time.
     The counts sit in the labels because the nights do not hold equal numbers of rounds. */
  const c = $("#sdNights"); c.innerHTML="";
  nights.forEach(k=>{
    const n = runs.filter(m=>runLabel(m)===k).length;
    const on = k===sdNight;
    const b = document.createElement("button");
    b.type="button"; b.className="chip"+(on?" on":"");
    b.setAttribute("aria-pressed", on?"true":"false");
    b.textContent = `${k} (${n})`;
    b.onclick=()=>{ sdNight=k; renderShowdown(); };
    c.appendChild(b);
  });
}
function sdCard(m){
  const a = m.agentic, insts = a.per_instance||[], p = a.perf||{};
  const stat = (k,v)=>`<div class="vrow"><b>${k}</b><code>${v}</code></div>`;
  return `<div class="sd-card" title="${m.id}">
    <div class="sd-head">${pill(m.verdict)}<h3>${m.model.slug||m.id}</h3>
      <span class="dim">${runLabel(m)}</span></div>
    <div class="sd-meta">${m.date} · ${m.hardware} · ${a.steps_cap==null?"step cap unrecorded":`${a.steps_cap}-step cap`}
      · T=${a.temperature==null?"?":a.temperature} · ${m.engine||"engine unrecorded"}</div>
    <div class="sd-stats">
      ${stat("resolved", `${a.resolved}/${a.n_instances}`)}
      ${stat("partial credit", fmt2(a.partial_credit))}
      ${stat("GPU-hours", fmt2(a.gpu_hours))}
      ${stat("resolved / GPU-h", fmt2(a.resolved_per_gpu_h))}
      ${stat("empty", a.empty)}
    </div>
    <div class="sd-perf"><b>agent-phase perf</b><div class="sd-stats">
      ${stat("decode med", p.decode_med==null?"not recorded":`${fmt1(p.decode_med)} tok/s`)}
      ${stat("encode med", p.encode_med==null?"not recorded":`${fmt1(p.encode_med)} tok/s`)}
      ${stat("cache hit", p.cache_pct==null?"not recorded":`${fmt1(p.cache_pct)}%`)}
      ${stat("MTP acc", p.mtp_acc_pct==null?"not recorded":`${fmt1(p.mtp_acc_pct)}%`)}
      ${stat("requests", fmt(p.requests))}
      ${stat("longest out / cap", `${fmt(p.max_out)} / ${fmt(p.cap_tokens)}`)}
      ${p.vram_gib==null?"":stat("VRAM", `${fmt1(p.vram_gib)} GiB`)}
    </div></div>
    ${sdWarn(p)}
    <div class="sd-grid">${insts.map(sdCell).join("")}</div>
    ${sdFoot(m)}
  </div>`;
}
function sdWarn(p){
  /* a window that caught a non-200 did not run clean: say so on the card, not only in the data */
  if(!p.errors) return "";
  return `<div class="sd-warn">warning: ${p.errors} non-200 response${p.errors===1?"":"s"} inside the agent-phase window — the speed figures above sit next to a serving error</div>`;
}
function sdCell(p){
  const [cls,txt] = SDCELL[p.result]||["e",p.result||"unrecorded"];   // `txt` not `lab`: keeps the label-truncating lab() visible below
  const steps = p.steps==null ? "steps unrecorded" : `${p.steps} step${p.steps===1?"":"s"}`;
  const tip = `${p.instance} · ${txt} · ${steps} · credit ${p.credit==null?"–":fmt2(p.credit)}` +
    ` · ${p.patch==null?"patch unrecorded":(p.patch?"patch submitted":"no patch")}`;
  return `<div class="icell ${cls}" title="${tip}"><b>${(p.instance||"").split("__").pop()||p.instance||"—"}</b><span>${steps}</span></div>`;
}
function sdFoot(m){
  /* the round's single agent_phase row: token speed while the agent worked. Shown as what it
     is — a different measurement condition from a tuning leg, so never charted next to one. */
  const r = (m.rows||[]).find(x=>x.leg==="agent_phase");
  if(!r) return "";
  return `<div class="dim sd-foot">agent-phase telemetry: ${fmt1(r.pp)} encode · ${fmt1(r.tps)} decode tok/s — measured while the agent worked, not comparable to the tuning-leg charts</div>`;
}

/* ---------- models lane: agent-phase performance of the showdown rounds ----------
   How fast the served build was while mini-swe-agent drove it, straight out of each manifest's
   `agentic.perf` block — this function reads those fields and plots them, it derives nothing.
   House rules hold: bars() only, one hue per round-model across all four charts, descending order.
   A figure no round recorded gets a sentence, never an empty axis and never a zero. */
function renderModelPerf(){
  dropChart("#mDecode"); dropChart("#mPrefill"); SD_CHARTS.forEach(dropChart);
  const runs = sdRuns();
  const names = runs.map(pfLabel);
  const window = m => { const p = perfOf(m);
    return ` · ${fmt(p.requests)} requests · window ${p.phase_wall_s==null?"unrecorded":`${Math.round(p.phase_wall_s)} s`}`; };
  pfChart("#pfDecode", "#pfDecodeNote", pfRows(runs,"decode_med"), "output tok/s",
    (v,n,x)=>{ const p=perfOf(x.raw);
      return `${fmt1(v)} decode tok/s (median) · mean ${fmt1(p.decode_avg)}${window(x.raw)}${pfProseTip(x.raw)}`; }, names);
  pfChart("#pfEncode", "#pfEncodeNote", pfRows(runs,"encode_med"), "input tok/s",
    (v,n,x)=>{ const p=perfOf(x.raw);
      return `${fmt1(v)} encode tok/s (median) · mean ${fmt1(p.encode_avg)}${window(x.raw)}${pfProseTip(x.raw)}`; }, names);
  pfChart("#pfCache", "#pfCacheNote", pfRows(runs,"cache_pct"), "cache hit %",
    (v,n,x)=>{ const p=perfOf(x.raw);
      return `${fmt1(v)}% of prompt tokens served from KV cache · ${fmt(p.in_tokens)} prompt tokens counted${pfProseTip(x.raw)}`; }, names);
  pfChart("#pfMTP", "#pfMTPNote", pfRows(runs,"mtp_acc_pct"), "draft acceptance %",
    (v,n,x)=>`${fmt1(v)}% of MTP draft tokens accepted`, names);
  pfCap(runs);
}
function pfChart(id, noteSel, rows, yTitle, fmtTip, names){
  const box = $(id).closest(".chart-box"), note = $(noteSel);
  if(!rows.length){
    dropChart(id); box.hidden = true;
    note.hidden = false;
    note.textContent = "No published round recorded this figure, so there is nothing to chart. It stays absent from the manifests rather than being filled in here.";
    return;
  }
  box.hidden = false; note.hidden = true; note.textContent = "";
  bars(id, rows, yTitle, fmtTip, names);
}
const PF_COUNTERS = [[4096,"n_out_gt4096"],[8192,"n_out_gt8192"]];
function pfCap(runs){
  /* A list, not a canvas: the point of this card is reading one round against one ceiling, and an
     amber row is a round whose longest response landed exactly on its cap, a red one a round that
     got past it (a counter counts against a cap only when its threshold is at or above that cap). */
  let pinned=0, over=0, nCap=0, nMax=0;
  const rows = runs.map(m=>{
    const p = perfOf(m);
    if(p.cap_tokens!=null) nCap++;
    if(p.max_out!=null) nMax++;
    const at = p.cap_tokens!=null && p.max_out!=null && p.max_out===p.cap_tokens;
    const past = (p.cap_tokens!=null && PF_COUNTERS.some(([thr,k])=>thr>=p.cap_tokens && (p[k]||0)>0))
              || (p.cap_tokens!=null && p.max_out!=null && p.max_out>p.cap_tokens);
    if(at) pinned++;
    if(past) over++;
    const state = p.cap_tokens==null ? "cap unrecorded"
      : p.max_out==null ? "longest response unrecorded"
      : past ? "engine exceeded its cap"
      : at ? "engine pinned at the cap" : "stopped short of the cap";
    const cnt = PF_COUNTERS.map(([thr,k])=>`<span>responses &gt;${thr} <code>${fmt(p[k])}</code></span>`).join("");
    return `<div class="caprow${at?" pinned":""}${past?" over":""}" title="${m.id}">
      <b>${pfLabel(m)}</b><span>cap <code>${fmt(p.cap_tokens)}</code></span>
      <span>longest response <code>${fmt(p.max_out)}</code></span>${cnt}
      <span class="capstate">${state}</span></div>`;
  }).join("");
  let concl;
  if(!nCap) concl = "Not one published round records the max_tokens it was configured with, so this checkout cannot answer the cap question at all.";
  else if(!nMax) concl = `All ${nCap} rounds state the cap they ran under, and none of them records the longest response it produced, so the ceiling is on the table here while whether the engine reached it is not.`;
  else if(over) concl = `${over} of ${nMax} rounds produced a response longer than the cap they were configured with, so that cap is a request setting the engine can walk past rather than a hard limit.`;
  else if(pinned) concl = `${pinned} of ${nMax} rounds ended with their longest response exactly at the cap, so the engine was pinned there instead of finishing on its own.`;
  else concl = `None of the ${nMax} rounds came anywhere near its cap, so those answers stopped short of the ceiling by themselves.`;
  $("#pfCap").innerHTML = rows;
  const note = $("#pfCapNote"); note.hidden = false; note.textContent = concl;
}

/* ---------- overview: cross-run aggregation ---------- */
function renderOverview(){
  const cross = crossRun();
  const names = Object.keys(cross.harnesses);
  const rowBar = (id, valFn, fmtTip) =>
    bars(id, names.map(h=>({label:h,name:h,v:valFn(cross.harnesses[h])})).sort((a,b)=>b.v-a.v),
         null, (v,h)=>fmtTip(v)+" · "+h, names);
  rowBar("#oResolved", h=>h.pct, v=>v.toFixed(0)+"% resolved");
  rowBar("#oTok", h=>h.input_tokens/1e6, v=>v.toFixed(1)+"M input tokens");
  rowBar("#oThr", h=>h.resolved_per_gpu_h, v=>v.toFixed(2)+" resolved / GPU-h");
  rowBar("#oWall", h=>h.wall_s/60/h.n_inst, v=>Math.round(v)+" min wall per instance (best run)");
  let html="<table><thead><tr><th>harness</th>"+DATA.runs.map(r=>`<th>${r.id.replace(/-strata-iq3s/,"")}</th>`).join("")+"</tr></thead><tbody>";
  names.forEach(h=>{
    html+=`<tr><td><i class="dot" style="background:${color(h,names)}"></i>${h}</td>`;
    DATA.runs.forEach(r=>{
      const x=r.harnesses[h];
      if(!x){ html+="<td class='dim'>—</td>"; return; }
      const pct=100*x.resolved/r.n_instances, best=x.src_run===r.id;
      html+=`<td class="${best?"best":""}">${pct.toFixed(0)}%<span class="dim"> (${x.resolved}/${r.n_instances})</span></td>`;
    });
    html+="</tr>";
  });
  $("#cohortTable").innerHTML=html+"</tbody></table>";
}

/* ---------- run detail ---------- */
function renderRun(){
  renderTabs(); renderChips(); renderVersions();
  const r=run();
  barSorted("#cResolved", h=>h.resolved, "resolved / "+r.n_instances, v=>fmt(v)+" resolved");
  barSorted("#cThr", h=>h.resolved_per_gpu_h, null, v=>v.toFixed(2)+" resolved / GPU-h");
  barSorted("#cTok", h=>h.input_tokens/1e6, "M input tokens", v=>v.toFixed(1)+"M input tokens");
  barSorted("#cWall", h=>h.wall_s/60, "minutes", v=>Math.round(v)+" min wall");
  barSorted("#cCache", h=>h.cache_tokens/1e6, "M cached tokens", v=>v.toFixed(1)+"M cached input tokens");
  failMix();
  barSorted("#cCalls", h=>h.resolved ? h.calls/h.resolved : null, null,   // null → Chart.js gap (never divide by 0)
    (v,h)=>`${v.toFixed(1)} calls / resolved · ${fmt(run().harnesses[h].calls)} total`);
  const hasDist = visible().some(h=>(r.windows[h]||[]).length);
  $("#cDist").closest(".card").style.display = hasDist?"":"none";
  distChart(); drawMc(); drawGrid();
}
function renderVersions(){
  const v=run().versions||{}; const hv=v.harness_versions||{};
  const row=(k,val)=>`<div class="vrow"><b>${k}</b><code>${val}</code></div>`;
  let html="";
  html+=row("rig", run().rig_id || v.rig || "bench-rig-01");
  html+=row("model", `${v.model||run().model}<br>${v.model_args||""}`);
  html+=row("inference stack", `strata ${v.strata_terminal||"?"}<br>engine ${v.engine||"?"}<br>llama-swap ${v.llama_swap||"?"}`);
  html+=row("hardware", v.gpu||"?");
  html+=row("dataset", v.dataset||"?");
  html+=row("runner", `workers ${v.runner_workers||"?"} · timeout ${v.per_instance_timeout_s||"?"} s`);
  html+=row("comparability", `seed ${run().seed??"?"} · workers ${run().workers??"?"} · rig ${run().rig_id||v.rig||"bench-rig-01"}`);
  html+=row("harness versions", Object.entries(hv).map(([k,x])=>`${k} = ${x}`).join("<br>")||"?");
  $("#versions").innerHTML=html;
}

/* ---------- rig ---------- */
function renderRig(){
  const h=(DATA.hardware||{});
  const row=(k,val)=>`<div class="vrow"><b>${k}</b><code>${val}</code></div>`;
  let html="";
  html+=row("rig id", `${h.id||"bench-rig-01"}`);
  html+=row("machine", h.description||"");
  html+=row("cpu", `${h.cpu?.model||"?"} · ${h.cpu?.cores||"?"} logical cores`);
  html+=row("memory", `${h.memory?.size_gib||"?"} GiB<br>${h.memory?.channels||""}${h.memory?.speed_mt_s?` @ ${h.memory.speed_mt_s} MT/s`:""}`);
  html+=row("gpu", `${h.gpu?.model||"?"}<br>${h.gpu?.vram_gib||"?"} GiB VRAM<br>PCIe ${h.gpu?.pcie_generation||"?"} · ${h.gpu?.pcie_lanes||"?"}`);
  html+=row("board", h.board||"?");
  const st=h.storage||{};
  if(st.boot_data) html+=row("storage", `${st.boot_data.model}<br>${st.boot_data.capacity_gib} GiB · ${st.boot_data.link}<br>${st.boot_data.role}${st.secondary?`<br><span class="dim">+ ${st.secondary.model} (${st.secondary.capacity_gib} GiB, ${st.secondary.role})</span>`:""}`);
  html+=row("software", `${h.os||"?"}<br>${h.served_by||""}`);
  html+=row("updated", h.updated_utc||"?");
  const users=DATA.runs.filter(r=>(r.rig_id||"bench-rig-01")===(h.id||"bench-rig-01")).map(r=>r.id);
  html+=row("runs on this rig", users.join("<br>")||"—");
  $("#rigBody").innerHTML=html;
}

/* ---------- Chart.js helpers ---------- */
function mkChart(id, cfg){
  if(charts[id]) charts[id].destroy();
  charts[id]=new Chart($(id), cfg);
}
const GRID="rgba(130,160,255,.08)";
function scaled(narrow, yTitle){
  return {x:{ticks:{color:"#c6cede",font:{size:narrow?10:11.5},maxRotation:45,minRotation:45,autoSkip:false},grid:{display:false}},
          y:{beginAtZero:true,ticks:{color:"#8a94a8"},grid:{color:GRID},
             title:{display:!!yTitle&&!narrow,text:yTitle,color:"#8a94a8"}}};
}
const baseOpts = {
  responsive:true, maintainAspectRatio:false, animation:false,
  plugins:{legend:{display:false},
    tooltip:{backgroundColor:"#0d1119",borderColor:"rgba(130,160,255,.25)",borderWidth:1}},
};
function narrowBox(id){ const b=$(id).closest(".chart-box, .hm"); return b && b.clientWidth<620; }
function lab(n, narrow){ return narrow && n.length>9 ? n.slice(0,8)+"…" : n; }
function dropChart(id){ if(charts[id]){ charts[id].destroy(); charts[id]=null; } }
/* The house style in one place: full-opacity PALETTE fill keyed on the series name,
   borderRadius 8, one bar per row, labels shortened inside a narrow box. Callers sort
   rows by descending value (the x order may be a semantic ladder instead — see cellChart).
   fmtTip(value, name, row) → the caller owns the tooltip wording. */
function bars(id, rows, yTitle, fmtTip, names){
  if(!rows.length){ dropChart(id); return; }
  const narrow=narrowBox(id);
  mkChart(id,{type:"bar",data:{labels:rows.map(x=>lab(x.label,narrow)),
    datasets:[{data:rows.map(x=>x.v),backgroundColor:rows.map(x=>color(x.name,names)),
      borderRadius:8,maxBarThickness:46}]},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>fmtTip(c.parsed.y, rows[c.dataIndex].name, rows[c.dataIndex])}}},
      scales:scaled(narrow,yTitle)}});
}
function barSorted(id, valFn, yTitle, fmtTip){
  const r=run();
  bars(id, visible().map(h=>({label:h,name:h,v:valFn(r.harnesses[h])})).sort((a,b)=>b.v-a.v),
       yTitle, fmtTip, harnessNames());
}

/* failure mix: one stacked bar per harness, R/E/T/U counted out of per_instance (same hues as the grid) */
function failMix(){
  const r=run(), narrow=narrowBox("#cFail");
  const rows=visible().map(h=>{ const m={R:0,E:0,T:0,U:0};
    Object.values(r.harnesses[h].per_instance||{}).forEach(v=>{ if(m[v]!=null) m[v]++; });
    return {h, m}; }).sort((a,b)=>b.m.R-a.m.R);          // resolved desc — same ordering as every other bar
  if(!rows.length) return;
  const top=rows.map(x=>{ let t=-1; OKEYS.forEach((k,i)=>{ if(x.m[k]) t=i; }); return t; });
  const s=scaled(narrow);
  mkChart("#cFail",{type:"bar",data:{labels:rows.map(x=>lab(x.h,narrow)),
    datasets:OKEYS.map((k,i)=>({label:OLAB[k], data:rows.map(x=>x.m[k]),
      // borderRadius 8 only on the top-most visible segment of each stack (indexable per-bar array):
      // rounding every segment — or an interior joint — reads as a gap, and Chart.js stacked bars have
      // no "cap the stack" option, so the radius is keyed to the last non-empty dataset per bar.
      backgroundColor:`rgba(${ORGB[k]},1)`,
      borderRadius:rows.map((_,j)=>top[j]===i ? 8 : 0), maxBarThickness:46}))},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>`${c.parsed.y} ${c.dataset.label}`}}},
      scales:{x:{...s.x,stacked:true}, y:{...s.y,stacked:true}}}});
}

/* ---------- heatmaps on canvas (min cell width + horizontal scroll) ---------- */
const tip = document.createElement("div"); tip.className="hm-tip"; document.body.appendChild(tip);
function showTip(ev,html){ tip.innerHTML=html; tip.style.display="block";
  tip.style.left=Math.min(ev.clientX+12, innerWidth-340)+"px"; tip.style.top=Math.min(ev.clientY+12, innerHeight-90)+"px"; }

function truncText(g, text, maxW){
  if(g.measureText(text).width<=maxW) return text;
  let t=text;
  while(t.length>1 && g.measureText(t+"…").width>maxW) t=t.slice(0,-1);
  return t+"…";
}

function drawGrid(){
  const cv=$("#cGrid"), r=run(), hs=visible(), insts=r.instances;
  if(!hs.length||!insts.length) return;
  const dpr=devicePixelRatio||1;
  const wrap=cv.closest(".hm"), avail=wrap.clientWidth;
  const narrow = avail < 620;
  const L=narrow?92:150, minCW=24, minW=L+hs.length*minCW+10;
  const W=Math.max(avail, minW);
  const cw=Math.min(46,(W-L-10)/hs.length);
  // vertical column headers: measure first so the header band never overlaps cells
  const mt=document.createElement("canvas").getContext("2d");
  mt.font=(narrow?"10px":"10.5px")+" ui-sans-serif";
  const maxLW=Math.max(...hs.map(h=>mt.measureText(h).width));
  const T=Math.min(150, Math.max(56, maxLW+18));
  const rh=Math.max(10, Math.min(15,(620-T)/insts.length));
  const boxH=T+insts.length*rh+16;
  cv.style.width=W+"px"; cv.style.height=boxH+"px";
  cv.width=W*dpr; cv.height=boxH*dpr;
  const g=cv.getContext("2d"); g.setTransform(dpr,0,0,dpr,0,0);
  g.textBaseline="middle";
  hs.forEach((h,j)=>{ g.fillStyle=color(h); g.font=(narrow?"10px":"10.5px")+" ui-sans-serif"; g.save();
    g.translate(L+j*cw+cw/2, T-8); g.rotate(-Math.PI/2);
    g.textAlign="left"; g.fillText(h,0,0); g.restore(); });
  insts.forEach((ins,i)=>{ g.fillStyle="#8a94a8"; g.font=(narrow?"9px":"10px")+" ui-sans-serif"; g.textAlign="right";
    g.fillText(truncText(g,ins,L-12), L-8, T+i*rh+rh/2);
    hs.forEach((h,j)=>{
      const cell=(r.harnesses[h].per_instance||{})[ins]||"?";
      g.fillStyle=`rgba(${ORGB[cell]||ORGB.U},${OALPHA[cell]||.14})`;
      g.fillRect(L+j*cw+1.5, T+i*rh, cw-3, rh-2);
    });
  });
  cv.onmousemove=ev=>{ const b=cv.getBoundingClientRect();
    const x=ev.clientX-b.left,y=ev.clientY-b.top;
    const j=Math.floor((x-L)/cw), i=Math.floor((y-T)/rh);
    if(j>=0&&j<hs.length&&i>=0&&i<insts.length){
      const cell=(r.harnesses[hs[j]].per_instance||{})[insts[i]]||"?";
      showTip(ev,`<b>${insts[i]}</b><br>${hs[j]} → ${{R:"resolved ✅",E:"empty/failed patch ❌",T:"timeout ⏱",U:"ungraded ?"}[cell]||cell}`);
    } else tip.style.display="none"; };
  cv.onmouseleave=()=>tip.style.display="none";
}

function drawMc(){
  const cv=$("#cMc"), r=run(), hs=visible(), n=hs.length;
  if(!n) return;
  const dpr=devicePixelRatio||1;
  const wrap=cv.closest(".hm"), avail=wrap.clientWidth;
  const narrow = avail < 620;
  const L=narrow?96:130;
  const minCW=40, minW=L+n*minCW+10;
  const W=Math.max(avail, minW);
  const cw=Math.min(52,(W-L-10)/n);
  const mt=document.createElement("canvas").getContext("2d");
  mt.font=(narrow?"10px":"11px")+" ui-sans-serif";
  const maxLW=Math.max(...hs.map(h=>mt.measureText(h).width));
  const T=Math.min(150, Math.max(72, maxLW+18));
  const rh=Math.max(26, Math.min(42,(380-T)/n));
  const boxH=T+n*rh+10;
  cv.style.width=W+"px"; cv.style.height=boxH+"px";
  cv.width=W*dpr; cv.height=boxH*dpr;
  const g=cv.getContext("2d"); g.setTransform(dpr,0,0,dpr,0,0);
  g.font=(narrow?"10px":"11px")+" ui-sans-serif";
  hs.forEach((h,j)=>{ g.fillStyle=color(h); g.save();
    g.translate(L+j*cw+cw/2, T-8); g.rotate(-Math.PI/2);
    g.textAlign="left"; g.fillText(h,0,0); g.restore(); });
  hs.forEach((a,i)=>{ g.fillStyle="#8a94a8"; g.textAlign="right"; g.textBaseline="middle";
    g.fillText(truncText(g,a,L-12), L-8, T+i*rh+rh/2);
    hs.forEach((b,j)=>{
      if(j>=i) return;                            // lower triangle only: each pair once, read row-vs-column
      const key=a+"|"+b, k2=b+"|"+a;
      let p=1, win=0, ao=null, bo=null;
      const d=r.mcnemar[key]||r.mcnemar[k2];
      if(d){ const dd = r.mcnemar[key]?d:{a_only:d.b_only,b_only:d.a_only};
        ao=dd.a_only; bo=dd.b_only; p=mcNemarP(ao,bo); win=ao-bo; }
      const sig = p<0.05;                         // hue only for significant cells; grey otherwise
      g.fillStyle = sig ? (win>0?`rgba(61,220,132,0.85)`:`rgba(255,93,93,0.85)`) : `rgba(130,160,255,0.10)`;
      g.fillRect(L+j*cw+2, T+i*rh+2, cw-4, rh-4);
      g.textAlign="center"; g.fillStyle = "#e8ecf5";
      g.fillText(ao===null?"—":ao+"–"+bo, L+j*cw+cw/2, T+i*rh+rh/2-6);
      g.font="9px ui-sans-serif"; g.fillStyle = sig?"#0b1020":"#8a94a8";
      g.fillText(p<0.001?"p<.001":(p<0.01?"p<.01":(sig?"p="+p.toFixed(2):"ns")), L+j*cw+cw/2, T+i*rh+rh/2+8);
      g.font=(narrow?"10px":"11px")+" ui-sans-serif";
    });
  });
  cv.onmousemove=ev=>{ const b=cv.getBoundingClientRect();
    const x=ev.clientX-b.left,y=ev.clientY-b.top;
    const j=Math.floor((x-L)/cw), i=Math.floor((y-T)/rh);
    if(i>=0&&i<n&&j>=0&&j<n&&i!==j){
      const key=hs[i]+"|"+hs[j], k2=hs[j]+"|"+hs[i];
      let d=r.mcnemar[key]||(r.mcnemar[k2]&&{a_only:r.mcnemar[k2].b_only,b_only:r.mcnemar[k2].a_only});
      if(d){ const p=mcNemarP(d.a_only,d.b_only);
        showTip(ev,`<b>${hs[i]} vs ${hs[j]}</b><br>${hs[i]} won alone: ${d.a_only} · ${hs[j]} won alone: ${d.b_only}<br>exact McNemar p = ${p.toFixed(4)}`);
      } else tip.style.display="none";
    } else tip.style.display="none"; };
  cv.onmouseleave=()=>tip.style.display="none";
}

/* ---------- per-instance wall distribution (p10/median/p90 — same visual language) ---------- */
function q(sorted,f){ if(!sorted.length) return null; return sorted[Math.min(sorted.length-1, Math.floor(f*(sorted.length-1)))]; }
function distChart(){
  const r=run(), hs=visible();
  const rows=hs.map(h=>{ const w=(r.windows[h]||[]).map(x=>x.wall_s/60).filter(v=>v!=null).sort((a,b)=>a-b);
    return {h, n:w.length, lo:q(w,.1), med:q(w,.5), hi:q(w,.9)}; })
    .filter(x=>x.n>=5)          // p10/p90 needs ≥5 samples; tiny windows sets (mini: 1–4 incl. hangs) blow up the scale
    .sort((a,b)=>b.med-a.med);   // same descending-value ordering as every other bar chart
  if(!rows.length){ dropChart("#cDist"); return; }
  const dropped=hs.filter(h=>!rows.some(x=>x.h===h));
  const dn=$("#distNote");
  if(dn){ dn.hidden=!dropped.length; dn.textContent=dropped.length?`Excluded (fewer than 5 timed instances): ${dropped.join(", ")}`:""; }
  const narrow=narrowBox("#cDist");
  const candle={id:"candles",afterDatasetsDraw(c){
    const xs=c.scales.x, ys=c.scales.y, g=c.ctx;   // x = category, y = minutes (vertical bars house style)
    rows.forEach((x,i)=>{
      const xc=xs.getPixelForValue(i), y1=ys.getPixelForValue(x.lo), y2=ys.getPixelForValue(x.hi), ym=ys.getPixelForValue(x.med);
      // candle body (p10–p90)
      g.save(); g.fillStyle=color(x.h);
      g.beginPath(); g.roundRect(xc-7, Math.min(y1,y2), 14, Math.max(2,Math.abs(y2-y1)), 4); g.fill();
      // median tick: always wider than the body so it can never hide inside the candle
      g.strokeStyle="#f2f5fa"; g.lineWidth=2.5; g.lineCap="round";
      g.beginPath(); g.moveTo(xc-11, ym); g.lineTo(xc+11, ym); g.stroke();
      g.restore(); });
  }};
  mkChart("#cDist",{data:{labels:rows.map(x=>lab(x.h,narrow)),
    datasets:[
      {type:"bar",label:"p10–p90",data:rows.map(x=>[x.lo,x.hi]),
       backgroundColor:"rgba(0,0,0,0)",borderWidth:0,maxBarThickness:26}]},
    options:{...baseOpts, interaction:{mode:"index",intersect:false},
      plugins:{...baseOpts.plugins, legend:{display:false},
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>{const x=rows[c.dataIndex];
        return `p10 ${x.lo.toFixed(1)} · median ${x.med.toFixed(1)} · p90 ${x.hi.toFixed(1)} min`;}}}},
      scales:scaled(narrow,"minutes (per instance)")}, plugins:[candle]});
}

/* ---------- calibration ---------- */
let TUNING=null;
function renderTuning(){
  const t=TUNING;
  if(!t){ $("#tuneBody").innerHTML="<p class='dim'>No calibration record published.</p>"; return; }
  const d=t.decoding||{}, b=t.compare||{};
  let rows="";
  const row=(k,val)=>rows+=`<div class="vrow"><b>${k}</b><code>${val}</code></div>`;
  row("status", t.status||"?");
  row("baseline decode", (d.baseline_tps?d.baseline_tps.toFixed(1)+" tok/s":"?"));
  row("best candidate decode", (d.candidates||[]).map(c=>`${c.settings||c.knobs||"?"} → ${c.tps?c.tps.toFixed(1):"?"} tok/s (${c.gain_pct>=0?"+":""}${(c.gain_pct||0).toFixed(1)}%)`).slice(0,4).join("<br>")||"?");
  row("chosen", t.applied||"?");
  row("bench delta", Object.entries(b).map(([k,v])=>`${k}: ${typeof v=="number"?(v>=0?"+":"")+v.toFixed(1):JSON.stringify(v)}`).join("<br>")||"?");
  $("#tuneBody").innerHTML=rows;
}

/* ---------- boot ---------- */
fetch("data/site.json").then(r=>r.json()).then(d=>{ DATA=d;
  runIdx = DATA.runs.reduce((b,r,i,a)=> r.n_instances > a[b].n_instances ? i : b, 0);
  fetch("data/tuning.json").then(r=>r.ok?r.json():null).then(t=>{TUNING=t; if(section==="calibration") renderTuning();}).catch(()=>{});
  // deep links: #overview · #runs(/<id>) · #models(/<id>) · #rig · #calibration · #methodology
  const h=(location.hash||"").slice(1);
  const go=route=>{ location.hash=route; showSection(route); };
  $$("#secNav .tab").forEach(t=>t.onclick=e=>{ e.preventDefault(); go(t.dataset.sec); });
  $$("#laneNav .tab").forEach(t=>t.onclick=e=>{ e.preventDefault(); go((t.getAttribute("href")||"#overview").slice(1)); });
  window.addEventListener("hashchange",()=>{ const hh=(location.hash||"").slice(1); if(hh) showSection(hh); });
  let rz; window.addEventListener("resize",()=>{ clearTimeout(rz); rz=setTimeout(()=>{ render(); },250); });
  showSection(h||"overview");
});

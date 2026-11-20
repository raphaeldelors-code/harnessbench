/* HarnessBench dashboard — data/site.json → sections: overview, runs, rig, calibration */
const PALETTE = ["#4cc9f0","#b57bff","#3ddc84","#ffb020","#ff5d8f","#57d0ff","#9d7bff",
                 "#6fe3a0","#ffd166","#ff8fa3","#8fd3ff"];
const fmt = n => n==null ? "–" : n.toLocaleString("en-US");
let DATA, section = "overview", runIdx = 0, hidden = new Set(), charts = {};

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
function binom(n){ let r=1; for(let i=1;i<=n;i++) r=r*(n-i+1)/i; return r; }
function mcNemarP(a,b){ const n=a+b; if(!n) return 1;
  let s=0; for(let k=0;k<=Math.min(a,b);k++) s+=binom(n,k);
  return Math.min(1, 2*s/Math.pow(2,n)); }

/* ---------- section routing ---------- */
function showSection(name){
  section = name;
  $$(".panel").forEach(p=>p.hidden = p.id !== "sec-"+name);
  $$("#secNav .tab").forEach(t=>t.classList.toggle("on", t.dataset.sec===name));
  render();
}
function render(){
  renderHero();
  if(section==="overview") renderOverview();
  if(section==="runs") renderRun();
  if(section==="rig") renderRig();
  if(section==="calibration") renderTuning();
  $("#foot").innerHTML=`Data regenerated ${DATA.generated} · every run stores a manifest + exact component versions under <code>runs/&lt;id&gt;/</code> · repo: <a href="https://github.com/raphaeldelors-code/harnessbench">harnessbench</a>`;
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
  const cross = crossRun();
  const hs=Object.entries(cross.harnesses).map(([h,x])=>({h,v:x.pct})).sort((a,b)=>b.v-a.v);
  const nRuns=DATA.runs.length, nH=hs.length;
  const rigs=[...new Set(DATA.runs.map(r=>r.rig_id).filter(Boolean))].join(", ")||"bench-rig-01";
  $("#hero").innerHTML=`<div class="big">${nH} coding-agent harnesses · ${nRuns} runs · ${DATA.runs.map(r=>r.n_instances).join(" + ")} graded instances ·
    model <b>${[...new Set(DATA.runs.map(r=>r.model))].join(", ")}</b> on a single RTX 3090 <span class="dim">(${rigs})</span></div>
    <div class="champ"><span class="medal">🏆</span><b>${hs[0].h}</b> leads the board at
    <b>${hs[0].v.toFixed(0)}%</b> resolved (best cohort)</div>`;
}

/* ---------- overview: cross-run aggregation ---------- */
function renderOverview(){
  const cross = crossRun();
  const names = Object.keys(cross.harnesses);
  const box = $("#oResolved").closest(".chart-box");
  const narrow = box.clientWidth < 620;
  const lab = n => narrow && n.length > 9 ? n.slice(0,8)+"…" : n;
  const rowBar = (id, valFn, fmtTip) => {
    const rows = names.map(h=>({h, v: valFn(cross.harnesses[h])})).sort((a,b)=>b.v-a.v);
    mkChart(id,{type:"bar",data:{labels:rows.map(x=>lab(x.h)),
      datasets:[{data:rows.map(x=>x.v),backgroundColor:rows.map(x=>PALETTE[names.indexOf(x.h)%PALETTE.length]),
        borderRadius:8,maxBarThickness:46}]},
      options:{...baseOpts, plugins:{...baseOpts.plugins,
        tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>fmtTip(c.parsed.y)+" · "+rows[c.dataIndex].h}}},
        scales:scaled(narrow)}});
  };
  rowBar("#oResolved", h=>h.pct, v=>v.toFixed(0)+"% resolved");
  rowBar("#oTok", h=>h.input_tokens/1e6, v=>v.toFixed(1)+"M input tokens");
  rowBar("#oThr", h=>h.resolved_per_gpu_h, v=>v.toFixed(2)+" resolved / GPU-h");
  rowBar("#oWall", h=>h.wall_s/60/h.n_inst, v=>Math.round(v)+" min wall per instance (best run)");
  let html="<table><thead><tr><th>harness</th>"+DATA.runs.map(r=>`<th>${r.id.replace(/-strata-iq3s/,"")}</th>`).join("")+"</tr></thead><tbody>";
  names.forEach(h=>{
    html+=`<tr><td><i class="dot" style="background:${PALETTE[names.indexOf(h)%PALETTE.length]}"></i>${h}</td>`;
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
  barSorted("#cTokps", h=>h.output_tokens/h.wall_s, "tok/s", v=>v.toFixed(1)+" output tok/s");
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
function barSorted(id, valFn, yTitle, fmtTip){
  const r=run();
  const narrow=narrowBox(id);
  const rows=visible().map(h=>({h,v:valFn(r.harnesses[h])})).sort((a,b)=>b.v-a.v);
  if(!rows.length) return;
  mkChart(id,{type:"bar",data:{labels:rows.map(x=>lab(x.h,narrow)),
    datasets:[{data:rows.map(x=>x.v),backgroundColor:rows.map(x=>color(x.h)),
      borderRadius:8,maxBarThickness:46}]},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>fmtTip(c.parsed.y)}}},
      scales:scaled(narrow,yTitle)}});
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
      g.fillStyle = cell==="R" ? "rgba(61,220,132,.85)" : cell==="E" ? "rgba(255,93,93,.5)"
        : cell==="T" ? "rgba(255,176,32,.65)" : "rgba(130,160,255,.14)";
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
      const key=a+"|"+b, k2=b+"|"+a;
      let p=1, win=0;
      if(i!==j){ const d=r.mcnemar[key]||r.mcnemar[k2];
        if(d){ const dd = r.mcnemar[key]?d:{a_only:d.b_only,b_only:d.a_only};
          p=mcNemarP(dd.a_only,dd.b_only); win=dd.a_only-dd.b_only; } }
      const alpha = i===j?0.12:(p<0.05?0.85:(p<0.2?0.35:0.12));
      g.fillStyle = win>0?`rgba(61,220,132,${alpha})`:win<0?`rgba(255,93,93,${alpha})`:`rgba(130,160,255,${alpha})`;
      g.fillRect(L+j*cw+2, T+i*rh+2, cw-4, rh-4);
      g.fillStyle = p<0.5?"#e8ecf5":"#8a94a8"; g.textAlign="center";
      g.fillText(i===j?"—":(p<0.001?"<.001":p.toFixed(narrow?2:3)), L+j*cw+cw/2, T+i*rh+rh/2);
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
  if(!rows.length){ if(charts.cDist){charts.cDist.destroy(); charts.cDist=null;} return; }
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
  // deep links: #runs / #calibration / #runs/<run-id>
  const h=(location.hash||"").slice(1);
  let sec="overview";
  if(h.startsWith("runs/")){ const i=DATA.runs.findIndex(r=>r.id===h.slice(5)); if(i>=0) runIdx=i; sec="runs"; }
  else if(["runs","rig","calibration","methodology"].includes(h)) sec=h;
  $$("#secNav .tab").forEach(t=>t.onclick=e=>{ e.preventDefault(); location.hash=t.dataset.sec; showSection(t.dataset.sec); });
  window.addEventListener("hashchange",()=>{ const hh=(location.hash||"").slice(1);
    if(hh.startsWith("runs/")){ const i=DATA.runs.findIndex(r=>r.id===hh.slice(5)); if(i>=0){ runIdx=i; showSection("runs"); } }
    else if(hh) showSection(hh); });
  let rz; window.addEventListener("resize",()=>{ clearTimeout(rz); rz=setTimeout(()=>{ render(); },250); });
  showSection(sec);
});

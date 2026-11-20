/* HarnessBench dashboard — data from data/site.json, rendered with Chart.js + canvas heatmaps */
const PALETTE = ["#4cc9f0","#b57bff","#3ddc84","#ffb020","#ff5d8f","#57d0ff","#9d7bff",
                 "#6fe3a0","#ffd166","#ff8fa3","#8fd3ff"];
const fmt = n => n==null ? "–" : n.toLocaleString("en-US");
let DATA, runIdx = 1, hidden = new Set(), charts = {};

const $ = s => document.querySelector(s);
function crossRun(){
  /* pseudo-run: best result of each harness across all real runs */
  const best = {};
  DATA.runs.forEach(r=>{
    Object.entries(r.harnesses).forEach(([h,x])=>{
      const pct = x.resolved / r.n_instances;
      if(!best[h] || pct > best[h].pct) best[h] = {pct, r, x};
    });
  });
  const harnesses = {}, per = {};
  Object.entries(best).forEach(([h,b])=>{
    harnesses[h] = {...b.x, pct: 100*b.pct, src_run: b.r.id};
    per[h] = b.x.per_instance;
  });
  const insts = DATA.runs.reduce((a,r)=> r.n_instances>a.length? r.instances:a, []);
  return {id:"cross", date:"", model:[...new Set(DATA.runs.map(r=>r.model))].join(", "),
          n_instances:40, instances:insts, harnesses, windows:{}, mcnemar:{},
          versions:{note:"each cell = best run for that harness (see bar tooltips for the source run)"}};
}
const run = () => runIdx===-1 ? crossRun() : DATA.runs[runIdx];
const visible = () => harnessNames().filter(h => !hidden.has(h));

function harnessNames(){ return Object.keys(run().harnesses); }
function color(h){ return PALETTE[harnessNames().indexOf(h) % PALETTE.length]; }

/* ---------- exact two-sided McNemar ---------- */
function binom(n){ let r=1; for(let i=1;i<=n;i++) r=r*(n-i+1)/i; return r; }
function mcNemarP(a,b){ const n=a+b; if(!n) return 1;
  let s=0; for(let k=0;k<=Math.min(a,b);k++) s+=binom(n,k);
  return Math.min(1, 2*s/Math.pow(2,n)); }

/* ---------- chrome ---------- */
function renderTabs(){
  const t = $("#runTabs"); t.innerHTML="";
  const c=document.createElement("button"); c.className="tab"+(runIdx===-1?" on":"");
  c.textContent="∑ cross-run best"; c.onclick=()=>{runIdx=-1; hidden.clear(); renderAll();};
  t.appendChild(c);
  DATA.runs.forEach((r,i)=>{
    const b=document.createElement("button"); b.className="tab"+(i===runIdx?" on":"");
    b.textContent = r.id.replace(/-strata-iq3s/,"");
    b.onclick=()=>{ runIdx=i; hidden.clear(); renderAll(); };
    t.appendChild(b);
  });
}
function renderChips(){
  const c=$("#chips"); c.innerHTML="";
  harnessNames().forEach(h=>{
    const el=document.createElement("span");
    el.className="chip"+(hidden.has(h)?" off":"");
    el.innerHTML=`<i style="background:${color(h)}"></i>${h}`;
    el.onclick=()=>{ hidden.has(h)?hidden.delete(h):hidden.add(h); renderAll(); };
    c.appendChild(el);
  });
  $("#chipAll").onclick=()=>{ hidden.clear(); renderAll(); };
}
function renderHero(){
  const r=run();
  const cross=r.id==="cross";
  const hs=harnessNames().map(h=>({h,v:cross?r.harnesses[h].pct:100*r.harnesses[h].resolved/r.n_instances}))
          .sort((a,b)=>b.v-a.v);
  $("#hero").innerHTML=`<div class="big">${cross?"Best of every harness across all runs":"SWE-bench arena"} · <b>${fmt(r.n_instances)} Verified instances</b> ·
    model <b>${r.model}</b> on a single RTX 3090 · <b>${hs.length} harnesses</b></div>
    <div class="champ"><span class="medal">🏆</span><b>${hs[0].h}</b> leads at
    <b>${hs[0].v.toFixed(0)}%</b> resolved${cross?"":` (${hs[0].v>0?fmt(Math.round(hs[0].v*r.n_instances/100))+"/"+r.n_instances:"0/"+r.n_instances})`}</div>`;
}
function renderVersions(){
  const v=run().versions||{}; const hv=v.harness_versions||{};
  if(v.note){
    let h="";
    Object.entries(run().harnesses).forEach(([k,x])=>h+=row(k, `${x.pct.toFixed(0)}% best · from ${x.src_run}`));
    $("#versions").innerHTML=h; return;
  }
  let html="";
  const row=(k,val)=>`<div class="vrow"><b>${k}</b><code>${val}</code></div>`;
  html+=row("model", `${v.model||run().model}<br>${v.model_args||""}`);
  html+=row("inference stack", `strata ${v.strata_terminal||"?"}<br>engine ${v.engine||"?"}<br>llama-swap ${v.llama_swap||"?"}`);
  html+=row("hardware", v.gpu||"?");
  html+=row("dataset", v.dataset||"?");
  html+=row("runner", `workers ${v.runner_workers||"?"} · timeout ${v.per_instance_timeout_s||"?"} s`);
  html+=row("harness versions", Object.entries(hv).map(([k,x])=>`${k} = ${x}`).join("<br>")||"?");
  $("#versions").innerHTML=html;
}

/* ---------- Chart.js helpers ---------- */
function mkChart(id, cfg){
  if(charts[id]) charts[id].destroy();
  charts[id]=new Chart($(id), cfg);
}
const baseOpts = {
  responsive:true, maintainAspectRatio:false,
  animation:{duration:900, easing:"easeOutQuart"},
  plugins:{legend:{display:false},
    tooltip:{backgroundColor:"#0d1119",borderColor:"rgba(130,160,255,.25)",borderWidth:1}},
  scales:{x:{ticks:{color:"#c6cede",font:{size:11.5}},grid:{color:"rgba(130,160,255,.08)"}},
          y:{ticks:{color:"#8a94a8"},grid:{color:"rgba(130,160,255,.08)"}}},
};
function barSorted(id, valFn, yTitle, fmtTip){
  const r=run();
  const rows=visible().map(h=>({h,v:valFn(r.harnesses[h])})).sort((a,b)=>b.v-a.v);
  mkChart(id,{type:"bar",data:{labels:rows.map(x=>x.h),
    datasets:[{data:rows.map(x=>x.v),backgroundColor:rows.map(x=>color(x.h)),
      borderRadius:8,maxBarThickness:46}]},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>fmtTip?fmtTip(c.parsed.y):fmt(c.parsed.y)}}},
      scales:{...baseOpts.scales,y:{...baseOpts.scales.y,title:{display:!!yTitle,text:yTitle,color:"#8a94a8"}}}}});
}

/* ---------- heatmaps on canvas ---------- */
const tip = document.createElement("div"); tip.className="hm-tip"; document.body.appendChild(tip);
function showTip(ev,html){ tip.innerHTML=html; tip.style.display="block";
  tip.style.left=Math.min(ev.clientX+12, innerWidth-340)+"px"; tip.style.top=(ev.clientY+12)+"px"; }

function drawGrid(){
  const cv=$("#cGrid"), r=run(), hs=visible(), insts=r.instances;
  const dpr=devicePixelRatio||1;
  const L=150,T=30;
  const rh=Math.max(9, Math.min(12,(380-T-6)/insts.length));
  const boxH=T+insts.length*rh+16;
  cv.style.height=boxH+"px";
  cv.width=cv.clientWidth*dpr; cv.height=boxH*dpr;
  const g=cv.getContext("2d"); g.scale(dpr,dpr);
  const W=cv.clientWidth;
  const cw=Math.min(46,(W-L-10)/hs.length);
  g.textBaseline="middle";
  hs.forEach((h,j)=>{ g.fillStyle=color(h); g.font="10.5px ui-sans-serif"; g.save();
    g.translate(L+j*cw+cw/2, T-10); g.rotate(-Math.PI/6);
    g.textAlign="right"; g.fillText(h,0,0); g.restore(); });
  insts.forEach((ins,i)=>{ g.fillStyle="#8a94a8"; g.font="9px ui-sans-serif"; g.textAlign="right";
    g.fillText(ins.slice(0,22), L-8, T+i*rh+rh/2);
    hs.forEach((h,j)=>{
      const cell=(r.harnesses[h].per_instance||{})[ins]||"?";
      g.fillStyle = cell==="R" ? "rgba(61,220,132,.85)" : cell==="E" ? "rgba(255,93,93,.35)" : "rgba(130,160,255,.1)";
      g.fillRect(L+j*cw+1.5, T+i*rh, cw-3, rh-2);
    });
  });
  cv.onmousemove=ev=>{ const b=cv.getBoundingClientRect();
    const x=ev.clientX-b.left,y=ev.clientY-b.top;
    const j=Math.floor((x-L)/cw), i=Math.floor((y-T)/rh);
    if(j>=0&&j<hs.length&&i>=0&&i<insts.length){
      const cell=(r.harnesses[hs[j]].per_instance||{})[insts[i]]||"?";
      showTip(ev,`<b>${insts[i]}</b><br>${hs[j]} → ${cell==="R"?"resolved ✅":"failed ❌"}`);
    } else tip.style.display="none"; };
  cv.onmouseleave=()=>tip.style.display="none";
}

function drawMc(){
  const cv=$("#cMc"), r=run(), hs=visible(), n=hs.length;
  const dpr=devicePixelRatio||1;
  const L=130,T=64, boxH=T+n*42+10;
  cv.style.height=boxH+"px";
  cv.width=cv.clientWidth*dpr; cv.height=boxH*dpr;
  const g=cv.getContext("2d"); g.scale(dpr,dpr);
  const W=cv.clientWidth;
  const cw=Math.min(58,(W-L-10)/n), rh=Math.min(42,(boxH-T-6)/n);
  g.font="11px ui-sans-serif";
  hs.forEach((h,j)=>{ g.fillStyle=color(h); g.save();
    g.translate(L+j*cw+cw/2, T-10); g.rotate(-Math.PI/5);
    g.textAlign="right"; g.fillText(h,0,0); g.restore(); });
  hs.forEach((a,i)=>{ g.fillStyle="#8a94a8"; g.textAlign="right"; g.textBaseline="middle";
    g.fillText(a, L-8, T+i*rh+rh/2);
    hs.forEach((b,j)=>{
      const key=i+"|"+j, k2=j+"|"+i;
      let p=1, win=0, ab=null;
      if(i===j){ ab={a_only:0,b_only:0}; p=1; }
      else{ const d=r.mcnemar[key]||r.mcnemar[k2]; if(!d){}
        else{ const dd = r.mcnemar[key]?d:{a_only:d.b_only,b_only:d.a_only};
          ab=dd; p=mcNemarP(dd.a_only,dd.b_only); win=dd.a_only-dd.b_only; } }
      const alpha = i===j?0.12:(p<0.05?0.85:(p<0.2?0.35:0.12));
      g.fillStyle = win>0?`rgba(61,220,132,${alpha})`:win<0?`rgba(255,93,93,${alpha})`:`rgba(130,160,255,${alpha})`;
      g.fillRect(L+j*cw+2, T+i*rh+2, cw-4, rh-4);
      g.fillStyle = p<0.5?"#e8ecf5":"#8a94a8"; g.textAlign="center";
      g.fillText(i===j?"—":(p<0.001?"<.001":p.toFixed(3)), L+j*cw+cw/2, T+i*rh+rh/2);
    });
  });
  cv.onmousemove=ev=>{ const b=cv.getBoundingClientRect();
    const x=ev.clientX-b.left,y=ev.clientY-b.top;
    const j=Math.floor((x-L)/cw), i=Math.floor((y-T)/rh);
    if(i>=0&&i<n&&j>=0&&j<n&&i!==j){
      const key=i+"|"+j, k2=j+"|"+i;
      let d=r.mcnemar[key]||(r.mcnemar[k2]&&{a_only:r.mcnemar[k2].b_only,b_only:r.mcnemar[k2].a_only});
      if(d){ const p=mcNemarP(d.a_only,d.b_only);
        showTip(ev,`<b>${hs[i]} vs ${hs[j]}</b><br>${hs[i]} won alone: ${d.a_only} · ${hs[j]} won alone: ${d.b_only}<br>exact McNemar p = ${p.toFixed(4)}`);
      } else tip.style.display="none";
    } else tip.style.display="none"; };
  cv.onmouseleave=()=>tip.style.display="none";
}

/* ---------- per-instance wall distribution (p10/median/p90 floating bars) ---------- */
function q(sorted,f){ if(!sorted.length) return null; return sorted[Math.min(sorted.length-1, Math.floor(f*(sorted.length-1)))]; }
function distChart(){
  const r=run(), hs=visible();
  const rows=hs.map(h=>{ const w=(r.windows[h]||[]).map(x=>x.wall_s/60).filter(v=>v!=null).sort((a,b)=>a-b);
    return {h, lo:q(w,.1), med:q(w,.5), hi:q(w,.9)}; }).filter(x=>x.med!=null);
  mkChart("#cDist",{type:"bar",data:{labels:rows.map(x=>x.h),
    datasets:[{data:rows.map(x=>[x.lo,x.hi]),backgroundColor:rows.map(x=>color(x.h)+"55"),
      borderColor:rows.map(x=>color(x.h)),borderWidth:1.5,borderRadius:8,maxBarThickness:40}]},
    options:{...baseOpts, plugins:{...baseOpts.plugins,
      tooltip:{...baseOpts.plugins.tooltip,callbacks:{label:c=>{const x=rows[c.dataIndex];
        return `p10 ${x.lo.toFixed(1)} · median ${x.med.toFixed(1)} · p90 ${x.hi.toFixed(1)} min`;}}}}}});
}

/* ---------- master render ---------- */
function renderAll(){
  renderTabs(); renderChips(); renderHero(); renderVersions();
  barSorted("#cResolved", h=> run().id==="cross" ? h.pct : h.resolved,
    run().id==="cross" ? "resolved %" : "resolved / "+run().n_instances,
    v=> run().id==="cross" ? v.toFixed(0)+"% (best run)" : fmt(v));
  barSorted("#cThr", h=>h.resolved_per_gpu_h, null, v=>v.toFixed(2)+" resolved / GPU-h");
  barSorted("#cTok", h=>h.input_tokens/1e6, "M input tokens", v=>v.toFixed(1)+"M input tokens");
  barSorted("#cWall", h=>h.wall_s/60, "minutes", v=>Math.round(v)+" min wall");
  const cross=run().id==="cross";
  document.querySelector("#cDist").closest(".card").style.display = cross?"none":"";
  document.querySelector("#cMc").closest(".card").style.display = cross?"none":"";
  if(!cross){ distChart(); drawMc(); }
  drawGrid();
  $("#foot").innerHTML=`Data regenerated ${DATA.generated} · every run stores exact component versions + config under <code>runs/&lt;id&gt;/data/versions.json</code> · repo: <a href="https://github.com/raphaeldelors-code/harnessbench">harnessbench</a>`;
}

function renderTuning(t){
  if(!t) return;
  $("#tuneCard").style.display="";
  const d=t.decoding||{}, b=t.compare||{};
  let rows="";
  const row=(k,val)=>rows+=`<div class="vrow"><b>${k}</b><code>${val}</code></div>`;
  row("status", t.status||"?");
  row("baseline decode", (d.baseline_tps?d.baseline_tps.toFixed(1)+" tok/s":"?"));
  row("best candidate decode", (d.candidates||[]).map(c=>`${c.settings||c.knobs||"?"} → ${c.tps?c.tps.toFixed(1):"?"} tok/s (${c.gain_pct>=0?"+":""}${(c.gain_pct||0).toFixed(1)}%)`).slice(0,4).join("<br>")||"?");
  row("chosen", t.applied||"?");
  row("bench delta", Object.entries(b).map(([k,v])=>`${k}: ${typeof v=="number"?(v>=0?"+":"")+v.toFixed(1):JSON.stringify(v)}`).join("<br>")||"?");
  row("verified at", t.applied_utc||"?");
  $("#tuneBody").innerHTML=rows;
}
fetch("data/site.json").then(r=>r.json()).then(d=>{ DATA=d;
  fetch("data/tuning.json").then(r=>r.ok?r.json():null).then(t=>renderTuning(t)).catch(()=>{});
  if(location.hash){ const i=DATA.runs.findIndex(r=>r.id===location.hash.slice(1)); if(i>=0) runIdx=i; }
  renderAll(); });

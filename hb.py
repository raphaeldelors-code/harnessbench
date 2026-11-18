#!/usr/bin/env python3
"""hb.py — harnessbench: compare coding harnesses on SWE-bench Verified tasks.

Methodology mirrors the harness-leaderboard ethos:
  - one model fixed (llama-swap model id), N harnesses as the only variable
  - identical task text for every harness; harness-internal prompts untouched
  - every harness runs headless inside the OFFICIAL sweb.eval image for the
    instance, with a portable node runtime (/opt/hb) mounted read-only
  - graded OUTSIDE the harness with the official swebench grader (F2P/P2P)
  - cost/telemetry measured OUTSIDE the harness (llama-swap activity metrics)
  - contamination and cheating checks on every trial

Usage:
  hb.py prep                      clone instance repos, checkout base commits
  hb.py smoke --harness H         toy-repo fix test inside an eval container
  hb.py run --harness H [--inst X]  one harness over the instance set
  hb.py eval --harness H          official grading of out/<h>/preds.json
  hb.py report                    leaderboard-style table

Stdlib only. Run on the rig host with python3.
"""
import argparse, json, os, shlex, subprocess, sys, time, threading

BASE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(BASE, "work")
OUT = os.path.join(BASE, "out")
REPOS = os.path.join(BASE, "repos")
HB = "/home/rapha/hb"          # host base
CTR_HB = "/opt/hb"           # same dir mounted read-only inside containers
DATASET = os.environ.get("HB_DATASET") or os.path.join(BASE, "data", "instances", "sb40_new.json")
if not os.path.exists(DATASET):
    DATASET = "/home/rapha/agentswe/sb10_new.json"
VENV = "/home/rapha/agentswe/.venv/bin/python"
MODEL = os.environ.get("HB_MODEL", "strata_iq3s")
RESUME = {"on": False}
RUN_TIMEOUT = int(os.environ.get("HB_TIMEOUT", "2700"))
NODE_PATH = f"{CTR_HB}/node/bin:{CTR_HB}/npm/bin"

# ---- shared task text (identical for every harness) ------------------------
TASK_TEMPLATE = """\
You are working in a git repository at /testbed, checked out at the base commit \
of a bug report. Do not create branches and do not commit.

Bug report:
{problem_statement}

Investigate the repository, reproduce the problem, and fix it with a minimal \
change to the repository sources (do not edit installed copies of the package \
under site-packages). Run the relevant tests if practical. Leave your changes \
in the working tree when you are done."""

# ---- harness registry -------------------------------------------------------
HARNESSES = {
  "claude-code": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "printf %s \"$HB_TASK\" | claude --verbose --output-format=stream-json "
      "--permission-mode=bypassPermissions --print"
    ),
    "env": {
      "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080",
      "ANTHROPIC_API_KEY": "***",
      "ANTHROPIC_AUTH_TOKEN": "***",
      "IS_SANDBOX": "1",
      "ANTHROPIC_MODEL": MODEL,
      "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
      "DISABLE_AUTOUPDATER": "1",
    },
  },
  "pi": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "pi --print --mode json --provider rig --model rig/" + MODEL +
      " --thinking off -- \"$HB_TASK\""
    ),
    "env": {},
  },
  "deepseek-harness": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "dsh headless --json --permission-mode danger-full-access -- \"$HB_TASK\""
    ),
    "env": {"OPENAI_API_KEY": "***", "OPENAI_BASE_URL": "http://127.0.0.1:8080/v1",
            "DEEPSEEK_API_KEY": "***"},
  },
  "opencode": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "opencode run --model llamaswap/" + MODEL + " --format json --auto -- \"$HB_TASK\""
    ),
    "env": {},
  },
  "codex": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "printf %s \"$HB_TASK\" | codex exec --json --dangerously-bypass-approvals-and-sandbox"
    ),
    "env": {"OPENAI_API_KEY": "***"},
  },
  "qwen-code": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "qwen -y -p \"$HB_TASK\""
    ),
    "env": {"OPENAI_API_KEY": "***", "OPENAI_BASE_URL": "http://127.0.0.1:8080/v1",
            "OPENAI_MODEL": MODEL, "QWEN_CODE_SUPPRESS_YOLO_WARNING": "1"},
  },
  "kimi-code": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "kimi -p \"$HB_TASK\" --output-format stream-json"
    ),
    "env": {},
  },
  "grok": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "grok -p \"$HB_TASK\" --always-approve --output-format json --disable-web-search"
    ),
    "env": {},
  },
  "openclaw": {
    "version": "?",
    "homes": True,
    "cmd": lambda task: (
      "openclaw agent --local --json --timeout 2100 --session-id \"hb-$(date +%s%N)\" -m \"$HB_TASK\""
    ),
    "env": {},
  },
  "hermes-agent": {
    "version": "?",
    "homes": True,
    "image": "nousresearch/hermes-agent:latest",
    "wd": "/testbed",
    "cmd": lambda task: (
      '/opt/hermes/bin/hermes -z "$HB_TASK" --yolo'
    ),
    "env": {"HERMES_HOME": "/root", "HERMES_WRITE_SAFE_ROOT": "/testbed"},
  },
}


# mini-swe-agent runs from the host via its own swebench integration
MINI_CMD = [VENV, "-m", "minisweagent.run.benchmarks.swebench",
            "-o", None, "-m", "openai/" + MODEL, "-c", "swebench.yaml",
            "-c", "bench_local7.yaml", "--subset", "verified", "--split", "test",
            "-w", "1"]

def purge_contents(path):
    """Empty a dir whose contents may be root-owned (written by containers)."""
    if os.path.exists(path):
        sh(["docker", "run", "--rm", "-v", f"{path}:/x", "alpine",
            "sh", "-c", "rm -rf /x/* /x/.[!.]* 2>/dev/null; exit 0"])

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)

def load_instances(inst_set):
    data = json.load(open(DATASET))
    insts = {}
    for r in data:
        iid = r["instance_id"]
        if inst_set and iid not in inst_set:
            continue
        insts[iid] = r
    return insts

def eval_image(iid):
    return "swebench/sweb.eval.x86_64." + iid.replace("__", "_1776_") + ":latest"

# ---- prep -------------------------------------------------------------------
def cmd_prep(a):
    insts = load_instances(None)
    repos = sorted({i["repo"] for i in insts.values()})
    for repo in repos:
        name = repo.replace("/", "__")
        dst = os.path.join(REPOS, name)
        if not os.path.isdir(dst):
            print("clone", repo)
            r = sh(["git", "clone", "--filter=blob:none", f"https://github.com/{repo}.git", dst])
            if r.returncode: print(r.stderr[:400]); sys.exit(1)
        else:
            sh(["git", "fetch", "--all"], cwd=dst)
    # record which base commits we need
    for iid, r in insts.items():
        d = os.path.join(REPOS, r["repo"].replace("/", "__"))
        e = sh(["git", "cat-file", "-t", r["base_commit"]], cwd=d)
        if e.returncode:
            sh(["git", "fetch", "--all"], cwd=d)
    print("PREP_DONE", len(insts), "instances,", len(repos), "repos")

def make_workdir(iid):
    insts = load_instances({iid})
    r = insts[iid]
    d = os.path.join(REPOS, r["repo"].replace("/", "__"))
    wd = os.path.join(WORK, iid, "repo")
    if os.path.isdir(wd):
        sh(["git", "-C", wd, "checkout", "--", "."]); sh(["git", "-C", wd, "clean", "-fd"])
        sh(["git", "-C", wd, "checkout", "-q", r["base_commit"]])
    else:
        os.makedirs(os.path.dirname(wd), exist_ok=True)
        sh(["git", "worktree", "add", "--detach", wd, r["base_commit"]], cwd=d)
    return wd

# ---- run one instance with a container harness ------------------------------
def run_container_harness(harness, iid, tag):
    spec = HARNESSES[harness]
    insts = load_instances({iid})
    r = insts[iid]
    wd = make_workdir(iid)
    od = os.path.join(WORK, iid, "out", harness)
    os.makedirs(od, exist_ok=True)
    if spec.get("image"):
        for d in (wd, od):
            subprocess.run(["chmod", "-R", "a+rwX", d])
    if not RESUME.get("on", False):
        purge_contents(od); purge_contents(os.path.join(WORK, iid, "repo"))
    home = os.path.join(HB, "homes", harness)
    os.makedirs(home, exist_ok=True)
    env = dict(spec["env"]); env["HB_TASK"] = TASK_TEMPLATE.format(problem_statement=r["problem_statement"])
    envargs = []
    for k, v in env.items():
        envargs += ["-e", f"{k}={v}"]
    inner = (
        "git config --global --add safe.directory /testbed; "
        "mkdir -p /out; cd /testbed; "
        f"timeout {RUN_TIMEOUT} {spec['cmd'](None)} > /out/traj.log 2>/out/err.log; "
        "EC=$?; echo $EC > /out/ec; "
        "find /testbed -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; git add -A; git diff --cached --binary > /out/patch.diff"

    )
    docker = ["docker", "run", "--rm", "--network=host",
              "-v", f"{HB}:/opt/hb:ro",
              "-v", f"{wd}:/testbed",
              "-v", f"{od}:/out",
              "-v", f"{home}:/root",
              "-e", "HOME=/root",
              "-e", f"PATH={NODE_PATH}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
    if spec.get("wd"): docker += ["-w", spec["wd"]]
    docker += envargs
    img = spec.get("image") or eval_image(iid)
    if spec.get("image"):
        docker += ["--entrypoint", "bash", img, "-c", inner]
    else:
        docker += [img, "bash", "-c", inner]
    t0 = time.time()
    p = subprocess.run(docker, capture_output=True, text=True, timeout=RUN_TIMEOUT + 180)
    wall = time.time() - t0
    patch = ""
    try: patch = open(os.path.join(od, "patch.diff")).read()
    except FileNotFoundError: pass
    ec = open(os.path.join(od, "ec")).read().strip() if os.path.exists(os.path.join(od, "ec")) else "crash"
    return {"instance_id": iid, "harness": harness, "wall": round(wall, 1),
            "ec": ec, "patch_bytes": len(patch.encode()), "patch": patch}

def cmd_run(a):
    harness = a.harness
    od = os.path.join(OUT, harness)
    os.makedirs(od, exist_ok=True)
    insts = load_instances(a.inst or sorted(load_instances(None)))
    preds_path = os.path.join(od, "preds.json")
    preds = json.load(open(preds_path)) if os.path.exists(preds_path) and a.resume else {}
    wins = open(os.path.join(od, "windows.jsonl"), "a")
    predlock = threading.Lock()
    # telemetry poller (HTTP only)
    stop = threading.Event()
    def poll():
        while not stop.is_set():
            r = sh(["curl", "-s", "-m", "10", "http://127.0.0.1:8080/api/metrics/activity?limit=100"])
            with open(os.path.join(od, "activity.jsonl"), "a") as f:
                f.write(r.stdout + "\n")
            time.sleep(30)
    threading.Thread(target=poll, daemon=True).start()
    todo = [i for i in insts if not (a.resume and i in preds)]
    def one(iid):
        t0 = int(time.time())
        res = run_container_harness(harness, iid, harness)
        t1 = int(time.time())
        with predlock:
            wins.write(json.dumps({"harness": harness, "instance_id": iid, "t0": t0, "t1": t1}) + "\n"); wins.flush()
            preds[iid] = {"model_name": f"hb-{MODEL}", "model_name_or_path": "openai/" + MODEL, "instance_id": iid, "model_patch": res["patch"]}
            json.dump(preds, open(preds_path, "w"))
        print(f"done {iid} wall={res['wall']}s ec={res['ec']} patch={res['patch_bytes']}B", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, getattr(a, "workers", 1))) as ex:
        list(ex.map(one, todo))
    stop.set()

def cmd_eval(a):
    od = os.path.join(OUT, a.harness)
    cmd = [VENV, "-m", "swebench.harness.run_evaluation", "-d", DATASET, "-s", "test",
           "-p", os.path.join(od, "preds.json"), "-id", f"hb_{a.harness}",
           "--max_workers", "2", "-t", "900"]
    print(" ".join(cmd))
    subprocess.run(cmd)

def cmd_run_mini(a):
    """mini-swe-agent runs from the host (its own swebench integration)."""
    import subprocess as sp
    tag = "mini"
    od = os.path.join(OUT, tag)
    os.makedirs(od, exist_ok=True)
    sel = load_instances(a.inst or None)
    filt = "^(" + "|".join(sorted(sel)) + ")$"
    cmd = [VENV, "-m", "minisweagent.run.benchmarks.swebench",
           "-o", os.path.join("/home/rapha/agentswe", "out9_mini"),
           "-m", "openai/" + MODEL, "-c", "swebench.yaml", "-c", "bench_local7.yaml",
           "--subset", "verified", "--split", "test", "--filter", filt,
           "-w", str(max(1, getattr(a, "workers", 1)))]
    stop = threading.Event()
    def poll():
        while not stop.is_set():
            r = sh(["curl", "-s", "-m", "10", "http://127.0.0.1:8080/api/metrics/activity?limit=100"])
            with open(os.path.join(od, "activity.jsonl"), "a") as f:
                f.write(r.stdout + "\n")
            time.sleep(30)
    threading.Thread(target=poll, daemon=True).start()
    t0 = int(time.time())
    sp.run(cmd, cwd="/home/rapha/agentswe")
    t1 = int(time.time())
    open(os.path.join(od, "windows.jsonl"), "a").write(
        json.dumps({"harness": tag, "instance_id": "ALL", "t0": t0, "t1": t1}) + "\n")
    src = "/home/rapha/agentswe/out9_mini/preds.json"
    if os.path.exists(src):
        dstp = os.path.join(od, "preds.json")
        merged = json.load(open(dstp)) if os.path.exists(dstp) else {}
        merged.update(json.load(open(src)))
        json.dump(merged, open(dstp, "w"))
    stop.set()

def cmd_report(a):
    import glob
    rows = []
    for h in list(HARNESSES) + ["mini"]:
        od = os.path.join(OUT, h)
        if not os.path.isdir(od): continue
        resolved = empty = "?"
        for f in glob.glob(os.path.join(BASE, "..", f"openai__*.hb_{h}*.json")) + \
                 glob.glob(f"/home/rapha/agentswe/openai__*.hb_{h}*.json"):
            try:
                r = json.load(open(f))
                resolved = f"{len(r.get('resolved_ids', []))}/10"
                empty = str(len(r.get('empty_patch_ids', [])))
            except Exception: pass
        wall = 0.0
        try:
            for line in open(os.path.join(od, "windows.jsonl")):
                w = json.loads(line); wall += w["t1"] - w["t0"]
        except FileNotFoundError: pass
        calls = tin = tout = tcache = 0; seen = set()
        try:
            for line in open(os.path.join(od, "activity.jsonl")):
                try: snap = json.loads(line)
                except Exception: continue
                for row in snap.get("data", snap if isinstance(snap, list) else []):
                    rid = row.get("id")
                    if rid in seen: continue
                    seen.add(rid)
                    t = row.get("tokens", {})
                    tin += t.get("input_tokens", 0) or 0
                    tout += t.get("output_tokens", 0) or 0
                    tcache += t.get("cache_tokens", 0) or 0
                    calls += 1
        except FileNotFoundError: pass
        rows.append((h, resolved, empty, round(wall/3600, 2), calls, tin, tout, tcache))
    print("| harness | resolved | empty patches | wall h | api calls | input tok | output tok | cached tok |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        gh = r[3]
        rr = r[1]
        rgh = (f"{int(rr.split('/')[0])/gh:.2f}/GPUh" if gh and rr != "?" else "?")
        print("|", " | ".join(map(str, r[:8])), "| resolved_per_GPUh:", rgh)

def cmd_smoke(a):
    # toy repo inside one eval container; harness must fix a tiny python bug
    wd = os.path.join(WORK, "_smoke", a.harness)
    os.makedirs(wd, exist_ok=True)
    purge_contents(wd); purge_contents(os.path.join(WORK, "_smoke_out", a.harness))
    os.makedirs(os.path.join(WORK, "_smoke_out", a.harness), exist_ok=True)
    open(os.path.join(wd, "buggy.py"), "w").write("def add(a, b):\n    return a - b\n")
    open(os.path.join(wd, "test_buggy.py"), "w").write("from buggy import add\nassert add(2, 3) == 5\nprint('OK')\n")
    sh(["git", "init", "-q"], cwd=wd); sh(["git", "add", "-A"], cwd=wd)
    sh(["git", "-c", "user.email=hb@hb", "-c", "user.name=hb", "commit", "-qm", "init"], cwd=wd)
    spec = HARNESSES[a.harness]
    if spec.get("image"):
        for d in (wd, os.path.join(WORK, "_smoke_out", a.harness)):
            subprocess.run(["chmod", "-R", "a+rwX", d])
    task = "In /testbed there is a python file buggy.py with a broken add(). Fix it so that running 'python3 test_buggy.py' prints OK. Leave the fix in the working tree."
    inner = ("git config --global --add safe.directory /testbed; mkdir -p /out; cd /testbed; "
             f"timeout 300 {spec['cmd'](None)} > /out/traj.log 2>/out/err.log; EC=$?; echo $EC > /out/ec; "
             "python3 test_buggy.py > /out/smoke.txt 2>&1; "
             "find /testbed -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; git add -A; git diff --cached > /out/patch.diff; cat /out/smoke.txt")
    docker = ["docker", "run", "--rm", "--network=host",
              "-v", f"{HB}:/opt/hb:ro", "-v", f"{wd}:/testbed",
              "-v", f"{WORK}/_smoke_out/{a.harness}:/out",
              "-v", f"{HB}/homes/{a.harness}:/root", "-e", "HOME=/root",
              "-e", f"PATH={NODE_PATH}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
    for k, v in spec["env"].items(): docker += ["-e", f"{k}={v}"]
    docker += ["-e", f"HB_TASK={task}"]
    img = spec.get("image") or "swebench/sweb.eval.x86_64.psf_1776_requests-1142:latest"
    if spec.get("image"):
        docker += ["--entrypoint", "bash", img, "-c", inner]
    else:
        docker += [img, "bash", "-c", inner]
    p = subprocess.run(docker, capture_output=True, text=True, timeout=420)
    print("docker rc=", p.returncode, "| stdout:", p.stdout[-200:], "| stderr:", p.stderr[-200:])
    od = f"{WORK}/_smoke_out/{a.harness}"
    for f in ("ec", "patch.diff"):
        fp = os.path.join(od, f)
        if os.path.exists(fp): print(f, "=>", open(fp).read()[:300])
    tp = os.path.join(od, "err.log")
    if os.path.exists(tp): print("err.log tail:", open(tp).read()[-500:])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prep")
    p = sub.add_parser("smoke"); p.add_argument("--harness", required=True)
    p = sub.add_parser("run"); p.add_argument("--harness", required=True)
    p.add_argument("--inst", action="append"); p.add_argument("--resume", action="store_true")
    p.add_argument("--workers", type=int, default=2); p.add_argument("--dataset")
    p = sub.add_parser("eval"); p.add_argument("--harness", required=True)
    p.add_argument("--dataset")
    p = sub.add_parser("run-mini"); p.add_argument("--inst", action="append")
    p.add_argument("--workers", type=int, default=2); p.add_argument("--dataset")
    sub.add_parser("report")
    a = ap.parse_args()
    if getattr(a, "dataset", None): DATASET = a.dataset
    {"prep": cmd_prep, "smoke": cmd_smoke, "run": cmd_run, "eval": cmd_eval,
     "report": cmd_report, "run-mini": cmd_run_mini}[a.cmd](a)

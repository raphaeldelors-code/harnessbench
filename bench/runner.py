"""Run engine: prep repos, run one harness per instance inside official
sweb.eval containers, capture patches, telemetry and version stamps."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from bench import config as C
from bench import harnesses as H
from bench.task import TASK_TEMPLATE
from bench.util import read_json as _read_json
from bench.util import read_text as _read_text
from bench.util import write_json as _write_json

RESUME = {"on": False}


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def purge_contents(path: str):
    """Empty a dir whose contents may be root-owned (written by containers)."""
    if os.path.exists(path):
        sh(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{path}:/x",
                "alpine",
                "sh",
                "-c",
                "rm -rf /x/* /x/.[!.]* 2>/dev/null; exit 0",
            ]
        )


def load_instances(inst_set=None):
    data = _read_json(C.DATASET)
    return {r["instance_id"]: r for r in data if not inst_set or r["instance_id"] in inst_set}


def eval_image(iid: str) -> str:
    return "swebench/sweb.eval.x86_64." + iid.replace("__", "_1776_") + ":latest"


def cmd_prep(_a=None):
    insts = load_instances()
    repos = sorted({i["repo"] for i in insts.values()})
    os.makedirs(C.REPOS, exist_ok=True)
    for repo in repos:
        name = repo.replace("/", "__")
        dst = str(C.REPOS / name)
        if not os.path.isdir(dst):
            print("clone", repo)
            r = sh(["git", "clone", "--filter=blob:none", f"https://github.com/{repo}.git", dst])
            if r.returncode:
                print(r.stderr[:400])
                raise SystemExit(1)
        else:
            sh(["git", "fetch", "--all"], cwd=dst)
    for _iid, r in insts.items():
        d = str(C.REPOS / r["repo"].replace("/", "__"))
        if sh(["git", "cat-file", "-t", r["base_commit"]], cwd=d).returncode:
            sh(["git", "fetch", "--all"], cwd=d)
    print("PREP_DONE", len(insts), "instances,", len(repos), "repos")


def make_workdir(iid: str) -> str:
    r = load_instances({iid})[iid]
    d = str(C.REPOS / r["repo"].replace("/", "__"))
    wd = str(C.WORK / iid / "repo")
    if os.path.isdir(wd):
        sh(["git", "-C", wd, "checkout", "--", "."])
        sh(["git", "-C", wd, "clean", "-fd"])
        sh(["git", "-C", wd, "checkout", "-q", r["base_commit"]])
    else:
        os.makedirs(os.path.dirname(wd), exist_ok=True)
        sh(["git", "worktree", "add", "--detach", wd, r["base_commit"]], cwd=d)
    return wd


def _docker_base(wd: str, od: str, home: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network=host",
        "-v",
        f"{C.RUNTIME_DIR}:{C.CTR_RUNTIME}:ro",
        "-v",
        f"{wd}:/testbed",
        "-v",
        f"{od}:/out",
        "-v",
        f"{home}:/root",
        "-e",
        "HOME=/root",
        "-e",
        f"PATH={C.NODE_PATH}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    ]


def _docker_exec(docker: list[str], spec: dict, env: dict, img: str, inner: str, timeout: int):
    for k, v in env.items():
        docker += ["-e", f"{k}={v}"]
    if spec.get("wd"):
        docker += ["-w", spec["wd"]]
    if spec.get("image"):
        docker += ["--entrypoint", "bash", img, "-c", inner]
    else:
        docker += [img, "bash", "-c", inner]
    return docker, timeout


def run_container_harness(harness: str, iid: str) -> dict:
    spec = H.HARNESSES[harness]
    r = load_instances({iid})[iid]
    wd = make_workdir(iid)
    od = str(C.WORK / iid / "out" / harness)
    os.makedirs(od, exist_ok=True)
    if spec.get("image"):
        for d in (wd, od):
            subprocess.run(["chmod", "-R", "a+rwX", d])
    if not RESUME.get("on", False):
        purge_contents(od)
        purge_contents(str(C.WORK / iid / "repo"))
    home = str(C.RUNTIME_DIR / "homes" / harness)
    os.makedirs(home, exist_ok=True)
    env = dict(spec["env"])
    env["HB_TASK"] = TASK_TEMPLATE.format(problem_statement=r["problem_statement"])
    inner = (
        "git config --global --add safe.directory /testbed; "
        "mkdir -p /out; cd /testbed; "
        f"timeout {C.RUN_TIMEOUT} {spec['cmd'](None)} > /out/traj.log 2>/out/err.log; "
        "EC=$?; echo $EC > /out/ec; "
        "find /testbed -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; "
        "git add -A; git diff --cached --binary > /out/patch.diff"
    )
    docker = _docker_base(wd, od, home)
    docker, timeout = _docker_exec(
        docker, spec, env, spec.get("image") or eval_image(iid), inner, C.RUN_TIMEOUT
    )
    t0 = time.time()
    subprocess.run(docker, capture_output=True, text=True, timeout=timeout + 180)
    wall = time.time() - t0
    patch = ""
    with contextlib.suppress(FileNotFoundError):
        patch = _read_text(os.path.join(od, "patch.diff"))
    ec = _read_text(os.path.join(od, "ec")).strip() if os.path.exists(os.path.join(od, "ec")) else "crash"
    return {
        "instance_id": iid,
        "harness": harness,
        "wall": round(wall, 1),
        "ec": ec,
        "patch_bytes": len(patch.encode()),
        "patch": patch,
    }


def hardware_facts() -> dict:
    """Best-effort machine facts for the reproducibility record."""

    def probe(cmd):
        try:
            r = sh(["bash", "-c", cmd])
            return (r.stdout.strip().splitlines() or ["?"])[0]
        except Exception:
            return "?"

    bus = probe("nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader").lower().split(":")[-3:]
    bdf = ":".join(bus) if len(bus) == 2 else "?"
    return {
        "cpu": probe("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2-"),
        "cores": probe("nproc"),
        "ram_gib": probe("free -g | awk '/Mem/{print $2}'"),
        "gpu": probe("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"),
        "pcie_link": probe(
            f"sudo -n lspci -vv -s {bdf} 2>/dev/null | grep -m1 LnkSta | "
            "sed -E 's/.*Speed ([0-9.]+GT\\/s).*Width (x[0-9]+).*/Gen link \\1, \\2 lanes/'"
        ),
        "board": probe(
            "sudo -n dmidecode -t baseboard 2>/dev/null | grep -E 'Manufacturer|Product Name' "
            "| cut -d: -f2- | tr '\\n' ' ' | sed 's/  */ /g'"
        ),
        "os": probe("grep PRETTY_NAME /etc/os-release | cut -d'\"' -f2"),
    }


def write_versions(od: str, harness: str, workers: int):
    """Record the exact component versions + config of this run (reproducibility contract)."""
    import glob

    def probe(cmd):
        try:
            r = sh(["bash", "-c", cmd])
            return (r.stdout.strip().splitlines() or ["?"])[0]
        except Exception:
            return "?"

    engines = sorted(glob.glob(os.path.expanduser("~/.local/share/strata/components/engine/*")))
    hv = {h: H.HARNESSES[h].get("version", "?") for h in H.HARNESSES}
    v = {
        "model": C.MODEL,
        "model_args": os.environ.get("HB_MODEL_ARGS", "?"),
        "backend_url": C.BACKEND_URL,
        "strata_terminal": probe("strata --version 2>/dev/null || echo ?"),
        "engine": engines[-1].split("/")[-1] if engines else "?",
        "llama_swap": probe("llama-swap --version 2>/dev/null || echo ?"),
        "gpu": probe("nvidia-smi --query-gpu=name --format=csv,noheader"),
        "hardware": hardware_facts(),
        "dataset": os.path.basename(C.DATASET),
        "runner_workers": workers,
        "per_instance_timeout_s": C.RUN_TIMEOUT,
        "harness": harness,
        "harness_versions": hv,
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _write_json(os.path.join(od, "versions.json"), v)


def _telemetry_poller(od: str, stop: threading.Event):
    while not stop.is_set():
        r = sh(["curl", "-s", "-m", "10", C.BACKEND_URL + "/api/metrics/activity?limit=100"])
        with open(os.path.join(od, "activity.jsonl"), "a") as f:
            f.write(r.stdout + "\n")
        time.sleep(30)


def cmd_run(a):
    harness = a.harness
    od = str(C.OUT / harness)
    os.makedirs(od, exist_ok=True)
    write_versions(od, harness, getattr(a, "workers", 2))
    insts = load_instances(a.inst or sorted(load_instances(None)))
    preds_path = os.path.join(od, "preds.json")
    preds = _read_json(preds_path) if os.path.exists(preds_path) and a.resume else {}

    def _win(record: dict):
        with open(os.path.join(od, "windows.jsonl"), "a") as fh:
            fh.write(json.dumps(record) + "\n")

    predlock = threading.Lock()
    stop = threading.Event()
    threading.Thread(target=lambda: _telemetry_poller(od, stop), daemon=True).start()
    todo = [i for i in insts if not (a.resume and i in preds)]

    def one(iid):
        t0 = int(time.time())
        res = run_container_harness(harness, iid)
        t1 = int(time.time())
        with predlock:
            _win({"harness": harness, "instance_id": iid, "t0": t0, "t1": t1})
            preds[iid] = {
                "model_name": f"hb-{C.MODEL}",
                "model_name_or_path": "openai/" + C.MODEL,
                "instance_id": iid,
                "model_patch": res["patch"],
            }
            _write_json(preds_path, preds)
        print(f"done {iid} wall={res['wall']}s ec={res['ec']} patch={res['patch_bytes']}B", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, getattr(a, "workers", 1))) as ex:
        list(ex.map(one, todo))
    stop.set()


def cmd_smoke(a):
    """Toy-repo fix test inside one eval container — proves the wiring end-to-end."""
    wd = str(C.WORK / "_smoke" / a.harness)
    od = str(C.WORK / "_smoke_out" / a.harness)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(od, exist_ok=True)
    purge_contents(wd)
    purge_contents(od)
    with open(os.path.join(wd, "buggy.py"), "w") as fh:
        fh.write("def add(a, b):\n    return a - b\n")
    with open(os.path.join(wd, "test_buggy.py"), "w") as fh:
        fh.write("from buggy import add\nassert add(2, 3) == 5\nprint('OK')\n")
    sh(["git", "init", "-q"], cwd=wd)
    sh(["git", "add", "-A"], cwd=wd)
    sh(["git", "-c", "user.email=hb@hb", "-c", "user.name=hb", "commit", "-qm", "init"], cwd=wd)
    spec = H.HARNESSES[a.harness]
    if spec.get("image"):
        for d in (wd, od):
            subprocess.run(["chmod", "-R", "a+rwX", d])
    task = (
        "In /testbed there is a python file buggy.py with a broken add(). "
        "Fix it so that running 'python3 test_buggy.py' prints OK. Leave the fix in the working tree."
    )
    inner = (
        "git config --global --add safe.directory /testbed; mkdir -p /out; cd /testbed; "
        f"timeout 300 {spec['cmd'](None)} > /out/traj.log 2>/out/err.log; EC=$?; echo $EC > /out/ec; "
        "python3 test_buggy.py > /out/smoke.txt 2>&1; "
        "find /testbed -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; "
        "git add -A; git diff --cached > /out/patch.diff; cat /out/smoke.txt"
    )
    docker = _docker_base(wd, od, str(C.RUNTIME_DIR / "homes" / a.harness))
    env = dict(spec["env"])
    env["HB_TASK"] = task
    docker, timeout = _docker_exec(
        docker,
        spec,
        env,
        spec.get("image") or "swebench/sweb.eval.x86_64.psf_1776_requests-1142:latest",
        inner,
        420,
    )
    p = subprocess.run(docker, capture_output=True, text=True, timeout=timeout + 120)
    print("docker rc=", p.returncode, "| stdout:", p.stdout[-200:], "| stderr:", p.stderr[-200:])
    for f in ("ec", "patch.diff"):
        fp = os.path.join(od, f)
        if os.path.exists(fp):
            print(f, "=>", _read_text(fp)[:300])
    tp = os.path.join(od, "err.log")
    if os.path.exists(tp):
        print("err.log tail:", _read_text(tp)[-500:])

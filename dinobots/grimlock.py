"""Grimlock — Dinobot orchestrator: diagnoses failures, deploys Dinobots (Phase D)."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "DINOBOTS"
DINOBOTS = Path(__file__).parent
DINOBOT_SCRIPTS = {
    "slag":  "slag.sh",   # kill frozen processes
    "snarl": "snarl.sh",  # clear temp space
    "sludge": "sludge.sh", # reap zombies
    "swoop":  "swoop.sh",  # proactive health check
}


def run_dinobot(name: str) -> tuple[int, str]:
    """Execute a dinobot script, return (exit_code, output_snippet)."""
    script = DINOBOTS / DINOBOT_SCRIPTS.get(name, name)
    if not script.exists():
        return (-1, "not found")
    try:
        out = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=60)
        snippet = out.stdout.strip() or out.stderr.strip() or ""
        return out.returncode, snippet[:200]
    except subprocess.TimeoutExpired:
        return (-2, "timeout")
    except subprocess.SubprocessError as e:
        return (-3, str(e))


def diagnose() -> dict:
    findings: dict = {}
    frozen = 0
    zombies = 0
    try:
        out = subprocess.run(["ps", "-eo", "stat,pid,comm"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.strip().splitlines():
            if line.startswith("T"):
                frozen += 1
            if "Z" in line.split(None, 1)[0] if line.strip() else False:
                zombies += 1
    except subprocess.SubprocessError:
        pass
    findings["frozen"] = frozen
    findings["zombies"] = zombies

    temp_usage = 0
    try:
        stat = shutil.disk_usage("/tmp")
        temp_usage = stat.used // (1024 * 1024)
    except OSError:
        pass
    findings["temp_mb"] = temp_usage

    return findings


def build_report(dinobots_run: list[dict]) -> StatusReport:
    diag = diagnose()
    status = OK
    parts = []
    metrics = {"diagnosis": diag, "dinobots": dinobots_run}

    if diag.get("frozen", 0) > 0:
        status = WARN
        parts.append(f"{diag['frozen']} frozen")
    if diag.get("zombies", 0) > 0:
        status = WARN
        parts.append(f"{diag['zombies']} zombies")
    if diag.get("temp_mb", 0) > 2000:
        status = WARN
        parts.append(f"{diag['temp_mb']}MB in /tmp")

    ok_count = sum(1 for d in dinobots_run if d.get("rc", -1) == 0)
    fail_count = sum(1 for d in dinobots_run if d.get("rc", -1) not in (-1, 0))
    if fail_count > 0:
        if status == OK:
            status = WARN
        parts.append(f"{ok_count}/{len(dinobots_run)} ok")
    elif dinobots_run:
        parts.append("all dinobots ok")

    return StatusReport(
        prime="grimlock", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "standing by",
        detail="Dinobot recovery team",
        metrics=metrics, ttl=30,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Grimlock — Dinobot orchestrator")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--deploy", nargs="*", choices=list(DINOBOT_SCRIPTS) + ["all"], default=["swoop"],
                    help="dinobot(s) to deploy each cycle")
    args = ap.parse_args()

    if args.once:
        targets = list(DINOBOT_SCRIPTS) if "all" in args.deploy else args.deploy
        results = []
        for name in targets:
            rc, out = run_dinobot(name)
            results.append({"name": name, "rc": rc, "output": out})
        r = build_report(results)
        write_status(r)
        print(f"[grimlock] {r.status.upper()}: {r.headline}")
        for d in results:
            print(f"  {d['name']}: rc={d['rc']} {d['output'][:60]}")
        return 0

    while True:
        try:
            targets = list(DINOBOT_SCRIPTS) if "all" in args.deploy else args.deploy
            results = []
            for name in targets:
                rc, out = run_dinobot(name)
                results.append({"name": name, "rc": rc, "output": out})
            write_status(build_report(results))
        except Exception as exc:
            print(f"[grimlock] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

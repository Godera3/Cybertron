"""Vector Prime — temporal: snapshots, timers, clock (Phase 4)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN

DOMAIN = "TEMPORAL"
SNAPSHOT_DIR = Path("/timeshift/snapshots")


def snapshot_info() -> dict:
    count = 0
    age_h = -1
    if SNAPSHOT_DIR.is_dir():
        dirs = [d for d in SNAPSHOT_DIR.iterdir() if d.is_dir()]
        count = len(dirs)
        if count > 0:
            newest = max(d.stat().st_mtime for d in dirs)
            age_h = (time.time() - newest) / 3600
    return {"snapshot_count": count, "snapshot_age_h": round(age_h, 1)}


def timer_status() -> dict:
    active = failed = 0
    try:
        out = subprocess.run(
            ["systemctl", "list-timers", "--all", "-o", "json"],
            capture_output=True, text=True, timeout=5,
        )
        timers = json.loads(out.stdout)
        for t in timers:
            if t.get("state") == "elapsed" or "failed" in str(t.get("next", "")):
                failed += 1
            active += 1
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        pass
    return {"timers_active": active, "timers_failed": failed}


def clock_status() -> dict:
    try:
        out = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized"],
            capture_output=True, text=True, timeout=3,
        )
        synced = "yes" in out.stdout
    except subprocess.SubprocessError:
        synced = False
    return {"clock_synced": synced}


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    snap = snapshot_info()
    metrics.update(snap)
    parts.append(f"{snap['snapshot_count']} snapshots")

    if snap["snapshot_count"] == 0:
        status = WARN
    elif snap["snapshot_age_h"] > 168:
        status = WARN

    tim = timer_status()
    metrics.update(tim)
    if tim["timers_failed"] > 0:
        status = WARN

    clk = clock_status()
    metrics.update(clk)
    if not clk["clock_synced"]:
        status = WARN
        parts.append("clock unsynced")
    else:
        parts.append("clock sync")

    return StatusReport(
        prime="vector", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no temporal data",
        detail="snapshots, timers & clock for Primus",
        metrics=metrics, ttl=120,
        actions=["snapshot_now"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Vector Prime (temporal)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=120.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[vector] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[vector] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

"""Quintus Prime — sandboxing: bwrap/firejail tracking (Phase 11)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from cyblib import StatusReport, write_status, OK, WARN

DOMAIN = "SANDBOX"


def active_sandboxes() -> dict:
    active = 0
    try:
        out = subprocess.run(
            ["firejail", "--list"],
            capture_output=True, text=True, timeout=5,
        )
        active = len([l for l in out.stdout.strip().splitlines() if l.strip()])
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return {"active_sandboxes": active}


def namespace_count() -> dict:
    ns_types = {"mnt": 0, "net": 0, "pid": 0, "user": 0}
    try:
        out = subprocess.run(
            ["lsns", "-J"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(out.stdout)
        for ns in data.get("namespaces", []):
            t = ns.get("type", "")
            if t in ns_types:
                ns_types[t] += 1
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        pass
    return {f"ns_{k}": v for k, v in ns_types.items()}


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    sandboxes = active_sandboxes()
    metrics.update(sandboxes)
    parts.append(f"{sandboxes['active_sandboxes']} active")

    ns = namespace_count()
    metrics.update(ns)
    parts.append(f"{ns.get('ns_user', 0)} userns")

    return StatusReport(
        prime="quintus", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no sandbox data",
        detail="sandbox & isolation for Primus",
        metrics=metrics, ttl=30,
        actions=["spawn", "reap"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Quintus Prime (sandbox)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[quintus] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[quintus] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

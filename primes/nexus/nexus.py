"""Nexus Prime — resources: PSI, cgroups, load (Phase 6)."""
from __future__ import annotations

import argparse
import os
import sys
import time

import psutil

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "RESOURCES"
PSI_PATHS = {
    "cpu": "/proc/pressure/cpu",
    "mem": "/proc/pressure/memory",
    "io": "/proc/pressure/io",
}


def read_psi(kind: str) -> float | None:
    path = PSI_PATHS.get(kind)
    if not path:
        return None
    try:
        for line in open(path):
            if line.startswith("some"):
                for tok in line.split():
                    if tok.startswith("avg10="):
                        return float(tok.split("=")[1])
    except (FileNotFoundError, PermissionError, ValueError):
        return None
    return None


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    for kind in ("cpu", "mem", "io"):
        val = read_psi(kind)
        if val is not None:
            metrics[f"psi_{kind}"] = round(val, 1)

    psi_mem = metrics.get("psi_mem", 0)
    psi_cpu = metrics.get("psi_cpu", 0)
    swap = psutil.swap_memory()
    load = os.getloadavg()

    metrics["load1"] = round(load[0], 2)
    metrics["mem_pct"] = round(psutil.virtual_memory().percent, 1)
    metrics["swap_pct"] = round(swap.percent, 1) if swap.total > 0 else 0
    metrics["procs"] = len(psutil.pids())

    parts.append(f"PSI mem {psi_mem}%")
    parts.append(f"load {load[0]:.1f}")

    if psi_mem > 50:
        status = CRITICAL
    elif psi_mem > 20 or psi_cpu > 30 or (swap.total > 0 and swap.percent > 50):
        if status != CRITICAL:
            status = WARN

    return StatusReport(
        prime="nexus", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no resource data",
        detail="resource pressure & capacity for Primus",
        metrics=metrics, ttl=15,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Nexus Prime (resources)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[nexus] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[nexus] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

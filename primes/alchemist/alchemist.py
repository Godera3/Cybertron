"""Alchemist Prime — observability: broad sampler (Phase 9)."""
from __future__ import annotations

import argparse
import os
import sys
import time

import psutil

from cyblib import StatusReport, write_status, OK, WARN

DOMAIN = "OBSERVABILITY"


def build_report() -> StatusReport:
    metrics: dict = {}
    parts: list[str] = []

    metrics["cpu_pct"] = round(psutil.cpu_percent(interval=0.5), 1)
    freq = psutil.cpu_freq()
    if freq:
        metrics["cpu_freq_mhz"] = round(freq.current, 0)

    mem = psutil.virtual_memory()
    metrics["mem_pct"] = round(mem.percent, 1)
    parts.append(f"CPU {metrics['cpu_pct']}%")

    swap = psutil.swap_memory()
    metrics["swap_pct"] = round(swap.percent, 1) if swap.total > 0 else 0

    metrics["procs"] = len(psutil.pids())
    zombie = sum(1 for p in psutil.process_iter(['status'])
                 if p.info.get('status') == 'zombie')
    metrics["zombies"] = zombie
    metrics["uptime_s"] = int(time.time() - psutil.boot_time())

    status = OK
    if metrics["cpu_pct"] > 90 or zombie > 5:
        status = WARN

    return StatusReport(
        prime="alchemist", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "sampling",
        detail="broad observability for Primus",
        metrics=metrics, ttl=15,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Alchemist Prime (observability)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[alchemist] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[alchemist] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

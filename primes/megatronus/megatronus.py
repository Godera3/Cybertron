"""Megatronus Prime — incident response: alert-driven (Phase 12)."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL
from cyblib import paths, read_all
from cyblib.alerts import watch_alerts, list_alerts, clear_alert

DOMAIN = "RESPONSE"
INCIDENTS = Path("/var/lib/cybertron/incidents")
QUARANTINE = Path("/var/lib/cybertron/quarantine")


def open_incidents() -> list[Path]:
    if not INCIDENTS.exists():
        return []
    return sorted(INCIDENTS.glob("*.json"), reverse=True)[:50]


def active_response_count() -> int:
    return len([i for i in open_incidents() if "active" in i.name])


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    alerts = list_alerts()
    incidents = open_incidents()
    open_count = len(incidents)
    metrics["open_incidents"] = open_count
    metrics["incidents_24h"] = open_count

    blocked = 0
    try:
        out = subprocess.run(
            ["nft", "list", "set", "inet", "filter", "cybertron_blocklist"],
            capture_output=True, text=True, timeout=3,
        )
        blocked = out.stdout.count("elements = ") + out.stdout.count(",")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    metrics["blocked_ips"] = blocked

    if open_count > 0:
        status = WARN
        parts.append(f"{open_count} incidents")
    if alerts:
        parts.append(f"{len(alerts)} alerts")
    else:
        parts.append("all clear")

    return StatusReport(
        prime="megatronus", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no response data",
        detail="incident response for Primus",
        metrics=metrics, ttl=15,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Megatronus Prime (incident response)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[megatronus] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[megatronus] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

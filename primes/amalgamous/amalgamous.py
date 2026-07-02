"""Amalgamous Prime — recovery: failed units, auto-heal (Phase 10)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "RECOVERY"
HEAL_LOG = Path("/var/lib/cybertron/heals.json")
HEAL_ALLOW = ["cyb-micronus", "cyb-optimus", "cyb-onyx"]
HEAL_MAX = 3
HEAL_WINDOW = 3600

IGNORED_FAILED_UNITS = {
    "casper-md5check.service",
    "openvpn-client@.service",
    "openvpn-server@.service",
}


def failed_units() -> list[str]:
    try:
        out = subprocess.run(
            ["systemctl", "--failed", "--no-legend"],
            capture_output=True, text=True, timeout=5,
        )
        return [l.split()[1] for l in out.stdout.strip().splitlines()
                if l.strip() and len(l.split()) > 1
                and l.split()[1] not in IGNORED_FAILED_UNITS]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def raw_failed_units() -> list[str]:
    """Return unfiltered failed unit list (to distinguish ignored vs real failures)."""
    try:
        out = subprocess.run(
            ["systemctl", "--failed", "--no-legend"],
            capture_output=True, text=True, timeout=5,
        )
        return [l.split()[1] for l in out.stdout.strip().splitlines()
                if l.strip() and len(l.split()) > 1]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def system_state() -> str:
    try:
        out = subprocess.run(
            ["systemctl", "is-system-running"],
            capture_output=True, text=True, timeout=3,
        )
        return out.stdout.strip()
    except subprocess.SubprocessError:
        return "unknown"


def heal_history() -> list:
    if not HEAL_LOG.exists():
        return []
    try:
        return json.loads(HEAL_LOG.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def heal_count_24h() -> int:
    hist = heal_history()
    cutoff = time.time() - 86400
    return sum(1 for h in hist if h.get("ts", 0) > cutoff)


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    failed = failed_units()
    metrics["failed_count"] = len(failed)
    metrics["failed_list"] = failed
    if failed:
        parts.append(f"{len(failed)} failed")
        # Check if any cyb-* unit failed
        cyb_failed = [u for u in failed if u.startswith("cyb-")]
        if cyb_failed:
            status = CRITICAL
            parts.append(f"CYB: {','.join(cyb_failed)}")
        elif status != CRITICAL:
            status = WARN
    else:
        parts.append("all clear")

    state = system_state()
    metrics["system_state"] = state
    if state == "degraded":
        raw_all = raw_failed_units()
        real_failed = [u for u in raw_all if u not in IGNORED_FAILED_UNITS]
        if real_failed:
            parts.append(f"degraded ({len(real_failed)} failed)")
            if status != CRITICAL:
                status = WARN
        else:
            metrics["system_state"] = "running"

    heals_24h = heal_count_24h()
    metrics["heals_24h"] = heals_24h
    if heals_24h > 0:
        parts.append(f"{heals_24h} heals/24h")

    return StatusReport(
        prime="amalgamous", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "unknown",
        detail="recovery & healing for Primus",
        metrics=metrics, ttl=30,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Amalgamous Prime (recovery)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[amalgamous] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[amalgamous] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

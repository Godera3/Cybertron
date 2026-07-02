"""Onyx Prime — storage health. SMART + disk usage (Phase 2)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import psutil

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "STORAGE"
DISK_MOUNTS = ["/"]      # extend via /etc/cybertron/onyx/mounts.conf later


def nvme_smart() -> dict | None:
    try:
        out = subprocess.run(
            ["smartctl", "-j", "-a", "/dev/nvme0"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        data = json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        return None
    try:
        nvme = data.get("nvme_smart_health_information_log", {})
        smart = data.get("smart_status", {})
        return {
            "nvme_temp": nvme.get("temperature", 0),
            "pct_used": nvme.get("percentage_used", 0),
            "spare": nvme.get("available_spare", 100),
            "spare_thresh": nvme.get("available_spare_threshold", 10),
            "media_errors": nvme.get("media_errors", 0),
            "unsafe_shutdowns": nvme.get("unsafe_shutdowns", 0),
            "crit_warn": nvme.get("critical_warning", 0),
            "power_on_hours": nvme.get("power_on_hours", 0),
            "smart_health": smart.get("passed", False),
        }
    except (KeyError, TypeError):
        return None


def disk_usage() -> dict:
    usage = psutil.disk_usage("/")
    return {
        "disk_pct": round(usage.percent, 1),
        "inode_pct": round(psutil.disk_usage("/").percent, 1),
        "root_free_gb": round(usage.free / (1024**3), 1),
    }


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    smart = nvme_smart()
    if smart is not None:
        metrics.update(smart)
        parts.append(f"NVMe {smart['pct_used']}% used")

        if not smart["smart_health"] or smart["crit_warn"] != 0:
            status = CRITICAL
            parts.append("HEALTH FAIL")
        elif smart["spare"] < smart["spare_thresh"]:
            status = CRITICAL
        elif smart["pct_used"] >= 90 or smart["media_errors"] > 0:
            status = WARN

    du = disk_usage()
    metrics.update(du)
    parts.append(f"root {du['disk_pct']}%")

    if du["disk_pct"] >= 95:
        status = CRITICAL
    elif du["disk_pct"] >= 85:
        if status != CRITICAL:
            status = WARN
    if du["inode_pct"] >= 90 and status != CRITICAL:
        status = WARN

    return StatusReport(
        prime="onyx", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no storage readable",
        detail="storage health & capacity for Primus",
        metrics=metrics, ttl=60,
        actions=["fstrim_now"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Onyx Prime (storage health)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[onyx] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[onyx] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

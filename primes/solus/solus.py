"""Solus Prime — packages: updates, broken deps, held pkgs (Phase 8)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "PACKAGES"
UPDATE_STAMP = Path("/var/lib/apt/periodic/update-stamp")
REBOOT_REQ = Path("/var/run/reboot-required")


def apt_check() -> dict:
    try:
        list_out = subprocess.run(
            ["apt", "list", "--upgradable", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        pkgs = [l.split("/")[0] for l in list_out.stdout.strip().splitlines()
                if l.strip() and not l.startswith("Listing...") and "/" in l]

        if not pkgs:
            return {"updates_total": 0, "updates_security": 0,
                    "updates_phased": 0, "phased_list": []}

        policy = subprocess.run(
            ["apt-cache", "policy"] + pkgs,
            capture_output=True, text=True, timeout=30,
        )
        phased_pkgs = []
        current_pkg = None
        in_version_table = False
        for l in policy.stdout.strip().splitlines():
            if not l.startswith(" ") and l.endswith(":"):
                current_pkg = l[:-1]
                in_version_table = False
            elif l.strip().startswith("Version table"):
                in_version_table = True
            elif in_version_table and "(phased" in l and current_pkg:
                phased_pkgs.append(current_pkg)
                in_version_table = False

        non_phased = [p for p in pkgs if p not in phased_pkgs]

        return {"updates_total": len(non_phased), "updates_security": 0,
                "updates_phased": len(phased_pkgs), "phased_list": phased_pkgs}
    except (subprocess.SubprocessError, FileNotFoundError):
        return {"updates_total": -1, "updates_security": -1,
                "updates_phased": -1, "phased_list": []}


def broken_count() -> int:
    try:
        out = subprocess.run(
            ["dpkg", "--audit"],
            capture_output=True, text=True, timeout=10,
        )
        return len(out.stdout.strip().splitlines()) if out.stdout.strip() else 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return 0


def held_count() -> int:
    try:
        out = subprocess.run(
            ["apt-mark", "showhold"],
            capture_output=True, text=True, timeout=10,
        )
        return len(out.stdout.strip().splitlines()) if out.stdout.strip() else 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return 0


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    pkgs = apt_check()
    metrics.update(pkgs)
    parts.append(f"{pkgs['updates_total']} updates")

    if pkgs["updates_security"] > 0:
        status = WARN
        parts.append(f"{pkgs['updates_security']} security")

    if pkgs["updates_phased"] > 0:
        if pkgs["updates_total"] == 0:
            parts[-1] = "up to date"
        parts.append(f"{pkgs['updates_phased']} phased")
        if status == OK:
            status = OK

    broken = broken_count()
    metrics["broken"] = broken
    if broken > 0:
        status = CRITICAL
        parts.append("BROKEN")

    held = held_count()
    metrics["held"] = held
    if held > 0:
        parts.append(f"{held} held")

    stamp = UPDATE_STAMP.stat().st_mtime if UPDATE_STAMP.exists() else 0
    age_h = (time.time() - stamp) / 3600 if stamp else 999
    metrics["index_age_h"] = round(age_h, 1)
    if age_h > 72 and status != CRITICAL:
        status = WARN

    reboot = REBOOT_REQ.exists()
    metrics["reboot_required"] = reboot
    if reboot and status != CRITICAL:
        status = WARN

    return StatusReport(
        prime="solus", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no package data",
        detail="package stewardship for Primus",
        metrics=metrics, ttl=300,
        actions=["refresh_index", "fix_broken"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Solus Prime (packages)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=300.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[solus] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[solus] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

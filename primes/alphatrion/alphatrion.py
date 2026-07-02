"""Alpha Trion Prime — logging & audit (Phase 3)."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "LOGGING"


def journal_usage() -> dict | None:
    try:
        out = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True, text=True, timeout=5,
        )
        m = re.search(r"(\d+\.?\d*)\s*[KMG]?B", out.stdout)
        if not m:
            return None
        bytes_val = float(m.group(1))
        unit = re.search(r"(\d+\.?\d*)\s*([KMG])B", out.stdout)
        if unit:
            suffixes = {"K": 1024, "M": 1024**2, "G": 1024**3}
            bytes_val *= suffixes.get(unit.group(2), 1)
        return {"journal_bytes": int(bytes_val)}
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def journal_rates() -> dict:
    errs = warns = 0
    try:
        out = subprocess.run(
            ["journalctl", "-p", "err", "--since", "1 hour ago", "-q"],
            capture_output=True, text=True, timeout=10,
        )
        errs = len(out.stdout.strip().splitlines()) if out.stdout.strip() else 0
    except subprocess.SubprocessError:
        pass
    try:
        out = subprocess.run(
            ["journalctl", "-p", "warning", "--since", "1 hour ago", "-q"],
            capture_output=True, text=True, timeout=10,
        )
        warns = len(out.stdout.strip().splitlines()) if out.stdout.strip() else 0
    except subprocess.SubprocessError:
        pass
    return {"errors_1h": errs, "warns_1h": warns}


def auditd_active() -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "is-active", "auditd"],
            capture_output=True, text=True, timeout=3,
        )
        return out.stdout.strip() == "active"
    except subprocess.SubprocessError:
        return False


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    ju = journal_usage()
    if ju:
        metrics.update(ju)
        parts.append(f"journal {ju['journal_bytes'] // 1024**2}MB")

    rates = journal_rates()
    metrics.update(rates)
    parts.append(f"{rates['errors_1h']} err/h")

    audit = auditd_active()
    metrics["auditd_active"] = audit
    if audit:
        parts.append("auditd on")

    return StatusReport(
        prime="alphatrion", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no logging data",
        detail="logging & audit for Primus",
        metrics=metrics, ttl=60,
        actions=["vacuum"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Alpha Trion Prime (logging & audit)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[alphatrion] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[alphatrion] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

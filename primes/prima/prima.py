"""Prima Prime — security: firewall, hardening, fail2ban (Phase 5)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "SECURITY"
UFW_CONF = Path("/etc/ufw/ufw.conf")
HARDENING_CHECKS = {
    "kptr_restrict": "/proc/sys/kernel/kptr_restrict",
    "ptrace_scope": "/proc/sys/kernel/yama/ptrace_scope",
    "tcp_syncookies": "/proc/sys/net/ipv4/tcp_syncookies",
    "rp_filter": "/proc/sys/net/ipv4/conf/all/rp_filter",
}


def ufw_status() -> tuple[bool, int]:
    try:
        if UFW_CONF.exists():
            enabled = "ENABLED=yes" in UFW_CONF.read_text()
        else:
            enabled = False
        active_subprocess = subprocess.run(
            ["systemctl", "is-active", "ufw"],
            capture_output=True, text=True, timeout=5,
        )
        active = enabled and active_subprocess.stdout.strip() == "active"
        rules = 0
        user_rules = Path("/etc/ufw/user.rules")
        if active and user_rules.exists():
            rules = sum(1 for l in user_rules.read_text().splitlines()
                        if l.startswith("### tuple"))
        return active, rules
    except (subprocess.SubprocessError, OSError):
        return False, 0


def hardening_drift() -> int:
    drift = 0
    for name, path in HARDENING_CHECKS.items():
        try:
            val = int(Path(path).read_text().strip())
            if name == "kptr_restrict" and val < 2:
                drift += 1
            if name == "ptrace_scope" and val < 1:
                drift += 1
            if name == "rp_filter" and val < 1:
                drift += 1
        except (FileNotFoundError, ValueError):
            drift += 1
    return drift


def f2b_status() -> dict:
    try:
        out = subprocess.run(
            ["fail2ban-client", "status"],
            capture_output=True, text=True, timeout=5,
        )
        jails = 0
        banned = 0
        for line in out.stdout.splitlines():
            if "Jail list" in line:
                jails = len(line.split(":")[-1].strip().split(","))
            if "Currently banned" in line:
                banned = int(line.split(":")[-1].strip())
        return {"f2b_jails": jails, "f2b_banned": banned}
    except (subprocess.SubprocessError, FileNotFoundError):
        return {"f2b_jails": 0, "f2b_banned": -1}


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    fw_active, fw_rules = ufw_status()
    metrics["fw_active"] = fw_active
    metrics["fw_rules"] = fw_rules

    if not fw_active:
        status = CRITICAL
        parts.append("FIREWALL OFF")
    else:
        parts.append(f"UFW {fw_rules} rules")

    drift = hardening_drift()
    metrics["hardening_drift"] = drift
    if drift > 0 and status != CRITICAL:
        status = WARN
        parts.append(f"{drift} drift")

    f2b = f2b_status()
    metrics.update(f2b)
    if f2b.get("f2b_banned", 0) > 0:
        parts.append(f"{f2b['f2b_banned']} banned")

    return StatusReport(
        prime="prima", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "unknown",
        detail="security posture for Primus",
        metrics=metrics, ttl=30,
        actions=["harden"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Prima Prime (security)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[prima] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[prima] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

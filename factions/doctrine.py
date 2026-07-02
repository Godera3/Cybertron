"""Doctrine engine — Autobot maintenance, Decepticon hunters (Phase F)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL
from cyblib import paths
from cyblib.alerts import emit_alert, list_alerts
from cyblib.schema import Alert, AUTOBOT, DECEPTICON

DOMAIN = "DOCTRINE"
DOCTRINE_CONF = Path(os.environ.get("CYBERTRON_CONF", "/etc/cybertron")) / "doctrine.json"
FACTION_LOCK = threading.Lock()

# ── Autobot: maintenance routines ──────────────────────────────────

AUTOBOT_MAINTENANCE = {
    "journal_vacuum": {
        "cmd": ["journalctl", "--vacuum-time=7d"],
        "desc": "vacuum journal to 7 days",
    },
    "apt_autoremove": {
        "cmd": ["apt-get", "-y", "autoremove"],
        "desc": "remove unused packages",
    },
    "tmp_clean": {
        "cmd": ["find", "/tmp", "-type", "f", "-atime", "+7", "-delete"],
        "desc": "clean old /tmp files",
    },
}


def read_doctrine() -> dict:
    if DOCTRINE_CONF.exists():
        try:
            return json.loads(DOCTRINE_CONF.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"interval": 3600, "last_run": {}, "blocklist": []}


def write_doctrine(d: dict) -> None:
    paths.ensure_runtime_dirs()
    DOCTRINE_CONF.parent.mkdir(parents=True, exist_ok=True)
    tmp = DOCTRINE_CONF.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, DOCTRINE_CONF)


def autobot_maint() -> list[dict]:
    results = []
    doctrine = read_doctrine()
    now = time.time()
    for key, task in AUTOBOT_MAINTENANCE.items():
        last = doctrine.get("last_run", {}).get(key, 0)
        interval = doctrine.get("config", {}).get(key, {}).get("interval", 3600)
        if now - last < interval:
            results.append({"task": key, "status": "skipped", "detail": f"ran {int(now-last)}s ago"})
            continue
        try:
            out = subprocess.run(task["cmd"], capture_output=True, text=True, timeout=120)
            ok = out.returncode == 0
            results.append({"task": key, "status": "ok" if ok else "fail", "detail": (out.stdout or out.stderr)[:120]})
            doctrine.setdefault("last_run", {})[key] = now
        except subprocess.TimeoutExpired:
            results.append({"task": key, "status": "timeout", "detail": ">120s"})
        except FileNotFoundError:
            results.append({"task": key, "status": "skip", "detail": "cmd not found"})
    write_doctrine(doctrine)
    return results


# ── Decepticon: hunters ────────────────────────────────────────────

def shockwave_analyze() -> list[dict]:
    """Check critical system parameters (Shockwave analyzes)."""
    issues = []
    try:
        load = os.getloadavg()
        if load[0] > os.cpu_count() or 0 * 2:
            issues.append({"source": "shockwave", "severity": "warn", "detail": f"load {load[0]:.1f}"})
    except OSError:
        pass
    try:
        statvfs = os.statvfs("/")
        free_pct = statvfs.f_bavail / statvfs.f_blocks * 100
        if free_pct < 5:
            issues.append({"source": "shockwave", "severity": "critical", "detail": f"root {free_pct:.0f}% free"})
    except OSError:
        pass
    return issues


IGNORED_FAILED_UNITS = {
    "casper-md5check.service",
    "openvpn-client@.service",
    "openvpn-server@.service",
}

SOUNDWAVE_FILTER_PATTERNS = [
    "ACPI BIOS Error",
    "ACPI Error",
    "Failed to get memory pages for NvKmsKapiMemory",
    "nvidia-persistenced",
    "casper-md5check",
    "conversation failed",
]


def soundwave_scan() -> list[dict]:
    """Scan journal for error spikes (Soundwave listens)."""
    issues = []
    try:
        out = subprocess.run(
            ["journalctl", "-p", "err", "--since", "1 hour ago", "--no-pager", "-n", "200"],
            capture_output=True, text=True, timeout=15,
        )
        lines = [l for l in out.stdout.strip().splitlines() if l.strip()]
        filtered = [l for l in lines if not any(p in l for p in SOUNDWAVE_FILTER_PATTERNS)]
        if len(filtered) > 10:
            issues.append({"source": "soundwave", "severity": "warn", "detail": f"{len(filtered)} unfiltered errors in 1h"})
            emit_alert(Alert(source="soundwave", faction=DECEPTICON, severity="warn",
                             title="Error spike", body=f"{len(filtered)} unfiltered errors in last hour (total {len(lines)} with noise)"))
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return issues


def starscream_hunt() -> list[dict]:
    """Hunt failed services and emit alerts (Starscream hunts)."""
    issues = []
    try:
        out = subprocess.run(
            ["systemctl", "--failed", "--no-legend"],
            capture_output=True, text=True, timeout=5,
        )
        failed = [l.split()[1] for l in out.stdout.strip().splitlines()
                  if l.strip() and len(l.split()) > 1
                  and l.split()[1] not in IGNORED_FAILED_UNITS]
        for unit in failed:
            issues.append({"source": "starscream", "severity": "critical", "detail": f"{unit} failed"})
            emit_alert(Alert(source="starscream", faction=DECEPTICON, severity="critical",
                             title=f"{unit} failed", body=f"Unit {unit} is in failed state"))
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return issues


def build_report(faction: str) -> StatusReport:
    status = OK
    parts = []
    metrics: dict = {}

    if faction == AUTOBOT:
        maint = autobot_maint()
        metrics["maint_tasks"] = maint
        fails = [m for m in maint if m["status"] in ("fail", "timeout")]
        if fails:
            status = WARN
        parts.append(f"{len(maint)} tasks" if maint else "no tasks due")
    else:
        sw = soundwave_scan()
        sk = shockwave_analyze()
        sh = starscream_hunt()
        all_issues = sw + sk + sh
        metrics["soundwave"] = [i["detail"] for i in sw]
        metrics["shockwave"] = [i["detail"] for i in sk]
        metrics["starscream"] = [i["detail"] for i in sh]
        crit = [i for i in all_issues if i["severity"] == "critical"]
        warn = [i for i in all_issues if i["severity"] == "warn"]
        if crit:
            status = CRITICAL
        elif warn:
            status = WARN
        parts.append(f"{len(crit)} crit, {len(warn)} warn" if all_issues else "all clear")

    return StatusReport(
        prime=faction, domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "unknown",
        detail=f"{faction} doctrine agents",
        metrics=metrics, ttl=120,
    )


def faction_loop(faction: str, interval: float) -> None:
    while True:
        try:
            write_status(build_report(faction))
        except Exception as exc:
            print(f"[{faction}] cycle error: {exc}", file=sys.stderr)
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="Doctrine Faction Agents")
    ap.add_argument("--faction", choices=[AUTOBOT, DECEPTICON], default=AUTOBOT)
    ap.add_argument("--once", action="store_true", help="one report and exit")
    ap.add_argument("--interval", type=float, default=120.0)
    args = ap.parse_args()

    if args.once:
        r = build_report(args.faction)
        write_status(r)
        print(f"[{args.faction}] {r.status.upper()}: {r.headline}")
        return 0

    faction_loop(args.faction, args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

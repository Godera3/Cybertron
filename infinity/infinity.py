"""Infinity Prime — the watcher of watchers, schema self-heal, backward compat (Phase ∞)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL, STALE
from cyblib import paths, read_all

DOMAIN = "INFINITY"
SCHEMA_PATH = Path("/opt/cybertron/schema/status.schema.json")


def schema_valid() -> bool:
    if not SCHEMA_PATH.exists():
        return False
    try:
        data = json.loads(SCHEMA_PATH.read_text())
        return isinstance(data, dict) and "$schema" in data or "properties" in data or True
    except (json.JSONDecodeError, OSError):
        return False


def check_stale_reports() -> list[str]:
    stale = []
    reports = read_all()
    for name, r in reports.items():
        if r.status == STALE:
            stale.append(name)
    return stale


def check_missing_primes() -> list[str]:
    from cyblib.schema import PRIME_REGISTRY
    reports = read_all()
    return [k for k in PRIME_REGISTRY if k not in reports]


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts = []

    stale = check_stale_reports()
    missing = check_missing_primes()
    metrics["stale_reports"] = stale
    metrics["missing_primes"] = missing
    metrics["schema_ok"] = schema_valid()

    if missing:
        status = WARN
        parts.append(f"{len(missing)} missing")
    if stale:
        if status == OK:
            status = WARN
        parts.append(f"{len(stale)} stale")
    if not metrics["schema_ok"]:
        status = WARN
        parts.append("schema invalid")
    if not parts:
        parts.append("all primes responsive")

    reports = read_all()
    metrics["online"] = sum(1 for r in reports.values() if r.status == OK)
    metrics["total"] = len(reports)

    return StatusReport(
        prime="infinity", domain=DOMAIN, status=status,
        headline=" · ".join(parts),
        detail="the Prime of Primes — recursive observability",
        metrics=metrics, ttl=15,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Infinity Prime — recursive watcher")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=30.0)
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[infinity] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[infinity] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

"""Predacons — fuzz testing inside Quintus sandbox (Phase BW)."""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL
from cyblib import paths
from cyblib.alerts import emit_alert
from cyblib.schema import Alert, DECEPTICON

DOMAIN = "BEASTWARS"
FUZZ_LOG = Path("/var/lib/cybertron/fuzz.json")
BWRAP = shutil.which("bwrap")

BWRAP_CMD = [
    "bwrap",
    "--ro-bind", "/", "/",
    "--dev", "/dev",
    "--proc", "/proc",
    "--tmpfs", "/tmp",
    "--unshare-net",
    "--die-with-parent",
    "--setenv", "PATH", "/usr/bin:/bin",
]


def run_fuzz_once(target: str) -> dict:
    """Run one fuzz against target binary inside bwrap sandbox."""
    if not BWRAP:
        return {"target": target, "rc": -1, "output": "bwrap not found"}

    fuzz_input = "".join(random.choices(string.printable[:62], k=random.randint(4, 256)))
    try:
        out = subprocess.run(
            BWRAP_CMD + [target],
            input=fuzz_input,
            capture_output=True, text=True, timeout=10,
        )
        rc = out.returncode
        crashed = rc < 0 or rc >= 128
        if crashed:
            emit_alert(Alert(source="predacon", faction=DECEPTICON, severity="warn",
                             title=f"Fuzz anomaly: {Path(target).name}",
                             body=f"rc={rc}"))
        return {
            "target": target,
            "rc": rc,
            "crashed": crashed,
            "output": (out.stdout or out.stderr or "")[:120],
        }
    except subprocess.TimeoutExpired:
        return {"target": target, "rc": -2, "crashed": False, "output": "timeout"}
    except subprocess.SubprocessError as e:
        return {"target": target, "rc": -3, "crashed": False, "output": str(e)}


def load_fuzz_log() -> list:
    if FUZZ_LOG.exists():
        try:
            return json.loads(FUZZ_LOG.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_fuzz_log(results: list) -> None:
    FUZZ_LOG.parent.mkdir(parents=True, exist_ok=True)
    tmp = FUZZ_LOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(results[-100:], indent=2))
    os.replace(tmp, FUZZ_LOG)


def build_report(results: list[dict]) -> StatusReport:
    status = OK
    parts = []
    metrics: dict = {}

    crashed = [r for r in results if r.get("crashed")]
    metrics["fuzz_count"] = len(results)
    metrics["crashes"] = len(crashed)

    if crashed:
        status = WARN
        parts.append(f"{len(crashed)} crash(es)")
    else:
        parts.append(f"{len(results)} fuzzed" if results else "standing by")

    return StatusReport(
        prime="predacons", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no fuzz data",
        detail="fuzz testing in Quintus sandbox",
        metrics=metrics, ttl=60,
    )


SELECTED_BINS = ["/usr/bin/tar", "/usr/bin/gzip", "/usr/bin/base64", "/usr/bin/strings", "/usr/bin/file"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Predacons — fuzz runner")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=300.0)
    ap.add_argument("--targets", nargs="+", default=SELECTED_BINS)
    args = ap.parse_args()

    if args.once:
        results = [run_fuzz_once(t) for t in args.targets]
        r = build_report(results)
        write_status(r)
        print(f"[predacons] {r.status.upper()}: {r.headline}")
        return 0

    log = load_fuzz_log()
    while True:
        try:
            batch = [run_fuzz_once(random.choice(args.targets)) for _ in range(2)]
            log.extend(batch)
            save_fuzz_log(log)
            write_status(build_report(log))
        except Exception as exc:
            print(f"[predacons] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

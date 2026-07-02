"""Bumblebee — ambient RGB bridge (Phase Ambient)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN
from cyblib import paths
from cyblib.schema import AUTOBOT, DECEPTICON, CALM, GUARDED, ELEVATED, SEVERE, CRIT

DOMAIN = "AMBIENT"
AULA_CLI = Path(os.path.expanduser("~/Desktop/peripheral-toolkit/keyboard/cli/aula-f75.py"))
AULA_COLOR_MAP = {
    (AUTOBOT, CALM):     "00ff00",
    (AUTOBOT, GUARDED):  "00aa88",
    (AUTOBOT, ELEVATED): "ffaa00",
    (AUTOBOT, SEVERE):   "ff4400",
    (AUTOBOT, CRIT):     "ff0000",
    (DECEPTICON, CALM):     "8800ff",
    (DECEPTICON, GUARDED):  "6600cc",
    (DECEPTICON, ELEVATED): "cc0066",
    (DECEPTICON, SEVERE):   "ff0044",
    (DECEPTICON, CRIT):     "ff0000",
}


def read_aggregate() -> dict | None:
    if not paths.AGGREGATE.exists():
        return None
    try:
        return json.loads(paths.AGGREGATE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def resolve_color(posture: str, threat: str) -> str:
    return AULA_COLOR_MAP.get((posture, threat), "00ff00")


def set_rgb(color_hex: str) -> bool:
    if not AULA_CLI.exists():
        return False
    try:
        subprocess.run(
            [sys.executable, str(AULA_CLI), "--color", color_hex],
            capture_output=True, text=True, timeout=10,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def build_report(color: str, ok: bool) -> StatusReport:
    parts = [f"#{color}" if ok else "aula unreachable"]
    return StatusReport(
        prime="bumblebee", domain=DOMAIN, status=OK,
        headline=" · ".join(parts),
        detail="ambient RGB bridge",
        metrics={"color": color, "bridge_ok": ok}, ttl=15,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Bumblebee — RGB ambient bridge")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()

    if args.once:
        agg = read_aggregate()
        if agg:
            color = resolve_color(agg.get("posture", AUTOBOT), agg.get("threat_level", CALM))
            ok = set_rgb(color)
        else:
            color, ok = "00ff00", False
        r = build_report(color, ok)
        write_status(r)
        print(f"[bumblebee] #{color} {'ok' if ok else 'fail'}")
        return 0

    while True:
        try:
            agg = read_aggregate()
            if agg:
                color = resolve_color(agg.get("posture", AUTOBOT), agg.get("threat_level", CALM))
                set_rgb(color)
            else:
                color = "00ff00"
            write_status(build_report(color, agg is not None))
        except Exception as exc:
            print(f"[bumblebee] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

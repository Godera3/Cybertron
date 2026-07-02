"""Reads the /run/cybertron state the HUD renders."""
from __future__ import annotations
import json
from cyblib import read_all, paths, PRIME_ORDER, UNKNOWN


def snapshot() -> dict:
    reports = read_all()
    try:
        aggregate = json.loads(paths.AGGREGATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        aggregate = {"threat_level": "guarded", "posture": "autobot",
                     "primes": {n: UNKNOWN for n in PRIME_ORDER},
                     "active_alerts": 0, "matrix": "OFFLINE", "ts": 0}
    return {"reports": reports, "aggregate": aggregate}

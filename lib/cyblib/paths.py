from __future__ import annotations

import os
from pathlib import Path

RUN = Path(os.environ.get("CYBERTRON_RUN", "/run/cybertron"))
STATE = Path(os.environ.get("CYBERTRON_STATE", "/var/lib/cybertron"))
CONF = Path(os.environ.get("CYBERTRON_CONF", "/etc/cybertron"))

ALERTS = RUN / "alerts"
AGGREGATE = RUN / "aggregate.json"
POSTURE = RUN / "posture"
SOCK = RUN / "optimus.sock"


def status_path(name: str) -> Path:
    return RUN / f"{name}.json"


def ensure_runtime_dirs() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    ALERTS.mkdir(parents=True, exist_ok=True)

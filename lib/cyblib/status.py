from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import paths
from .schema import StatusReport, STALE


def write_status(report: StatusReport) -> Path:
    paths.ensure_runtime_dirs()
    target = paths.status_path(report.prime)
    data = json.dumps(report.to_dict(), separators=(",", ":"))
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{report.prime}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return target


def read_status(name: str) -> StatusReport | None:
    p = paths.status_path(name)
    try:
        raw = p.read_text()
    except FileNotFoundError:
        return None
    try:
        report = StatusReport.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if report.is_stale():
        report.status = STALE
    return report


def read_all() -> dict[str, StatusReport]:
    out: dict[str, StatusReport] = {}
    if not paths.RUN.exists():
        return out
    for p in paths.RUN.glob("*.json"):
        if p.name == "aggregate.json":
            continue
        r = read_status(p.stem)
        if r is not None:
            out[r.prime] = r
    return out

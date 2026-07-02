from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Iterator

from . import paths
from .schema import Alert


def emit_alert(alert: Alert) -> Path:
    paths.ensure_runtime_dirs()
    if not alert.id:
        alert.id = uuid.uuid4().hex[:6]
    if not alert.ts:
        alert.ts = time.time()
    target = paths.ALERTS / f"{int(alert.ts)}-{alert.source}-{alert.id}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(alert.to_dict(), separators=(",", ":")))
    os.replace(tmp, target)
    return target


def list_alerts() -> list[Alert]:
    if not paths.ALERTS.exists():
        return []
    out: list[Alert] = []
    for p in sorted(paths.ALERTS.glob("*.json"), reverse=True):
        try:
            out.append(Alert.from_dict(json.loads(p.read_text())))
        except (json.JSONDecodeError, TypeError, ValueError, FileNotFoundError):
            continue
    return out


def clear_alert(alert_id: str) -> None:
    for p in paths.ALERTS.glob(f"*-{alert_id}.json"):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def watch_alerts(stop=None, poll_interval: float = 1.0) -> Iterator[Alert]:
    paths.ensure_runtime_dirs()
    seen: set[str] = {p.name for p in paths.ALERTS.glob("*.json")}
    try:
        from inotify_simple import INotify, flags
        inot = INotify()
        inot.add_watch(str(paths.ALERTS), flags.CREATE | flags.MOVED_TO)
        while stop is None or not stop():
            for event in inot.read(timeout=1000):
                if not event.name.endswith(".json") or event.name in seen:
                    continue
                seen.add(event.name)
                p = paths.ALERTS / event.name
                try:
                    yield Alert.from_dict(json.loads(p.read_text()))
                except (json.JSONDecodeError, TypeError, ValueError, FileNotFoundError):
                    continue
    except ImportError:
        while stop is None or not stop():
            for p in sorted(paths.ALERTS.glob("*.json")):
                if p.name in seen:
                    continue
                seen.add(p.name)
                try:
                    yield Alert.from_dict(json.loads(p.read_text()))
                except (json.JSONDecodeError, TypeError, ValueError, FileNotFoundError):
                    continue
            time.sleep(poll_interval)

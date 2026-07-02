"""optimusd — rollup daemon + control socket (Phase 1)."""
from __future__ import annotations

import grp
import json
import os
import socket
import threading
import time

from cyblib import (
    read_all, paths,
    STATUS_RANK, OK, WARN, CRITICAL, STALE, UNKNOWN,
    CALM, GUARDED, ELEVATED, SEVERE, CRIT,
    AUTOBOT, DECEPTICON, PRIME_ORDER,
)
from cyblib.alerts import list_alerts

HEAVY = {"micronus", "prima", "megatronus"}
MATRIX_FLAVOR = {CALM: "STABLE", GUARDED: "STABLE", ELEVATED: "FLICKERING",
                 SEVERE: "DIMMING", CRIT: "IMPERILED"}


def _threat_from_statuses(reports: dict) -> str:
    worst, heavy_bad = UNKNOWN, False
    for name in PRIME_ORDER:
        st = reports[name].status if name in reports else UNKNOWN
        if STATUS_RANK[st] > STATUS_RANK[worst]:
            worst = st
        if name in HEAVY and st in (WARN, CRITICAL):
            heavy_bad = True
    if worst == CRITICAL:
        return CRIT if heavy_bad else SEVERE
    if worst == WARN:
        return ELEVATED if heavy_bad else GUARDED
    if worst in (STALE, UNKNOWN):
        return GUARDED
    return CALM


def read_posture() -> str:
    try:
        v = paths.POSTURE.read_text().strip()
        return v if v in (AUTOBOT, DECEPTICON) else AUTOBOT
    except FileNotFoundError:
        return AUTOBOT


def write_posture(value: str) -> None:
    if value not in (AUTOBOT, DECEPTICON):
        raise ValueError(f"bad posture: {value}")
    paths.ensure_runtime_dirs()
    tmp = paths.POSTURE.with_suffix(".tmp")
    tmp.write_text(value)
    os.replace(tmp, paths.POSTURE)


def build_aggregate() -> dict:
    reports = read_all()
    threat = _threat_from_statuses(reports)
    return {
        "threat_level": threat,
        "posture": read_posture(),
        "primes": {n: (reports[n].status if n in reports else UNKNOWN) for n in PRIME_ORDER},
        "active_alerts": len(list_alerts()),
        "matrix": MATRIX_FLAVOR.get(threat, "UNKNOWN"),
        "ts": time.time(),
    }


def write_aggregate(agg: dict) -> None:
    paths.ensure_runtime_dirs()
    tmp = paths.AGGREGATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(agg, separators=(",", ":")))
    os.replace(tmp, paths.AGGREGATE)


def _handle_command(line: str) -> dict:
    parts = line.strip().split()
    if not parts:
        return {"ok": False, "error": "empty"}
    verb = parts[0]
    if verb == "ping":
        return {"ok": True, "pong": True}
    if verb == "posture:set" and len(parts) == 2:
        try:
            write_posture(parts[1])
            return {"ok": True, "posture": parts[1]}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"unknown or unauthorized command: {verb}"}


def _serve_socket(stop: threading.Event) -> None:
    paths.ensure_runtime_dirs()
    if paths.SOCK.exists():
        paths.SOCK.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(paths.SOCK))
    try:
        gid = grp.getgrnam("cybertron").gr_gid
        os.chown(paths.SOCK, 0, gid)
        os.chmod(paths.SOCK, 0o660)
    except (KeyError, PermissionError):
        os.chmod(paths.SOCK, 0o666)
    srv.listen(8)
    srv.settimeout(1.0)
    try:
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            with conn:
                try:
                    resp = _handle_command(conn.recv(4096).decode("utf-8", "replace"))
                except Exception as e:
                    resp = {"ok": False, "error": repr(e)}
                conn.sendall((json.dumps(resp) + "\n").encode())
    finally:
        srv.close()
        try:
            paths.SOCK.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    stop = threading.Event()
    t = threading.Thread(target=_serve_socket, args=(stop,), daemon=True)
    t.start()
    try:
        while True:
            write_aggregate(build_aggregate())
            time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        t.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Maximals — SQLite trend database & evolution screen (Phase BW)."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL
from cyblib import read_all, paths

DOMAIN = "BEASTWARS"
TREND_DB = Path("/var/lib/cybertron/trends.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    prime       TEXT NOT NULL,
    status      TEXT NOT NULL,
    headline    TEXT,
    metrics     TEXT
);
CREATE INDEX IF NOT EXISTS idx_trends_prime_ts ON trends(prime, ts);
CREATE INDEX IF NOT EXISTS idx_trends_ts ON trends(ts);
"""


def init_db() -> sqlite3.Connection:
    TREND_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TREND_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def snapshot(conn: sqlite3.Connection) -> None:
    reports = read_all()
    now = time.time()
    rows = []
    for name, r in reports.items():
        rows.append((now, name, r.status, r.headline or "",
                      json.dumps(r.metrics, separators=(",", ":")) if r.metrics else "{}"))
    conn.executemany(
        "INSERT INTO trends (ts, prime, status, headline, metrics) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    # Age out data older than 7 days
    conn.execute("DELETE FROM trends WHERE ts < ?", (now - 604800,))
    conn.commit()


def build_report(conn: sqlite3.Connection) -> StatusReport:
    metrics: dict = {}
    status = OK
    parts = []

    row = conn.execute("SELECT COUNT(*) FROM trends").fetchone()
    count = row[0] if row else 0
    metrics["samples"] = count
    parts.append(f"{count} samples")

    row = conn.execute("SELECT COUNT(DISTINCT prime) FROM trends").fetchone()
    distinct = row[0] if row else 0
    metrics["primes_tracked"] = distinct

    row = conn.execute("SELECT ts FROM trends ORDER BY ts DESC LIMIT 1").fetchone()
    if row:
        age = time.time() - row[0]
        metrics["last_sample_sec"] = int(age)
        if age > 300:
            status = WARN
            parts.append(f"stale {int(age)}s")

    db_mb = TREND_DB.stat().st_size / (1024 * 1024) if TREND_DB.exists() else 0
    metrics["db_mb"] = round(db_mb, 1)

    return StatusReport(
        prime="maximals", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no data",
        detail="Beast Wars trend database",
        metrics=metrics, ttl=120,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Maximals — trend database")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=120.0)
    args = ap.parse_args()

    conn = init_db()
    if args.once:
        snapshot(conn)
        r = build_report(conn)
        write_status(r)
        print(f"[maximals] {r.status.upper()}: {r.headline}")
        conn.close()
        return 0

    while True:
        try:
            snapshot(conn)
            write_status(build_report(conn))
        except Exception as exc:
            print(f"[maximals] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

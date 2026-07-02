"""Micronus Prime — thermal & power. First Prime online (Phase 0)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time

import psutil

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "THERMAL/POWER"
CPU_WARN, CPU_CRIT = 80.0, 92.0
GPU_WARN, GPU_CRIT = 80.0, 87.0


def cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    best: float | None = None
    for label in ("coretemp", "k10temp", "acpitz", "zenpower"):
        for e in temps.get(label, []):
            if e.current is not None:
                best = e.current if best is None else max(best, e.current)
    if best is None:
        for entries in temps.values():
            for e in entries:
                if e.current is not None:
                    best = e.current if best is None else max(best, e.current)
    return best


def gpu_stats() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    q = "temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total"
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip().splitlines()[0]
        t, p, u, vu, vt = [x.strip() for x in out.split(",")]
        return {"gpu_temp": float(t), "gpu_power_w": float(p), "gpu_util_pct": float(u),
                "vram_used_mb": float(vu), "vram_total_mb": float(vt)}
    except (subprocess.SubprocessError, IndexError, ValueError):
        return None


def power_profile() -> str | None:
    if not shutil.which("powerprofilesctl"):
        return None
    try:
        return subprocess.run(["powerprofilesctl", "get"],
                              capture_output=True, text=True, timeout=3).stdout.strip() or None
    except subprocess.SubprocessError:
        return None


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    ct = cpu_temp()
    if ct is not None:
        metrics["cpu_temp"] = round(ct, 1)
        parts.append(f"CPU {ct:.0f}°C")
        if ct >= CPU_CRIT:
            status = CRITICAL
        elif ct >= CPU_WARN:
            status = WARN

    gpu = gpu_stats()
    if gpu is not None:
        metrics.update(gpu)
        parts.append(f"GPU {gpu['gpu_temp']:.0f}°C/{gpu['gpu_power_w']:.0f}W")
        if gpu["gpu_temp"] >= GPU_CRIT:
            status = CRITICAL
        elif gpu["gpu_temp"] >= GPU_WARN and status != CRITICAL:
            status = WARN
    else:
        parts.append("dGPU off/absent")

    bat = psutil.sensors_battery()
    if bat is not None:
        metrics["battery_pct"] = round(bat.percent, 0)
        metrics["on_ac"] = bool(bat.power_plugged)
        parts.append(f"bat {bat.percent:.0f}%{'⚡' if bat.power_plugged else ''}")

    prof = power_profile()
    if prof:
        metrics["power_profile"] = prof
        parts.append(prof)

    return StatusReport(
        prime="micronus", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no sensors readable",
        detail="thermal & power envelope for Primus",
        metrics=metrics, ttl=15,
        actions=["profile_power", "profile_balanced", "profile_performance"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Micronus Prime (thermal & power)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[micronus] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[micronus] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

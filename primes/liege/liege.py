"""Liege Maximo — networking: connectivity, DNS, VPN (Phase 7)."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import psutil

from cyblib import StatusReport, write_status, OK, WARN, CRITICAL

DOMAIN = "NETWORK"
ANCHOR = ("1.1.1.1", 443)


def probe_connectivity() -> tuple[bool, float]:
    """TCP connect probe — no CAP_NET_RAW needed (avoids ICMP)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        t0 = time.time()
        s.connect(ANCHOR)
        lat = (time.time() - t0) * 1000
        s.close()
        return True, round(lat, 1)
    except (OSError, socket.error):
        return False, 0


def dns_mode() -> str:
    try:
        out = subprocess.run(
            ["resolvectl", "status"],
            capture_output=True, text=True, timeout=3,
        )
        if "DNSOverTLS" in out.stdout and "yes" in out.stdout.split("DNSOverTLS")[1][:10]:
            return "dot"
        return "plain"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def vpn_status() -> tuple[bool, str]:
    addrs = psutil.net_if_addrs()
    for iface in addrs:
        if iface.startswith("wg") or iface.startswith("tun"):
            return True, iface
    return False, ""


def build_report() -> StatusReport:
    metrics: dict = {}
    status = OK
    parts: list[str] = []

    online, lat = probe_connectivity()
    metrics["online"] = online
    metrics["latency_ms"] = lat

    if not online:
        status = CRITICAL
        parts.append("OFFLINE")
    else:
        parts.append(f"{lat}ms")

    dns = dns_mode()
    metrics["dns_mode"] = dns
    parts.append(dns)

    vpn_up, vpn_if = vpn_status()
    metrics["vpn_up"] = vpn_up
    metrics["vpn_iface"] = vpn_if
    if vpn_up:
        parts.append(f"VPN {vpn_if}")

    net = psutil.net_io_counters(pernic=True)
    default = psutil.net_if_stats()
    for iface in default:
        if default[iface].isup and iface.startswith(("eth", "enp", "wlp", "wlan")):
            metrics["default_iface"] = iface
            stats = net.get(iface)
            if stats:
                metrics["rx_kbps"] = round(
                    (stats.bytes_recv - getattr(build_report, "_last_rx", 0)) / 1024, 1)
                metrics["tx_kbps"] = round(
                    (stats.bytes_sent - getattr(build_report, "_last_tx", 0)) / 1024, 1)
            break

    return StatusReport(
        prime="liege", domain=DOMAIN, status=status,
        headline=" · ".join(parts) if parts else "no network data",
        detail="network connectivity & privacy for Primus",
        metrics=metrics, ttl=30,
        actions=["vpn_up", "vpn_down"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Liege Maximo (network)")
    ap.add_argument("--once", action="store_true", help="emit one report and exit")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between reports")
    args = ap.parse_args()

    if args.once:
        r = build_report()
        write_status(r)
        print(f"[liege] {r.status.upper()}: {r.headline}")
        return 0

    while True:
        try:
            write_status(build_report())
        except Exception as exc:
            print(f"[liege] cycle error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

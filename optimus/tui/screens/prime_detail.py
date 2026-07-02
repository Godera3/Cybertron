"""Detailed view for a single Prime — lore, metrics, actions, trends."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding

from cyblib import StatusReport, PRIME_REGISTRY, OK, WARN, CRITICAL, STALE, UNKNOWN
from ..poller import snapshot

STATUS_GLYPH = {OK: "\u25cf", WARN: "\u25b2", CRITICAL: "\u2716", STALE: "\u25cc", UNKNOWN: "\u25cb"}

PRIME_LORE: dict[str, dict] = {
    "prima": {
        "title": "Prima \u2014 Keeper of the Matrix",
        "lore": "The first of the Thirteen, Prima was forged by Primus to wield the Star Saber. "
                "As the original bearer of the Matrix of Leadership, he embodies law, order, and protection.",
        "function": "Monitors your system's firewall (UFW), fail2ban intrusion detection, and kernel hardening "
                    "parameters (kptr_restrict, ptrace_scope, syncookies, rp_filter). Reports security drift.",
    },
    "vector": {
        "title": "Vector Prime \u2014 Lord of Time",
        "lore": "Vector Prime is the keeper of the Flow of Time, charged with safeguarding the timestream itself. "
                "He is the wisest and most patient of the Thirteen, watching from the end of all things.",
        "function": "Tracks Timeshift snapshots, systemd timer health, and NTP clock synchronisation. "
                    "Ensures your system's temporal integrity.",
    },
    "alphatrion": {
        "title": "Alpha Trion \u2014 The Chronicler",
        "lore": "Alpha Trion is the oldest living Transformer, the archivist of Cybertron's history. "
                "He maintains the Covenant of Primus and guides those who carry the Matrix.",
        "function": "Monitors journald log size, error/warn rates, and auditd status. "
                    "Keeps your system's story — the logs — healthy and searchable.",
    },
    "solus": {
        "title": "Solus Prime \u2014 The Artisan",
        "lore": "Solus Prime is the creator of the Thirteen's legendary weapons — the Star Saber, "
                "the Forge of Solus Prime, and more. She is the divine smith, patron of makers and craftsmen.",
        "function": "Audits package health: available updates, security patches, phased updates, "
                    "broken dependencies, held packages, and reboot requirements.",
    },
    "micronus": {
        "title": "Micronus Prime \u2014 The Spark",
        "lore": "Micronus Prime is the smallest of the Thirteen, yet his spark burns brightest. "
                "He embodies the essence of life energy and the connection between all beings.",
        "function": "Reads CPU/GPU temperatures, GPU power draw, VRAM usage, and battery status. "
                    "Monitors the thermal and power envelope of Primus.",
    },
    "nexus": {
        "title": "Nexus Prime \u2014 The Connector",
        "lore": "Nexus Prime is the master of combination, the one who unites disparate parts into a greater whole. "
                "He represents synergy and the bonds that make a team stronger than its parts.",
        "function": "Reports Pressure Stall Information (PSI), load averages, memory/swap pressure, "
                    "and process counts. Your system's vital signs.",
    },
    "onyx": {
        "title": "Onyx Prime \u2014 The Beast",
        "lore": "Onyx Prime is the enigmatic Beast Former, master of the Triptych Mask. "
                "He commands the wild forces of nature and walks between worlds.",
        "function": "Reports NVMe SSD health via SMART data: temperature, wear level, spare capacity, "
                    "media errors, and disk usage. Guards your data's physical home.",
    },
    "alchemist": {
        "title": "Alchemist Prime \u2014 The Transmuter",
        "lore": "Alchemist Prime is the scientist and philosopher of the Thirteen. "
                "He experiments with the fundamental forces of reality, seeking truth through transformation.",
        "function": "Samples broad system observability: CPU frequency, memory, swap, process counts, "
                    "zombie processes, and uptime. A general health sampler.",
    },
    "amalgamous": {
        "title": "Amalgamous Prime \u2014 The Shapeshifter",
        "lore": "Amalgamous Prime is the trickster of the Thirteen, able to shift form at will. "
                "Nothing is ever what it seems with Amalgamous, but he always lands on his feet.",
        "function": "Scans for failed systemd units, monitors system state (running/degraded), "
                    "and tracks heal history. The recovery and healing specialist.",
    },
    "quintus": {
        "title": "Quintus Prime \u2014 The Visionary",
        "lore": "Quintus Prime is the dreamer and creator of new life. "
                "He seeded worlds with his visions, for better or worse — the Creator of the Quintessons.",
        "function": "Reports active firejail sandboxes, Linux namespace isolation (mount, net, PID, user). "
                    "Oversees containment and experimental spaces.",
    },
    "liege": {
        "title": "Liege Maximo \u2014 The Deceiver",
        "lore": "Liege Maximo is the silver-tongued manipulator of the Thirteen. "
                "Master of illusion and half-truths, he serves his own agenda above all.",
        "function": "Probes external connectivity (TCP to 1.1.1.1:443), DNS mode (DoT/plain), "
                    "VPN status, interface throughput. The network's truth-teller — or liar.",
    },
    "megatronus": {
        "title": "Megatronus \u2014 The Destroyer",
        "lore": "Megatronus is the most feared of the Thirteen, the warrior of darkness. "
                "His power is destruction itself, and even the other Primes tread carefully around him.",
        "function": "Tracks open security incidents, recent incident history, and nftables blocklist size. "
                    "The last line of defense when all else fails.",
    },
}

METRICS_META: dict[str, tuple[str, str, str]] = {
    "cpu_temp":       ("CPU Temp",          "%.1f",        "\u00b0C"),
    "gpu_temp":       ("GPU Temp",          "%.1f",        "\u00b0C"),
    "gpu_power_w":    ("GPU Power",         "%.0f",        " W"),
    "gpu_util_pct":   ("GPU Util",          "%.0f",        "%%"),
    "vram_used_mb":   ("VRAM Used",         "%.0f",        " MiB"),
    "vram_total_mb":  ("VRAM Total",        "%.0f",        " MiB"),
    "battery_pct":    ("Battery",           "%.0f",        "%%"),
    "on_ac":          ("On AC",             "bool",        ""),
    "power_profile":  ("Power Profile",     "str",         ""),
    "nvme_temp":      ("NVMe Temp",         "%.0f",        "\u00b0C"),
    "pct_used":       ("NVMe Used",         "%.1f",        "%%"),
    "spare":          ("Spare Capacity",    "%.0f",        "%%"),
    "media_errors":   ("Media Errors",      "int",         ""),
    "smart_health":   ("SMART Health",      "str",         ""),
    "disk_pct":       ("Disk /",            "%.1f",        "%%"),
    "inode_pct":      ("Inode /",           "%.1f",        "%%"),
    "root_free_gb":   ("Root Free",         "%.1f",        " GiB"),
    "journal_bytes":  ("Journal Size",      "bytes",       ""),
    "errors_1h":      ("Errors (1h)",       "int",         ""),
    "warns_1h":       ("Warnings (1h)",     "int",         ""),
    "auditd_active":  ("auditd",            "bool",        ""),
    "snapshot_count": ("Snapshots",         "int",         ""),
    "snapshot_age_h": ("Snapshot Age",      "%.1f",        " h"),
    "timers_active":  ("Timers Active",     "int",         ""),
    "timers_failed":  ("Timers Failed",     "int",         ""),
    "clock_synced":   ("NTP Sync",          "bool",        ""),
    "fw_active":      ("UFW Active",        "bool",        ""),
    "fw_rules":       ("FW Rules",          "int",         ""),
    "hardening_drift":("Hardening Drift",   "int",         "/4"),
    "f2b_jails":      ("Fail2ban Jails",    "int",         ""),
    "f2b_banned":     ("Fail2ban Banned",   "int",         ""),
    "psi_cpu":        ("PSI CPU",           "%.2f",        " avg10"),
    "psi_mem":        ("PSI Memory",        "%.2f",        " avg10"),
    "psi_io":         ("PSI I/O",           "%.2f",        " avg10"),
    "load1":          ("Load (1m)",         "%.2f",        ""),
    "mem_pct":        ("Memory",            "%.1f",        "%%"),
    "swap_pct":       ("Swap",              "%.1f",        "%%"),
    "procs":          ("Processes",         "int",         ""),
    "online":         ("Online",            "bool",        ""),
    "latency_ms":     ("Latency",           "%.0f",        " ms"),
    "dns_mode":       ("DNS Mode",          "str",         ""),
    "vpn_up":         ("VPN Up",            "bool",        ""),
    "vpn_iface":      ("VPN Interface",     "str",         ""),
    "default_iface":  ("Default IF",        "str",         ""),
    "rx_kbps":        ("RX Throughput",     "%.0f",        " kb/s"),
    "tx_kbps":        ("TX Throughput",     "%.0f",        " kb/s"),
    "updates_total":  ("Updates Available", "int",         ""),
    "updates_security":("Security Updates", "int",         ""),
    "updates_phased": ("Phased Updates",    "int",         ""),
    "phased_list":    ("Phased Packages",   "list",        ""),
    "broken":         ("Broken Deps",       "int",         ""),
    "held":           ("Held Packages",     "int",         ""),
    "index_age_h":    ("Index Age",         "%.1f",        " h"),
    "reboot_required":("Reboot Required",   "bool",        ""),
    "cpu_pct":        ("CPU",               "%.1f",        "%%"),
    "cpu_freq_mhz":   ("CPU Frequency",     "%.0f",        " MHz"),
    "zombies":        ("Zombie Procs",      "int",         ""),
    "uptime_s":       ("Uptime",            "dur",         ""),
    "failed_count":   ("Failed Units",      "int",         ""),
    "failed_list":    ("Failed List",       "list",        ""),
    "system_state":   ("System State",      "str",         ""),
    "heals_24h":      ("Healed (24h)",      "int",         ""),
    "active_sandboxes":("Active Sandboxes", "int",         ""),
    "ns_mnt":         ("NS Mount",          "int",         ""),
    "ns_net":         ("NS Net",            "int",         ""),
    "ns_pid":         ("NS PID",            "int",         ""),
    "ns_user":        ("NS User",           "int",         ""),
    "open_incidents": ("Open Incidents",    "int",         ""),
    "incidents_24h":  ("Incidents (24h)",   "int",         ""),
    "blocked_ips":    ("Blocked IPs",       "int",         ""),
    "spare_thresh":   ("Spare Threshold",   "%.0f",        "%%"),
    "unsafe_shutdowns":("Unsafe Shutdowns", "int",         ""),
    "crit_warn":      ("Critical Warning",  "int",         ""),
    "power_on_hours": ("Power-On Hours",    "int",         " h"),
    "failed_list":    ("Failed Units",      "list",        ""),
}

ACTION_DESC: dict[str, str] = {
    "profile_power":       "Switch CPU governor to powersave \u2014 reduces energy and heat",
    "profile_balanced":    "Switch CPU governor to balanced \u2014 default performance/energy trade-off",
    "profile_performance": "Switch CPU governor to performance \u2014 maximum speed at higher power cost",
    "fstrim_now":          "Run fstrim on / \u2014 TRIMs unused blocks on your SSD",
    "vacuum":              "Vacuum journald logs older than 7 days \u2014 frees disk space",
    "snapshot_now":        "Create a new Timeshift snapshot \u2014 captures system state now",
    "harden":              "Re-apply kernel hardening sysctls \u2014 tightens security knobs",
    "vpn_up":              "Bring VPN interface up \u2014 (wired to wg0)",
    "vpn_down":            "Bring VPN interface down \u2014 disconnects tunnel",
    "refresh_index":       "Run apt update \u2014 refreshes package index from repositories",
    "fix_broken":          "Run apt --fix-broken install \u2014 repairs broken dependencies",
    "spawn":               "Spawn a firejail sandbox \u2014 launch an isolated shell",
    "reap":                "Reap orphaned sandboxes \u2014 clean up stale firejail instances",
}

TRENDS_DB = Path("/var/lib/cybertron/trends.db")


def _fmt(key: str, val, meta: tuple | None = None) -> str:
    if meta is None:
        meta = METRICS_META.get(key)
    if meta:
        label, fmt_type, unit = meta
    else:
        label, fmt_type, unit = key.replace("_", " ").title(), "str", ""

    if isinstance(val, bool):
        v_str = "\u2713" if val else "\u2717"
    elif fmt_type == "bool":
        v_str = "\u2713" if val else "\u2717"
    elif fmt_type == "int":
        v_str = str(int(val))
    elif fmt_type == "dur":
        h = int(val // 3600)
        m = int((val % 3600) // 60)
        v_str = f"{h}h {m}m"
    elif fmt_type == "bytes":
        b = int(val)
        if b > 1073741824:
            v_str = f"{b / 1073741824:.1f} GiB"
        elif b > 1048576:
            v_str = f"{b / 1048576:.1f} MiB"
        elif b > 1024:
            v_str = f"{b / 1024:.1f} KiB"
        else:
            v_str = f"{b} B"
    elif fmt_type == "list":
        v_str = ", ".join(str(x) for x in val) if val else "\u2014"
    elif isinstance(val, float):
        try:
            v_str = fmt_type % val
        except (TypeError, ValueError):
            v_str = str(val)
    elif val is None:
        v_str = "\u2014"
    else:
        v_str = str(val)

    return label, f"{v_str}{unit}"


def _read_trends(prime_key: str, limit: int = 10) -> list[dict]:
    if not TRENDS_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(TRENDS_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ts, status, headline FROM trends WHERE prime = ? ORDER BY ts DESC LIMIT ?",
            (prime_key, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except (sqlite3.Error, FileNotFoundError):
        return []


class PrimeDetailScreen(Screen):
    AUTO_FOCUS = "#btn-back"
    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("q", "back", "Back", priority=True),
    ]

    def __init__(self, prime_key: str, report: StatusReport | None) -> None:
        super().__init__(id=f"detail-{prime_key}")
        self.prime_key = prime_key
        self.report = report

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="detail-scroll"):
            yield Static(id="detail-banner")
            yield Static(id="detail-lore")
            yield Static(id="detail-metrics")
            yield Static(id="detail-trends")
            yield Static(id="detail-actions")
            yield Button("Back", id="btn-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._rebuild()
        self.set_interval(3.0, self._refresh_report)

    def _refresh_report(self) -> None:
        snap = snapshot()
        self.report = snap["reports"].get(self.prime_key)
        self._rebuild()

    def _rebuild(self) -> None:
        r = self.report
        name, domain = PRIME_REGISTRY.get(self.prime_key, (self.prime_key.upper(), "?"))
        lore = PRIME_LORE.get(self.prime_key)

        # --- Banner ---
        if r is None:
            self.query_one("#detail-banner").update(
                f"[bold]{name}[/bold]  [dim]{domain}[/dim]\n\n"
                f"[red]\u25cf OFFLINE[/red]  [dim]no report data[/dim]"
            )
        else:
            glyph = STATUS_GLYPH.get(r.status, "\u25cb")
            banner = (
                f"[bold]{name}[/bold]  [dim]{domain}[/dim]\n"
                f"[{r.status}]{glyph} {r.status.upper()}[/{r.status}]"
            )
            if r.headline:
                banner += f"  [italic]{r.headline}[/italic]"
            if r.detail:
                banner += f"\n[dim]{r.detail}[/dim]"
            self.query_one("#detail-banner").update(banner)

        # --- Lore ---
        if lore:
            self.query_one("#detail-lore").update(
                f"[bold]{lore['title']}[/bold]\n"
                f"{lore['lore']}\n\n"
                f"[bold]System role:[/bold] {lore['function']}"
            )
        else:
            self.query_one("#detail-lore").update("")

        # --- Metrics ---
        if r and r.metrics:
            rows = []
            for k, v in r.metrics.items():
                label, v_str = _fmt(k, v)
                if v_str.startswith("\u2713"):
                    line = f"  [b]{label}[/b]  [green]{v_str}[/green]"
                elif v_str.startswith("\u2717"):
                    line = f"  [b]{label}[/b]  [red]{v_str}[/red]"
                else:
                    line = f"  [b]{label}[/b]  {v_str}"
                rows.append(line)
            self.query_one("#detail-metrics").update("\n".join(rows))
        else:
            self.query_one("#detail-metrics").update("[dim]No metrics reported[/dim]")

        # --- Trends ---
        trends = _read_trends(self.prime_key, 10)
        if trends:
            trend_lines = []
            for t in trends:
                glyph = STATUS_GLYPH.get(t["status"], "\u25cb")
                ago = time.time() - t["ts"]
                ago_str = f"{ago/60:.0f}m ago" if ago < 3600 else f"{ago/3600:.1f}h ago"
                headline = t.get("headline", "") or "\u2014"
                trend_lines.append(f"  {glyph} [{t['status']}]{headline}[/{t['status']}] [dim]{ago_str}[/dim]")
            self.query_one("#detail-trends").update(
                "[bold]RECENT HISTORY[/bold]\n" + "\n".join(trend_lines)
            )
        else:
            self.query_one("#detail-trends").update("")

        # --- Actions ---
        if r and r.actions:
            action_lines = [
                f"[bold]ACTIONS[/bold]  [dim](clickable once wired to optimusd)[/dim]"
            ]
            for a in r.actions:
                desc = ACTION_DESC.get(a, "")
                action_lines.append(f"  \u25b6 [b]{a}[/b]")
                if desc:
                    action_lines.append(f"    [dim]{desc}[/dim]")
            self.query_one("#detail-actions").update("\n".join(action_lines))
        else:
            self.query_one("#detail-actions").update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.action_back()

    def action_back(self) -> None:
        self.app.pop_screen()

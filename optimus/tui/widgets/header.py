"""Top banner: PRIMUS identity + overall threat + posture."""
from __future__ import annotations
import socket, time
import psutil
from textual.widgets import Static
from cyblib import CALM, GUARDED, ELEVATED, SEVERE, CRIT, AUTOBOT

THREAT_COLOR = {CALM: "green", GUARDED: "cyan", ELEVATED: "yellow",
                SEVERE: "orange1", CRIT: "red"}


def _uptime() -> str:
    s = int(time.time() - psutil.boot_time())
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
    return f"{d}d {h:02d}h {m:02d}m"


class Header(Static):
    def __init__(self) -> None:
        super().__init__(id="hud-header")
        self.host = socket.gethostname()

    def update_aggregate(self, agg: dict) -> None:
        threat = agg.get("threat_level", GUARDED)
        color = THREAT_COLOR.get(threat, "cyan")
        self.update(
            f"[b]PRIMUS[/b] · {self.host} · up {_uptime()}    "
            f"THREAT: [b {color}]{threat.upper()}[/]    "
            f"◈ MATRIX: {agg.get('matrix', '?')}    "
            f"[b]\\[{agg.get('posture', AUTOBOT).upper()}][/b]    "
            f"alerts: {agg.get('active_alerts', 0)}"
        )

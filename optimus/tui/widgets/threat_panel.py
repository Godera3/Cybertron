"""The Unicron panel — active threats + system 'entropy' indicators."""
from __future__ import annotations
import os, time
import psutil
from textual.widgets import Static

SEV_COLOR = {"critical": "red", "warn": "yellow", "info": "cyan"}


def _psi(kind: str) -> float | None:
    try:
        with open(f"/proc/pressure/{kind}") as fh:
            for line in fh:
                if line.startswith("some"):
                    for tok in line.split():
                        if tok.startswith("avg10="):
                            return float(tok.split("=")[1])
    except (FileNotFoundError, PermissionError, ValueError):
        return None
    return None


def _entropy_line() -> str:
    load = os.getloadavg()[0]
    mp = _psi("memory")
    mem = f"{mp:.0f}%" if mp is not None else f"{psutil.virtual_memory().percent:.0f}%*"
    return f"entropy: load {load:.1f} · mem-PSI {mem} · disk {psutil.disk_usage('/').percent:.0f}%"


class ThreatPanel(Static):
    def __init__(self) -> None:
        super().__init__(id="threat-panel")
        self._alerts: list = []
        self._rebuild()

    def set_alerts(self, alerts: list) -> None:
        self._alerts = alerts[:6]; self._rebuild()

    def add_alert(self, alert) -> None:
        self._alerts.insert(0, alert); self._alerts = self._alerts[:6]; self._rebuild()

    def _rebuild(self) -> None:
        lines = ["[b]UNICRON[/b] — active threats"]
        if not self._alerts:
            lines.append("[dim]all quiet · no threats detected[/dim]")
        else:
            for a in self._alerts:
                c = SEV_COLOR.get(getattr(a, "severity", "info"), "cyan")
                ts = time.strftime("%H:%M", time.localtime(getattr(a, "ts", time.time())))
                lines.append(f"[{c}]{ts} {getattr(a, 'title', str(a))}[/{c}]")
        lines += ["", f"[dim]{_entropy_line()}[/dim]"]
        self.update("\n".join(lines))

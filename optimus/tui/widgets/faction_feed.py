"""A short scrolling log of faction activity and operator actions."""
from __future__ import annotations
import time
from textual.widgets import Static


class FactionFeed(Static):
    MAX = 8

    def __init__(self) -> None:
        super().__init__(id="faction-feed")
        self._lines: list[str] = []
        self.log_event("Optimus online — the Matrix stirs")

    def log_event(self, text: str, faction: str = "autobot") -> None:
        color = {"autobot": "cyan", "decepticon": "magenta", "dinobot": "orange1",
                 "maximal": "green", "predacon": "red"}.get(faction, "white")
        self._lines.insert(0, f"[dim]{time.strftime('%H:%M')}[/dim] [{color}]{text}[/{color}]")
        self._lines = self._lines[: self.MAX]
        self.update("[b]FACTION ACTIVITY[/b]\n" + "\n".join(self._lines))

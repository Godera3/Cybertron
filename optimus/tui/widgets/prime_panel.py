"""A single Prime tile in the HUD grid."""
from __future__ import annotations
from textual.widgets import Static
from cyblib import PRIME_REGISTRY, UNKNOWN, OK, WARN, CRITICAL, STALE

GLYPH = {OK: "●", WARN: "▲", CRITICAL: "✖", STALE: "◌", UNKNOWN: "○"}


class PrimePanel(Static):
    def __init__(self, prime_key: str) -> None:
        super().__init__(id=f"prime-{prime_key}", classes="prime-panel status-unknown")
        self.prime_key = prime_key
        self.display_name, self.domain = PRIME_REGISTRY[prime_key]
        self._rebuild(UNKNOWN, "not yet online")

    def _rebuild(self, status: str, headline: str) -> None:
        glyph = GLYPH.get(status, "○")
        self.update(f"[b]{self.display_name}[/b]\n{glyph} {self.domain}\n{headline}")
        for st in (OK, WARN, CRITICAL, STALE, UNKNOWN):
            self.remove_class(f"status-{st}")
        self.add_class(f"status-{status}")

    def update_report(self, report) -> None:
        if report is None:
            self._rebuild(UNKNOWN, "not yet online")
        else:
            self._rebuild(report.status, report.headline or "—")

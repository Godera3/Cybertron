"""A single Prime tile in the HUD grid."""
from __future__ import annotations
from textual.widgets import Static
from cyblib import PRIME_REGISTRY, UNKNOWN, OK, WARN, CRITICAL, STALE

GLYPH = {OK: "\u25cf", WARN: "\u25b2", CRITICAL: "\u2716", STALE: "\u25cc", UNKNOWN: "\u25cb"}

STATUS_DOMAIN = {
    "micronus":   "thermal/power",
    "onyx":       "storage",
    "alphatrion": "logging",
    "vector":     "temporal",
    "prima":      "security",
    "nexus":      "resources",
    "liege":      "network",
    "solus":      "packages",
    "alchemist":  "observability",
    "amalgamous": "recovery",
    "quintus":    "sandbox",
    "megatronus": "response",
}


class PrimePanel(Static):
    can_focus = True

    def __init__(self, prime_key: str) -> None:
        super().__init__(id=f"prime-{prime_key}", classes="prime-panel status-unknown")
        self.prime_key = prime_key
        self.display_name, _ = PRIME_REGISTRY[prime_key]
        self.domain = STATUS_DOMAIN.get(prime_key, "")
        self._last_report = None
        self._rebuild(UNKNOWN, "not yet online")

    def _rebuild(self, status: str, headline: str) -> None:
        glyph = GLYPH.get(status, "\u25cb")
        self.update(
            f"[b]{self.display_name}[/b]\n[{status}]{glyph}[/{status}] "
            f"[dim]{self.domain}[/dim]\n{headline}"
        )
        for st in (OK, WARN, CRITICAL, STALE, UNKNOWN):
            self.remove_class(f"status-{st}")
        self.add_class(f"status-{status}")

    def _on_key(self, event) -> None:
        if event.key in ("enter", "space"):
            event.stop()
            self.app.action_open_detail(self.prime_key)

    def update_report(self, report) -> None:
        self._last_report = report
        if report is None:
            self._rebuild(UNKNOWN, "not yet online")
        else:
            self._rebuild(report.status, report.headline or "\u2014")

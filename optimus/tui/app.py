"""optimus — the live HUD (Phase 1 centerpiece).

Run:  optimus     (or:  python -m optimus.tui.app)
"""
from __future__ import annotations
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer

from cyblib import PRIME_ORDER, AUTOBOT, DECEPTICON
from .widgets import PrimePanel, Header, ThreatPanel, FactionFeed
from . import poller, watcher, control


class OptimusApp(App):
    CSS_PATH = "optimus.tcss"
    TITLE = "OPTIMUS · Cybertron HUD"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_posture", "Posture"),
        Binding("m", "decepticon_hunt", "Hunt"),
        Binding("d", "dinobots", "Dinobots"),
        Binding("r", "refresh_now", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._panels: dict[str, PrimePanel] = {}
        self._stop = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="prime-grid"):
            for key in PRIME_ORDER:
                self._panels[key] = PrimePanel(key)
                yield self._panels[key]
        with Horizontal(id="bottom"):
            yield ThreatPanel()
            yield FactionFeed()
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.5, self.refresh_data)
        self.refresh_data()
        self.run_worker(self._run_alert_watcher, thread=True, name="alert-watcher")

    def on_unmount(self) -> None:
        self._stop.set()

    def _run_alert_watcher(self) -> None:
        watcher.run(lambda a: self.call_from_thread(self._on_alert, a), self._stop)

    def refresh_data(self) -> None:
        snap = poller.snapshot()
        self.query_one(Header).update_aggregate(snap["aggregate"])
        for key, panel in self._panels.items():
            panel.update_report(snap["reports"].get(key))

    def _on_alert(self, alert) -> None:
        self.query_one(ThreatPanel).add_alert(alert)
        self.query_one(FactionFeed).log_event(
            f"{getattr(alert, 'source', '?')} raised: {getattr(alert, 'title', '')}",
            getattr(alert, "faction", "decepticon"))

    def action_toggle_posture(self) -> None:
        cur = poller.snapshot()["aggregate"].get("posture")
        new = DECEPTICON if cur == AUTOBOT else AUTOBOT
        resp = control.send_command(f"posture:set {new}")
        if resp.get("ok"):
            self.query_one(FactionFeed).log_event(f"posture → {new.upper()}", new)
            self.refresh_data()
        else:
            self.query_one(FactionFeed).log_event(
                f"posture change failed: {resp.get('error')}", "decepticon")

    def action_decepticon_hunt(self) -> None:
        self.query_one(FactionFeed).log_event(
            "Decepticon hunt requested (wired in Phase F)", "decepticon")

    def action_dinobots(self) -> None:
        self.query_one(FactionFeed).log_event(
            "Dinobots summoned (wired in Phase D)", "dinobot")

    def action_refresh_now(self) -> None:
        self.refresh_data()


def main() -> int:
    OptimusApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

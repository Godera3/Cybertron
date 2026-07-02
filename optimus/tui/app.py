"""optimus — the live HUD (Phase 1 centerpiece).

Run:  optimus     (or:  python -m optimus.tui.app)
"""
from __future__ import annotations
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.events import Click
from textual.widgets import Footer
from textual import on

from cyblib import PRIME_ORDER, AUTOBOT, DECEPTICON
from .widgets import PrimePanel, Header, ThreatPanel, FactionFeed
from . import poller, watcher, control
from .screens import PrimeDetailScreen


class OptimusApp(App):
    CSS_PATH = "optimus.tcss"
    TITLE = "OPTIMUS · Cybertron HUD"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_posture", "Posture"),
        Binding("m", "decepticon_hunt", "Hunt"),
        Binding("d", "dinobots", "Dinobots"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("up", "grid_up", "Up", show=False),
        Binding("down", "grid_down", "Down", show=False),
        Binding("left", "grid_left", "Left", show=False),
        Binding("right", "grid_right", "Right", show=False),
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

    @on(Click, ".prime-panel")
    def on_prime_panel_click(self, event: Click) -> None:
        widget = event.widget
        if isinstance(widget, PrimePanel):
            self.push_screen(PrimeDetailScreen(widget.prime_key, widget._last_report))

    def action_toggle_posture(self) -> None:
        cur = poller.snapshot()["aggregate"].get("posture")
        new = DECEPTICON if cur == AUTOBOT else AUTOBOT
        resp = control.send_command(f"posture:set {new}")
        if resp.get("ok"):
            self.query_one(FactionFeed).log_event(f"posture \u2192 {new.upper()}", new)
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

    def _focus_index(self, i: int) -> None:
        if 0 <= i < len(PRIME_ORDER):
            self._panels[PRIME_ORDER[i]].focus()

    def action_grid_up(self) -> None:
        cur = self._current_focus_index()
        if cur is not None:
            self._focus_index(cur - 4)

    def action_grid_down(self) -> None:
        cur = self._current_focus_index()
        if cur is not None:
            self._focus_index(cur + 4)

    def action_grid_left(self) -> None:
        cur = self._current_focus_index()
        if cur is not None:
            row_start = (cur // 4) * 4
            self._focus_index(cur - 1 if cur > row_start else cur)

    def action_grid_right(self) -> None:
        cur = self._current_focus_index()
        if cur is not None:
            row_end = (cur // 4) * 4 + 3
            self._focus_index(cur + 1 if cur < row_end else cur)

    def _current_focus_index(self) -> int | None:
        focused = self.focused
        if focused is None or not isinstance(focused, PrimePanel):
            return 0
        return PRIME_ORDER.index(focused.prime_key) if focused.prime_key in PRIME_ORDER else None

    def action_open_detail(self, prime_key: str) -> None:
        self.push_screen(PrimeDetailScreen(prime_key, self._panels[prime_key]._last_report))

    def action_refresh_now(self) -> None:
        self.refresh_data()


def main() -> int:
    OptimusApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

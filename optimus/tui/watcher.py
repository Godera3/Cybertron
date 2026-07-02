"""Bridges cyblib.watch_alerts into the Textual app."""
from __future__ import annotations
import threading
from typing import Callable
from cyblib import watch_alerts, Alert


def run(on_alert: Callable[[Alert], None], stop_event: threading.Event) -> None:
    for alert in watch_alerts(stop=stop_event.is_set):
        on_alert(alert)
        if stop_event.is_set():
            break

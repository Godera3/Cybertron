"""cyblib — the shared contract library for Project Cybertron."""
from . import paths, schema, status, alerts
from .schema import (
    StatusReport, Alert, PRIME_REGISTRY, PRIME_ORDER,
    OK, WARN, CRITICAL, STALE, UNKNOWN, STATUS_RANK,
    CALM, GUARDED, ELEVATED, SEVERE, CRIT, THREAT_ORDER,
    AUTOBOT, DECEPTICON,
)
from .status import write_status, read_status, read_all
from .alerts import emit_alert, list_alerts, clear_alert, watch_alerts

__version__ = "0.1.0"

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

OK = "ok"; WARN = "warn"; CRITICAL = "critical"; STALE = "stale"; UNKNOWN = "unknown"
STATUS_RANK = {UNKNOWN: 0, OK: 1, STALE: 2, WARN: 3, CRITICAL: 4}

CALM = "calm"; GUARDED = "guarded"; ELEVATED = "elevated"; SEVERE = "severe"; CRIT = "critical"
THREAT_ORDER = [CALM, GUARDED, ELEVATED, SEVERE, CRIT]

AUTOBOT = "autobot"; DECEPTICON = "decepticon"

PRIME_REGISTRY: dict[str, tuple[str, str]] = {
    "prima":      ("Prima",        "SECURITY"),
    "vector":     ("Vector Prime", "TEMPORAL"),
    "alphatrion": ("Alpha Trion",  "LOGGING"),
    "solus":      ("Solus Prime",  "PACKAGES"),
    "micronus":   ("Micronus",     "THERMAL/POWER"),
    "nexus":      ("Nexus Prime",  "RESOURCES"),
    "onyx":       ("Onyx Prime",   "STORAGE"),
    "alchemist":  ("Alchemist",    "OBSERVABILITY"),
    "amalgamous": ("Amalgamous",   "RECOVERY"),
    "quintus":    ("Quintus",      "SANDBOX"),
    "liege":      ("Liege Maximo", "NETWORK"),
    "megatronus": ("Megatronus",   "RESPONSE"),
}
PRIME_ORDER = list(PRIME_REGISTRY.keys())


@dataclass
class StatusReport:
    prime: str
    domain: str
    status: str = UNKNOWN
    headline: str = ""
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    posture: str = AUTOBOT
    ts: float = field(default_factory=time.time)
    ttl: int = 15
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StatusReport":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def is_stale(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now > (self.ts + self.ttl)


@dataclass
class Alert:
    source: str
    faction: str
    severity: str
    title: str
    body: str = ""
    id: str = ""
    ts: float = field(default_factory=time.time)
    suggested_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Alert":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

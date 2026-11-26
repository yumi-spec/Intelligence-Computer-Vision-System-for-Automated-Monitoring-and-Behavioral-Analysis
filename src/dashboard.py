
"""Alert handling for the Milkfish Monitoring Dashboard."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


KIND_LABEL = {
    "normal": "Normal Movement",
    "unusual": "Unusual Swimming Activity",
    "erratic": "Erratic Movement Suspected",
    "low_oxygen": "Possible Low Oxygen",
    "no_fish": "No Fish Detected",
    "insufficient": "Insufficient Tracking Data",
}


@dataclass
class Alert:
    ts: float
    kind: str
    level: str
    message: str


class AlertManager:

    def __init__(self, settings: Any, max_recent: int = 200):
        self.settings = settings
        self.recent = deque(maxlen=max_recent)
        self._condition_since = None
        self._last_alert_at = 0.0
        self._last_kind = None

    def check(self, snap: Any, now: float):
        kind = str(getattr(snap, "kind", "") or "")
        unusual_count = int(getattr(snap, "unusual", 0) or 0)
        level = str(getattr(snap, "level", "ok") or "ok")

        condition = (
            kind in {"unusual", "erratic", "low_oxygen"}
            or (
                unusual_count > 0
                and level in {"warning", "critical"}
            )
        )

        if not condition:
            self._condition_since = None
            self._last_kind = None
            return None

        if (
            self._condition_since is None
            or self._last_kind != kind
        ):
            self._condition_since = float(now)
            self._last_kind = kind

        confirm_s = max(
            0.0,
            float(getattr(self.settings, "alert_confirm_s", 3))
        )

        cooldown_s = max(
            0.0,
            float(getattr(self.settings, "alert_cooldown_s", 60))
        )

        if float(now) - self._condition_since < confirm_s:
            return None

        if float(now) - self._last_alert_at < cooldown_s:
            return None

        if kind not in KIND_LABEL:
            kind = "unusual"

        message = str(
            getattr(snap, "description", "")
            or "Unusual swimming activity was observed in the analyzed video."
        )

        alert = Alert(
            ts=float(now),
            kind=kind,
            level=(
                "critical"
                if level == "critical"
                else "warning"
            ),
            message=message,
        )

        self.recent.append(alert)
        self._last_alert_at = float(now)

        return alert

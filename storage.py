"""Tiny CSV logging helpers."""
from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Iterable

METRICS_HEADER = ["timestamp", "count", "avg_speed", "cohesion", "fps",
                  "normal", "schooling", "feeding", "unusual", "status"]
ALERTS_HEADER = ["timestamp", "level", "kind", "message", "sms"]

# The live loop (metrics.csv, alerts.csv) and the SMS thread (alerts.csv) can write at the same
# time; one lock keeps rows from interleaving and the header from being written twice.
_LOCK = threading.Lock()


def append_row(path: Path, header: Iterable[str], row: Iterable) -> None:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(list(header))
            w.writerow(list(row))
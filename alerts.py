"""Alert logic (debounce + cooldown) and optional SMS delivery.

SMS is off unless you enable it in Settings AND configure a provider in .env.
Supported providers: Twilio and Semaphore (Philippines). Add another by writing
one more branch in SmsSender.send().
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional

from src import db
from src.config import ROOT

try:  # optional
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ABNORMAL = {"unusual", "no_fish"}
LEVEL_RANK = {"warning": 1, "critical": 2}

# Cautious wording used in the alert log and SMS: unusual swimming seen in video is an observation,
# not a diagnosis. "erratic" and "low_oxygen" are kept only so older log rows still get a label.
KIND_LABEL = {
    "unusual": "Unusual Swimming Activity",
    "no_fish": "No Fish Detected",
    "erratic": "Erratic Movement",
    "low_oxygen": "Low-Oxygen",
}
KIND_ACTION = {
    "unusual": "Inspect the fingerlings and pond conditions",
}


@dataclass
class Alert:
    ts: float
    level: str
    kind: str
    message: str
    sms: str = "off"  # off | sending | sent | failed


class SmsSender:
    def __init__(self, recipients_text: str = ""):
        raw = recipients_text.strip() or os.getenv("SMS_RECIPIENTS", "")
        self.recipients: List[str] = [r.strip() for r in raw.split(",") if r.strip()]
        self.provider = os.getenv("SMS_PROVIDER", "none").strip().lower()

    @property
    def ready(self) -> bool:
        return self.provider in ("twilio", "semaphore") and bool(self.recipients)

    def send(self, text: str) -> bool:
        import requests

        try:
            if self.provider == "twilio":
                sid, token = os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")
                sender = os.getenv("TWILIO_FROM", "")
                ok = True
                for to in self.recipients:
                    r = requests.post(
                        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                        data={"To": to, "From": sender, "Body": text}, auth=(sid, token), timeout=10)
                    ok = ok and r.status_code < 300
                return ok
            if self.provider == "semaphore":
                payload = {"apikey": os.getenv("SEMAPHORE_API_KEY", ""),
                           "number": ",".join(self.recipients), "message": text}
                if os.getenv("SEMAPHORE_SENDER"):
                    payload["sendername"] = os.getenv("SEMAPHORE_SENDER")
                r = requests.post("https://api.semaphore.co/api/v4/messages", data=payload, timeout=10)
                return r.status_code < 300
        except Exception:
            return False
        return False


class AlertManager:
    def __init__(self, settings):
        self.s = settings
        self.recent: Deque[Alert] = deque(maxlen=20)
        self._since: Dict[str, float] = {}
        self._last_fired: Dict[str, float] = {}

    def check(self, snap, now: Optional[float] = None) -> Optional[Alert]:
        now = time.time() if now is None else now
        kind = snap.kind
        for k in list(self._since):          # condition cleared -> restart its timer
            if k != kind:
                del self._since[k]
        if kind not in ABNORMAL:
            return None
        since = self._since.setdefault(kind, now)
        if now - since < self.s.alert_confirm_s:
            return None
        if now - self._last_fired.get(kind, -1e12) < self.s.alert_cooldown_s:
            return None
        self._last_fired[kind] = now

        label = KIND_LABEL.get(kind, snap.status)
        action = KIND_ACTION.get(kind, snap.action)
        text = f"{label}: {snap.description}"
        alert = Alert(now, snap.level, kind, text)
        self.recent.appendleft(alert)

        wants_sms = (self.s.sms_enabled and kind != "no_fish"
                     and LEVEL_RANK.get(snap.level, 0) >= LEVEL_RANK.get(self.s.sms_min_level, 1))
        if wants_sms:
            sender = SmsSender(self.s.sms_recipients)
            if sender.ready:
                alert.sms = "sending"
                body = f"[Milkfish Monitor  {datetime.fromtimestamp(now):%H:%M}] {text} Action: {action}."
                # the SMS thread writes the single log row once the final result is known
                threading.Thread(target=self._send, args=(sender, body, alert), daemon=True).start()
                return alert
            alert.sms = "failed"  # enabled but provider/recipients not configured
        self._log(alert)
        return alert

    def _send(self, sender: SmsSender, body: str, alert: Alert) -> None:
        alert.sms = "sent" if sender.send(body) else "failed"
        self._log(alert)

    @staticmethod
    def _log(alert: Alert) -> None:
        """One database row per alert, saved with its final SMS status (off | sent | failed)."""
        db.add_alert(datetime.fromtimestamp(alert.ts).strftime("%Y-%m-%d %H:%M:%S"),
                     alert.level, alert.kind, alert.message, alert.sms)
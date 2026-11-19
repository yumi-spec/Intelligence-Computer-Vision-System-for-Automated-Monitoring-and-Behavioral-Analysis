"""Behavior analysis: per-fish speed / heading / turns, school cohesion, and rule-based classification
into four behaviors: Normal Swimming, Schooling, Feeding Activity and Unusual Swimming.

All thresholds are pixel-based heuristics, so they must be calibrated against your own camera and footage
(and checked against manually annotated video) before being trusted. The core thresholds live in Settings
(config.py). The newer ones (schooling, feeding, inactivity, isolation) are read with getattr(), so they use the
defaults below unless you add them to Settings.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

ARROWS = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]
HIST_SECONDS = 4.0     # how much position history is kept per fish
WARMUP_SECONDS = 2.0   # need this much history before judging behavior

# ---- defaults for the four-behavior rules (distances are fractions of the frame diagonal) ----
SCHOOL_RADIUS = 0.12       # neighbours this close can form a school
SCHOOL_MIN_FISH = 3        # fish needed (including itself) that move together
SCHOOL_ALIGN_DEG = 35.0    # headings within this angle count as "same direction"
SCHOOL_SPEED_RATIO = 2.0   # speeds within this ratio count as "similar speed"
FEEDING_RADIUS = 0.08      # tighter gathering than schooling
FEEDING_MIN_FISH = 4       # fish needed (including itself) in the gathering
FEEDING_ZONE = 0.0         # top fraction of the frame where feeding happens (0 = anywhere)
FEEDING_MAX_POLARIZATION = 0.6   # gathering fish heading every which way (milling) = below this
INACTIVE_SECS = 10.0       # a fish that barely moves this long counts as unusual
ISOLATION_FRAC = 0.35      # a fish this far from every other fish counts as separated from the group
GROUP_SHARE = 0.40         # share of fish needed to call the whole school "Schooling" or "Feeding"

STATUSES = ("Normal", "Schooling", "Feeding", "Unusual")


@dataclass
class FishState:
    id: int
    bbox: tuple
    conf: float
    speed: float
    arrow: str
    status: str          # "Normal" | "Schooling" | "Feeding" | "Unusual"
    active: bool
    turn_rate: float
    note: str = ""       # why a fish was called Unusual


@dataclass
class Snapshot:
    fish: List[FishState] = field(default_factory=list)
    count: int = 0
    avg_speed: float = 0.0
    cohesion: Optional[float] = None
    active: int = 0
    inactive: int = 0
    normal: int = 0
    schooling: int = 0
    feeding: int = 0
    unusual: int = 0
    erratic: int = 0         # kept for older code: same as `unusual`
    low_oxygen: int = 0      # kept for older code: always 0 (low oxygen is no longer judged from video)
    kind: str = "idle"       # idle | warming | normal | schooling | feeding | unusual | no_fish
    status: str = "Waiting for video"
    level: str = "ok"        # ok | warning
    description: str = "Start monitoring to see live behavior analysis."
    action: str = "Press Start to begin"
    action_detail: str = "Monitoring is currently stopped."
    details: Dict[str, str] = field(default_factory=lambda: {
        "Movement Pattern": "—", "Speed Trend": "—", "Direction Changes": "—", "Schooling": "—"})


def _heading_arrow(dx: float, dy: float) -> str:
    angle = math.degrees(math.atan2(-dy, dx)) % 360  # screen y points down
    return ARROWS[int(round(angle / 45.0)) % 8]


def _speed(dq: deque, t: float):
    """Net displacement over the last second -> (px/s, (dx, dy) or None)."""
    ref = None
    for p in dq:
        if p[0] >= t - 1.0:
            ref = p
            break
    if ref is None or ref is dq[-1]:
        return 0.0, None
    dt = dq[-1][0] - ref[0]
    if dt < 0.4:
        return 0.0, None
    dx, dy = dq[-1][1] - ref[1], dq[-1][2] - ref[2]
    return math.hypot(dx, dy) / dt, (dx, dy)


def _turn_rate(dq: deque, min_speed: float, angle_deg: float) -> float:
    """Sharp turns per second, measured on points resampled every 0.5 s."""
    if len(dq) < 3:
        return 0.0
    pts = [dq[0]]
    for p in dq:
        if p[0] - pts[-1][0] >= 0.5:
            pts.append(p)
    span = pts[-1][0] - pts[0][0]
    if len(pts) < 3 or span < 1.5:
        return 0.0
    headings = []
    for a, b in zip(pts[:-1], pts[1:]):
        dt = b[0] - a[0]
        dx, dy = b[1] - a[1], b[2] - a[2]
        if math.hypot(dx, dy) / dt >= min_speed:
            headings.append(math.atan2(dy, dx))
    turns = 0
    for h1, h2 in zip(headings[:-1], headings[1:]):
        d = abs((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)
        if math.degrees(d) >= angle_deg:
            turns += 1
    return turns / span


class BehaviorAnalyzer:
    def __init__(self, settings):
        self.s = settings
        self.reset()

    def reset(self) -> None:
        self.hist: Dict[int, deque] = {}
        self.last_seen: Dict[int, float] = {}
        self.still_since: Dict[int, float] = {}
        self.speed_hist: deque = deque()
        self.t_first: Optional[float] = None

    def _p(self, name: str, default):
        return getattr(self.s, name, default)

    # ------------------------------------------------------------------
    def update(self, tracks, t: float, frame_shape) -> Snapshot:
        s = self.s
        h, w = frame_shape[:2]
        if self.t_first is None:
            self.t_first = t
        warm = (t - self.t_first) < WARMUP_SECONDS

        raw = []
        seen = set()
        for tr in tracks:
            x1, y1, x2, y2 = tr.bbox
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            dq = self.hist.setdefault(tr.id, deque())
            if dq:
                if t <= dq[-1][0]:
                    continue
                cx, cy = 0.5 * cx + 0.5 * dq[-1][1], 0.5 * cy + 0.5 * dq[-1][2]  # smooth jitter
            dq.append((t, cx, cy))
            while dq and dq[0][0] < t - HIST_SECONDS:
                dq.popleft()
            seen.add(tr.id)
            self.last_seen[tr.id] = t

            speed, vec = _speed(dq, t)
            active = speed >= s.active_speed
            arrow = _heading_arrow(*vec) if (active and vec) else "—"
            unit = None
            if active and vec:
                n = math.hypot(*vec)
                unit = (vec[0] / n, vec[1] / n)
            turn_rate = _turn_rate(dq, s.active_speed, s.turn_angle_deg)

            if not warm:  # remember since when a fish has barely been moving
                if active:
                    self.still_since.pop(tr.id, None)
                else:
                    self.still_since.setdefault(tr.id, t)

            raw.append({"id": tr.id, "bbox": tr.bbox, "conf": tr.conf, "cx": cx, "cy": cy, "speed": speed,
                        "arrow": arrow, "unit": unit, "active": active, "turn": turn_rate})

        for fid in [i for i in self.hist if i not in seen and t - self.last_seen.get(i, t) > 3.0]:
            self.hist.pop(fid, None)
            self.last_seen.pop(fid, None)
            self.still_since.pop(fid, None)

        fish = self._classify(raw, t, warm, (w, h))
        points = [(r["cx"], r["cy"]) for r in raw]
        unit_vecs = [r["unit"] for r in raw if r["unit"] is not None]
        return self._summarise(fish, points, unit_vecs, t, (w, h), warm)

    # ------------------------------------------------------------------
    def _classify(self, raw: list, t: float, warm: bool, size) -> List[FishState]:
        """Rule-based behavior per fish. Priority: Unusual > Feeding > Schooling > Normal."""
        s = self.s
        w, h = size
        n = len(raw)
        if n == 0:
            return []
        diag = math.hypot(w, h)
        school_r = self._p("school_radius", SCHOOL_RADIUS) * diag
        feed_r = self._p("feeding_radius", FEEDING_RADIUS) * diag
        school_min = int(self._p("school_min_fish", SCHOOL_MIN_FISH))
        feed_min = int(self._p("feeding_min_fish", FEEDING_MIN_FISH))
        align_cos = math.cos(math.radians(self._p("school_align_deg", SCHOOL_ALIGN_DEG)))
        ratio = float(self._p("school_speed_ratio", SCHOOL_SPEED_RATIO))
        zone = self._p("feeding_zone", FEEDING_ZONE)
        inactive_s = self._p("inactive_secs", INACTIVE_SECS)
        isolation = self._p("isolation_frac", ISOLATION_FRAC) * diag

        pts = np.array([[r["cx"], r["cy"]] for r in raw])
        d = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
        np.fill_diagonal(d, np.inf)
        nearest = d.min(axis=1)

        out = []
        for i, r in enumerate(raw):
            status, note = "Normal", ""
            if not warm:
                if r["speed"] >= s.erratic_speed or r["turn"] >= s.erratic_turn_rate:
                    status, note = "Unusual", "sudden speed or direction changes"
                elif t - self.still_since.get(r["id"], t) >= inactive_s:
                    status, note = "Unusual", "long inactivity"
                elif n >= 4 and nearest[i] > isolation:
                    status, note = "Unusual", "separated from the group"
                elif r["unit"] is not None:
                    # feeding: a tight gathering (in the feeding zone, if set) whose fish head every which way
                    close = [j for j in np.where(d[i] <= feed_r)[0]]
                    if (zone <= 0 or r["cy"] < h * zone) and len(close) + 1 >= feed_min:
                        vecs = [raw[j]["unit"] for j in close if raw[j]["unit"] is not None] + [r["unit"]]
                        if float(np.linalg.norm(np.mean(vecs, axis=0))) < FEEDING_MAX_POLARIZATION:
                            status = "Feeding"
                    # schooling: close neighbours swimming in the same direction at a similar speed
                    if status == "Normal":
                        mates = 0
                        for j in np.where(d[i] <= school_r)[0]:
                            u = raw[j]["unit"]
                            if u is None:
                                continue
                            cos = u[0] * r["unit"][0] + u[1] * r["unit"][1]
                            q = raw[j]["speed"] / r["speed"] if r["speed"] > 0 else 0.0
                            if cos >= align_cos and 1.0 / ratio <= q <= ratio:
                                mates += 1
                        if mates + 1 >= school_min:
                            status = "Schooling"
            out.append(FishState(r["id"], r["bbox"], r["conf"], r["speed"], r["arrow"], status,
                                 r["active"], r["turn"], note))
        return out

    # ------------------------------------------------------------------
    def _summarise(self, fish, points, unit_vecs, t, size, warm) -> Snapshot:
        s = self.s
        n = len(fish)
        snap = Snapshot(fish=fish, count=n)
        snap.active = sum(f.active for f in fish)
        snap.inactive = n - snap.active
        snap.normal = sum(f.status == "Normal" for f in fish)
        snap.schooling = sum(f.status == "Schooling" for f in fish)
        snap.feeding = sum(f.status == "Feeding" for f in fish)
        snap.unusual = sum(f.status == "Unusual" for f in fish)
        snap.erratic = snap.unusual
        snap.low_oxygen = 0
        snap.avg_speed = float(np.mean([f.speed for f in fish])) if n else 0.0

        # trend of the school's average speed (last 5 s vs the 5 s before); the warm-up
        # ramp (speeds still building from zero) is left out so it can't fake a trend
        if not warm:
            self.speed_hist.append((t, snap.avg_speed))
        while self.speed_hist and self.speed_hist[0][0] < t - 10.0:
            self.speed_hist.popleft()
        recent = [v for ts, v in self.speed_hist if ts >= t - 5.0]
        prev = [v for ts, v in self.speed_hist if ts < t - 5.0]
        trend = "Stable"
        if recent and prev:
            r, p = float(np.mean(recent)), float(np.mean(prev))
            if abs(r - p) > 0.5 * s.active_speed and abs(r - p) > 0.2 * max(p, 1e-6):
                trend = "Increasing" if r > p else "Decreasing"

        # cohesion: closeness of neighbours (+ heading alignment when fish are moving)
        if n >= 2:
            pts = np.array(points)
            d = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
            np.fill_diagonal(d, np.inf)
            diag = math.hypot(*size)
            proximity = float(np.clip(1.0 - d.min(axis=1).mean() / (0.25 * diag), 0.0, 1.0))
            if len(unit_vecs) >= 2:
                polarization = float(np.linalg.norm(np.mean(unit_vecs, axis=0)))
                snap.cohesion = 100.0 * (0.5 * proximity + 0.5 * polarization)
            else:
                snap.cohesion = 100.0 * proximity
        school = "N/A"
        if snap.cohesion is not None:
            school = "Maintained" if snap.cohesion >= 60 else "Loosening" if snap.cohesion >= 30 else "Dispersed"

        mean_turn = float(np.mean([f.turn_rate for f in fish])) if n else 0.0
        turns = ("Low" if mean_turn < 0.3 * s.erratic_turn_rate
                 else "Moderate" if mean_turn < s.erratic_turn_rate else "High")

        enough = n >= s.min_fish_alert
        u_frac = snap.unusual / n if n else 0.0
        group = self._p("group_share", GROUP_SHARE)

        if n == 0:
            snap.kind, snap.level, snap.status = "no_fish", "warning", "No Fish Detected"
            snap.description = "No milkfish detected in view. Check the camera, lighting or water clarity."
            snap.action, snap.action_detail = "Check Camera View", "Confirm the camera is clear and the pond is in frame."
            pattern = "—"
        elif enough and u_frac >= s.abnormal_fraction:
            snap.kind, snap.level, snap.status = "unusual", "warning", "Unusual Swimming Activity"
            snap.description = (f"{snap.unusual} of {n} milkfish ({u_frac:.0%}) show unusual swimming "
                                "(sudden speed or direction changes, long inactivity, or separation from the "
                                "group). This is a video-based observation, not a disease diagnosis.")
            snap.action, snap.action_detail = "Inspect the Pond", "Inspect the fingerlings and pond conditions."
            pattern = "Unusual"
        elif warm:
            snap.kind, snap.level, snap.status = "warming", "ok", "Analyzing Movement"
            snap.description = "Collecting initial motion data before judging behavior."
            snap.action, snap.action_detail = "Continue Routine Monitoring", "No immediate action required."
            pattern = "Analyzing"
        elif enough and snap.feeding / n >= group:
            snap.kind, snap.level, snap.status = "feeding", "ok", "Feeding Activity"
            snap.description = (f"{snap.feeding} of {n} milkfish are gathering and moving actively, "
                                "which matches feeding activity.")
            snap.action, snap.action_detail = "Continue Routine Monitoring", "No immediate action required."
            pattern = "Feeding"
        elif enough and snap.schooling / n >= group:
            snap.kind, snap.level, snap.status = "schooling", "ok", "Schooling Behavior"
            snap.description = f"{snap.schooling} of {n} milkfish are swimming close together in the same direction."
            snap.action, snap.action_detail = "Continue Routine Monitoring", "No immediate action required."
            pattern = "Schooling"
        else:
            snap.kind, snap.level, snap.status = "normal", "ok", "Normal Swimming"
            snap.description = "Milkfish are swimming steadily with consistent movement patterns."
            snap.action, snap.action_detail = "Continue Routine Monitoring", "No immediate action required."
            pattern = "Normal"

        snap.details = {"Movement Pattern": pattern, "Speed Trend": trend,
                        "Direction Changes": turns, "Schooling": school}
        return snap
"""Movement-based behavior analysis for milkfish (YOLO detections + DeepSORT track IDs).

No fixed swimming-speed value decides whether a fish is normal or unusual. Each fish is judged from how its
trajectory behaves over time:

* direction and direction changes, directional consistency, path straightness, speed variability;
* its own movement history (a personal baseline), and the typical movement of the school in this video;
* coordination with nearby fish (shared direction over time, steady spacing while moving together);
* repeated, localized, collective movement (the only movement pattern that can suggest feeding).

Technical parameters (noise gate, tracking-error guard, minimum tracking time) protect data quality. They are not
behavior thresholds. A fish that has not been tracked long enough, or whose track is unstable, is reported as
"Insufficient" instead of being given a guessed behavior. Activity (active / low movement) is kept separate from
behavior. Everything here is a movement-based observation, not a diagnosis of fish health or water quality.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

ARROWS = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]

# ---- data quality / noise (not behavior thresholds) ----
GRID_S = 0.4            # trajectories are resampled to this time step
WINDOW_S = 5.0          # movement window
MIN_TRACK_S = 3.0       # tracking time needed before a fish is judged
MAX_GAP_S = 0.8         # a longer gap in observations starts a new trajectory
MAX_BL_PER_S = 25.0     # tracking-error guard: faster than this (body lengths/s) is a position jump, not swimming
GLITCH_RATIO_MAX = 0.25
NOISE_K = 5.0           # a step must exceed this many times the measured position jitter to define a heading
NOISE_FLOOR_PX = 0.5
HEAD_MIN_BL = 0.06
MIN_ACTIVE_STEPS = 5
KEEP_S = 8.0

# ---- movement-pattern parameters ----
LOW_MOVE_BL = 0.6       # activity: area covered during the window, in body lengths
UNUSUAL_Z = 3.0         # statistical deviation from normal movement
UNUSUAL_PERSIST_S = 1.5
DROP_Z = 4.5
DROP_PERSIST_S = 3.0
HOLD_S = 1.0
POOL_MIN, POOL_MAX = 60, 2500
BASE_MIN_S = 6.0
BASE_TAU_S = 15.0
FEATS4 = ("omega", "inc", "cv", "tort")
FLOORS = {"omega": 0.5, "inc": 0.1, "cv": 0.1, "tort": 0.1, "lm": 0.3}
SCHOOL_NEIGHBOR_BL = 6.0
SCHOOL_COORD = 0.7
SCHOOL_DIST_CV = 0.5
SCHOOL_MIN_FISH = 3
FEED_WINDOW_S = 6.0
FEED_MIN_SPAN_S = 4.5
FEED_LOCAL_BL = 6.0
FEED_MIN_PATH_BL = 4.0
FEED_REVISIT = 0.35
FEED_MAX_POLARIZATION = 0.6
FEED_MIN_FISH = 3
GROUP_SHARE = 0.40


@dataclass
class FishState:
    id: int
    bbox: tuple
    conf: float
    speed: float           # px/s (path length / time over the movement window); only meaningful if speed_ok
    arrow: str
    status: str            # "Normal" | "Schooling" | "Feeding" | "Unusual" | "Insufficient"
    activity: str          # "active" | "low" | "unknown"  (separate from behavior)
    turn_rate: float       # rad/s, mean absolute direction change
    note: str = ""         # why the fish got this status
    speed_ok: bool = False

    @property
    def active(self) -> bool:
        return self.activity == "active"


@dataclass
class Snapshot:
    fish: List[FishState] = field(default_factory=list)
    count: int = 0
    avg_speed: float = 0.0
    speed_known: int = 0        # fish with enough tracking data for a speed
    cohesion: Optional[float] = None
    active: int = 0
    inactive: int = 0           # low movement over the whole window
    activity_unknown: int = 0   # not enough tracking data to tell
    normal: int = 0
    schooling: int = 0
    feeding: int = 0
    unusual: int = 0
    insufficient: int = 0       # tracked, but not enough data to classify
    erratic: int = 0            # kept for older code: same as `unusual`
    low_oxygen: int = 0         # kept for older code: always 0
    kind: str = "idle"          # idle | warming | normal | schooling | feeding | unusual | no_fish
    status: str = "Waiting for video"
    level: str = "ok"           # ok | warning
    description: str = "Start monitoring to see live behavior analysis."
    action: str = "Press Start to begin"
    action_detail: str = "Monitoring is currently stopped."
    details: Dict[str, str] = field(default_factory=lambda: {
        "Movement Pattern": "—", "Schooling": "—", "Group arrangement": "—", "Feeding evidence": "—"})


def _heading_arrow(dx: float, dy: float) -> str:
    angle = math.degrees(math.atan2(-dy, dx)) % 360  # screen y points down
    return ARROWS[int(round(angle / 45.0)) % 8]


class _Fish:
    """Movement history of one tracked fish."""

    def __init__(self) -> None:
        self.pts: deque = deque()             # (t, smoothed x, smoothed y, raw x, raw y) of one trajectory
        self.sizes: deque = deque(maxlen=40)  # long side of the box = body length in pixels
        self.pending = None                   # a suspicious sample waiting for the next frame to confirm it
        self.glitch_t: deque = deque()        # times of rejected position jumps
        self.last_seen = 0.0
        self.bbox = (0, 0, 0, 0)
        self.conf = 0.0
        self.base: dict = {}                  # own baseline: feature -> [mean, variance]
        self.base_time = 0.0
        self.last_base_t: Optional[float] = None
        self.last_pool_t = -1e9
        self.cond_kind = ""
        self.evid = 0.0
        self.last_eval_t: Optional[float] = None
        self.unusual_until = -1e9
        self.suspect = False
        self.note = ""
        self.feed_t = -1e9
        self.feed = None

    def add(self, t: float, cx: float, cy: float, w: float, h: float, max_bl: float) -> None:
        L = max(w, h, 1.0)
        self.last_seen = t
        if self.pts:
            dt = t - self.pts[-1][0]
            if dt <= 1e-6:
                return
            if dt > MAX_GAP_S:                       # long gap: start a new trajectory
                self.pts.clear()
                self.pending = None
            else:
                ref = float(np.median(self.sizes)) if self.sizes else L
                rx, ry = self.pts[-1][3], self.pts[-1][4]
                limit = max_bl * ref
                jump = math.hypot(cx - rx, cy - ry) / dt > limit or not (0.4 <= L / ref <= 2.5)
                if jump:
                    if self.pending is None:         # hold it: one odd frame is usually a tracking error
                        self.pending = (t, cx, cy, L)
                        self.glitch_t.append(t)
                        return
                    pt, px, py, pl = self.pending
                    if math.hypot(cx - px, cy - py) / max(t - pt, 1e-6) <= limit:
                        self.pts.clear()             # two samples agree: a real discontinuity, new trajectory
                        self.sizes.clear()
                        self._push(pt, px, py, pl)
                        self.pending = None
                    else:
                        self.pending = (t, cx, cy, L)
                        self.glitch_t.append(t)
                        return
                else:
                    self.pending = None
        self._push(t, cx, cy, L)

    def _push(self, t: float, rx: float, ry: float, L: float) -> None:
        if self.pts:
            sx = 0.6 * rx + 0.4 * self.pts[-1][1]
            sy = 0.6 * ry + 0.4 * self.pts[-1][2]
        else:
            sx, sy = rx, ry
        self.pts.append((t, sx, sy, rx, ry))
        self.sizes.append(L)
        while self.pts and self.pts[0][0] < t - KEEP_S:
            self.pts.popleft()
        while self.glitch_t and self.glitch_t[0] < t - KEEP_S:
            self.glitch_t.popleft()

    def noise(self) -> float:
        """Position jitter (px) from second differences of the raw positions."""
        if len(self.pts) < 8:
            return NOISE_FLOOR_PX
        a = np.array([(p[3], p[4]) for p in self.pts])
        d2 = a[2:] - 2 * a[1:-1] + a[:-2]
        return max(1.4826 * float(np.median(np.abs(d2))) / math.sqrt(6.0), NOISE_FLOOR_PX)


class BehaviorAnalyzer:
    def __init__(self, settings):
        self.s = settings
        self.reset()

    def reset(self) -> None:
        self.fish: Dict[int, _Fish] = {}
        self.pool: deque = deque(maxlen=POOL_MAX)   # movement of the whole school in this video
        self.pool_stats = None
        self.pool_t = -1e9

    def _p(self, name: str, default):
        return getattr(self.s, name, default)

    # ------------------------------------------------------------------ per-fish movement features
    def _features(self, f: _Fish, g: np.ndarray, tau: float, min_pts: int, low_bl: float):
        if len(f.pts) < 4:
            return None, "tracking too short to judge"
        arr = np.array([p[:3] for p in f.pts])
        ts = arr[:, 0]
        valid = (g >= ts[0] - 1e-9) & (g <= ts[-1] + 1e-9)
        if int(valid.sum()) < min_pts:
            return None, "tracking too short to judge"
        lo = g[valid][0]
        n_samp = int((ts >= lo).sum())
        n_gl = sum(1 for x in f.glitch_t if x >= lo)
        if n_gl and n_gl > GLITCH_RATIO_MAX * (n_gl + n_samp):
            return None, "unstable tracking (position jumps)"
        P = np.full((len(g), 2), np.nan)
        P[valid, 0] = np.interp(g[valid], ts, arr[:, 1])
        P[valid, 1] = np.interp(g[valid], ts, arr[:, 2])
        V = P[valid]
        steps = np.diff(V, axis=0)
        sl = np.hypot(steps[:, 0], steps[:, 1])
        L = float(np.median(f.sizes))
        span = (len(V) - 1) * tau
        S = float(sl.sum())
        D = float(math.hypot(V[-1, 0] - V[0, 0], V[-1, 1] - V[0, 1]))
        ext = float(math.hypot(np.ptp(V[:, 0]), np.ptp(V[:, 1]))) / L
        gate = max(HEAD_MIN_BL * L, NOISE_K * f.noise())
        mv = sl >= gate
        feat = {"P": P, "L": L, "gate": gate, "speed": S / span if span > 0 else 0.0, "ext": ext,
                "activity": "active" if ext >= low_bl else "low", "tort": (1.0 - D / S) if S > 1e-6 else 0.0,
                "dir_ok": False, "omega": 0.0, "R": None, "cv": 0.0, "uh": None, "arrow": "—"}
        if int(mv.sum()) >= MIN_ACTIVE_STEPS:
            th = np.arctan2(steps[:, 1], steps[:, 0])
            both = mv[:-1] & mv[1:]
            if int(both.sum()) >= 3:
                d = np.abs((th[1:] - th[:-1] + np.pi) % (2 * np.pi) - np.pi)
                u = np.array([np.cos(th[mv]).mean(), np.sin(th[mv]).mean()])
                R = float(math.hypot(u[0], u[1]))
                sp = sl[mv] / tau
                feat.update(dir_ok=True, omega=float(d[both].mean() / tau), R=R,
                            cv=float(sp.std() / sp.mean()) if sp.mean() > 0 else 0.0,
                            uh=(u / R) if R > 1e-6 else None,
                            arrow=_heading_arrow(u[0], u[1]) if R >= 0.5 else "—")
        return feat, ""

    @staticmethod
    def _vals(feat: dict) -> dict:
        vals = {"lm": math.log(feat["ext"] + 0.1)}
        if feat["dir_ok"]:
            vals.update(omega=feat["omega"], inc=1.0 - feat["R"], cv=feat["cv"], tort=feat["tort"])
        return vals

    # ------------------------------------------------------------------ own history + school reference
    def _refresh_pool(self, t: float) -> None:
        if len(self.pool) >= POOL_MIN and t - self.pool_t >= 1.0:
            a = np.array(self.pool)
            med = np.median(a, axis=0)
            mad = 1.4826 * np.median(np.abs(a - med), axis=0)
            self.pool_stats = (med, np.maximum(mad, [FLOORS[k] for k in FEATS4]))
            self.pool_t = t

    def _base_update(self, f: _Fish, vals: dict, t: float) -> None:
        if f.last_base_t is not None and t - f.last_base_t < 0.5:
            return
        dt = 0.5 if f.last_base_t is None else min(t - f.last_base_t, 2.0)
        a = 1.0 - math.exp(-dt / BASE_TAU_S)
        for k, v in vals.items():
            m, var = f.base.get(k, [v, 0.0])
            d = v - m
            f.base[k] = [m + a * d, (1.0 - a) * (var + a * d * d)]
        f.base_time += dt
        f.last_base_t = t

    def _unusual(self, f: _Fish, feat: dict, t: float) -> bool:
        """Irregular direction changes, or a marked change compared with the fish's own movement history."""
        Z0 = float(self._p("unusual_z", UNUSUAL_Z))
        persist = float(self._p("unusual_persist_s", UNUSUAL_PERSIST_S))
        Z = Z0 * (0.7 if t < f.unusual_until else 1.0)      # easier to stay flagged than to become flagged
        vals = self._vals(feat)
        pool_sc = dict(zip(FEATS4, self.pool_stats[1])) if self.pool_stats is not None else {}
        zown = {}
        if f.base_time >= BASE_MIN_S:
            for k, v in vals.items():
                if k in f.base:
                    m, var = f.base[k]
                    zown[k] = (v - m) / max(math.sqrt(var), FLOORS[k], 0.5 * pool_sc.get(k, 0.0))
        zpool = {}
        if self.pool_stats is not None and feat["dir_ok"]:
            med = self.pool_stats[0]
            zpool = {k: (vals[k] - med[i]) / self.pool_stats[1][i] for i, k in enumerate(FEATS4)}
        a = bool(zpool) and zpool["omega"] >= Z and zpool["inc"] >= 0.66 * Z
        n_dev = sum(1 for k in ("omega", "inc", "cv", "lm") if k in zown and abs(zown[k]) >= Z)
        dir_dev = any(k in zown and abs(zown[k]) >= Z for k in ("omega", "inc"))
        b = n_dev >= 2 and dir_dev
        c = "lm" in zown and zown["lm"] <= -max(DROP_Z, 1.5 * Z0) * (Z / Z0)
        cond = "A" if a else ("B" if b else ("C" if c else ""))
        f.suspect = bool(cond) or any(abs(z) >= 0.66 * Z for z in zown.values()) or (
            bool(zpool) and zpool["omega"] >= 0.66 * Z and zpool["inc"] >= 0.5 * Z)
        # evidence builds while the pattern is present and fades slowly, so brief dips do not reset it
        dt = 0.0 if f.last_eval_t is None else min(t - f.last_eval_t, 1.0)
        f.last_eval_t = t
        if cond:
            f.cond_kind = cond
            f.evid = min(f.evid + dt, 2.0 * (DROP_PERSIST_S if cond == "C" else persist))
        else:
            f.evid = max(f.evid - 0.5 * dt, 0.0)
        if f.cond_kind and f.evid >= (DROP_PERSIST_S if f.cond_kind == "C" else persist):
            f.unusual_until = t + HOLD_S
            f.note = {"A": "irregular direction changes compared with the school",
                      "B": "movement pattern changed compared with its own history",
                      "C": "marked drop in movement compared with its own history"}[f.cond_kind]
        return t < f.unusual_until

    # ------------------------------------------------------------------ group movement
    def _pairs(self, items: list, tau: float, min_pts: int, eligible: list):
        """Coordinated neighbours for every fish: shared direction over time, steady spacing while moving."""
        n = len(items)
        counts = [0] * n
        if n < 2:
            return counts, None
        P = np.stack([ft["P"] for ft in items])
        L = np.array([ft["L"] for ft in items])
        gate = np.array([ft["gate"] for ft in items])
        radius = float(self._p("school_neighbor_bl", SCHOOL_NEIGHBOR_BL)) * float(np.median(L))
        thr = float(self._p("school_coord", SCHOOL_COORD))
        with np.errstate(invalid="ignore", divide="ignore"):
            S = np.diff(P, axis=1)
            sl = np.hypot(S[..., 0], S[..., 1])
            mv = np.isfinite(sl) & (sl >= gate[:, None])
            U = np.where(mv[..., None], S / np.where(sl > 0, sl, 1.0)[..., None], 0.0)
            both = mv[:, None, :] & mv[None, :, :]
            cnt = both.sum(-1)
            cosm = np.einsum("ikc,jkc->ijk", U, U)
            C = np.where(cnt >= MIN_ACTIVE_STEPS, (cosm * both).sum(-1) / np.maximum(cnt, 1), np.nan)
            D = np.linalg.norm(P[:, None] - P[None], axis=-1)
            ok = np.isfinite(D)
            cD = ok.sum(-1)
            mean = np.where(ok, D, 0.0).sum(-1) / np.maximum(cD, 1)
            var = np.where(ok, (D - mean[..., None]) ** 2, 0.0).sum(-1) / np.maximum(cD, 1)
            cvd = np.sqrt(var) / np.maximum(mean, 1e-6)
            el = np.array(eligible)
            near = (cD >= min_pts) & (mean <= radius)
            coord = near & (C >= thr) & (cvd <= SCHOOL_DIST_CV) & el[:, None] & el[None, :]
        np.fill_diagonal(coord, False)
        off = near & ~np.eye(n, dtype=bool)
        med_cvd = float(np.median(cvd[off])) if off.any() else None
        return [int(x) for x in coord.sum(1)], med_cvd

    def _feed_ind(self, f: _Fish, t: float, tau: float):
        """Repeated movement inside a small area (looping / back-and-forth), judged over a longer window."""
        pts = [p for p in f.pts if p[0] >= t - FEED_WINDOW_S]
        if len(pts) < 8 or pts[-1][0] - pts[0][0] < FEED_MIN_SPAN_S:
            return None
        arr = np.array([p[:3] for p in pts])
        g = np.arange(arr[0, 0], arr[-1, 0] + 1e-9, tau)
        P = np.column_stack([np.interp(g, arr[:, 0], arr[:, 1]), np.interp(g, arr[:, 0], arr[:, 2])])
        L = float(np.median(f.sizes))
        steps = np.diff(P, axis=0)
        sl = np.hypot(steps[:, 0], steps[:, 1])
        S = float(sl.sum())
        ext = float(math.hypot(np.ptp(P[:, 0]), np.ptp(P[:, 1]))) / L
        lag = max(int(round(1.5 / tau)), 2)
        rev = [float(np.min(np.linalg.norm(P[:k - lag + 1] - P[k], axis=1))) <= L for k in range(lag, len(P))]
        share = float(np.mean(rev)) if rev else 0.0
        mv = sl >= max(HEAD_MIN_BL * L, NOISE_K * f.noise())
        if mv.sum() >= 3:
            th = np.arctan2(steps[mv, 1], steps[mv, 0])
            R = float(math.hypot(np.cos(th).mean(), np.sin(th).mean()))
        else:
            R = 1.0
        ind = (S / L >= FEED_MIN_PATH_BL and ext <= FEED_LOCAL_BL and share >= FEED_REVISIT
               and R < FEED_MAX_POLARIZATION)
        return {"ind": bool(ind), "c": P.mean(0)}

    # ------------------------------------------------------------------ main entry
    def update(self, tracks, t: float, frame_shape) -> Snapshot:
        h, w = frame_shape[:2]
        tau = GRID_S
        window = float(self._p("move_window_s", WINDOW_S))
        min_track = float(self._p("min_track_s", MIN_TRACK_S))
        max_bl = float(self._p("max_bl_per_s", MAX_BL_PER_S))
        low_bl = float(self._p("low_move_bl", LOW_MOVE_BL))
        min_pts = int(math.ceil(min_track / tau - 1e-9)) + 1
        g = t - tau * np.arange(int(round(window / tau)), -1, -1)

        seen = []
        for tr in tracks:
            x1, y1, x2, y2 = tr.bbox
            f = self.fish.get(tr.id)
            if f is None:
                f = self.fish[tr.id] = _Fish()
            f.add(t, (x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1, max_bl)
            f.bbox, f.conf = tr.bbox, tr.conf
            if f.pts:
                seen.append((tr.id, f))
        for tid in [i for i, f in self.fish.items() if t - f.last_seen > 5.0]:
            del self.fish[tid]

        self._refresh_pool(t)
        feats, unusual = {}, {}
        for tid, f in seen:
            feat, reason = self._features(f, g, tau, min_pts, low_bl)
            feats[tid] = (feat, reason)
            if feat is None:
                continue
            unusual[tid] = self._unusual(f, feat, t)
            if not unusual[tid] and not f.suspect:
                vals = self._vals(feat)
                self._base_update(f, vals, t)
                if feat["dir_ok"] and t - f.last_pool_t >= 0.5:
                    self.pool.append([vals[k] for k in FEATS4])
                    f.last_pool_t = t

        ids = [tid for tid, _ in seen if feats[tid][0] is not None]
        items = [feats[tid][0] for tid in ids]
        eligible = [ft["activity"] == "active" and not unusual[tid] for tid, ft in zip(ids, items)]
        school_n, med_cvd = self._pairs(items, tau, min_pts, eligible)
        school_n = dict(zip(ids, school_n))

        # feeding: localized repeated movement that several fish share
        Lmed = float(np.median([ft["L"] for ft in items])) if items else 1.0
        cand = []
        feed_seen = False
        for tid, f in seen:
            if feats[tid][0] is None or unusual[tid]:
                continue
            if t - f.feed_t >= 0.25:
                f.feed, f.feed_t = self._feed_ind(f, t, tau), t
            feed_seen = feed_seen or f.feed is not None
            if f.feed and f.feed["ind"]:
                cand.append((tid, f.feed["c"]))
        zone = float(self._p("feeding_zone", 0.0))
        feed_min = int(self._p("feeding_min_fish", FEED_MIN_FISH))
        feeding = set()
        if len(cand) >= feed_min:
            C = np.array([c for _, c in cand])
            cnt = (np.linalg.norm(C[:, None] - C[None], axis=-1) <= FEED_LOCAL_BL * Lmed).sum(1) - 1
            feeding = {tid for (tid, c), k in zip(cand, cnt)
                       if k >= feed_min - 1 and (zone <= 0 or c[1] < h * zone)}
        evidence = ("supported by repeated localized group movement" if feeding else
                    "not observed" if feed_seen else "not enough tracking time to judge")

        school_min = int(self._p("school_min_fish", SCHOOL_MIN_FISH))
        states = []
        for tid, f in seen:
            feat, reason = feats[tid]
            if feat is None:
                states.append(FishState(tid, f.bbox, f.conf, 0.0, "—", "Insufficient", "unknown", 0.0, reason))
                continue
            if unusual[tid]:
                status, note = "Unusual", f.note
            elif tid in feeding:
                status, note = "Feeding", "repeated localized movement shared with nearby fish"
            elif eligible[ids.index(tid)] and school_n[tid] >= school_min - 1:
                status, note = "Schooling", f"coordinated with {school_n[tid]} nearby fish"
            else:
                status, note = "Normal", ""
            states.append(FishState(tid, f.bbox, f.conf, feat["speed"], feat["arrow"], status, feat["activity"],
                                    feat["omega"], note, True))
        return self._summarise(states, seen, items, med_cvd, evidence, (w, h))

    # ------------------------------------------------------------------ whole-school summary
    def _summarise(self, fish, seen, items, med_cvd, evidence, size) -> Snapshot:
        s = self.s
        n = len(fish)
        snap = Snapshot(fish=fish, count=n)
        snap.active = sum(f.activity == "active" for f in fish)
        snap.inactive = sum(f.activity == "low" for f in fish)
        snap.activity_unknown = n - snap.active - snap.inactive
        for key, label in (("normal", "Normal"), ("schooling", "Schooling"), ("feeding", "Feeding"),
                           ("unusual", "Unusual"), ("insufficient", "Insufficient")):
            setattr(snap, key, sum(f.status == label for f in fish))
        snap.erratic = snap.unusual
        known = [f.speed for f in fish if f.speed_ok]
        snap.speed_known = len(known)
        snap.avg_speed = float(np.mean(known)) if known else 0.0

        # cohesion: nearest-neighbour closeness (in body lengths) + heading alignment of moving fish
        if len(seen) >= 2:
            pos = np.array([[f.pts[-1][1], f.pts[-1][2]] for _, f in seen])
            d = np.linalg.norm(pos[:, None] - pos[None], axis=-1)
            np.fill_diagonal(d, np.inf)
            Lm = float(np.median([np.median(f.sizes) for _, f in seen]))
            scale = float(self._p("school_neighbor_bl", SCHOOL_NEIGHBOR_BL)) * Lm
            prox = float(np.clip(1.0 - d.min(axis=1).mean() / scale, 0.0, 1.0))
            uh = [ft["uh"] for ft in items if ft["uh"] is not None and ft["activity"] == "active"]
            pol = float(np.linalg.norm(np.mean(uh, axis=0))) if len(uh) >= 2 else None
            snap.cohesion = 100.0 * (prox if pol is None else 0.5 * prox + 0.5 * pol)
        school = ("N/A" if snap.cohesion is None else "Maintained" if snap.cohesion >= 60
                  else "Loosening" if snap.cohesion >= 30 else "Dispersed")
        arrangement = "—" if med_cvd is None else ("Stable" if med_cvd < 0.25 else "Changing")

        cl = snap.normal + snap.schooling + snap.feeding + snap.unusual
        enough = cl >= int(getattr(s, "min_fish_alert", 3))
        u_frac = snap.unusual / cl if cl else 0.0
        group = float(self._p("group_share", GROUP_SHARE))
        ok_act = ("Continue Routine Monitoring", "No immediate action required.")
        if n == 0:
            snap.kind, snap.level, snap.status = "no_fish", "warning", "No Fish Detected"
            snap.description = "No milkfish detected in view. Check the camera, lighting or water clarity."
            snap.action, snap.action_detail = "Check Camera View", "Confirm the camera is clear and the pond is in frame."
            pattern = "—"
        elif cl == 0:
            snap.kind, snap.level, snap.status = "warming", "ok", "Collecting Movement Data"
            snap.description = (f"{n} fish tracked. Each fish needs a few seconds of tracking before its behavior "
                                "can be judged.")
            snap.action, snap.action_detail = ok_act
            pattern = "Collecting data"
        elif enough and u_frac >= getattr(s, "abnormal_fraction", 0.3):
            snap.kind, snap.level, snap.status = "unusual", "warning", "Unusual Swimming Activity"
            snap.description = (f"{snap.unusual} of {cl} classified milkfish ({u_frac:.0%}) show irregular movement "
                                "compared with the school or with their own earlier movement. This is a video-based "
                                "observation, not a disease diagnosis.")
            snap.action, snap.action_detail = "Inspect the Pond", "Inspect the fingerlings and pond conditions."
            pattern = "Unusual"
        elif enough and snap.feeding / cl >= group:
            snap.kind, snap.level, snap.status = "feeding", "ok", "Feeding Activity"
            snap.description = (f"{snap.feeding} of {cl} milkfish show repeated, localized group movement that is "
                                "consistent with feeding. Movement alone cannot confirm feeding.")
            snap.action, snap.action_detail = ok_act
            pattern = "Feeding-consistent"
        elif enough and snap.schooling / cl >= group:
            snap.kind, snap.level, snap.status = "schooling", "ok", "Schooling Behavior"
            snap.description = f"{snap.schooling} of {cl} milkfish are moving together in a coordinated way."
            snap.action, snap.action_detail = ok_act
            pattern = "Schooling"
        else:
            snap.kind, snap.level, snap.status = "normal", "ok", "Normal Swimming"
            snap.description = "Milkfish are swimming with consistent movement patterns."
            snap.action, snap.action_detail = ok_act
            pattern = "Normal"
        snap.details = {"Movement Pattern": pattern, "Schooling": school, "Group arrangement": arrangement,
                        "Feeding evidence": evidence}
        return snap

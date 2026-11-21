"""CLAHE -> YOLOv8 -> DeepSORT -> behavior analysis, plus box, ID and movement-path drawing."""
from __future__ import annotations

import math
import time
from collections import deque
from types import SimpleNamespace

import cv2
import numpy as np

from src.behavior import BehaviorAnalyzer, Snapshot
from src.detector import YoloDetector
from src.preprocessing import Preprocessor
from src.tracker import FishTracker

# BGR colours per behavior (match the dashboard palette)
COLORS = {"Normal": (113, 204, 46), "Schooling": (110, 118, 15), "Feeding": (13, 163, 101),
          "Unusual": (6, 119, 217), "Insufficient": (160, 165, 160)}

STAGES = ("enhance", "detect", "track", "behavior")
TRAIL_LEN = 40        # points kept for each fish's movement path
TRAIL_DROP = 90       # frames after which a lost fish's path is forgotten
CONFIRM_FRAMES = 4    # a new track must be seen this many frames before it counts as a fish (ignores flicker)
REID_SECONDS = 3.0    # a fish that reappears within this time near where it vanished gets its old ID back


class FrameResult:
    """Result for one frame. The boxes are drawn only when `.frame` is first read, so frames that are never
    shown on screen cost nothing to draw. `.snapshot` (the analysis) is always ready."""

    def __init__(self, raw: np.ndarray, snapshot: Snapshot, infer_ms: float, draw_fn):
        self._raw = raw
        self._draw_fn = draw_fn
        self._img = None
        self.snapshot = snapshot
        self.infer_ms = infer_ms

    @property
    def frame(self) -> np.ndarray:
        if self._img is None:
            self._img = self._draw_fn(self._raw.copy(), self.snapshot)
        return self._img


class MonitoringPipeline:
    def __init__(self, settings, model_path: str):
        self.s = settings
        self.pre = Preprocessor(settings)
        self.detector = YoloDetector(model_path, settings)
        self.tracker = FishTracker(max_age=settings.max_age)
        self.analyzer = BehaviorAnalyzer(settings)
        self._clear_timing()
        self._clear_ids()

    @property
    def tracker_name(self) -> str:
        return self.tracker.backend

    @property
    def device(self) -> str:
        """What the detector runs on, e.g. 'GPU: NVIDIA ...' or 'CPU'."""
        return getattr(self.detector, "device_name", "unknown")

    def _clear_timing(self) -> None:
        self._stage_s = {k: 0.0 for k in STAGES}
        self._n = 0

    def _clear_ids(self) -> None:
        self.id_map = {}      # tracker id -> 1, 2, 3 ... in order of first appearance (shown as 01, 02, ...)
        self.trails = {}      # tracker id -> recent centre points (movement path)
        self._last = {}       # tracker id -> frame number it was last seen
        self._frame_i = 0
        self.alias = {}       # raw tracker id -> stable fish id (one fish keeps one ID even if the tracker switches)
        self.seen_n = {}      # stable id -> frames seen
        self.last_pos = {}    # stable id -> (cx, cy, w, h, time) where and when it was last seen
        self._next_sid = 1

    def stage_ms(self) -> dict:
        """Average milliseconds per frame spent in each stage since the last reset()."""
        n = max(self._n, 1)
        return {k: 1000.0 * v / n for k, v in self._stage_s.items()}

    def reset(self) -> None:
        self.tracker = FishTracker(max_age=self.s.max_age)
        self.analyzer.reset()
        self._clear_timing()
        self._clear_ids()

    def process(self, frame: np.ndarray, t: float) -> FrameResult:
        t0 = time.perf_counter()
        enhanced = self.pre.apply(frame)
        t1 = time.perf_counter()
        dets = self.detector.detect(enhanced)
        t2 = time.perf_counter()
        tracks = self._stabilize(self.tracker.update(frame, dets), t)
        t3 = time.perf_counter()
        snap = self.analyzer.update(tracks, t, frame.shape)
        t4 = time.perf_counter()

        st = self._stage_s
        st["enhance"] += t1 - t0
        st["detect"] += t2 - t1
        st["track"] += t3 - t2
        st["behavior"] += t4 - t3
        self._n += 1
        self._update_ids(snap)
        return FrameResult(frame, snap, (t4 - t0) * 1000.0, self._draw)

    def _stabilize(self, tracks, t: float) -> list:
        """Keep each fish's ID consistent and unique.

        1. A new tracker ID that appears close to where a known fish just vanished is the same fish: it gets the old
           ID back (this repairs the ID switches an IoU tracker makes after missed detections or crossings).
        2. Two fish never share an ID at the same time, and an ID is never given to a different fish.
        3. A track must be seen for a few frames before it counts, so one-frame false detections are ignored.
        """
        used, known, pending = set(), [], []
        for tr in tracks:
            sid = self.alias.get(tr.id)
            if sid is None:
                pending.append(tr)
            elif sid not in used:
                used.add(sid)
                known.append((sid, tr))
        lost = {sid: pos for sid, pos in self.last_pos.items()
                if sid not in used and t - pos[4] <= REID_SECONDS and self.seen_n.get(sid, 0) >= CONFIRM_FRAMES}
        pairs = []
        for i, tr in enumerate(pending):
            x1, y1, x2, y2 = tr.bbox
            cx, cy, w, h = (x1 + x2) / 2.0, (y1 + y2) / 2.0, max(x2 - x1, 1.0), max(y2 - y1, 1.0)
            for sid, (lx, ly, lw, lh, lt) in lost.items():
                dist = math.hypot(cx - lx, cy - ly)
                reach = 2.0 * max(lw, lh) + 60.0 * (t - lt)  # how far a fish could plausibly have moved
                ratio = (w * h) / max(lw * lh, 1.0)
                if dist <= reach and 0.4 <= ratio <= 2.5:
                    pairs.append((dist, i, sid))
        taken = set()
        for dist, i, sid in sorted(pairs):
            if i in taken or sid in used:
                continue
            taken.add(i)
            used.add(sid)
            self.alias[pending[i].id] = sid
            known.append((sid, pending[i]))
        for i, tr in enumerate(pending):
            if i not in taken:  # a new fish: give it a brand-new ID
                sid = self._next_sid
                self._next_sid += 1
                self.alias[tr.id] = sid
                used.add(sid)
                known.append((sid, tr))

        out = []
        for sid, tr in known:
            self.seen_n[sid] = self.seen_n.get(sid, 0) + 1
            x1, y1, x2, y2 = tr.bbox
            self.last_pos[sid] = ((x1 + x2) / 2.0, (y1 + y2) / 2.0, max(x2 - x1, 1.0), max(y2 - y1, 1.0), t)
            if self.seen_n[sid] >= CONFIRM_FRAMES:
                out.append(SimpleNamespace(id=sid, bbox=tr.bbox, conf=tr.conf))
        for sid in [s for s, pos in self.last_pos.items() if t - pos[4] > 2 * REID_SECONDS]:
            self.last_pos.pop(sid, None)
            self.seen_n.pop(sid, None)
        return out

    def _update_ids(self, snap: Snapshot) -> None:
        self._frame_i += 1
        for f in snap.fish:
            self.id_map.setdefault(f.id, len(self.id_map) + 1)
            x1, y1, x2, y2 = f.bbox
            self.trails.setdefault(f.id, deque(maxlen=TRAIL_LEN)).append((int((x1 + x2) / 2), int((y1 + y2) / 2)))
            self._last[f.id] = self._frame_i
        for fid in [i for i, k in self._last.items() if self._frame_i - k > TRAIL_DROP]:
            self._last.pop(fid, None)
            self.trails.pop(fid, None)

    def _draw(self, img: np.ndarray, snap: Snapshot) -> np.ndarray:
        fs = max(0.4, img.shape[1] / 1600.0)
        for f in snap.fish:  # movement paths first, so the boxes stay on top
            pts = self.trails.get(f.id)
            if pts and len(pts) > 1:
                color = COLORS.get(f.status, COLORS["Normal"])
                cv2.polylines(img, [np.array(pts, dtype=np.int32)], False, color, 1, cv2.LINE_AA)
        for f in snap.fish:
            color = COLORS.get(f.status, COLORS["Normal"])
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
            label = f"ID {self.id_map.get(f.id, f.id):02d}  {f.conf:.2f}"
            (tw, th), base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
            top = max(0, y1 - th - base - 4)
            cv2.rectangle(img, (x1, top), (x1 + tw + 8, top + th + base + 4), color, -1)
            cv2.putText(img, label, (x1 + 4, top + th + 1), cv2.FONT_HERSHEY_SIMPLEX, fs,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return img

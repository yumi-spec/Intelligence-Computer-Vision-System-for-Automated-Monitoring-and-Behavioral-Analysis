"""Multi-object tracking: DeepSORT, with a simple IoU tracker as fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Track:
    id: int
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    conf: float


def _iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class _IoUTracker:
    """Greedy IoU matching. Only used if deep-sort-realtime can't be loaded."""

    def __init__(self, max_age: int = 30, iou_thr: float = 0.2):
        self.max_age, self.iou_thr = max_age, iou_thr
        self.tracks = {}  # id -> [bbox, conf, missed]
        self.next_id = 1

    def update(self, dets) -> List[Track]:
        pairs = []
        for tid, (bbox, _, _) in self.tracks.items():
            for j, d in enumerate(dets):
                v = _iou(bbox, d[:4])
                if v >= self.iou_thr:
                    pairs.append((v, tid, j))
        pairs.sort(reverse=True)
        used_t, used_d, out = set(), set(), []
        for _, tid, j in pairs:
            if tid in used_t or j in used_d:
                continue
            used_t.add(tid)
            used_d.add(j)
            self.tracks[tid] = [dets[j][:4], dets[j][4], 0]
            out.append(Track(tid, tuple(dets[j][:4]), dets[j][4]))
        for j, d in enumerate(dets):
            if j not in used_d:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = [d[:4], d[4], 0]
                out.append(Track(tid, tuple(d[:4]), d[4]))
        for tid in list(self.tracks):
            if tid not in used_t and tid not in {t.id for t in out}:
                self.tracks[tid][2] += 1
                if self.tracks[tid][2] > self.max_age:
                    del self.tracks[tid]
        return out


class FishTracker:
    def __init__(self, max_age: int = 30, n_init: int = 3):
        self.backend = "DeepSORT"
        self._ds = None
        self._fallback = None
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort

            self._ds = DeepSort(max_age=max_age, n_init=n_init, embedder="mobilenet",
                                half=False, bgr=True)
        except Exception:  # missing package, missing torch, etc.
            self._fallback = _IoUTracker(max_age=max_age)
            self.backend = "IoU tracker (DeepSORT unavailable)"

    def update(self, frame: np.ndarray, dets) -> List[Track]:
        if self._ds is None:
            return self._fallback.update(dets)
        raw = [([d[0], d[1], d[2] - d[0], d[3] - d[1]], d[4], "milkfish") for d in dets]
        out = []
        for t in self._ds.update_tracks(raw, frame=frame):
            if not t.is_confirmed() or t.time_since_update > 0:
                continue
            x1, y1, x2, y2 = t.to_ltrb()
            conf = t.get_det_conf() if hasattr(t, "get_det_conf") else None
            out.append(Track(int(t.track_id), (x1, y1, x2, y2), float(conf) if conf is not None else 0.0))
        return out

"""Underwater image enhancement (CLAHE on the lightness channel)."""
from __future__ import annotations

import cv2
import numpy as np


class Preprocessor:
    def __init__(self, settings):
        self.s = settings
        self._clahe = None
        self._key = None

    def apply(self, frame: np.ndarray) -> np.ndarray:
        if not self.s.use_clahe:
            return frame
        key = (float(self.s.clahe_clip), int(self.s.clahe_tile))
        if key != self._key:
            self._clahe = cv2.createCLAHE(clipLimit=key[0], tileGridSize=(key[1], key[1]))
            self._key = key
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

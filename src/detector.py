"""YOLOv8 detector wrapper (Ultralytics)."""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

Detection = Tuple[float, float, float, float, float]  # x1, y1, x2, y2, conf


class YoloDetector:
    def __init__(self, model_path: str, settings):
        from ultralytics import YOLO  # imported here so the app can start without it

        self.s = settings
        self.model = YOLO(model_path)
        # Half precision is faster on an NVIDIA GPU. It is only used for .pt weights on CUDA.
        self.half = False
        self.device_name = "CPU"
        try:
            import torch

            if torch.cuda.is_available():
                self.device_name = f"GPU: {torch.cuda.get_device_name(0)}"
                self.half = str(model_path).lower().endswith(".pt")
        except Exception:
            pass

    def detect(self, frame: np.ndarray) -> List[Detection]:
        opts = {"half": True} if self.half else {}  # on CPU the option is left out, so no deprecation warning
        result = self.model.predict(
            frame,
            conf=float(self.s.conf),
            iou=float(self.s.iou),
            imgsz=int(self.s.imgsz),
            verbose=False,
            **opts,
        )[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        return [(float(x1), float(y1), float(x2), float(y2), float(c))
                for (x1, y1, x2, y2), c in zip(xyxy, conf)]
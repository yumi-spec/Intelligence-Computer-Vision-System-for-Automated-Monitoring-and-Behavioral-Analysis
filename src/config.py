"""Paths and user-adjustable settings (saved to settings.json)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional, Tuple, Union

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
VIDEOS_DIR = ROOT / "videos"
LOGS_DIR = ROOT / "logs"
SETTINGS_FILE = ROOT / "settings.json"
METRICS_LOG = LOGS_DIR / "metrics.csv"
ALERTS_LOG = LOGS_DIR / "alerts.csv"

MODEL_EXTS = {".pt", ".onnx"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v"}

for _d in (MODELS_DIR, VIDEOS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def list_files(folder: Path, exts: set) -> list:
    return sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts)


@dataclass
class Settings:
    # ---- source & model ----
    model_file: str = ""
    source_type: str = "Video file"          # "Video file" | "Webcam" | "Stream URL"
    video_file: str = ""
    camera_index: int = 0
    stream_url: str = ""

    # ---- detection / preprocessing (administrator) ----
    conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
    use_clahe: bool = True
    clahe_clip: float = 2.0
    clahe_tile: int = 8
    process_width: int = 768
    loop_video: bool = True
    show_ids: bool = False
    max_age: int = 30                         # frames a lost track is kept by the tracker

    # ---- analysis speed ----
    realtime: bool = False                    # True = wait so a video plays at its natural speed (slower)
    frame_stride: int = 1                     # analyse every Nth frame (1 = every frame)

    # ---- behavior thresholds (pixel based -> calibrate to YOUR camera) ----
    active_speed: float = 5.0                 # px/s: below this a fish counts as inactive
    erratic_speed: float = 150.0              # px/s: sustained speed above this = unusual
    erratic_turn_rate: float = 1.0            # sharp turns per second considered unusual
    turn_angle_deg: float = 60.0              # heading change that counts as a "sharp turn"
    surface_zone: float = 0.0                 # no longer used (kept so old settings.json files still load)
    surface_secs: float = 5.0                 # no longer used
    abnormal_fraction: float = 0.30           # share of fish needed to flag the whole school as unusual
    min_fish_alert: int = 3                   # don't flag the school with fewer fish than this
    inactive_secs: float = 10.0               # a fish barely moving this long counts as unusual

    # ---- schooling and feeding rules (distances are fractions of the frame diagonal) ----
    school_radius: float = 0.12               # fish this close can form a school
    school_min_fish: int = 3                  # fish moving together needed to call it schooling
    school_align_deg: float = 35.0            # headings within this angle = same direction
    feeding_radius: float = 0.08              # tighter gathering = feeding
    feeding_min_fish: int = 4                 # fish needed in the gathering
    feeding_zone: float = 0.0                 # top fraction of the frame where feeding happens (0 = anywhere)

    # ---- appearance ----
    theme: str = "dark"                       # old setting, no longer used
    theme_mode: str = "light"                 # "light" | "dark"

    # ---- alerts ----
    sms_enabled: bool = False
    sms_recipients: str = ""                  # comma separated; falls back to SMS_RECIPIENTS in .env
    sms_min_level: str = "warning"            # "warning" | "critical"
    alert_cooldown_s: int = 300
    alert_confirm_s: int = 5

    # ------------------------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                valid = {f.name for f in fields(cls)}
                for k, v in data.items():
                    if k in valid:
                        setattr(s, k, v)
            except (OSError, ValueError):
                pass
        s.autofill()
        return s

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def autofill(self) -> None:
        """Pick sensible defaults from whatever is in models/ and videos/."""
        models = list_files(MODELS_DIR, MODEL_EXTS)
        if models and self.resolve_model() is None:
            self.model_file = "best.pt" if "best.pt" in models else models[0]
        videos = list_files(VIDEOS_DIR, VIDEO_EXTS)
        if videos and not (self.video_file and (VIDEOS_DIR / self.video_file).is_file()):
            self.video_file = videos[0]

    # ------------------------------------------------------------------
    def resolve_model(self) -> Optional[Path]:
        if not self.model_file:
            return None
        p = Path(self.model_file)
        if not p.is_absolute():
            p = MODELS_DIR / p
        return p if p.is_file() else None

    def resolve_source(self) -> Optional[Tuple[Union[int, str], str]]:
        """Return (value for cv2.VideoCapture, label to show) or None."""
        if self.source_type == "Webcam":
            return int(self.camera_index), f"Webcam {int(self.camera_index)}"
        if self.source_type == "Stream URL":
            url = self.stream_url.strip()
            return (url, url) if url else None
        if not self.video_file:
            return None
        p = Path(self.video_file)
        if not p.is_absolute():
            p = VIDEOS_DIR / p
        return (str(p), p.name) if p.is_file() else None
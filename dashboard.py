"""Milkfish Monitoring Dashboard (Streamlit).

Run from PyCharm: right-click run.py -> Run, or in the terminal:
    streamlit run src/dashboard.py
"""
from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import sys
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src import behavior_ui as bui
from src import components as ui
from src import db, history
from src.alerts import KIND_LABEL, AlertManager
from src.behavior import Snapshot
from src.config import (ALERTS_LOG, LOGS_DIR, METRICS_LOG, MODEL_EXTS, MODELS_DIR, VIDEO_EXTS,
                        VIDEOS_DIR, Settings, list_files)
from src.styles import build_css

logging.getLogger("ultralytics").setLevel(logging.ERROR)  # hide repeated Ultralytics warnings (e.g. the "half" notice)

st.set_page_config(page_title="Milkfish Monitoring", page_icon="🐟", layout="wide",
                   initial_sidebar_state="expanded")
_s0 = st.session_state.get("settings") or Settings.load()
st.markdown(f"<style>{ui.h(build_css(getattr(_s0, 'theme_mode', 'light')))}</style>", unsafe_allow_html=True)

PAGES = ["Dashboard", "Analytics", "Alerts", "Reports", "Settings"]
NAV_ICONS = {"Dashboard": ":material/home:", "Analytics": ":material/bar_chart:",
             "Alerts": ":material/notifications:", "Reports": ":material/description:",
             "Settings": ":material/settings:"}

# chart colours (same palette as styles.py)
C_ACC, C_OK, C_WARN, C_BAD = "#14532D", "#16A34A", "#D97706", "#DC2626"


# ======================================================================== state
def init_state() -> None:
    ss = st.session_state
    if "settings" not in ss:
        ss.settings = Settings.load()
    ss.setdefault("page", "Dashboard")
    if ss.page not in PAGES:  # e.g. a stale page name from an older session
        ss.page = "Dashboard"
    ss.setdefault("running", True)
    ss.setdefault("last", None)
    ss.setdefault("count_hist", deque(maxlen=600))
    ss.settings.source_type = "Video file"  # also overrides an old "Webcam" saved in settings.json
    if "alerts" not in ss:
        ss.alerts = AlertManager(ss.settings)


def setup_problems(s: Settings) -> list:
    problems = []
    if s.resolve_model() is None:
        problems.append("No YOLOv8 model found in the models folder")
    if s.resolve_source() is None:
        problems.append("No video source found (add a video to the videos folder)")
    return problems


def get_pipeline(s: Settings):
    """Load the model once; reload only when the model file or tracker memory changes."""
    ss = st.session_state
    model = s.resolve_model()
    key = (str(model), s.max_age)
    if ss.get("pipe_key") != key or "pipe" not in ss:
        from src.pipeline import MonitoringPipeline  # heavy import (torch) kept lazy

        with st.spinner("Loading YOLOv8 model…"):
            ss.pipe = MonitoringPipeline(s, str(model))
            ss.pipe_key = key
    return ss.pipe


# ======================================================================== upload / layout
def _save_upload(up, folder: Path) -> bool:
    dest = folder / Path(up.name).name
    if dest.exists() and dest.stat().st_size == up.size:
        return False
    dest.write_bytes(up.getbuffer())
    return True


def video_uploader() -> None:
    """Upload box in the sidebar, under Start / Stop. A new file replaces the current video and restarts playback."""
    ss = st.session_state
    up = st.file_uploader("Upload a video", type=[e.strip(".") for e in VIDEO_EXTS],
                          key="dash_upload", label_visibility="collapsed",
                          help="Upload a video to analyse. It replaces the current one.")
    try:
        max_mb = int(st.get_option("server.maxUploadSize"))
    except Exception:
        max_mb = 200
    fmts = ", ".join(sorted(e.strip(".").upper() for e in VIDEO_EXTS))
    st.markdown(f'<div class="mf mf-note" style="margin-top:0">{fmts} · max {max_mb} MB</div>',
                unsafe_allow_html=True)
    if up is not None and ss.get("_last_upload") != (up.name, up.size):
        ss["_last_upload"] = (up.name, up.size)
        _save_upload(up, VIDEOS_DIR)
        ss.settings.video_file = Path(up.name).name
        ss.pop("set_video_file", None)      # drop the old Settings-page selection
        ss.last = None                      # forget the previous frame
        ss.count_hist.clear()               # fresh chart for the new video
        ss.running = True                   # start playing it


def build_layout() -> dict:
    """Three slots: head (title + KPIs) / main (video + behavior column) / lower (analysis + table).
    Each slot is one HTML block laid out with CSS grid (see styles.py)."""
    return {"head": st.empty(), "main": st.empty(), "lower": st.empty(),
            "_media": "", "_progress": "", "_frame": None, "_view": None, "_side": "", "_head": "", "_lower": ""}


def frame_html(frame) -> str:
    """Embed a BGR frame as an inline JPEG so it lives inside the same HTML block as the cards."""
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return ""
    return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf).decode()}" alt="live frame"/>'


def draw(ph: dict, main_only: bool = False) -> None:
    v = ph["_view"]
    if v is None:
        return
    if ph.get("_frame") is not None:  # JPEG-encode only when the picture is actually drawn, not on every frame
        ph["_media"] = frame_html(ph["_frame"].frame)  # drawing the boxes happens here, only for shown frames
        ph["_frame"] = None
    video = ui.video_card(ph["_media"], v["running"], v.get("ended", False), v["label"],
                          v["size"], v["src_fps"], v["duration"])
    ph["main"].markdown(
        ui.h(f'<div class="mf mf-main"><div style="min-width:0">{video}{ph.get("_progress", "")}</div>'
             f'<div class="mf-side">{ph["_side"]}</div></div>'), unsafe_allow_html=True)
    if main_only:
        return
    ph["head"].markdown(ph["_head"], unsafe_allow_html=True)
    ph["lower"].markdown(ph["_lower"], unsafe_allow_html=True)


# ======================================================================== overall results
MIN_OBS = 50           # a track must be seen in at least this many frames to count as a fish (about 2 s at 25 fps).
                       # behavior.py needs ~1.5 s of history to judge speed and turns, so shorter tracks are not
                       # reliable and a brand-new track would otherwise count as "Normal"
ABNORMAL_SHARE = 0.20  # a fish counts as Erratic / Low Oxygen if it showed that for >= 20% of its time on screen


def series_trend(series: list, min_delta: float, min_len: int = 10) -> str:
    """First half vs second half of a series. Honest 'Insufficient Data' when it is too short."""
    if len(series) < min_len:
        return ui.INSUFFICIENT
    half = len(series) // 2
    a = sum(series[:half]) / half
    b = sum(series[half:]) / (len(series) - half)
    if b - a >= min_delta:
        return "Increasing"
    if a - b >= min_delta:
        return "Decreasing"
    return "Stable"


class OverallStats:
    """Accumulates every frame of the video so the end-of-video report covers the WHOLE video."""

    def __init__(self, min_obs: int = MIN_OBS) -> None:
        self.min_obs = min_obs  # frames a track needs to be reliable (lower when frames are skipped)
        self.frames = 0
        self.eval_frames = 0  # frames after the warm-up (speeds are still 0 during warm-up)
        self.count_sum = 0
        self.peak = 0
        self.speed_sum, self.speed_n = 0.0, 0
        self.coh_sum, self.coh_n = 0.0, 0
        self.alert_frames = 0
        self.speed_series: list = []
        self.coh_series: list = []
        self.fish: dict = {}  # id -> {"seen", "sp": speed sum, "n": observations, "st": Counter, "ar": Counter}

    def add(self, snap) -> None:
        warming = getattr(snap, "kind", "") == "warming"
        self.frames += 1
        self.count_sum += snap.count
        self.peak = max(self.peak, snap.count)
        if not warming:
            self.eval_frames += 1
            if snap.count:
                self.speed_sum += snap.avg_speed
                self.speed_n += 1
                self.speed_series.append(snap.avg_speed)
            if snap.cohesion is not None:
                self.coh_sum += snap.cohesion
                self.coh_n += 1
                self.coh_series.append(snap.cohesion)
            if snap.level != "ok":
                self.alert_frames += 1
        for f in snap.fish:
            rec = self.fish.setdefault(f.id, {"seen": 0, "sp": 0.0, "n": 0, "st": Counter(), "ar": Counter()})
            rec["seen"] += 1
            if not warming:
                rec["sp"] += f.speed
                rec["n"] += 1
                rec["st"][f.status] += 1
                rec["ar"][getattr(f, "arrow", "—")] += 1

    def usable(self) -> int:
        """Fish with enough observations to judge (same rule as the end-of-video report)."""
        return sum(1 for r in self.fish.values() if r["seen"] >= self.min_obs and r["n"] > 0)

    def extra(self) -> dict:
        return {"coh_trend": series_trend(self.coh_series, 5.0), "peak": self.peak, "usable": self.usable()}


def _fish_class(rec: dict) -> str:
    """Behavior that best describes a fish over the whole video. Unusual wins when it was shown for a meaningful
    share of the fish's time on screen; otherwise the most common of Normal / Schooling / Feeding."""
    n = rec["n"]
    if n == 0:
        return "Normal"
    if rec["st"].get("Unusual", 0) / n >= ABNORMAL_SHARE:
        return "Unusual"
    best = max(("Normal", "Schooling", "Feeding"), key=lambda k: (rec["st"].get(k, 0), k == "Normal"))
    return best


def _fish_arrow(rec: dict) -> str:
    arrows = [a for a, _ in rec["ar"].most_common() if a not in ("—", "", None)]
    return arrows[0] if arrows else "—"


def overall_snapshot(st_: OverallStats, s: Settings, events: list | None = None) -> SimpleNamespace:
    """Turn the accumulated stats into a Snapshot-like object the normal panels can display."""
    fish = {i: r for i, r in st_.fish.items() if r["seen"] >= st_.min_obs} or st_.fish
    total = len(fish)
    dom = {i: _fish_class(r) for i, r in fish.items()}
    mean_sp = {i: (r["sp"] / r["n"] if r["n"] else 0.0) for i, r in fish.items()}
    normal = sum(1 for v in dom.values() if v == "Normal")
    schooling = sum(1 for v in dom.values() if v == "Schooling")
    feeding = sum(1 for v in dom.values() if v == "Feeding")
    unusual = sum(1 for v in dom.values() if v == "Unusual")
    active_thr = getattr(s, "active_speed", 5.0)
    active = sum(1 for v in mean_sp.values() if v > active_thr)
    avg_speed = st_.speed_sum / st_.speed_n if st_.speed_n else 0.0
    cohesion = st_.coh_sum / st_.coh_n if st_.coh_n else None
    alert_pct = 100.0 * st_.alert_frames / st_.eval_frames if st_.eval_frames else 0.0
    frac_unusual = unusual / total if total else 0.0
    thr = getattr(s, "abnormal_fraction", 0.3)
    min_fish = getattr(s, "min_fish_alert", 1)

    ser = st_.speed_series
    trend = "Stable"
    if len(ser) >= 10:
        half = len(ser) // 2
        a, b = sum(ser[:half]) / half, sum(ser[half:]) / (len(ser) - half)
        if a > 0 and b > a * 1.10:
            trend = "Increasing"
        elif a > 0 and b < a * 0.90:
            trend = "Decreasing"
    else:
        trend = ui.INSUFFICIENT

    if total == 0:
        kind, level, status = "no_fish", "warning", "No Fish Tracked"
        desc = "No milkfish were tracked in this video."
        action, detail = "Review the Video", "Check the video quality and the detection settings."
    elif frac_unusual >= thr or unusual >= min_fish or alert_pct >= 30:
        kind, level, status = "unusual", "warning", "Unusual Swimming Activity Observed"
        desc = (f"{unusual} of {total} fish ({frac_unusual:.0%}) showed unusual swimming. Unusual activity was "
                f"present in {alert_pct:.0f}% of the video. This is a video-based observation, not a diagnosis.")
        action, detail = "Inspect the Pond", "Inspect the fingerlings and pond conditions; keep monitoring closely."
    else:
        kind, level, status = "normal", "ok", "Normal Movement Overall"
        desc = (f"Milkfish swam steadily throughout the video. Normal swimming: {normal}, schooling: {schooling}, "
                f"feeding: {feeding}.")
        action, detail = "Continue Routine Monitoring", "No immediate action required."

    events = list(events or [])
    if events:
        desc += f" {len(events)} alert event(s) were raised during the video."
    rows = [SimpleNamespace(id=i, speed=mean_sp[i], arrow=_fish_arrow(fish[i]), status=dom[i],
                            active=mean_sp[i] > active_thr,
                            track="Tracked" if fish[i]["seen"] >= st_.min_obs else "Short track")
            for i in sorted(fish)]
    return SimpleNamespace(
        kind=kind, count=total, avg_speed=avg_speed, cohesion=cohesion, normal=normal, schooling=schooling,
        feeding=feeding, unusual=unusual, erratic=unusual, low_oxygen=0, active=active, inactive=total - active, status=status, level=level,
        description=desc, action=action, action_detail=detail, fish=rows, events=events,
        details={"Speed Trend": trend, "Peak Count": str(st_.peak)})


# ======================================================================== painting
def make_view(snap, fps, running, label, size, src_fps, duration, frame=None, tone="ok",
              status="System Online", extra=None, ended=False) -> dict:
    return {"snap": snap, "fps": fps, "running": running, "label": label, "size": size,
            "src_fps": src_fps, "duration": duration, "frame": frame, "status_tone": tone,
            "status_text": status, "extra": extra or dict(ui.DEFAULT_EXTRA), "ended": ended}


def paint(ph: dict, v: dict, media: str | None = None) -> None:
    """Rebuild every panel from the view `v`, optionally swap the video area, then redraw."""
    if media is not None:
        ph["_media"] = media
    s = st.session_state.settings
    snap = v["snap"]
    ended = bool(v.get("ended", False))
    extra = v.get("extra") or dict(ui.DEFAULT_EXTRA)
    ph["_view"] = v
    if ended:
        ph["_progress"] = bui.progress_bar(1.0, (v.get("timing") or {}).get("wall_s", 0.0), 0.0, finished=True)

    side = bui.category_panel(snap, ended) + bui.recommendation(snap)
    if snap.level != "ok":
        side += ui.alert_card(snap.status, snap.description, "bad" if snap.level == "critical" else "warn")
    ph["_side"] = side
    ph["_head"] = ui.h(bui.header(v["status_text"], v["status_tone"], datetime.now()) +
                       ui.kpi_row(snap, v["fps"], v["src_fps"], ended, extra))
    ph["_lower"] = ui.h(bui.lower(snap, ended, st.session_state.get("id_map")))
    draw(ph)


def resize_to_width(frame, width: int):
    h, w = frame.shape[:2]
    if width and w != width:
        return cv2.resize(frame, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    return frame


# ======================================================================== live loop
def run_live(ph: dict, s: Settings, pipe, source, label: str) -> None:
    ss = st.session_state
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        ss.running = False
        paint(ph, make_view(Snapshot(), 0.0, False, label, None, 0.0, None, tone="bad", status="Video Error"),
              media=ui.message_card("Cannot open video source", str(label)))
        return

    is_file = isinstance(source, str) and Path(source).is_file()
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    if src_fps <= 1 or src_fps > 240:
        src_fps = 25.0 if is_file else 0.0
    nframes = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = nframes / src_fps if (is_file and src_fps and nframes > 0) else None

    stride = max(1, int(getattr(s, "frame_stride", 1))) if is_file else 1   # analyse every Nth frame
    realtime = bool(getattr(s, "realtime", False)) and is_file               # wait so the video plays at natural speed
    pipe.reset()
    ss.id_map = pipe.id_map  # fish numbers 01, 02, ... (the same numbers as the boxes on the video)
    stats = OverallStats(min_obs=max(5, MIN_OBS // stride))
    started = time.time()
    frame_no, fps_ema, last_ui, last_sec, last_draw = 0, 0.0, 0.0, 0.0, 0.0
    n_proc, t_proc, t_show = 0, 0.0, 0.0   # timing report: frames analysed, seconds in analysis, seconds drawing
    finished = False
    view = None
    size = None
    try:
        while True:
            t_start = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                finished = True  # end of the video: stop the feed (no looping)
                break
            frame = resize_to_width(frame, int(s.process_width))
            size = (frame.shape[1], frame.shape[0])
            t = frame_no / src_fps if is_file else time.monotonic()
            frame_no += 1

            p0 = time.perf_counter()
            res = pipe.process(frame, t)
            t_proc += time.perf_counter() - p0
            n_proc += 1
            stats.add(res.snapshot)
            ph["_frame"] = res  # boxes are drawn and the JPEG encoded later, only if this frame gets shown

            dt = time.perf_counter() - t_start
            inst = 1.0 / dt if dt > 0 else fps_ema
            fps_ema = inst if fps_ema == 0 else 0.9 * fps_ema + 0.1 * inst

            u0 = time.perf_counter()
            now = time.time()
            if is_file and nframes > 0:  # progress under the video: how far along, time used, time left
                done = min(frame_no / nframes, 1.0)
                el = now - started
                ph["_progress"] = bui.progress_bar(done, el, el * (1 - done) / done if done > 0.02 else None)
            if now - last_ui >= 0.5:
                last_ui = now
                snap = res.snapshot
                if now - last_sec >= 1.0:
                    last_sec = now
                    ss.count_hist.append((now, snap.count))
                    db.add_metric(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), snap.count, snap.avg_speed,
                                  snap.cohesion, fps_ema, snap.normal, snap.schooling, snap.feeding, snap.unusual,
                                  snap.status)
                ss.alerts.check(snap, now)
                view = make_view(snap, fps_ema, True, label, size, src_fps, duration,
                                 frame=res.frame, extra=stats.extra())
                paint(ph, view)
                ss.last = view
                last_draw = now
            elif ph["_view"] is not None and now - last_draw >= 0.1:  # keep the video smooth between panel updates
                last_draw = now
                draw(ph, main_only=True)
            t_show += time.perf_counter() - u0

            if realtime:  # optional: play files at their natural speed (slower)
                spare = stride / src_fps - (time.perf_counter() - t_start)
                if spare > 0:
                    time.sleep(spare)

            for _ in range(stride - 1):  # skip frames between analysed ones; time stays correct via frame_no
                if not cap.grab():
                    break
                frame_no += 1
    finally:
        cap.release()

    if finished:
        ss.running = False
        events = [a for a in list(ss.alerts.recent) if getattr(a, "ts", 0) >= started]
        overall = overall_snapshot(stats, s, events)  # results for the WHOLE video, not just the last frame
        base = view or make_view(overall, fps_ema, False, label, size, src_fps, duration)
        view = dict(base, snap=overall, running=False, ended=True, fps=fps_ema, size=size or base["size"],
                    status_text="System Online", status_tone="ok", extra=stats.extra(),
                    analyzed_at=datetime.now(),
                    timing={"frames": n_proc, "proc_ms": 1000 * t_proc / max(n_proc, 1),
                            "show_ms": 1000 * t_show / max(n_proc, 1), "wall_s": time.time() - started,
                            "stride": stride, "realtime": realtime, "src_fps": src_fps,
                            "stages": pipe.stage_ms() if hasattr(pipe, "stage_ms") else {},
                            "device": getattr(pipe, "device", ""),
                            "tracker": getattr(pipe, "tracker_name", "")})
        ss.last = view
        paint(ph, view)
        try:  # keep this video's results in the monitoring history
            history.save(history.make_record(view, ss.id_map))
        except Exception as exc:
            st.warning(f"The video finished, but its result could not be saved to the history: {exc}")


def render_live_page() -> None:
    ss, s = st.session_state, st.session_state.settings
    ph = build_layout()
    problems = setup_problems(s)

    if problems:
        paint(ph, make_view(Snapshot(), 0.0, False, "—", None, 0.0, None, tone="bad", status="Setup Required"),
              media=ui.setup_card(problems, str(MODELS_DIR), str(VIDEOS_DIR)))
        return

    source, label = s.resolve_source()
    if not ss.running:
        last = ss.last
        if last is not None:
            media = frame_html(last["frame"]) if last.get("frame") is not None else ""
            if last.get("ended"):  # keep the "Video ended" state until Start is pressed
                paint(ph, dict(last, running=False), media=media)
                tm = last.get("timing")
                if tm and tm["frames"]:
                    eff = tm["frames"] * tm["stride"] / max(tm["wall_s"], 1e-6)
                    st.caption(f"Analysis speed: {eff:.1f} video frames/s ({tm['wall_s']:.0f} s total, "
                               f"{'real-time playback' if tm['realtime'] else 'as fast as possible'}). "
                               f"Per analysed frame: analysis {tm['proc_ms']:.0f} ms, drawing the screen "
                               f"{tm['show_ms']:.0f} ms. Every {tm['stride']} frame(s) analysed.")
                    stg = tm.get("stages") or {}
                    if stg:
                        st.caption("Analysis breakdown per frame: "
                                   f"contrast enhancement {stg.get('enhance', 0):.0f} ms · "
                                   f"detection (YOLO) {stg.get('detect', 0):.0f} ms · "
                                   f"tracking ({tm.get('tracker') or 'tracker'}) {stg.get('track', 0):.0f} ms · "
                                   f"behavior {stg.get('behavior', 0):.0f} ms. "
                                   f"Model runs on: {tm.get('device') or 'unknown'}.")
            else:
                paint(ph, dict(last, running=False, status_text="Paused", status_tone="warn"), media=media)
        else:
            paint(ph, make_view(Snapshot(), 0.0, False, label, None, 0.0, None, tone="warn", status="Paused"),
                  media=ui.message_card("Monitoring is stopped", "Press Start in the sidebar.", "warn"))
        return

    try:
        pipe = get_pipeline(s)
    except Exception as exc:  # bad weights, missing ultralytics, ...
        ss.running = False
        paint(ph, make_view(Snapshot(), 0.0, False, label, None, 0.0, None, tone="bad", status="Model Error"),
              media=ui.message_card("Could not load the model", f"{type(exc).__name__}: {exc}"))
        return
    run_live(ph, s, pipe, source, label)


# ======================================================================== other pages
def _read_csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def page_analytics() -> None:
    st.markdown(ui.page_title("Analytics", "Trends from everything the dashboard has logged"), unsafe_allow_html=True)
    df = db.metrics_df()
    if df is None or df.empty:
        st.info("No data yet. Run the dashboard for a while and the trends will appear here.")
        return
    df["time"] = pd.to_datetime(df["timestamp"])
    span = st.radio("Range", ["Last 15 min", "Last hour", "Last 24 h", "All"], horizontal=True, index=1)
    mins = {"Last 15 min": 15, "Last hour": 60, "Last 24 h": 1440}.get(span)
    if mins:
        df = df[df["time"] >= df["time"].max() - pd.Timedelta(minutes=mins)]
    df = df.set_index("time")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(ui.section("Swimming Speed Trend"), unsafe_allow_html=True)
        st.line_chart(df[["avg_speed"]], color=[C_WARN], height=240)
        st.markdown(ui.section("Detection Count"), unsafe_allow_html=True)
        st.caption("Milkfish detected per sample (detections, not unique fish)")
        st.line_chart(df[["count"]], color=[C_ACC], height=240)
    with c2:
        st.markdown(ui.section("Schooling Cohesion Trend"), unsafe_allow_html=True)
        st.caption("Cohesion (%) · gaps mean fewer than 2 fish were tracked")
        st.line_chart(df[["cohesion"]], color=[C_OK], height=240)
        st.markdown(ui.section("Behavior Distribution"), unsafe_allow_html=True)
        st.caption("Fish per sample, by behavior category")
        cols = {"Normal swimming": df["normal"]}
        for key, name in (("schooling", "Schooling"), ("feeding", "Feeding")):
            if key in df:
                cols[name] = df[key]
        cols["Unusual swimming"] = df["unusual"] if "unusual" in df else df["erratic"] + df["low_oxygen"]
        pal = {"Normal swimming": C_OK, "Schooling": "#0F766E", "Feeding": "#65A30D", "Unusual swimming": C_WARN}
        st.area_chart(pd.DataFrame(cols), color=[pal[k] for k in cols], height=240)

    st.markdown(ui.section("Detection and Tracking Statistics"), unsafe_allow_html=True)
    k = st.columns(4)
    k[0].metric("Samples", f"{len(df):,}")
    k[1].metric("Avg. detections", f"{df['count'].mean():.1f}")
    k[2].metric("Peak detections", f"{int(df['count'].max())}")
    k[3].metric("Avg. processing FPS", f"{df['fps'].mean():.1f}")

    st.markdown(ui.section("Alerts and Observation History"), unsafe_allow_html=True)
    a = db.alerts_df()
    if a is not None and not a.empty:
        st.dataframe(a.iloc[::-1].drop(columns=["id", "reviewed"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No alerts have been raised.")


def _mark_reviewed(alert_id: int) -> None:
    db.mark_reviewed(alert_id)


def _report_downloads(rec: dict, tag: str) -> None:
    """CSV and PDF download buttons for one analysed video."""
    c1, c2 = st.columns(2)
    c1.download_button("Download report (CSV)", history.report_csv(rec), "Milkfish_Monitoring_Report.csv",
                       "text/csv", key=f"dl_csv_{tag}")
    pdf = history.report_pdf(rec)
    if pdf:
        c2.download_button("Download report (PDF)", pdf, "Milkfish_Monitoring_Report.pdf", "application/pdf",
                           key=f"dl_pdf_{tag}")
    else:
        c2.caption("PDF export needs the reportlab package: pip install reportlab")


def page_reports() -> None:
    st.markdown(ui.page_title("Reports", "Monitoring results, video history and downloadable reports"),
                unsafe_allow_html=True)
    ss = st.session_state
    last = ss.get("last")

    st.markdown(ui.section("Latest Video Report"), unsafe_allow_html=True)
    if last and last.get("ended"):
        rec = history.make_record(last, ss.get("id_map") or {})
        st.markdown(bui.record_view(rec), unsafe_allow_html=True)
        _report_downloads(rec, "latest")
    else:
        st.info("No finished video yet. Let a video play to the end to generate its report.")

    st.markdown(ui.section("Video Monitoring History"), unsafe_allow_html=True)
    recs = history.load()
    if recs:
        st.dataframe(pd.DataFrame([{"Date": r["analyzed_at"], "Video": r["video"], "Fish tracked": r["n"],
                                    "Normal": r["normal"], "Schooling": r["schooling"], "Feeding": r["feeding"],
                                    "Unusual": r["unusual"], "Status": "Normal" if r["ok"] else "Unusual activity"}
                                   for r in recs]), use_container_width=True, hide_index=True)
        labels = [f"{r['analyzed_at']}  ·  {r['video']}" for r in recs]
        pick = st.selectbox("Review an earlier video", labels, key="hist_pick")
        rec = recs[labels.index(pick)]
        st.markdown(bui.record_view(rec), unsafe_allow_html=True)
        _report_downloads(rec, "hist")
    else:
        st.caption("Analysed videos are saved here automatically when they finish.")

    m = db.metrics_df()
    with st.expander("Logged metrics (technical)"):
        if m is not None and not m.empty:
            c = st.columns(3)
            c[0].metric("Samples logged", f"{len(m):,}")
            c[1].metric("Avg. detections", f"{m['count'].mean():.1f}")
            c[2].metric("Peak detections", f"{int(m['count'].max())}")
            st.dataframe(m.tail(200).iloc[::-1], use_container_width=True, hide_index=True)
            st.download_button("Download metrics.csv", m.to_csv(index=False), "metrics.csv", "text/csv")
        else:
            st.caption("No metrics logged yet.")

    c1, c2 = st.columns(2)
    if c1.button("Clear metrics and alert logs"):
        db.clear_logs()
        st.session_state.count_hist.clear()
        st.rerun()
    if c2.button("Clear video history"):
        db.clear_history()
        st.rerun()


def page_alerts() -> None:
    st.markdown(ui.page_title("Alerts", "Unusual swimming activity noticed in analyzed videos"), unsafe_allow_html=True)
    a = db.alerts_df()
    if a is None or a.empty:
        st.info("No alerts have been raised.")
        return
    recent = a.iloc[::-1].head(20).to_dict("records")
    new = sum(not r["reviewed"] for r in recent)
    st.caption(f"{new} new and {len(recent) - new} reviewed (latest {len(recent)} alerts)")
    for r in recent:
        reviewed = bool(r["reviewed"])
        title = f"{'Reviewed' if reviewed else 'New'} · {KIND_LABEL.get(r['kind'], r['kind'])} · {r['timestamp']}"
        desc = f"{r['message']} Recommended: inspect the fingerlings and pond conditions."
        st.markdown(ui.alert_card(title, desc, "bad" if r["level"] == "critical" else "warn"), unsafe_allow_html=True)
        if not reviewed:
            st.button("Mark as reviewed", key=f"rev_{r['id']}", on_click=_mark_reviewed, args=(r["id"],))
    st.download_button("Download alerts.csv", a.drop(columns=["id"]).to_csv(index=False), "alerts.csv", "text/csv")
    st.caption("Unusual swimming is an observation from video, not a confirmed disease diagnosis.")


def _admin_password() -> str:
    """Set ADMIN_PASSWORD in your .env file. Without it the default below is used, so change it."""
    return os.getenv("ADMIN_PASSWORD") or "milkfish-admin"


def page_settings() -> None:
    """Basic settings for pond operators, and password-protected advanced settings for the administrator."""
    ss = st.session_state
    s: Settings = ss.settings
    st.markdown(ui.page_title("Settings", "General application preferences"), unsafe_allow_html=True)

    def bind(widget, label, attr, **kw):
        key = f"set_{attr}"
        if key not in ss:
            ss[key] = getattr(s, attr)
        setattr(s, attr, widget(label, key=key, **kw))

    # ---- appearance ----
    st.markdown(ui.section("Appearance"), unsafe_allow_html=True)
    mode = st.radio("Theme", ["Light", "Dark"], index=1 if s.theme_mode == "dark" else 0, horizontal=True,
                    key="set_theme_radio")
    if mode.lower() != s.theme_mode:
        s.theme_mode = mode.lower()
        s.save()
        st.rerun()
    st.caption("Tables and charts keep their light look in Dark mode.")

    # ---- basic ----
    st.markdown(ui.section("Basic"), unsafe_allow_html=True)
    models = list_files(MODELS_DIR, MODEL_EXTS)
    if models:
        if s.model_file not in models:
            s.model_file = models[0]
        bind(st.selectbox, "YOLOv8 model (models folder)", "model_file", options=models)
    else:
        st.warning(f"No model found. Copy your weights (e.g. best.pt) into {MODELS_DIR}")
    up = st.file_uploader("…or upload a model", type=["pt", "onnx"], key="up_model")
    if up is not None and _save_upload(up, MODELS_DIR):
        s.model_file = Path(up.name).name
        ss.pop("set_model_file", None)
        st.rerun()

    s.source_type = "Video file"  # video files only
    vids = list_files(VIDEOS_DIR, VIDEO_EXTS)
    if vids:
        if s.video_file not in vids:
            s.video_file = vids[0]
        bind(st.selectbox, "Video (videos folder)", "video_file", options=vids)
    else:
        st.warning(f"No videos found. Copy your sample videos into {VIDEOS_DIR}")
    st.caption("To use a new video, upload it on the Dashboard (sidebar, under Start / Stop).")

    presets = {"Accurate": {"process_width": 768, "imgsz": 640, "frame_stride": 1},
               "Balanced": {"process_width": 640, "imgsz": 640, "frame_stride": 2},
               "Fast": {"process_width": 640, "imgsz": 480, "frame_stride": 3}}
    current = next((n for n, p in presets.items() if all(getattr(s, k) == v for k, v in p.items())), "Custom")
    names = list(presets) + (["Custom"] if current == "Custom" else [])
    pick = st.selectbox("Analysis speed", names, index=names.index(current), key="set_speed_preset")
    if pick != current and pick in presets:
        for k, v in presets[pick].items():
            setattr(s, k, v)
    bind(st.checkbox, "Play videos in real time (slower)", "realtime")
    st.caption("Accurate analyses every frame. Balanced analyses every 2nd frame. Fast analyses every 3rd frame "
               "with a smaller model input and can miss brief events. Changes apply to the next video you start.")

    # ---- advanced (administrator only) ----
    st.markdown(ui.section("Advanced Settings"), unsafe_allow_html=True)
    st.markdown('<span class="mf-badge warn">Administrator only</span>', unsafe_allow_html=True)
    if not ss.get("admin_ok"):
        st.caption("Enter administrator password to access technical configurations.")
        pw = st.text_input("Administrator password", type="password", key="admin_pw")
        if st.button("Unlock advanced settings"):
            if hmac.compare_digest(pw.encode(), _admin_password().encode()):
                ss.admin_ok = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        st.markdown('<span class="mf-badge ok">Unlocked</span>', unsafe_allow_html=True)
        if st.button("Lock advanced settings"):
            ss.admin_ok = False
            st.rerun()
        with st.expander("Detection (YOLOv8)", expanded=True):
            bind(st.slider, "Confidence threshold", "conf", min_value=0.05, max_value=0.95, step=0.05)
            bind(st.slider, "IoU threshold", "iou", min_value=0.10, max_value=0.90, step=0.05)
            sizes = sorted({320, 480, 640, 800, 960, 1280, int(s.imgsz)})
            bind(st.selectbox, "Model input size (px)", "imgsz", options=sizes)
        with st.expander("Image enhancement (CLAHE)"):
            bind(st.checkbox, "Use CLAHE contrast enhancement", "use_clahe")
            bind(st.slider, "CLAHE clip limit", "clahe_clip", min_value=1.0, max_value=8.0, step=0.5)
            bind(st.slider, "CLAHE tile size", "clahe_tile", min_value=2, max_value=16, step=1)
        with st.expander("Tracking (DeepSORT)"):
            bind(st.slider, "Frames a lost fish is remembered", "max_age", min_value=5, max_value=120, step=5)
        with st.expander("Behavior rules (pixel based: calibrate to your camera)"):
            bind(st.number_input, "Inactive below (px/s)", "active_speed", min_value=0.0, step=1.0)
            bind(st.number_input, "Unusual above (px/s)", "erratic_speed", min_value=0.0, step=10.0)
            bind(st.number_input, "Unusual sharp turns per second", "erratic_turn_rate", min_value=0.0, step=0.1)
            bind(st.number_input, "Sharp turn angle (degrees)", "turn_angle_deg", min_value=10.0, step=5.0)
            bind(st.number_input, "Inactive for unusual (seconds)", "inactive_secs", min_value=1.0, step=1.0)
            bind(st.slider, "Share of fish to flag the school", "abnormal_fraction", min_value=0.05, max_value=1.0, step=0.05)
            bind(st.number_input, "Minimum fish to flag the school", "min_fish_alert", min_value=1, step=1)
            bind(st.slider, "Schooling distance (fraction of frame)", "school_radius", min_value=0.02, max_value=0.4, step=0.01)
            bind(st.number_input, "Fish needed for schooling", "school_min_fish", min_value=2, step=1)
            bind(st.slider, "Same-direction angle (degrees)", "school_align_deg", min_value=10.0, max_value=90.0, step=5.0)
            bind(st.slider, "Feeding gathering distance (fraction of frame)", "feeding_radius", min_value=0.02, max_value=0.3, step=0.01)
            bind(st.number_input, "Fish needed for feeding", "feeding_min_fish", min_value=2, step=1)
            bind(st.slider, "Feeding zone: top fraction of frame (0 = anywhere)", "feeding_zone", min_value=0.0, max_value=1.0, step=0.05)
        with st.expander("Alerts"):
            bind(st.number_input, "Seconds unusual activity must last before an alert", "alert_confirm_s", min_value=1, step=1)
            bind(st.number_input, "Seconds between repeated alerts", "alert_cooldown_s", min_value=10, step=10)
            bind(st.checkbox, "Send SMS alerts", "sms_enabled")
            bind(st.text_input, "SMS recipients (comma separated)", "sms_recipients")
        st.caption("Advanced changes apply to the next video you start.")

    if st.button("Save settings"):
        s.save()
        st.success("Saved to settings.json")


# ======================================================================== main
init_state()
ss = st.session_state


def _go(name: str) -> None:
    st.session_state.page = name


def _button(label, icon, **kw):
    """st.button with a Material icon; falls back to plain text on older Streamlit."""
    try:
        return st.button(label, icon=icon, **kw)
    except TypeError:
        return st.button(label, **kw)


if ss.page != "Dashboard":  # the sidebar only holds Start / Stop and the uploader on the Dashboard
    st.markdown("<style>[data-testid='stExpandSidebarButton'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='collapsedControl']{display:none!important}</style>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(ui.sidebar_brand(), unsafe_allow_html=True)
    for name in PAGES:
        _button(name, NAV_ICONS[name], key=f"nav_{name}", on_click=_go, args=(name,),
                type="primary" if ss.page == name else "secondary")
    if ss.page == "Dashboard":
        st.markdown(ui.sidebar_label("Monitoring"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            _button("Start", ":material/play_arrow:", key="btn_start",
                    on_click=lambda: st.session_state.update(running=True))
        with c2:
            _button("Stop", ":material/stop:", key="btn_stop",
                    on_click=lambda: st.session_state.update(running=False))
        st.markdown(ui.sidebar_label("Video source"), unsafe_allow_html=True)
        video_uploader()

# Bottom navigation bar: shown only on phones / narrow windows (see styles.py)
with st.container(key="bottomnav"):
    for col, name in zip(st.columns(len(PAGES)), PAGES):
        with col:
            _button(name, NAV_ICONS[name], key=f"bnav_{name}", on_click=_go, args=(name,),
                    type="primary" if ss.page == name else "secondary")

# Streamlit remembers a collapsed sidebar in the browser. On wide windows reopen it (and forget the
# remembered state) so the sidebar can never stay hidden. The script also hides its own empty iframe.
SIDEBAR_FIX_JS = """<script>
(function () {
  try {
    var w = window.parent, d = w.document, fe = window.frameElement;
    if (fe) {
      var c = fe.closest('[data-testid="stElementContainer"]');
      if (c) { c.style.position = 'absolute'; c.style.height = '0'; c.style.overflow = 'hidden'; }
    }
    if (w.innerWidth < 1000) return;
    Object.keys(w.localStorage).forEach(function (k) {
      if (k.indexOf('stSidebarCollapsed') === 0) w.localStorage.removeItem(k);
    });
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      var sb = d.querySelector('[data-testid="stSidebar"]');
      if (sb && sb.getAttribute('aria-expanded') === 'false') {
        var b = d.querySelector('[data-testid="stExpandSidebarButton"]') ||
                d.querySelector('[data-testid="stSidebarCollapsedControl"] button') ||
                d.querySelector('[data-testid="collapsedControl"] button');
        if (b) b.click();
      } else if (sb) { clearInterval(t); }
      if (tries > 10) clearInterval(t);
    }, 400);
  } catch (e) {}
})();
</script>"""


def _inject_html(html: str) -> None:
    """Hidden helper page: st.iframe on newer Streamlit versions, st.components.v1.html on older ones."""
    if hasattr(st, "iframe"):
        try:
            st.iframe(html, height=0)
            return
        except Exception:
            pass
    components.html(html, height=0)


_inject_html(SIDEBAR_FIX_JS)

page = ss.page

# Render the whole page inside ONE placeholder. Because the live loop never returns while
# playing, Streamlit would otherwise keep the previous page's widgets on screen.
page_slot = st.empty()
with page_slot.container():
    if page == "Dashboard":
        render_live_page()
    elif page == "Analytics":
        page_analytics()
    elif page == "Alerts":
        page_alerts()
    elif page == "Reports":
        page_reports()
    else:
        page_settings()
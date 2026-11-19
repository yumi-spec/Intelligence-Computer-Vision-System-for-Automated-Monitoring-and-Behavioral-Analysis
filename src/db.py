"""SQLite database for metrics, alerts and analysed-video history (put this file in src/).

The database is one file: logs/milkfish.db. Tables: metrics, alerts, videos, fish.
The first time it is created, any old CSV files in logs/ (metrics.csv, alerts.csv, history.csv) are imported.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import threading
from contextlib import contextmanager

import pandas as pd

from src.config import ALERTS_LOG, LOGS_DIR, METRICS_LOG

DB_FILE = LOGS_DIR / "milkfish.db"
HISTORY_CSV = LOGS_DIR / "history.csv"
REVIEWED_JSON = LOGS_DIR / "alerts_reviewed.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, count INTEGER, avg_speed REAL, cohesion REAL,
    fps REAL, normal INTEGER, schooling INTEGER, feeding INTEGER, unusual INTEGER, status TEXT);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, level TEXT, kind TEXT, message TEXT,
    sms TEXT, reviewed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, analyzed_at TEXT NOT NULL, video TEXT, duration TEXT, n INTEGER,
    normal INTEGER, schooling INTEGER, feeding INTEGER, unusual INTEGER, dominant TEXT, avg_speed REAL,
    cohesion REAL, status TEXT, ok INTEGER);
CREATE TABLE IF NOT EXISTS fish (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    fish_id TEXT, behavior TEXT, tone TEXT, pattern TEXT, speed REAL);
CREATE INDEX IF NOT EXISTS idx_fish_video ON fish(video_id);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(timestamp);
"""
METRIC_COLS = ["timestamp", "count", "avg_speed", "cohesion", "fps", "normal", "schooling", "feeding", "unusual", "status"]
ALERT_COLS = ["id", "timestamp", "level", "kind", "message", "sms", "reviewed"]

_lock = threading.Lock()
_ready = False


def _init() -> None:
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        fresh = not DB_FILE.exists()
        con = sqlite3.connect(DB_FILE, timeout=10)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)
            if fresh:
                with con:
                    _import_old_csv(con)
        finally:
            con.close()
        _ready = True


@contextmanager
def _conn():
    _init()
    con = sqlite3.connect(DB_FILE, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        with con:  # commit, or roll back on an error
            yield con
    finally:
        con.close()


# ------------------------------------------------------------------ one-time import of the old CSV files
def _rows(path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v, cast=float, default=None):
    try:
        return cast(v) if v not in (None, "") else default
    except ValueError:
        return default


def _import_old_csv(con) -> None:
    try:
        for r in _rows(METRICS_LOG):
            unusual = _num(r.get("unusual"), int)
            if unusual is None:  # older files had erratic / low_oxygen columns
                unusual = (_num(r.get("erratic"), int, 0) or 0) + (_num(r.get("low_oxygen"), int, 0) or 0)
            con.execute("INSERT INTO metrics (timestamp,count,avg_speed,cohesion,fps,normal,schooling,feeding,unusual,status)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (r["timestamp"], _num(r.get("count"), int, 0), _num(r.get("avg_speed")), _num(r.get("cohesion")),
                         _num(r.get("fps")), _num(r.get("normal"), int, 0), _num(r.get("schooling"), int, 0),
                         _num(r.get("feeding"), int, 0), unusual, r.get("status", "")))
    except Exception:
        pass
    try:
        done = set(json.loads(REVIEWED_JSON.read_text(encoding="utf-8"))) if REVIEWED_JSON.exists() else set()
        for r in _rows(ALERTS_LOG):
            con.execute("INSERT INTO alerts (timestamp,level,kind,message,sms,reviewed) VALUES (?,?,?,?,?,?)",
                        (r["timestamp"], r.get("level"), r.get("kind"), r.get("message"), r.get("sms"),
                         int(f"{r['timestamp']}|{r.get('kind')}" in done)))
    except Exception:
        pass
    try:
        for r in _rows(HISTORY_CSV):
            vid = con.execute("INSERT INTO videos (analyzed_at,video,duration,n,normal,schooling,feeding,unusual,dominant,"
                              "avg_speed,cohesion,status,ok) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (r["analyzed_at"], r["video"], r["duration"], int(r["n"]), int(r["normal"]), int(r["schooling"]),
                               int(r["feeding"]), int(r["unusual"]), r["dominant"], float(r["avg_speed"]),
                               _num(r["cohesion"]), r["status"], int(r["ok"]))).lastrowid
            for f in json.loads(r["fish"] or "[]"):
                con.execute("INSERT INTO fish (video_id,fish_id,behavior,tone,pattern,speed) VALUES (?,?,?,?,?,?)",
                            (vid, f["id"], f["behavior"], f["tone"], f["pattern"], f["speed"]))
    except Exception:
        pass


# ------------------------------------------------------------------ metrics
def add_metric(ts: str, count, avg_speed, cohesion, fps, normal, schooling, feeding, unusual, status) -> None:
    try:  # a logging problem must never stop the video analysis
        with _conn() as con:
            con.execute("INSERT INTO metrics (timestamp,count,avg_speed,cohesion,fps,normal,schooling,feeding,unusual,status)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (ts, count, round(avg_speed, 2), None if cohesion is None else round(cohesion, 1),
                         round(fps, 1), normal, schooling, feeding, unusual, status))
    except sqlite3.Error:
        pass


def metrics_df() -> pd.DataFrame:
    with _conn() as con:
        rows = con.execute(f"SELECT {','.join(METRIC_COLS)} FROM metrics ORDER BY id").fetchall()
    return pd.DataFrame([tuple(r) for r in rows], columns=METRIC_COLS)


# ------------------------------------------------------------------ alerts
def add_alert(ts: str, level: str, kind: str, message: str, sms: str) -> None:
    try:
        with _conn() as con:
            con.execute("INSERT INTO alerts (timestamp,level,kind,message,sms) VALUES (?,?,?,?,?)",
                        (ts, level, kind, message, sms))
    except sqlite3.Error:
        pass


def alerts_df() -> pd.DataFrame:
    with _conn() as con:
        rows = con.execute(f"SELECT {','.join(ALERT_COLS)} FROM alerts ORDER BY id").fetchall()
    return pd.DataFrame([tuple(r) for r in rows], columns=ALERT_COLS)


def mark_reviewed(alert_id: int) -> None:
    with _conn() as con:
        con.execute("UPDATE alerts SET reviewed=1 WHERE id=?", (int(alert_id),))


# ------------------------------------------------------------------ analysed videos
def add_video(rec: dict) -> int:
    with _conn() as con:
        vid = con.execute(
            "INSERT INTO videos (analyzed_at,video,duration,n,normal,schooling,feeding,unusual,dominant,avg_speed,"
            "cohesion,status,ok) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["analyzed_at"], rec["video"], rec["duration"], rec["n"], rec["normal"], rec["schooling"], rec["feeding"],
             rec["unusual"], rec["dominant"], round(rec["avg_speed"], 2), rec["cohesion"], rec["status"],
             int(rec["ok"]))).lastrowid
        con.executemany("INSERT INTO fish (video_id,fish_id,behavior,tone,pattern,speed) VALUES (?,?,?,?,?,?)",
                        [(vid, f["id"], f["behavior"], f["tone"], f["pattern"], f["speed"]) for f in rec["fish"]])
    return vid


def load_videos() -> list:
    """Saved video records, newest first (same shape history.make_record() produces)."""
    out = []
    with _conn() as con:
        for v in con.execute("SELECT * FROM videos ORDER BY id DESC").fetchall():
            fish = [{"id": f["fish_id"], "behavior": f["behavior"], "tone": f["tone"], "pattern": f["pattern"],
                     "speed": f["speed"]}
                    for f in con.execute("SELECT * FROM fish WHERE video_id=? ORDER BY id", (v["id"],)).fetchall()]
            out.append({"analyzed_at": v["analyzed_at"], "video": v["video"], "duration": v["duration"], "n": v["n"],
                        "normal": v["normal"], "schooling": v["schooling"], "feeding": v["feeding"],
                        "unusual": v["unusual"], "dominant": v["dominant"], "avg_speed": v["avg_speed"],
                        "cohesion": v["cohesion"], "status": v["status"], "ok": bool(v["ok"]), "fish": fish})
    return out


# ------------------------------------------------------------------ clearing
def clear_logs() -> None:
    with _conn() as con:
        con.execute("DELETE FROM metrics")
        con.execute("DELETE FROM alerts")


def clear_history() -> None:
    with _conn() as con:
        con.execute("DELETE FROM videos")  # its fish rows are deleted with it
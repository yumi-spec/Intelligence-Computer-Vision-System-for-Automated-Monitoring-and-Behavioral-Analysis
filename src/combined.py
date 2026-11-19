"""Combined Water-Quality and Milkfish Behavioral Alert System.

Combines MANUALLY entered water-quality readings (water.py) with the result of an analysed video.
Nothing here reads a sensor. Nothing is assumed: a reading and a video are only combined when the
user-configured time window says they belong together, and every result is shown on its own as well.

Wording is deliberately cautious. A combination of a water-quality result and a movement result can raise
concern. It does not prove that one caused the other, and movement alone never proves low oxygen.

Logs (appended, never overwritten):
    logs/video_sessions.csv    one row per finished video analysis
    logs/combined_alerts.csv   one row per recorded assessment / alert
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from src import components as ui
from src import water
from src.config import LOGS_DIR
from src.storage import append_row

SESSIONS_LOG = LOGS_DIR / "video_sessions.csv"
COMBINED_ALERTS_LOG = LOGS_DIR / "combined_alerts.csv"

SESSION_HEADER = ["session_id", "analyzed_at", "video", "duration_s", "tracks_usable", "unique_tracked",
                  "avg_speed", "cohesion", "normal", "erratic", "low_oxygen", "kind", "status", "events"]
ALERT_HEADER = ["alert_id", "created_at", "level", "message", "triggers", "reason", "action", "completeness",
                "reading_id", "measured_at", "readings", "session_id", "video", "analyzed_at", "time_diff_min",
                "behavior", "detections", "avg_speed_px_s", "tracks_usable", "source"]

LEVELS = ("Critical", "Warning", "Normal", "Insufficient Data")
TONE = {"Critical": "bad", "Warning": "warn", "Normal": "ok", "Insufficient Data": "mut"}
UNAVAILABLE = "Behavior Analysis Unavailable"


# ---------------------------------------------------------------- video sessions
def record_session(view: dict) -> dict:
    """Save a finished video analysis (called by dashboard.py when a video ends). Returns the saved row."""
    snap = view["snap"]
    extra = view.get("extra") or {}
    at = view.get("analyzed_at") or datetime.now()
    coh = getattr(snap, "cohesion", None)
    dur = view.get("duration")
    row = {"session_id": f"V{at:%y%m%d%H%M%S}", "analyzed_at": at.strftime("%Y-%m-%d %H:%M:%S"),
           "video": str(view.get("label", "")), "duration_s": "" if not dur else round(float(dur), 1),
           "tracks_usable": int(extra.get("usable", 0)), "unique_tracked": int(snap.count),
           "avg_speed": round(float(snap.avg_speed), 2), "cohesion": "" if coh is None else round(float(coh), 1),
           "normal": int(snap.normal), "erratic": int(snap.erratic), "low_oxygen": int(snap.low_oxygen),
           "kind": str(getattr(snap, "kind", "")), "status": str(getattr(snap, "status", "")),
           "events": len(getattr(snap, "events", []) or [])}
    append_row(SESSIONS_LOG, SESSION_HEADER, [row[h] for h in SESSION_HEADER])
    return row


def read_sessions() -> pd.DataFrame:
    if not SESSIONS_LOG.exists() or SESSIONS_LOG.stat().st_size == 0:
        return pd.DataFrame(columns=SESSION_HEADER + ["analyzed_dt"])
    try:
        df = pd.read_csv(SESSIONS_LOG, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame(columns=SESSION_HEADER + ["analyzed_dt"])
    for c in SESSION_HEADER:
        if c not in df.columns:
            df[c] = ""
    df["analyzed_dt"] = pd.to_datetime(df["analyzed_at"], errors="coerce")
    return df.dropna(subset=["analyzed_dt"]).sort_values("analyzed_dt").reset_index(drop=True)


def session_label(r) -> str:
    return f'{r["session_id"]} · {r["video"]} · {r["analyzed_at"][:16]}'


def _f(x):
    try:
        return None if x in (None, "") or pd.isna(x) else float(x)
    except (TypeError, ValueError):
        return None


def behavior_from_session(sess: dict | None, rules: dict) -> dict:
    """Behavior result from the whole-video analysis. Never classifies without enough reliable tracks."""
    if not sess:
        return {"available": False, "concern": False, "label": UNAVAILABLE,
                "reason": "No analysed video session is selected.", "detail": ""}
    kind = str(sess.get("kind", ""))
    usable = int(_f(sess.get("tracks_usable")) or 0)
    if kind in ("", "idle", "warming", "no_fish"):
        return {"available": False, "concern": False, "label": UNAVAILABLE,
                "reason": "No milkfish were tracked in this video.", "detail": ""}
    if usable < rules["min_tracks"]:
        return {"available": False, "concern": False, "label": UNAVAILABLE,
                "reason": f"Only {usable} reliably tracked fish (minimum {rules['min_tracks']:g}).", "detail": ""}
    n = int(_f(sess.get("unique_tracked")) or 0)
    detail = (f"{int(_f(sess.get('erratic')) or 0)} erratic and {int(_f(sess.get('low_oxygen')) or 0)} possible "
              f"low-oxygen-related of {n} tracked fish")
    if kind == "low_oxygen":
        label, concern = "Possible Low-Oxygen-Related Behavior", True
    elif kind == "erratic":
        label, concern = "Erratic Movement Suspected", True
    elif kind == "normal":
        label, concern = "Normal Movement", False
    else:
        label, concern = "Unusual Movement Detected", True
    return {"available": True, "concern": concern, "label": label, "reason": "", "detail": detail}


# ---------------------------------------------------------------- the combined decision
def fmt_gap(minutes: float) -> str:
    if minutes < 90:
        return f"{minutes:.0f} min"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h"
    return f"{minutes / 1440:.1f} days"


def _names(items: list) -> str:
    return ", ".join(r["label"] for r in items)


def combine(results: list | None, reading_dt: datetime | None, sess: dict | None, rules: dict,
            now: datetime | None = None) -> dict:
    """Combine one water reading (already assessed) with one video session.

    Water and behavior are always evaluated on their own first. They are combined only when the
    reading is within the configured window of the video analysis.
    """
    now = now or datetime.now()
    sess_dt = pd.to_datetime(sess["analyzed_at"]).to_pydatetime() if sess else None
    age_h = diff_min = matched = None
    if reading_dt is not None:
        age_h = (now - reading_dt).total_seconds() / 3600
        if sess_dt is not None:
            diff_min = abs((reading_dt - sess_dt).total_seconds()) / 60
            matched = diff_min <= rules["match_window_min"]
    assessed = [r for r in (results or []) if r["status"] in ("Normal", "Warning", "Critical")]
    crit = [r for r in assessed if r["status"] == "Critical"]
    warn = [r for r in assessed if r["status"] == "Warning"]
    current = reading_dt is not None and (matched is True or (age_h is not None and age_h <= rules["max_age_h"]))

    # ---- water quality on its own
    if reading_dt is None or results is None:
        wlevel, wnote = "Insufficient Data", "No water-quality reading is available."
    elif not assessed:
        wlevel, wnote = "Insufficient Data", ("None of the entered parameters could be assessed (value missing, or "
                                              "no reference range configured for it).")
    elif not current:
        past = f" It recorded: {_names(crit + warn)}." if (crit or warn) else ""
        wlevel, wnote = "Insufficient Data", (f"The reading is {fmt_gap(age_h * 60)} old (limit "
                                              f"{rules['max_age_h']:g} h) and may not represent current "
                                              f"conditions.{past} Re-measure.")
    elif crit:
        wlevel, wnote = "Critical", f"{_names(crit)} reached a critical limit."
    elif warn:
        wlevel, wnote = "Warning", f"{_names(warn)} outside the target range."
    else:
        wlevel, wnote = "Normal", "All assessed parameters are within their configured target ranges."

    # ---- behavior on its own
    b = behavior_from_session(sess, rules)
    concern = b["available"] and b["concern"]
    blevel = "Insufficient Data" if not b["available"] else ("Warning" if concern else "Normal")

    # ---- decision
    if wlevel == "Critical":
        level = "Critical"
    elif wlevel == "Warning":
        level = "Warning"
    elif wlevel == "Normal":
        level = "Warning" if concern else ("Normal" if (b["available"] and matched is True) else "Insufficient Data")
    else:
        level = "Warning" if concern else "Insufficient Data"
    together = concern and matched is True and wlevel in ("Critical", "Warning")

    # ---- wording
    notes = []
    do_low = any(r["param"] == "do" and r["reason"].startswith("Below") for r in warn + crit)
    low_ox_like = b.get("label") in ("Erratic Movement Suspected", "Possible Low-Oxygen-Related Behavior")
    if level == "Critical":
        if together:
            message = ("CRITICAL: A water-quality parameter has reached its critical limit. Concerning milkfish "
                       "behavior was also detected. Verify the measurement and inspect the culture environment "
                       "immediately.")
            explanation = (f"{_names(crit)} reached a critical limit and the video showed “{b['label']}”. This "
                           "combination raises serious concern, but it does not prove that the water condition "
                           "caused the movement.")
        else:
            message = (f"CRITICAL: {_names(crit)} has reached its critical limit. Verify the measurement and "
                       "inspect the culture environment immediately.")
            explanation = ("A critical water-quality reading is reported even when fish movement looks normal or "
                           "was not analysed.")
    elif level == "Warning":
        if together:
            message = ("WARNING: Water-quality parameter(s) are outside their target ranges and unusual milkfish "
                       "movement was detected.")
            if do_low and low_ox_like:
                explanation = ("Low dissolved oxygen was recorded, and "
                               f"{'erratic movement' if b['label'].startswith('Erratic') else 'possible low-oxygen-related behavior'}"
                               " was detected. This combination raises concern about possible low-oxygen-related "
                               "behavior, but does not prove that low oxygen caused the movement.")
            else:
                explanation = (f"{_names(warn)} was outside the target range and “{b['label']}” was detected. This "
                               "combination raises concern, but it does not show that the water condition caused "
                               "the movement.")
        elif wlevel == "Warning":
            if len(warn) > 1:
                message = "WARNING: Multiple water-quality parameters are outside their target ranges."
            elif do_low:
                message = "WARNING: Dissolved oxygen is below the target range. Monitor milkfish behavior closely."
            else:
                message = f"WARNING: {warn[0]['label']} is outside its target range. Monitor milkfish behavior closely."
            explanation = wnote
        else:
            message = "WARNING: Unusual milkfish movement detected. Review water-quality readings."
            explanation = (f"The video analysis reported “{b['label']}” ({b['detail']}). Movement alone does not "
                           "establish low oxygen or any other water-quality problem.")
            if wlevel == "Insufficient Data":
                explanation += " No valid water-quality reading was available to compare."
    elif level == "Normal":
        message = "NORMAL: No current water-quality or movement concerns were detected from the available data."
        explanation = ("This is not proof that the culture environment is completely safe. It only reflects the "
                       "readings and the video analysed here.")
    else:
        reasons = []
        if wlevel == "Insufficient Data":
            reasons.append(wnote)
        if not b["available"]:
            reasons.append(b["reason"])
        if wlevel != "Insufficient Data" and b["available"] and matched is not True:
            reasons.append("The reading and the video could not be matched.")
        message = ("ASSESSMENT INCOMPLETE: Combined water-quality and behavioral analysis cannot be completed. "
                   "Enter valid readings or analyze a usable video.")
        explanation = " ".join(reasons)

    if diff_min is not None and matched is False:
        notes.append(f"The reading was taken {fmt_gap(diff_min)} from the video analysis (allowed window ±"
                     f"{rules['match_window_min']:g} min), so the two were not combined. Their separate results "
                     "are shown.")
    if sess is None and reading_dt is not None:
        notes.append("No video session is selected, so only the water-quality result is available.")

    # ---- triggers, action, completeness
    triggers = [f"{r['label']}: {r['value']:.{r['dec']}f} {r['unit']}".rstrip() + f" · reference {r['range']} · "
                f"{r['status']} · {r['reason']}" for r in crit + warn]
    if concern:
        triggers.append(f"Behavior: {b['label']} · {b['detail']}")
    action = {"Critical": "Verify the measurement with your instrument, then inspect the culture environment "
                          "(aeration, water exchange, feeding) immediately.",
              "Warning": ("Re-measure to confirm, review pond conditions, and keep watching milkfish behavior."
                          if wlevel == "Warning" else
                          "Review or take water-quality readings (DO, ammonia, pH) and keep monitoring."),
              "Normal": "Continue routine monitoring.",
              "Insufficient Data": "Enter a valid recent reading, analyze a video with enough tracked fish, and link "
                                   "the reading to that video session."}[level]
    if wlevel != "Insufficient Data" and b["available"]:
        completeness = "Complete" if matched is True else "Not matched (separate results only)"
    elif wlevel != "Insufficient Data":
        completeness = "Water-quality only"
    elif b["available"]:
        completeness = "Video only"
    else:
        completeness = "Incomplete"

    return {"level": level, "message": message, "explanation": explanation, "notes": notes, "action": action,
            "completeness": completeness, "triggers": triggers, "water_level": wlevel, "water_note": wnote,
            "behavior": b, "behavior_level": blevel, "matched": matched, "diff_min": diff_min, "age_h": age_h,
            "results": results or []}


# ---------------------------------------------------------------- alert log
def _reading_values(rec: dict | None) -> str:
    if not rec:
        return ""
    parts = []
    for k, label in (("do", "DO mg/L"), ("salinity", "Salinity ppt"), ("ph", "pH"), ("temp", "Temp °C")):
        v = water._num(rec.get(k))
        parts.append(f"{label}: {'—' if v is None else f'{v:g}'}")
    a = water._num(rec.get("ammonia"))
    parts.append(f"Ammonia ({rec.get('ammonia_type') or 'type not recorded'}) mg/L: {'—' if a is None else f'{a:g}'}")
    return "; ".join(parts)


def read_alerts() -> pd.DataFrame:
    if not COMBINED_ALERTS_LOG.exists() or COMBINED_ALERTS_LOG.stat().st_size == 0:
        return pd.DataFrame(columns=ALERT_HEADER)
    try:
        df = pd.read_csv(COMBINED_ALERTS_LOG, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame(columns=ALERT_HEADER)
    for c in ALERT_HEADER:
        if c not in df.columns:
            df[c] = ""
    return df[ALERT_HEADER]


def log_alert(res: dict, sess: dict | None, rec: dict | None, source: str) -> bool:
    """Append the assessment to the alert history. Returns False if an identical record already exists."""
    sid = sess["session_id"] if sess else ""
    rid = rec["id"] if rec else ""
    old = read_alerts()
    if not old.empty and ((old["session_id"] == sid) & (old["reading_id"] == rid) & (old["level"] == res["level"])).any():
        return False
    b = res["behavior"]
    row = {"alert_id": f"A{datetime.now():%y%m%d%H%M%S}{uuid.uuid4().hex[:3]}",
           "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "level": res["level"],
           "message": res["message"], "triggers": " | ".join(res["triggers"]),
           "reason": " ".join([res["explanation"], *res["notes"]]).strip(), "action": res["action"],
           "completeness": res["completeness"], "reading_id": rid, "measured_at": rec["measured_at"] if rec else "",
           "readings": _reading_values(rec), "session_id": sid, "video": sess["video"] if sess else "",
           "analyzed_at": sess["analyzed_at"] if sess else "",
           "time_diff_min": "" if res["diff_min"] is None else round(res["diff_min"], 1),
           "behavior": b["label"], "detections": sess["unique_tracked"] if sess else "",
           "avg_speed_px_s": sess["avg_speed"] if (sess and b["available"]) else "",
           "tracks_usable": sess["tracks_usable"] if sess else "", "source": source}
    append_row(COMBINED_ALERTS_LOG, ALERT_HEADER, [row[h] for h in ALERT_HEADER])
    return True


def assess_and_log(sess: dict, source: str = "video ended") -> dict:
    """Used when a video finishes: pair it with the reading linked to it (or the latest one) and log the result.
    The time window still decides whether they are combined, so an unrelated reading is never merged silently."""
    thresholds, rules = water._read_config()
    records = water.read_records()
    rec = None
    if not records.empty:
        linked = records[records["session"] == sess["session_id"]]
        rec = (linked if not linked.empty else records).iloc[-1].to_dict()
    results = water.assess_record(rec, thresholds) if rec else None
    res = combine(results, rec["measured_dt"].to_pydatetime() if rec else None, sess, rules)
    log_alert(res, sess, rec, source)
    return res


# ---------------------------------------------------------------- page
def _banner(level: str, message: str) -> str:
    tone = TONE[level]
    return ui.h(f'<div class="mf-alert" style="border-left-color:var(--{tone})">'
                f'<div class="mf-ch" style="margin-bottom:6px">{ui.badge(level, tone)}</div>'
                f'<div style="font-size:15px;font-weight:600">{ui.esc(message)}</div></div>')


def page_assessment() -> None:
    thresholds, rules = water._read_config()
    st.markdown(ui.page_title("Combined Assessment",
                              "Manual water-quality readings together with milkfish video analysis"),
                unsafe_allow_html=True)
    sessions = read_sessions()
    records = water.read_records()

    st.markdown(ui.section("Choose the data to assess"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    s_labels = ["(no video session)"] + [session_label(r) for _, r in sessions.iloc[::-1].iterrows()]
    s_choice = c1.selectbox("Video analysis session", s_labels, key="cmb_session")
    sess = None
    if s_choice != s_labels[0]:
        sess = sessions[sessions["session_id"] == s_choice.split(" · ")[0]].iloc[0].to_dict()

    r_labels, r_ids, default = ["(no reading)"], [None], 0
    for _, r in records.iloc[::-1].iterrows():
        link = sess and r["session"] in (sess["session_id"], sess["video"])
        r_labels.append(f'{r["id"]} · measured {r["measured_at"]}' + (" · linked to this session" if link else ""))
        r_ids.append(r["id"])
    for i, rid in enumerate(r_ids):  # linked reading first, otherwise the latest one (newest is index 1)
        if rid and "linked to this session" in r_labels[i]:
            default = i
            break
    else:
        default = 1 if len(r_ids) > 1 else 0
    r_choice = c2.selectbox("Water-quality reading", r_labels, index=default, key=f"cmb_reading_{s_choice}")
    rec = None
    if r_ids[r_labels.index(r_choice)]:
        rec = records[records["id"] == r_ids[r_labels.index(r_choice)]].iloc[0].to_dict()

    results = water.assess_record(rec, thresholds) if rec else None
    res = combine(results, rec["measured_dt"].to_pydatetime() if rec else None, sess, rules)

    st.markdown(ui.section("Combined Water-Quality and Behavioral Assessment"), unsafe_allow_html=True)
    st.markdown(_banner(res["level"], res["message"]), unsafe_allow_html=True)
    if res["explanation"]:
        st.write(res["explanation"])
    for n in res["notes"]:
        st.warning(n)
    st.markdown(f"**Recommended next action:** {res['action']}")
    st.caption(f"Data completeness: {res['completeness']}")
    if res["triggers"]:
        st.markdown("**What triggered this alert**")
        for t in res["triggers"]:
            st.markdown(f"- {t}")

    st.markdown(ui.section("Water-quality result"), unsafe_allow_html=True)
    if rec:
        age = f" · {fmt_gap(res['age_h'] * 60)} ago" if res["age_h"] is not None else ""
        st.caption(f'Reading {rec["id"]} · measured {rec["measured_at"]}{age}')
        st.markdown(ui.badge(res["water_level"], TONE[res["water_level"]]) + " " + ui.esc(res["water_note"]),
                    unsafe_allow_html=True)
        st.markdown(water.results_html(res["results"]), unsafe_allow_html=True)
    else:
        st.info("No water-quality reading selected. Enter one on the Water Quality page.")

    st.markdown(ui.section("Milkfish behavior result"), unsafe_allow_html=True)
    b = res["behavior"]
    rows = [("Video", sess["video"] if sess else "—"),
            ("Video analysis time", sess["analyzed_at"] if sess else "—"),
            ("Milkfish tracked (unique)", sess["unique_tracked"] if sess else "—"),
            ("Reliably tracked fish", f'{sess["tracks_usable"]} (minimum {rules["min_tracks"]:g})' if sess else "—"),
            ("Average swimming speed",
             f'{float(sess["avg_speed"]):.1f} px/s' if (sess and b["available"]) else
             ("Not reliable enough to report" if sess else "—")),
            ("Behavior classification", b["label"]),
            ("Detail", b["detail"] or b["reason"] or "—"),
            ("Time between reading and video",
             fmt_gap(res["diff_min"]) + (" (within window)" if res["matched"] else " (outside window)")
             if res["diff_min"] is not None else "—")]
    st.markdown(ui.kv_card("Video analysis", [(k, str(v)) for k, v in rows]), unsafe_allow_html=True)
    st.caption("Speed is in pixels per second (not calibrated). Behavior comes from the existing video analysis and "
               "is an indicator only.")

    if st.button("Record this assessment in the alert history"):
        if log_alert(res, sess, rec, "manual"):
            st.success("Recorded in the alert history.")
        else:
            st.info("An identical record for this session, reading and level already exists.")

    st.markdown(ui.section("Alert History"), unsafe_allow_html=True)
    alerts = read_alerts()
    if alerts.empty:
        st.caption("No assessments have been recorded yet. One is recorded automatically each time a video finishes.")
    else:
        pick = st.multiselect("Show levels", list(LEVELS), default=list(LEVELS), key="cmb_levels")
        view = alerts[alerts["level"].isin(pick)].iloc[::-1]
        st.dataframe(view[["created_at", "level", "message", "triggers", "reason", "action", "readings", "video",
                           "behavior", "time_diff_min", "completeness", "source"]],
                     use_container_width=True, hide_index=True)
        st.download_button("Download alert history (CSV)", alerts.to_csv(index=False),
                           "combined_alerts.csv", "text/csv")

    st.markdown(ui.section("Monitoring Reports"), unsafe_allow_html=True)
    if sessions.empty:
        st.caption("No finished video analyses recorded yet.")
    else:
        st.dataframe(sessions.drop(columns=["analyzed_dt"]).iloc[::-1], use_container_width=True, hide_index=True)
        st.download_button("Download video sessions (CSV)", sessions.drop(columns=["analyzed_dt"]).to_csv(index=False),
                           "video_sessions.csv", "text/csv")
    if not records.empty:
        st.download_button("Download water readings (CSV)", records[water.HEADER].to_csv(index=False),
                           "water_readings.csv", "text/csv")
    n_val = sum(1 for k in thresholds if thresholds[k]["validated"])
    st.caption(f"{n_val} of {len(thresholds)} reference ranges are marked as validated. Edit them on the Water "
               "Quality page, Reference ranges tab.")

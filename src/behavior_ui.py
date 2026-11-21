"""Dashboard panels for the four behavior categories (put this file in src/).

Categories: Normal Swimming, Schooling Behavior, Feeding Activity, Unusual Swimming Activity.
Everything here only builds HTML / text from a Snapshot (or a saved record); it never touches the video.
"""
from __future__ import annotations

TITLE = "Milkfish Monitoring Dashboard"
SUBTITLE = "Intelligent computer vision for automated monitoring and behavioral analysis"

ICONS = {
    "ok": "M4 12l5 5L20 6",
    "grp": "M9 11a3 3 0 100-6 3 3 0 000 6zM3 20a6 6 0 0112 0M17 11a3 3 0 100-6M21 20a6 6 0 00-4-5.6",
    "drop": "M12 3c4 5 6 8 6 11a6 6 0 01-12 0c0-3 2-6 6-11z",
    "warn": "M12 3L2 21h20zM12 10v5M12 18v.5",
}
# key, title, short description, icon, bar tone
CATS = [
    ("normal", "Normal Swimming", "Steady, relaxed movement", "ok", "ok"),
    ("schooling", "Schooling Behavior", "Fish moving close together", "grp", "ok"),
    ("feeding", "Feeding Activity", "Fish gathering to feed", "drop", "ok"),
    ("unusual", "Unusual Swimming Activity", "Sudden or irregular movement", "warn", "warn"),
]
STATUS_MAP = {  # fish status -> (label, badge tone)
    "insufficient": ("Not enough data", "mut"),
    "normal": ("Normal Swimming", "ok"), "normal swimming": ("Normal Swimming", "ok"),
    "schooling": ("Schooling", "ok"), "schooling behavior": ("Schooling", "ok"),
    "feeding": ("Feeding", "ok"), "feeding activity": ("Feeding", "ok"),
    "unusual": ("Unusual", "warn"), "erratic": ("Unusual", "warn"), "low oxygen": ("Unusual", "warn"),
}
PATTERNS = {"Normal": "Consistent swimming", "Schooling": "Moves in coordination with nearby fish",
            "Feeding": "Repeated localized group movement", "Unusual": "Irregular movement",
            "Insufficient": "Tracked too briefly to judge"}
ACTIVITY = {"active": "Active", "low": "Low movement", "unknown": "Not enough data"}
DIR_WORDS = {"→": "right", "↗": "up-right", "↑": "up", "↖": "up-left",
             "←": "left", "↙": "down-left", "↓": "down", "↘": "down-right"}
NOTE = "Unusual swimming is an observation from video. It is not a confirmed disease diagnosis."
FEED_NOTE = ("Feeding Activity is inferred only from repeated, localized group movement. "
             "Movement alone cannot confirm that fish are feeding.")


# ------------------------------------------------------------------ small helpers
def header(status_text: str, tone: str, now) -> str:
    """Page header: title, subtitle, system status badge and time."""
    return (f'<div class="mf mf-head"><div><div class="mf-title">{TITLE}</div><div class="mf-sub">{SUBTITLE}</div></div>'
            f'<div class="mf-headr"><span class="mf-badge {tone}">{status_text}</span>'
            f'<span class="mf-time">{now:%b %d, %Y · %I:%M %p}</span></div></div>')


def counts(snap) -> dict:
    unusual = getattr(snap, "unusual", None)
    if unusual is None:
        unusual = getattr(snap, "erratic", 0) + getattr(snap, "low_oxygen", 0)
    return {"normal": getattr(snap, "normal", 0), "schooling": getattr(snap, "schooling", 0),
            "feeding": getattr(snap, "feeding", 0), "unusual": unusual}


def classified(c: dict) -> int:
    return sum(c.values())


def np_text(n: int, total: int) -> str:
    """'28 (58%)' - the count first, then its share in brackets."""
    return f"{n} ({round(100 * n / total) if total else 0}%)"


def display_id(idmap: dict, raw) -> str:
    """Friendly fish number: 01, 02, 03 ... in the order fish first appear (the tracker's raw id can be any number)."""
    return f"{idmap.setdefault(raw, len(idmap) + 1):02d}"


def _pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def _ico(name: str, warn: bool = False) -> str:
    return (f'<div class="mf-ico{" w" if warn else ""}"><svg width="20" height="20" viewBox="0 0 24 24" '
            f'aria-hidden="true"><path d="{ICONS[name]}"/></svg></div>')


def _fmt_time(sec: float) -> str:
    m, s = divmod(int(max(sec, 0)), 60)
    return f"{m}:{s:02d}"


def dominant(c: dict) -> str:
    if not sum(c.values()):
        return "—"
    best = CATS[0]
    for cat in CATS:
        if c[cat[0]] > c[best[0]]:
            best = cat
    return best[1]


def group_text(cohesion) -> str:
    if cohesion is None:
        return "Insufficient data"
    return "Consistent group movement" if cohesion >= 60 else "Loosening group movement" if cohesion >= 30 else "Dispersed movement"


def facts(snap) -> dict:
    """The key results of one analysed video as plain values (also what is saved in the history)."""
    c = counts(snap)
    out = {"n": int(getattr(snap, "count", sum(c.values()))), **c, "dominant": dominant(c),
           "avg_speed": float(getattr(snap, "avg_speed", 0.0)), "cohesion": getattr(snap, "cohesion", None),
           "status": str(getattr(snap, "status", "")), "ok": getattr(snap, "level", "ok") == "ok"}
    for k in ("active", "inactive", "activity_unknown"):
        if hasattr(snap, k):
            out[k] = int(getattr(snap, k))
    return out


def sentences(f: dict) -> list:
    """The written monitoring result, in plain words."""
    n = f["n"]
    cl = sum(f[k] for k in ("normal", "schooling", "feeding", "unusual"))
    out = [f"A total of {n} milkfish were tracked in the video."]
    if cl:
        out.append(f"The dominant observed behavior was {f['dominant']}.")
        if n > cl:
            out.append(f"{n - cl} fish {'was' if n - cl == 1 else 'were'} tracked too briefly to classify.")
    elif n:
        out.append("Behavior could not be classified because the fish were not tracked long enough.")
    if f.get("active", 0) + f.get("inactive", 0):
        out.append(f"{f['active']} fish were active and {f['inactive']} showed low movement.")
    if f["avg_speed"] > 0:
        out.append(f"The average swimming speed was {f['avg_speed']:.1f} pixels per second.")
    coh = f.get("cohesion")
    if coh is not None:
        out.append("The fish displayed relatively consistent group movement during the observation." if coh >= 60
                   else "The group movement of the fish was loosening during the observation." if coh >= 30
                   else "The fish were widely dispersed, with little group movement.")
    if cl:
        if f["unusual"] == 0:
            out.append("No unusual swimming activity was detected during this analysis.")
        else:
            out.append(f"Unusual swimming activity was observed in {f['unusual']} of {cl} classified fish. This is a "
                       "video-based observation, not a disease diagnosis. Inspect the fingerlings and pond conditions.")
    if f["feeding"] > 0:
        out.append(FEED_NOTE)
    out.append("Overall monitoring status: " + ("Not enough tracking data to assess." if (n and not cl)
                                                else "Normal." if f["ok"] else "Unusual activity observed."))
    return out


def pattern(status, arrow="—", glyph: bool = False, note: str = "") -> str:
    label, _ = STATUS_MAP.get(str(status).lower(), ("Normal Swimming", "ok"))
    key = "Insufficient" if label.startswith("Not") else label.split()[0]
    text = (note[:1].upper() + note[1:]) if (key == "Unusual" and note) else PATTERNS[key]
    if key in ("Normal", "Schooling") and arrow in DIR_WORDS:
        text += f", mostly {DIR_WORDS[arrow]}"
        if glyph:
            text = f"{arrow} {text}"
    return text


def fish_rows(snap, idmap: dict, glyph: bool = True) -> list:
    """One row per tracked fish, numbered 01, 02, ... in order of first appearance (same numbers as the video boxes)."""
    fish = sorted(getattr(snap, "fish", []), key=lambda f: idmap.get(getattr(f, "id", None), 10 ** 9))
    rows = []
    for f in fish:
        label, tone = STATUS_MAP.get(str(getattr(f, "status", "")).lower(), ("Normal Swimming", "ok"))
        known = getattr(f, "speed_ok", True)
        rows.append({"id": display_id(idmap, getattr(f, "id", None)), "behavior": label, "tone": tone,
                     "activity": ACTIVITY.get(getattr(f, "activity", "unknown"), "—"),
                     "pattern": pattern(getattr(f, "status", ""), getattr(f, "arrow", "—"), glyph,
                                        getattr(f, "note", "")),
                     "speed": float(getattr(f, "speed", 0.0)) if known else None})
    return rows


# ------------------------------------------------------------------ cards
def category_panel(snap, ended: bool = False) -> str:
    c = counts(snap)
    cl = classified(c)
    n = max(int(getattr(snap, "count", cl)), cl)
    rows = "".join(
        f'<div class="mf-cat">{_ico(ic, k == "unusual")}<div style="min-width:0"><div class="mf-ct">{t}</div>'
        f'<div class="mf-cd">{d}</div></div><div class="mf-cn"{" style=color:var(--warn)" if k == "unusual" else ""}>'
        f'{c[k]} <small style="display:inline;font-size:12px;font-weight:500;color:var(--mut)">'
        f'({_pct(c[k], cl)}%)</small></div></div>'
        for k, t, d, ic, _ in CATS)
    tag = "Whole video" if ended else "Current frame"
    note = f"Shares are of the {cl} fish that could be classified."
    if n > cl:
        note += f" {n - cl} more fish need more tracking time."
    return (f'<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Behavior categories</span>'
            f'<span class="mf-badge mut">{tag}</span></div><div class="mf-cats">{rows}</div>'
            f'<div class="mf-note">{note} {NOTE}</div></div>')


def recommendation(snap) -> str:
    c = counts(snap)
    total = classified(c)
    if total == 0:
        return ('<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Recommendation</span>'
                '<span class="mf-badge mut">Waiting</span></div><div class="mf-act">Collecting movement data</div>'
                '<div class="mf-note">Each fish needs a few seconds of tracking before its behavior is judged.</div></div>')
    if c["unusual"] > 0:
        return ('<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Recommendation</span>'
                '<span class="mf-badge warn">Check pond</span></div>'
                f'<div class="mf-act">Unusual swimming seen in {c["unusual"]} of {total} fish</div>'
                '<div class="mf-note">Inspect the fingerlings and pond conditions, and keep monitoring.</div></div>')
    return ('<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Recommendation</span>'
            '<span class="mf-badge ok">All clear</span></div><div class="mf-act">Continue routine monitoring</div>'
            '<div class="mf-note">No unusual swimming activity was observed.</div></div>')


def distribution_card(c: dict, info: str = "", missing: int = 0) -> str:
    cl = classified(c)
    bars = "".join(
        f'<div><div class="mf-brow"><span>{t}</span><span>{np_text(c[k], cl)}</span></div>'
        f'<div class="mf-bar"><i class="{tone}" style="width:{_pct(c[k], cl)}%"></i></div></div>'
        for k, t, _, _, tone in CATS)
    extra = f" · {missing} fish not classified yet (tracked too briefly)" if missing else ""
    note = f'<div class="mf-note">{info}{extra}</div>' if (info or extra) else ""
    return (f'<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Behavior distribution</span></div>'
            f'<div class="mf-bars">{bars}</div>{note}</div>')


def fish_table(rows: list) -> str:
    def speed(r):
        return "—" if r.get("speed") is None else f'{r["speed"]:.0f}'
    body = "".join(
        f'<tr><td>Milkfish {r["id"]}</td><td><span class="mf-badge {r["tone"]}">{r["behavior"]}</span></td>'
        f'<td>{r.get("activity", "—")}</td><td>{r["pattern"]}</td><td class="num">{speed(r)}</td></tr>'
        for r in rows[:60])
    if not body:
        body = '<tr><td colspan="5" class="m">No fish tracked yet</td></tr>'
    return ('<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Individual fish tracking details</span>'
            f'<span class="mf-badge mut">{len(rows)} fish</span></div><div class="mf-tw"><table class="mf-tbl">'
            '<thead><tr><th>Fish ID</th><th>Behavior</th><th>Activity</th><th>Movement pattern</th>'
            '<th class="num">Speed (px/s)</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>')


def overall_card(f: dict, tag: str = "Video complete") -> str:
    cl = sum(f[k] for k in ("normal", "schooling", "feeding", "unusual"))
    if f["n"] and not cl:
        status = '<span class="mf-badge mut">Not enough data</span>'
    elif f["ok"]:
        status = '<span class="mf-badge ok">Normal</span>'
    else:
        status = '<span class="mf-badge warn">Unusual activity observed</span>'
    rows = [("Milkfish tracked", f["n"]), ("Dominant behavior", f["dominant"])]
    if "active" in f:
        rows.append(("Active / low-movement fish", f'{f["active"]} / {f["inactive"]}'))
    rows += [("Average swimming speed", f'{f["avg_speed"]:.1f} px/s' if f["avg_speed"] > 0 else "—"),
             ("Group movement", group_text(f.get("cohesion"))), ("Overall monitoring status", status)]
    kv = "".join(f'<div class="mf-kv"><span>{k}</span><b>{v}</b></div>' for k, v in rows)
    text = " ".join(sentences(f))
    return ('<div class="mf-card"><div class="mf-cardhead"><span class="mf-ch">Overall results</span>'
            f'<span class="mf-badge mut">{tag}</span></div>{kv}<div class="mf-note">{text}</div></div>')


def lower(snap, ended: bool = False, idmap: dict | None = None) -> str:
    idmap = {} if idmap is None else idmap
    coh = getattr(snap, "cohesion", None)
    info = f'Average speed {getattr(snap, "avg_speed", 0.0):.0f} px/s'
    info += f" · Schooling cohesion {coh:.0f}%" if coh is not None else ""
    top = overall_card(facts(snap)) if ended else ""
    return ('<div class="mf" style="display:flex;flex-direction:column;gap:16px">' + top +
            f'<div class="mf-bottom">{distribution_card(counts(snap), info, max(int(getattr(snap, "count", 0)) - classified(counts(snap)), 0))}'
            f'{fish_table(fish_rows(snap, idmap))}</div></div>')


def record_view(rec: dict) -> str:
    """The same results panels, built from a saved history record."""
    c = {k: rec[k] for k in ("normal", "schooling", "feeding", "unusual")}
    return ('<div class="mf" style="display:flex;flex-direction:column;gap:16px">' + overall_card(rec, rec.get("analyzed_at", "")) +
            f'<div class="mf-bottom">{distribution_card(c, "", max(rec["n"] - classified(c), 0))}{fish_table(rec.get("fish", []))}</div></div>')


def progress_bar(done: float, elapsed: float, eta, finished: bool = False) -> str:
    """Progress card shown under the video while a recorded video is being analysed."""
    pct = round(100 * min(max(done, 0.0), 1.0))
    if finished:
        title, right = "Analysis complete", f"100% · took {_fmt_time(elapsed)}"
        badge = '<span class="mf-badge ok">Done</span>'
    else:
        title = "Analyzing video…"
        left = f"about {_fmt_time(eta)} left" if eta is not None else "estimating time left"
        right, badge = f"{pct}% · {_fmt_time(elapsed)} elapsed · {left}", ""
    return (f'<div class="mf-card" style="margin-top:16px"><div class="mf-brow"><span class="mf-ct">{title}</span>'
            f'<span>{right}</span></div><div class="mf-bar"><i class="ok" style="width:{pct}%"></i></div>'
            f'{badge and "<div style=margin-top:8px>" + badge + "</div>"}</div>')
